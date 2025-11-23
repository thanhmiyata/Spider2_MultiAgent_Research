import re
import sqlite3
import time
from langchain_core.prompts import PromptTemplate
from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

class Validator:
    def __init__(self, model_name=GEMINI_MODEL, max_retries=2):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "sql", "syntax_error"],
            template="""
            You are a SQL Reviewer.
            Review the generated SQL query for syntax errors and logical consistency.
            
            CHECKLIST:
            1. **Ambiguity**: Are all column names qualified with table aliases? (Fix "ambiguous column name" errors).
            2. **Syntax**: Is the syntax valid for SQLite?
            3. **GROUP BY**: Are all non-aggregated columns in the SELECT clause present in the GROUP BY clause?
            4. **Window Functions**: Are window functions (RANK, NTILE, etc.) used correctly?
            5. **Logic**: Does the query answer the specific question asked?
            
            Schema:
            {schema}

            Question: {question}

            Generated SQL:
            {sql}
            
            {syntax_error}

            If the SQL is correct, return "CORRECT".
            If there are errors, return the corrected SQL query ONLY.
            CRITICAL: Do NOT provide explanations, markdown formatting, or chat. Just the raw SQL.
            """
        )
        self.chain = self.prompt | self.llm

    def _extract_table_aliases(self, sql: str) -> dict:
        """Extracts table aliases from a SQL query."""
        aliases = {}
        # Regex to find FROM/JOIN clauses and capture table name and its alias
        # This is a simplified regex and might not cover all complex cases
        # It looks for "table_name AS alias" or "table_name alias"
        matches = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_`"]+)(?:\s+AS)?\s+([a-zA-Z0-9_`"]+)', sql, re.IGNORECASE)
        for table, alias in matches:
            aliases[alias.lower()] = table.lower()
        
        # Handle cases where table name is used without explicit alias but is aliased implicitly
        # e.g., SELECT T1.col FROM Table1 T1
        matches_implicit = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_`"]+)\s+([a-zA-Z0-9_`"]+)(?![a-zA-Z0-9_`"])', sql, re.IGNORECASE)
        for table, alias in matches_implicit:
            if alias.lower() not in aliases: # Avoid overwriting explicit AS aliases
                aliases[alias.lower()] = table.lower()
        
        return aliases

    def _detect_ambiguous_columns(self, sql: str, schema: str) -> list:
        """Detects potentially ambiguous column names in the SQL query."""
        ambiguous_columns = []
        # This is a very basic detection. A full parser would be needed for robust detection.
        # For now, we look for column names that appear without a table alias prefix
        # and exist in multiple tables in the schema.

        # Parse schema to get table-column mapping
        schema_tables = {}
        current_table = None
        for line in schema.split('\n'):
            line = line.strip()
            if line.startswith('CREATE TABLE'):
                match = re.search(r'CREATE TABLE\s+`?(\w+)`?', line, re.IGNORECASE)
                if match:
                    current_table = match.group(1).lower()
                    schema_tables[current_table] = []
            elif current_table and line.startswith('`') and '`' in line[1:]:
                match = re.search(r'`?(\w+)`?\s+\w+', line)
                if match:
                    schema_tables[current_table].append(match.group(1).lower())
            elif current_table and line == ');':
                current_table = None

        # Extract columns from the SQL query that are not prefixed with an alias
        # This regex is simplified and might miss some cases or have false positives
        # It tries to find words that look like column names, not preceded by a dot (alias.column)
        # and not SQL keywords.
        # A more robust solution would involve parsing the SQL.
        
        # Get all column names from the schema
        all_schema_columns = set()
        for cols in schema_tables.values():
            all_schema_columns.update(cols)

        # Find potential column names in the SQL query that are not prefixed
        # This regex attempts to find identifiers that are not preceded by a dot (e.g., `alias.column`)
        # and are not common SQL keywords.
        # This is a heuristic and can be imperfect.
        sql_keywords = set(['select', 'from', 'where', 'join', 'on', 'and', 'or', 'group', 'by', 'order', 'limit', 'insert', 'update', 'delete', 'values', 'set', 'as', 'distinct', 'count', 'sum', 'avg', 'min', 'max', 'case', 'when', 'then', 'else', 'end', 'union', 'except', 'intersect', 'having', 'like', 'in', 'not', 'is', 'null', 'between', 'exists', 'true', 'false'])
        
        # Find identifiers that are not preceded by a dot and are not keywords
        # This pattern looks for a word boundary, then a word, then another word boundary,
        # ensuring it's not part of an alias.column structure.
        # It also tries to avoid matching numbers or string literals.
        potential_columns = re.findall(r'(?<![\w."`])([a-zA-Z_][a-zA-Z0-9_]*)(?![\w."`])', sql, re.IGNORECASE)
        
        for col_name in set(potential_columns):
            col_name_lower = col_name.lower()
            if col_name_lower in all_schema_columns and col_name_lower not in sql_keywords:
                # Check if this column exists in multiple tables
                tables_containing_column = [
                    table for table, cols in schema_tables.items() if col_name_lower in cols
                ]
                if len(tables_containing_column) > 1:
                    ambiguous_columns.append(col_name)
        return ambiguous_columns

    def _test_syntax(self, sql: str) -> str:
        """Test SQL syntax by executing on empty in-memory database."""
        try:
            conn = sqlite3.connect(':memory:')
            cursor = conn.cursor()
            # Try to explain the query (doesn't execute, just validates syntax)
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            conn.close()
            return ""
        except Exception as e:
            return f"Syntax Error Detected: {str(e)}"

    def _detect_hallucinated_numbers(self, sql: str) -> str:
        """Detects hardcoded numbers in SELECT clauses (hallucinations)."""
        # Look for SELECT followed by a number (integer or float), possibly after a comma
        # e.g., "SELECT 100", "SELECT 'date', 100", "SELECT col, 100 AS alias"
        
        # Pattern: SELECT ... , <number> ... or SELECT <number> ...
        # We want to avoid matching things like "LIMIT 5" or "OFFSET 10" or "CASE WHEN x=1"
        
        # Simplified heuristic: Look for number in SELECT list
        # This is tricky with regex alone.
        
        # Let's look for specific pattern seen in the error:
        # SELECT '2018-12-05' AS sale_date, 100 AS predicted_sales
        
        matches = re.findall(r'SELECT\s+.*?(?:\s|,)((?:\d+(?:\.\d+)?))\s+(?:AS\s+\w+\s+)?(?:FROM|$)', sql, re.IGNORECASE | re.DOTALL)
        
        # Filter out common valid numbers like 0, 1 (often used for flags or count)
        # But even 0 or 1 should usually be calculated if it's a prediction.
        
        # A safer check: if we see a UNION ALL with hardcoded numbers, it's definitely a hallucination for this task.
        if "UNION ALL" in sql.upper() and re.search(r'SELECT\s+.*?\d+', sql):
             # Check if there's a FROM clause in the sub-selects
             # If a SELECT has a number but NO "FROM", it's a constant row -> Hallucination (usually)
             
             # Find SELECTs without FROM
             # Split by UNION ALL
             parts = re.split(r'UNION\s+ALL', sql, flags=re.IGNORECASE)
             for part in parts:
                 if "SELECT" in part.upper() and "FROM" not in part.upper():
                     # Check if it has a number
                     if re.search(r'\d+', part):
                         return "Hallucination Detected: The SQL contains hardcoded numbers in SELECT without a FROM clause. You must calculate values using SQL formulas (e.g., Linear Regression formula), not hardcode them."
        
        return ""

    def _validate_joins(self, sql: str, schema: str) -> str:
        """Validates that JOINs follow proper foreign key relationships."""
        # Extract all table references (FROM and JOIN clauses)
        # Pattern: FROM table AS alias or JOIN table AS alias
        table_pattern = r'(?:FROM|JOIN)\s+`?(\w+)`?\s+(?:AS\s+)?(\w+)?'
        table_refs = re.findall(table_pattern, sql, re.IGNORECASE)
        
        # Build alias -> table mapping
        alias_to_table = {}
        for table_name, alias in table_refs:
            table_lower = table_name.lower()
            alias_lower = (alias or table_name).lower()
            alias_to_table[alias_lower] = table_lower
        
        # Extract JOIN clauses with ON conditions
        join_pattern = r'(?:INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|JOIN)\s+`?(\w+)`?\s+(?:AS\s+)?(\w+)?\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        joins = re.findall(join_pattern, sql, re.IGNORECASE)
        
        for join in joins:
            # join format: (joined_table, alias, left_alias, left_col, right_alias, right_col)
            if len(join) >= 6:
                left_alias = join[2].lower()
                right_alias = join[4].lower()
                
                # Map aliases to table names
                left_table = alias_to_table.get(left_alias, left_alias)
                right_table = alias_to_table.get(right_alias, right_alias)
                
                # Check for problematic joins
                if (left_table == 'orders' and right_table == 'products') or \
                   (left_table == 'products' and right_table == 'orders'):
                    return "Missing intermediate table. Orders and Products must be joined via Order_Items. Do not join them directly."
        
        return ""

    def validate(self, question: str, schema: str, sql: str, max_iterations=3) -> str:
        """Validates and corrects SQL with iterative improvement (3 iterations) and timeout handling."""
        # Clean SQL first
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        current_sql = sql
        
        for iteration in range(max_iterations):
            # Test syntax
            syntax_error_message = self._test_syntax(current_sql)
            
            # Detect ambiguous columns even if syntax passes
            ambiguous_cols = self._detect_ambiguous_columns(current_sql, schema)
            
            # Detect hallucinations
            hallucination_error = self._detect_hallucinated_numbers(current_sql)
            
            # Validate joins
            join_error = self._validate_joins(current_sql, schema)
            
            error_messages = []
            if syntax_error_message:
                error_messages.append(syntax_error_message)
            if ambiguous_cols:
                error_messages.append(f"Potential Ambiguous Columns Detected: {', '.join(ambiguous_cols)}. Please qualify them with table aliases.")
            if hallucination_error:
                error_messages.append(hallucination_error)
            if join_error:
                error_messages.append(join_error)

            # If no errors found, return the SQL
            if not error_messages:
                return current_sql
            
            # Prepare error message for LLM
            error_for_prompt = f"Errors Detected:\n" + "\n".join(error_messages)
            
            # Try to validate with retry logic
            validation_success = False
            for attempt in range(self.max_retries):
                try:
                    response = self.chain.invoke({
                        "question": question, 
                        "schema": schema, 
                        "sql": current_sql,
                        "syntax_error": error_for_prompt
                    })
                    
                    validation = extract_content(response)
                    validation_success = True
                    
                    if validation.upper() == "CORRECT":
                        return current_sql
                    else:
                        # Clean the corrected SQL
                        corrected = validation.replace("```sql", "").replace("```", "").strip()
                        # Extract SQL if wrapped in text
                        sql_match = re.search(r'(SELECT|WITH|INSERT|UPDATE|DELETE)', corrected, re.IGNORECASE)
                        if sql_match:
                            corrected = corrected[sql_match.start():]
                        
                        # If correction is same as original, break to avoid loop
                        if corrected.strip() == current_sql.strip():
                            return current_sql
                        
                        current_sql = corrected.strip()
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    print(f"[Validator] Error in validation attempt {attempt + 1}/{self.max_retries}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                    else:
                        # Failed all retries, return current SQL
                        return current_sql
            
            if not validation_success:
                return current_sql
        
        return current_sql
