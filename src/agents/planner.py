from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

class Planner:
    def __init__(self, model_name=GEMINI_MODEL):
        self.llm = get_llm(model_name=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are a Senior Data Analyst.
            Plan the logical steps to answer the following question using the provided schema.
            
            IMPORTANT: 
            - Do NOT write SQL code yet. Focus on the logic.
            - SPECIFY exact SQL functions needed (e.g., "Use NTILE(5) for quintile ranking", "Use JULIANDAY() for date difference", "Use STRFTIME('%Y', date_col) for year extraction").
            - Break down complex calculations into clear steps.
            - Outline the Logical Order of Operations:
              1. Filter (WHERE)
              2. Join (JOIN)
              3. Aggregate (GROUP BY)
              4. Window Functions (OVER)
              5. Order/Limit
            
            Schema:
            {schema}

            Question: {question}

            Provide a detailed step-by-step plan with specific SQL functions mentioned.
            """
        )
        self.chain = self.prompt | self.llm

    def plan(self, question: str, schema: str) -> str:
        """Generates a logical plan."""
        try:
            response = self.chain.invoke({"question": question, "schema": schema})
            return extract_content(response)
        except Exception as e:
            print(f"Error in planning: {e}")
            return "Proceed directly to SQL generation."
