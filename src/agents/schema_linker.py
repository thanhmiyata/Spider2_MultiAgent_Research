from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content

class SchemaLinker:
    def __init__(self, model_name=CLAUDE_MODEL):
        self.llm = get_llm(model_name=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are an expert database architect.
            Your task is to identify the relevant tables and columns from the given schema that are needed to answer the user's question.
            
            IMPORTANT GUIDELINES:
            1. **Select Minimal Columns**: Only select columns that are absolutely necessary for the query (SELECT, WHERE, JOIN, GROUP BY, ORDER BY).
            2. **Keep Keys**: ALWAYS include Primary Keys and Foreign Keys for the selected tables, even if not explicitly mentioned, to enable JOINs.
            3. **Keep Date/Time**: If the question involves time (e.g., "recent", "last year", "duration"), include all relevant DATE/TIME columns.
            4. **Data Types**: Include data types for all selected columns.
            
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
            return extract_content(response)
        except Exception as e:
            print(f"Error in schema linking: {e}")
            return schema # Fallback to full schema
