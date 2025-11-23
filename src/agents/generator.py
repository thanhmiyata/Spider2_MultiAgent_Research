import time
import re
from langchain_core.prompts import PromptTemplate
from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content
from prompts.generator_prompts import get_generator_prompt_template

class Generator:
    def __init__(self, model_name=CLAUDE_MODEL, max_retries=2, include_examples=True):
        self.model_name = model_name
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        
        # Get the prompt template with proper formatting
        prompt_template = get_generator_prompt_template(include_examples=include_examples)
        
        # Replace double braces with single braces for LangChain
        prompt_template = prompt_template.replace("{{schema}}", "{schema}")
        prompt_template = prompt_template.replace("{{question}}", "{question}")
        prompt_template = prompt_template.replace("{{plan}}", "{plan}")
        
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "plan"],
            template=prompt_template
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
        # Inject Linear Regression Template if needed
        keywords = ["linear regression", "trend", "slope", "intercept"]
        if any(k in question.lower() for k in keywords) or any(k in plan.lower() for k in keywords):
            linear_regression_template = """
Linear Regression in SQLite Template:
To calculate Slope (m) and Intercept (b) for y = mx + b:
SELECT
  (N * SUM(x*y) - SUM(x)*SUM(y)) / (N * SUM(x*x) - SUM(x)*SUM(x)) AS slope,
  (SUM(y) - slope * SUM(x)) / N AS intercept
FROM (
  SELECT col_x AS x, col_y AS y, COUNT(*) OVER() AS N
  FROM table_name
)
"""
            # Append to schema or plan to ensure it's seen
            plan += "\n\n" + linear_regression_template

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
