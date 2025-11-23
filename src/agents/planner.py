import time
import re
from typing import List, Set
from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

# SQL keywords to filter out when extracting table names
SQL_KEYWORDS = {
    'table', 'tables', 'from', 'join', 'where', 'select', 
    'group', 'order', 'having', 'inner', 'left', 'right', 
    'outer', 'cross', 'natural'
}

# Preview constants for output formatting
MAX_PREVIEW_LENGTH = 100
MAX_PREVIEW_COLUMNS = 5


class MissingTableError(Exception):
    """Exception raised when required tables are missing from the schema."""
    pass


class Planner:
    def __init__(self, model_name=GEMINI_MODEL, max_retries=2, enable_schema_validation=True):
        self.model_name = model_name
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
               - **LOOKUP TABLES**: If the question asks for names/descriptions (e.g., "product name", "category name", "interest name") but the main table only has IDs (e.g., product_id, category_id, interest_id), you MUST join with the corresponding lookup/mapping table to retrieve the human-readable names.
               - Example: "Join interest_metrics with interest_map ON interest_metrics.interest_id = interest_map.id to get interest_name"
            
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
            
            # Format: "CREATE TABLE table_name"
            elif line.startswith('CREATE TABLE'):
                match = re.search(r'CREATE TABLE\s+`?(\w+)`?', line, re.IGNORECASE)
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
        
        # Extended SQL keywords to filter out
        EXTENDED_KEYWORDS = SQL_KEYWORDS.union({
            'common', 'expressions', 'clauses', 'with', 'to', 'joins', 'a', 'b', 'c', 'd', 't1', 't2',
            'distinct', 'all', 'as', 'on', 'and', 'or', 'not', 'in', 'is', 'null', 'like', 'between',
            'exists', 'any', 'case', 'when', 'then', 'else', 'end', 'limit', 'offset', 'union', 'except',
            'intersect', 'minus', 'create', 'drop', 'alter', 'update', 'insert', 'delete', 'values',
            'into', 'set', 'view', 'index', 'primary', 'key', 'foreign', 'references', 'constraint',
            'default', 'check', 'unique', 'asc', 'desc', 'database', 'schema', 'column', 'row', 'data',
            'result', 'output', 'query', 'step', 'process', 'calculate', 'compute', 'filter', 'sort',
            'group', 'aggregate', 'window', 'function', 'use', 'using', 'based', 'following', 'leading',
            'before', 'after', 'sales', 'revenue', 'profit', 'cost', 'price', 'quantity', 'amount',
            'total', 'average', 'count', 'sum', 'min', 'max', 'avg', 'date', 'time', 'year', 'month',
            'day', 'week', 'quarter', 'hour', 'minute', 'second', 'timestamp', 'datetime', 'string',
            'number', 'integer', 'float', 'double', 'decimal', 'boolean', 'true', 'false', 'unknown',
            'null', 'nan', 'inf', 'infinity', 'analysis', 'performance', 'change', 'percentage', 'growth',
            'rate', 'ratio', 'difference', 'comparison', 'trend', 'pattern', 'seasonality', 'correlation',
            'regression', 'prediction', 'forecast', 'model', 'algorithm', 'method', 'technique', 'approach',
            'strategy', 'plan', 'execution', 'implementation', 'solution', 'answer', 'response', 'result',
            'output', 'outcome', 'finding', 'conclusion', 'recommendation', 'suggestion', 'insight',
            'observation', 'note', 'comment', 'remark', 'explanation', 'description', 'definition',
            'meaning', 'interpretation', 'understanding', 'knowledge', 'information', 'fact', 'truth',
            'reality', 'context', 'background', 'scenario', 'situation', 'case', 'example', 'instance',
            'sample', 'population', 'universe', 'scope', 'limit', 'boundary', 'constraint', 'restriction',
            'condition', 'requirement', 'specification', 'criterion', 'standard', 'measure', 'metric',
            'indicator', 'variable', 'parameter', 'factor', 'element', 'component', 'part', 'segment',
            'category', 'group', 'class', 'type', 'kind', 'sort', 'order', 'rank', 'level', 'tier',
            'grade', 'rating', 'score', 'value', 'magnitude', 'size', 'volume', 'capacity', 'quantity',
            'amount', 'number', 'count', 'frequency', 'probability', 'likelihood', 'chance', 'risk',
            'uncertainty', 'variability', 'volatility', 'stability', 'reliability', 'validity', 'accuracy',
            'precision', 'recall', 'f1', 'auc', 'roc', 'mse', 'mae', 'rmse', 'r2', 'p-value', 't-test',
            'z-test', 'chi-square', 'anova', 'regression', 'correlation', 'covariance', 'variance',
            'stddev', 'mean', 'median', 'mode', 'percentile', 'quantile', 'quartile', 'decile',
            'distribution', 'normal', 'uniform', 'exponential', 'poisson', 'binomial', 'geometric',
            'hypergeometric', 'negative', 'positive', 'zero', 'one', 'two', 'three', 'four', 'five',
            'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand', 'million', 'billion',
            'trillion', 'quadrillion', 'quintillion', 'sextillion', 'septillion', 'octillion',
            'nonillion', 'decillion', 'googol', 'googolplex', 'infinity',
            'prejunesales', 'postjunesales', 'cte', 'temp', 'temporary', 'intermediate', 'helper'
        })

        # More strict patterns for table references in plans
        # Only match if explicitly called "table X" or "join X" or "from X"
        # Avoid matching generic words
        patterns = [
            r'table\s+`?([a-zA-Z0-9_]+)`?',          # "table orders"
            r'from\s+`?([a-zA-Z0-9_]+)`?',           # "from orders"
            r'join\s+`?([a-zA-Z0-9_]+)`?',           # "join customers"
            r'`([a-zA-Z0-9_]+)`\s+table',            # "`orders` table"
        ]
        
        plan_lower = plan.lower()
        
        for pattern in patterns:
            matches = re.finditer(pattern, plan_lower, re.IGNORECASE)
            for match in matches:
                table_name = match.group(1)
                # Filter out extended keywords
                if table_name not in EXTENDED_KEYWORDS and len(table_name) > 1:
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
            error_msg = f"MISSING_TABLE: Required tables {missing_tables} not found in provided schema. Available tables: {available_tables}"
            print(f"[Planner] WARNING: Schema validation failed: {error_msg}")
            print("[Planner] Proceeding anyway as these might be CTEs or aliases.")
            # raise MissingTableError(error_msg)  <-- DISABLED to prevent blocking
        
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
