import re
import sqlite3
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import DEFAULT_MODEL
import sqlite3
import tempfile
import os

class Validator:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "sql", "syntax_error"],
            template="""
            You are a SQL Reviewer.
            Review the generated SQL query for syntax errors and logical consistency.
            
            CHECKLIST:
            1. Are all column names qualified with table aliases? (Fix "ambiguous column name" errors).
            2. Is the syntax valid for SQLite?
            3. Are there any misplaced keywords (e.g., ORDER BY in subqueries)?
            
            Schema:
            {schema}

            Question: {question}

            Generated SQL:
            {sql}
            
            {syntax_error}

            If the SQL is correct, return "CORRECT".
            If there are errors, return the corrected SQL query ONLY (no markdown).
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

    def validate(self, question: str, schema: str, sql: str) -> str:
        """Validates and corrects SQL."""
        # Clean SQL first
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        # Test syntax
        syntax_error_message = self._test_syntax(sql)
        
        # Detect ambiguous columns even if syntax passes, as it's a logical/best practice issue
        ambiguous_cols = self._detect_ambiguous_columns(sql, schema)
        
        if ambiguous_cols:
            # If ambiguous columns are found, add this to the error message for the LLM
            if syntax_error_message:
                syntax_error_message += f"\nPotential Ambiguous Columns Detected: {', '.join(ambiguous_cols)}. Please qualify them with table aliases."
            else:
                syntax_error_message = f"Potential Ambiguous Columns Detected: {', '.join(ambiguous_cols)}. Please qualify them with table aliases."

        if not syntax_error_message:
            # If no syntax errors and no ambiguous columns detected by our simple check
            syntax_error_message = "Syntax test passed. No obvious ambiguous columns detected."
        
        try:
            response = self.chain.invoke({
                "question": question,
                "schema": schema,
                "sql": sql,
                "syntax_error": syntax_error_message
            })
            result = response.content.strip()
            if result == "CORRECT":
                corrected_sql = sql
            else:
                corrected_sql = result.replace("```sql", "").replace("```", "").strip()

            # Post-process: auto-qualify ambiguous columns if any remain
            ambiguous_cols = self._detect_ambiguous_columns(corrected_sql, schema)
            if ambiguous_cols:
                # Build column-to-table map from schema (first table containing column)
                col_table_map = {}
                for line in schema.splitlines():
                    if line.lower().startswith("table:"):
                        tbl = line.split(":",1)[1].strip()
                    elif line.lower().startswith("columns:"):
                        cols_part = line.split(":",1)[1]
                        cols = [c.strip().split(' ')[0] for c in cols_part.split(',')]
                        for c in cols:
                            col_table_map.setdefault(c, []).append(tbl)
                for col in ambiguous_cols:
                    if col in col_table_map and col_table_map[col]:
                        tbl = col_table_map[col][0]
                        corrected_sql = re.sub(rf"\\b{col}\\b", f"{tbl}.{col}", corrected_sql)
            return corrected_sql
        except Exception as e:
            print(f"Error in validation: {e}")
            return sql
