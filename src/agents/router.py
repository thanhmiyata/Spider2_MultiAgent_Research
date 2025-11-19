import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

from config import DEFAULT_MODEL

class RouterAgent:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            You are an expert SQL complexity analyzer.
            Analyze the following natural language query and classify it into one of these categories:
            - EASY: Simple retrieval, 1-2 tables, basic filtering.
            - MEDIUM: Aggregations, grouping, 3-4 tables, subqueries.
            - HARD: Complex logic, window functions, 5+ tables, nested subqueries, CTEs.

            Query: {query}

            Return ONLY the category name (EASY, MEDIUM, or HARD).
            """
        )
        self.chain = self.prompt | self.llm

    def route(self, query: str) -> str:
        """Classifies the query complexity."""
        try:
            response = self.chain.invoke({"query": query})
            return response.content.strip().upper()
        except Exception as e:
            print(f"Error in routing: {e}")
            return "HARD" # Default to HARD for safety

if __name__ == "__main__":
    router = RouterAgent()
    print(router.route("Show me all employees."))
    print(router.route("Calculate the average salary per department for the last 5 years."))
