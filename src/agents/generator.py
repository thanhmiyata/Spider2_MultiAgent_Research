from langchain_core.prompts import PromptTemplate
from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content

class Generator:
    def __init__(self, model_name=CLAUDE_MODEL):
        self.llm = get_llm(model_name=model_name, temperature=0)
        self.prompt = PromptTemplate(
            input_variables=["question", "schema", "plan"],
            template="""
            You are an expert SQL Developer.
            Generate a valid SQL query based on the provided schema and execution plan.
            
            CRITICAL RULES:
            1. **Aliases**: ALWAYS use table aliases (e.g., t1, t2) for ALL tables.
            1. **Aliases**: ALWAYS use short, explicit table aliases (e.g., `T1`, `T2` or `orders`, `cust`).
            2. **Qualification**: ALWAYS prefix EVERY column name with its table alias (e.g., `T1.order_id`, `T2.price`).
            3. **Syntax**: Use valid SQLite syntax.
            4. **Date Functions**: Use `STRFTIME('%Y-%m-%d', col)` or `JULIANDAY(col)` for date operations.
            5. **CTEs**: Use Common Table Expressions (WITH clauses) for complex logic.
            6. **Window Functions**: Use `RANK()`, `DENSE_RANK()`, `NTILE()`, `ROW_NUMBER()` as needed.
            7. **CASE WHEN**: Use `CASE WHEN condition THEN val ELSE val END` for conditional logic.
            
            Schema:
            {schema}

            Question: {question}

            Execution Plan:
            {plan}

            Return ONLY the SQL query. Do NOT include markdown formatting (```sql ... ```) or explanations.
            """
        )
        self.chain = self.prompt | self.llm

    def generate(self, question: str, schema: str, plan: str) -> str:
        """Generates SQL based on plan."""
        try:
            response = self.chain.invoke({"question": question, "schema": schema, "plan": plan})
            sql = extract_content(response)
            # Remove markdown code blocks if present
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql
        except Exception as e:
            print(f"Error in generation: {e}")
            return ""
