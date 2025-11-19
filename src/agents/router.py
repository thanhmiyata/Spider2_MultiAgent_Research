import os
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

class RouterAgent:
    def __init__(self, model_name=GEMINI_MODEL):
        self.llm = get_llm(model_name=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            You are a Query Complexity Classifier.
            Classify the following SQL query complexity as EASY, MEDIUM, or HARD.
            
            Definitions:
            - EASY: Simple SELECT, WHERE, basic aggregation (COUNT, SUM), single table or simple JOIN.
            - MEDIUM: Multiple JOINs, GROUP BY with HAVING, subqueries.
            - HARD: Window functions (RANK, NTILE), CTEs (WITH), complex nested subqueries, set operations (UNION, INTERSECT), date manipulation, CASE WHEN.

            Query: {query}

            Return ONLY the complexity level (EASY, MEDIUM, or HARD).
            """
        )
        self.chain = self.prompt | self.llm

    def route(self, query: str) -> str:
        """Classifies the query complexity."""
        try:
            response = self.chain.invoke({"query": query})
            complexity = extract_content(response).upper()
            if complexity in ["EASY", "MEDIUM", "HARD"]:
                return complexity
            else:
                return "HARD" # Default to HARD for safety
        except Exception as e:
            print(f"Error in routing: {e}")
            return "HARD" # Default to HARD for safety

if __name__ == "__main__":
    router = RouterAgent()
    print(router.route("Show me all employees."))
    print(router.route("Calculate the average salary per department for the last 5 years."))
