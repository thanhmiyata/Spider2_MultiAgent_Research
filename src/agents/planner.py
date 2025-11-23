import time
from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

class Planner:
    def __init__(self, model_name=GEMINI_MODEL, max_retries=2):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
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

    def plan(self, question: str, schema: str) -> str:
        """Generates a logical plan with retry logic and timeout."""
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
                
                return plan
                
            except Exception as e:
                print(f"[Planner] Error in planning (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Fixed wait time instead of exponential
                else:
                    return "Proceed directly to SQL generation."
        
        return "Proceed directly to SQL generation."
