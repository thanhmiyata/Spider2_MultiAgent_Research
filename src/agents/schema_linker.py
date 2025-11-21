import time
from langchain_core.prompts import PromptTemplate

from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content

class SchemaLinker:
    def __init__(self, model_name=CLAUDE_MODEL, max_retries=2):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are an expert database architect specializing in schema analysis for SQL generation.
            Your task is to identify ONLY the relevant tables and columns from the given schema that are needed to answer the user's question.
            
            CRITICAL RULES:
            1. **Minimal Selection**: Only include tables and columns that are DIRECTLY needed for:
               - SELECT clause (columns to return)
               - WHERE clause (filtering conditions)
               - JOIN conditions (foreign keys)
               - GROUP BY / ORDER BY clauses
               - Aggregations and calculations
            
            2. **Always Include Keys**: For ANY table you select, ALWAYS include:
               - Primary Key (usually `id` or `{{table_name}}_id`)
               - Foreign Keys (to enable JOINs with other selected tables)
               - Even if not mentioned in the question, keys are essential for JOINs
            
            3. **Time-Related Columns**: If the question mentions:
               - Dates, years, months, days → Include ALL date/time columns
               - "recent", "last", "first", "since" → Include timestamp columns
               - Duration, period → Include start/end date columns
            
            4. **Data Types**: Include data types for all columns in format: `column_name (TYPE)`
            
            5. **Table Relationships**: If you select multiple tables, ensure they can be joined via foreign keys.
            
            Schema:
            {schema}

            Question: {question}

            Output Format (EXACTLY):
            Table: {{table_name}}
            Columns: col1 (TYPE), col2 (TYPE), col3 (TYPE)
            
            Table: {{another_table}}
            Columns: col1 (TYPE), col2 (TYPE)
            
            Return ONLY the relevant schema subset in the format above. No explanations, no markdown.
            """
        )
        self.chain = self.prompt | self.llm

    def link(self, question: str, schema: str) -> str:
        """Returns the relevant schema subset with retry logic and timeout."""
        for attempt in range(self.max_retries):
            try:
                response = self.chain.invoke({"question": question, "schema": schema})
                linked_schema = extract_content(response)
                
                # Basic validation: check if we got something meaningful
                if len(linked_schema.strip()) < 10:
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return schema  # Fallback to full schema
                
                return linked_schema
                
            except Exception as e:
                print(f"[SchemaLinker] Error in schema linking (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Fixed wait time instead of exponential
                else:
                    return schema  # Fallback to full schema
        
        return schema  # Final fallback
