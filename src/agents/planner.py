import time
import re
from typing import List, Set
from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

# SQL keywords and common English words to filter out when extracting table names
SQL_KEYWORDS = {
    'table', 'tables', 'from', 'join', 'where', 'select', 
    'group', 'order', 'having', 'inner', 'left', 'right', 
    'outer', 'cross', 'natural'
}

# Common English words that appear in plans but are not table names
STOP_WORDS = {
    'the', 'a', 'an', 'is', 'to', 'from', 'for', 'with', 'common', 
    'expression', 'table', 'tables', 'column', 'columns', 'data',
    'using', 'based', 'on', 'in', 'of', 'and', 'or', 'not',
    'this', 'that', 'these', 'those', 'will', 'should', 'can',
    'use', 'used', 'create', 'select', 'where', 'join', 'group',
    'order', 'by', 'having', 'limit', 'offset', 'distinct',
    'clauses', 'clause', 'expression', 'expressions', 'common',
    'cte', 'ctes', 'subquery', 'subqueries', 'query', 'queries',
    'sql', 'database', 'schema', 'row', 'rows', 'value', 'values',
    'result', 'results', 'set', 'sets', 'list', 'lists'
}

# Preview constants for output formatting
MAX_PREVIEW_LENGTH = 100
MAX_PREVIEW_COLUMNS = 5


class MissingTableError(Exception):
    """Exception raised when required tables are missing from the schema."""
    pass


