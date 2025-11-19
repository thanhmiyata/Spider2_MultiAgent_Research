from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import DEFAULT_MODEL

class Generator:
    def __init__(self, model_name=DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "plan"],
            template="""
            You are an expert SQL Developer.
            Generate a valid SQL query based on the provided schema and execution plan.
            
            CRITICAL RULES:
            1. ALWAYS use table aliases (e.g., t1, t2) for ALL tables.
            2. ALWAYS qualify ALL column names with their table alias (e.g., t1.col_name) to avoid "ambiguous column name" errors.
            3. Use SQLite syntax.
            4. Do NOT use Markdown formatting. Return ONLY the raw SQL.
            
            EXAMPLES OF ADVANCED PATTERNS:
            
            Example 1 - Window Functions for Ranking:
            SELECT t1.customer_id, t1.total_sales,
                   NTILE(5) OVER (ORDER BY t1.total_sales DESC) AS quintile
            FROM sales AS t1
            
            Example 2 - Date Functions:
            SELECT JULIANDAY(t1.end_date) - JULIANDAY(t1.start_date) AS days_diff
            FROM orders AS t1
            
            Example 3 - Complex JOIN with USING:
            SELECT t1.customer_id, SUM(t2.amount)
            FROM customers AS t1
            JOIN orders AS t2 USING (customer_id)
            GROUP BY t1.customer_id
            
            Schema:
            {schema}

            Question: {question}

            Execution Plan:
            {plan}

            Return ONLY the SQL query.
            """
        )
        self.chain = self.prompt | self.llm

    def generate(self, question: str, schema: str, plan: str) -> str:
        """Generates SQL based on plan."""
        try:
            response = self.chain.invoke({"question": question, "schema": schema, "plan": plan})
            return response.content.strip()
        except Exception as e:
            print(f"Error in generation: {e}")
            return ""
