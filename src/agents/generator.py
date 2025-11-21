import time
import re
from langchain_core.prompts import PromptTemplate
from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content

class Generator:
    def __init__(self, model_name=CLAUDE_MODEL, max_retries=2):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "plan"],
            template="""
            You are an expert SQL Developer specializing in SQLite.
            Generate a valid, production-ready SQL query based on the provided schema and execution plan.
            
            MANDATORY RULES (Follow STRICTLY):
            
            1. **Table Aliases**: 
               - ALWAYS use short, meaningful aliases for EVERY table (e.g., `orders AS o`, `customers AS c`)
               - Use consistent naming (lowercase, 1-3 characters preferred)
            
            2. **Column Qualification**:
               - ALWAYS prefix EVERY column with its table alias: `o.order_id`, `c.customer_name`
               - This prevents "ambiguous column name" errors
               - Even in WHERE, JOIN, GROUP BY, ORDER BY clauses
            
            3. **SQLite Syntax**:
               - Use SQLite-compatible functions only
               - No proprietary extensions
            
            4. **Date/Time Functions**:
               - `STRFTIME('%Y-%m-%d', date_col)` for date formatting
               - `JULIANDAY(date1) - JULIANDAY(date2)` for date differences
               - `DATE(date_col)` to extract date part
               - `STRFTIME('%Y', date_col)` for year extraction
            
            5. **Complex Features**:
               - Use CTEs (WITH ... AS ...) for complex multi-step logic
               - Use window functions: `RANK() OVER (PARTITION BY ... ORDER BY ...)`
               - Use `NTILE(n)` for percentile/quantile calculations
               - Use `CASE WHEN ... THEN ... ELSE ... END` for conditional logic
            
            6. **Best Practices**:
               - Use proper JOIN syntax (INNER JOIN, LEFT JOIN, etc.)
               - Include all necessary JOIN conditions in ON clause
               - Use parentheses for complex WHERE conditions
               - Ensure GROUP BY includes all non-aggregated SELECT columns
            
            Schema:
            {schema}

            Question: {question}

            Execution Plan:
            {plan}

            Generate the SQL query following ALL rules above. Return ONLY the raw SQL query.
            Do NOT include:
            - Markdown code blocks (```sql ... ```)
            - Explanations or comments
            - Any text before or after the SQL
            """
        )
        self.chain = self.prompt | self.llm

    def _clean_sql(self, sql: str) -> str:
        """Cleans SQL output from markdown and extra text."""
        # Remove markdown code blocks
        sql = re.sub(r'```sql\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'```\s*', '', sql)
        
        # Remove common prefixes/suffixes
        sql = re.sub(r'^(Here is|Here\'s|The SQL query is|SQL:|Query:)\s*', '', sql, flags=re.IGNORECASE)
        sql = sql.strip()
        
        # Extract SQL if it's wrapped in quotes or other text
        sql_match = re.search(r'(SELECT|WITH|INSERT|UPDATE|DELETE)', sql, re.IGNORECASE)
        if sql_match:
            sql = sql[sql_match.start():]
        
        return sql.strip()

    def generate(self, question: str, schema: str, plan: str) -> str:
        """Generates SQL based on plan with retry logic and timeout."""
        for attempt in range(self.max_retries):
            try:
                response = self.chain.invoke({"question": question, "schema": schema, "plan": plan})
                sql = extract_content(response)
                sql = self._clean_sql(sql)
                
                # Basic validation: check if we got SQL
                if not sql or len(sql.strip()) < 10:
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return ""
                
                # Check if it looks like SQL
                if not re.search(r'\b(SELECT|WITH|INSERT|UPDATE|DELETE)\b', sql, re.IGNORECASE):
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return ""
                
                return sql
                
            except Exception as e:
                print(f"[Generator] Error in generation (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Fixed wait time instead of exponential
                else:
                    return ""
        
        return ""