class Planner:
    def __init__(self, model_name=GEMINI_MODEL, max_retries=2, enable_schema_validation=False):  # Keep disabled for now
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.enable_schema_validation = enable_schema_validation
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are a Senior Data Analyst specializing in SQL query planning.
            Create a detailed logical execution plan to answer the following question using the provided schema.
            
            CRITICAL INSTRUCTIONS:
            - Do NOT write SQL code. Focus ONLY on the logical steps and strategy.
            - Be SPECIFIC about SQL functions and techniques to use.
            - Break down complex operations into clear, sequential steps.
            
            Planning Structure:
            
            1. **Data Filtering** (WHERE clause):
               - What conditions need to be applied?
               - What date ranges, value thresholds, or categorical filters?
            
            2. **Table Joins** (FROM/JOIN clauses):
               - Which tables need to be joined?
               - What are the join keys?
               - Join type (INNER, LEFT, etc.)?
               - **CRITICAL**: If joining distant tables, specify the complete join path.
               - Example: "Join Path: orders -> order_items -> products"
               - Do NOT assume direct joins exist between unrelated tables.
            
            3. **Grouping & Aggregation** (GROUP BY):
               - What grouping columns?
               - What aggregate functions? (COUNT, SUM, AVG, MIN, MAX, etc.)
               - Any HAVING conditions?
            
            4. **Window Functions** (if needed):
               - RANK(), DENSE_RANK(), ROW_NUMBER() for ranking
               - NTILE(n) for percentile/quantile calculations
               - LAG()/LEAD() for time-series comparisons
               - PARTITION BY and ORDER BY for window frames
            
            5. **CTEs** (Common Table Expressions):
               - Should complex logic be broken into CTEs?
               - What intermediate results are needed?
            
            6. **Final Operations**:
               - ORDER BY for sorting
               - LIMIT for top-N results
               - DISTINCT for uniqueness
            
            SPECIFIC SQL Functions to Mention:
            - Date functions: STRFTIME('%Y-%m-%d', col), JULIANDAY(col), DATE(col)
            - String functions: SUBSTR(), LENGTH(), UPPER(), LOWER()
            - Math functions: ROUND(), ABS(), CAST()
            - Conditional: CASE WHEN ... THEN ... ELSE ... END
            
            Schema:
            {schema}

            Question: {question}

            Provide a clear, numbered step-by-step execution plan. Be specific about functions and techniques.
            """
        )
        self.chain = self.prompt | self.llm

    def _extract_tables_from_schema(self, schema: str) -> Set[str]:
        """
        Extract all table names from the schema string.
        
        Args:
            schema: Schema string in various formats
            
        Returns:
            Set of table names found in the schema
        """
        tables = set()
        
        # Parse different schema formats
        for line in schema.split('\n'):
            line = line.strip()
            
            # Format: "Table: table_name" or "1. table_name"
            if line.startswith('Table:'):
                table_name = line.replace('Table:', '').strip()
                if table_name:
                    tables.add(table_name)
            elif re.match(r'^\d+\.\s+(\w+)', line):
                match = re.match(r'^\d+\.\s+(\w+)', line)
                if match:
                    tables.add(match.group(1))
            
            # Format: "CREATE TABLE table_name" or "CREATE TABLE `table_name`" or "CREATE TABLE "table_name""
            elif line.startswith('CREATE TABLE') or 'CREATE TABLE' in line.upper():
                # Match table names with backticks, double quotes, or no quotes
                match = re.search(r'CREATE TABLE\s+[`"\']?(\w+)[`"\']?', line, re.IGNORECASE)
                if match:
                    tables.add(match.group(1))
        
        return tables

    def _extract_required_tables_from_plan(self, plan: str) -> Set[str]:
        """
        Extract table names mentioned in the execution plan.
        
        Args:
            plan: The generated execution plan
            
        Returns:
            Set of table names referenced in the plan
        """
        required_tables = set()
        
        # Common patterns for table references in plans
        patterns = [
            r'table[s]?\s+`?(\w+)`?',  # "table orders", "tables orders"
            r'from\s+`?(\w+)`?',        # "from orders"
            r'join\s+`?(\w+)`?',        # "join customers"
            r'`(\w+)`\s+table',         # "`orders` table"
            r'\b(\w+)\s+table\b',       # "orders table"
        ]
        
        plan_lower = plan.lower()
        
        for pattern in patterns:
            matches = re.finditer(pattern, plan_lower, re.IGNORECASE)
            for match in matches:
                table_name = match.group(1)
                # Filter out SQL keywords and stop words
                if table_name not in SQL_KEYWORDS and table_name not in STOP_WORDS and len(table_name) > 2:
                    required_tables.add(table_name)
        
        return required_tables

    def _validate_schema(self, plan: str, schema: str) -> None:
        """
        Validate that all required tables mentioned in the plan exist in the schema.
        
        Args:
            plan: The generated execution plan
            schema: The schema string
            
        Raises:
            MissingTableError: If required tables are missing from the schema
        """
        if not self.enable_schema_validation:
            return
        
        # Extract tables from schema and plan
        available_tables = self._extract_tables_from_schema(schema)
        required_tables = self._extract_required_tables_from_plan(plan)
        
        # Check for missing tables
        missing_tables = required_tables - available_tables
        
        if missing_tables:
            error_msg = f"MISSING_TABLE: Required tables {missing_tables} not found in provided schema. Available tables: {available_tables}"
            print(f"[Planner] Schema validation failed: {error_msg}")
            raise MissingTableError(error_msg)
        
        if required_tables:
            print(f"[Planner] Schema validation passed. Required tables {required_tables} are available.")

    def plan(self, question: str, schema: str) -> str:
        """
        Generates a logical plan with retry logic, timeout, and schema validation.
        
        Args:
            question: User's natural language question
            schema: Database schema string
            
        Returns:
            Generated execution plan
            
        Raises:
            MissingTableError: If plan requires tables not in the schema
        """
        for attempt in range(self.max_retries):
            try:
                response = self.chain.invoke({"question": question, "schema": schema})
                plan = extract_content(response)
                
                # Basic validation
                if len(plan.strip()) < 20:
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return "Proceed directly to SQL generation."
                
                # Schema validity check
                try:
                    self._validate_schema(plan, schema)
                except MissingTableError:
                    # Re-raise to let caller handle - preserves traceback
                    raise
                
                return plan
                
            except MissingTableError:
                # Re-raise schema validation errors
                raise
            except Exception as e:
                print(f"[Planner] Error in planning (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Fixed wait time instead of exponential
                else:
                    return "Proceed directly to SQL generation."
        
        return "Proceed directly to SQL generation."
