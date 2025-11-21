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

    def validate(self, question: str, schema: str, sql: str, max_iterations=2) -> str:
        """Validates and corrects SQL with iterative improvement and timeout handling."""
        # Clean SQL first
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        current_sql = sql
        
        for iteration in range(max_iterations):
            # Test syntax
            syntax_error_message = self._test_syntax(current_sql)
            
            # Detect ambiguous columns even if syntax passes
            ambiguous_cols = self._detect_ambiguous_columns(current_sql, schema)
            
            if ambiguous_cols:
                if syntax_error_message:
                    syntax_error_message += f"\nPotential Ambiguous Columns Detected: {', '.join(ambiguous_cols)}. Please qualify them with table aliases."
                else:
                    syntax_error_message = f"Potential Ambiguous Columns Detected: {', '.join(ambiguous_cols)}. Please qualify them with table aliases."

            # If no errors found, return the SQL
            if not syntax_error_message and not ambiguous_cols:
                return current_sql
            
            # Prepare error message for LLM
            error_for_prompt = ""
            if syntax_error_message and syntax_error_message != "Syntax test passed. No obvious ambiguous columns detected.":
                error_for_prompt = f"Errors Detected: {syntax_error_message}"
            
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
