from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

from config import DEFAULT_MODEL

class SchemaLinker:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are an expert database architect.
            Your task is to identify the relevant tables and columns from the given schema that are needed to answer the user's question.
            
            IMPORTANT:
            - Include data types for columns (especially for date/time columns)
            - Note any primary/foreign key relationships
            - Keep columns that might be needed for window functions or complex calculations
            
            Schema:
            {schema}

            Question: {question}

            Return ONLY the relevant schema subset. 
            Format your output as a list of table names and their relevant columns with data types.
            Example:
            Table: employees
            Columns: id (INTEGER), name (TEXT), department_id (INTEGER), hire_date (DATE)
            
            Table: departments
            Columns: id (INTEGER), name (TEXT)
            """
        )
        self.chain = self.prompt | self.llm

    def link(self, question: str, schema: str) -> str:
        """Returns the relevant schema subset."""
        try:
            response = self.chain.invoke({"question": question, "schema": schema})
            return response.content.strip()
        except Exception as e:
            print(f"Error in schema linking: {e}")
            return schema # Fallback to full schema
