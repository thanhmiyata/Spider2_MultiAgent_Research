from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

from config import DEFAULT_MODEL

class Planner:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are a Senior Data Analyst.
            Plan the logical steps to answer the following question using the provided schema.
            
            IMPORTANT: 
            - Do NOT write SQL code yet. Focus on the logic.
            - SPECIFY exact SQL functions needed (e.g., "Use NTILE(5) for quintile ranking", "Use JULIANDAY() for date difference")
            - Break down complex calculations into clear steps.
            
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
            return response.content.strip()
        except Exception as e:
            print(f"Error in planning: {e}")
            return "Proceed directly to SQL generation."
