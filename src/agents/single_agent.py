import os
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

try:
    load_dotenv()
except Exception as e:
    pass  # Ignore errors loading .env

from config import DEFAULT_MODEL, get_llm, extract_content

class SingleAgent:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are an expert SQL generator.
            Given the following database schema and a natural language question, generate a valid SQL query.
            
            Schema:
            {schema}

            Question: {question}

            Return ONLY the SQL query. Do not include markdown formatting (```sql ... ```).
            """
        )
        self.chain = self.prompt | self.llm

    def generate(self, question: str, schema: str) -> str:
        """Generates SQL for a given question and schema."""
        try:
            response = self.chain.invoke({"question": question, "schema": schema})
            return extract_content(response)
        except Exception as e:
            print(f"Error in single agent generation: {e}")
            return ""

if __name__ == "__main__":
    agent = SingleAgent()
    # Mock schema and question
    schema = "CREATE TABLE employees (id INT, name TEXT, salary INT);"
    question = "Show me all employees with salary > 5000."
    print(agent.generate(question, schema))
