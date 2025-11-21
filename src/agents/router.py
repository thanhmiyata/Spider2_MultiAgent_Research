import os
import time
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

from config import DEFAULT_MODEL, GEMINI_MODEL, get_llm, extract_content

class RouterAgent:
    def __init__(self, model_name=GEMINI_MODEL, max_retries=3):
        self.llm = get_llm(model_name=model_name, temperature=0)
        self.max_retries = max_retries
        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            You are an expert Query Complexity Classifier for SQL generation tasks.
            Analyze the following natural language question and classify its complexity as EASY, MEDIUM, or HARD.
            
            Classification Guidelines:
            
            **EASY** - Simple queries that can be answered with:
            - Single table SELECT with WHERE clause
            - Basic aggregations (COUNT, SUM, AVG, MIN, MAX) on single table
            - Simple JOINs (1-2 tables, straightforward relationships)
            - Basic filtering and sorting
            Examples: "Show all employees", "Count orders in 2023", "List products with price > 100"
            
            **MEDIUM** - Moderate complexity requiring:
            - Multiple JOINs (3+ tables)
            - GROUP BY with HAVING clauses
            - Subqueries (correlated or uncorrelated)
            - Multiple aggregations with different grouping
            - Date range filtering with calculations
            Examples: "Find customers who bought more than 5 items", "Average sales per region with minimum threshold"
            
            **HARD** - Complex queries requiring advanced SQL features:
            - Window functions (RANK, DENSE_RANK, NTILE, ROW_NUMBER, LAG, LEAD)
            - Common Table Expressions (CTEs with WITH clause)
            - Complex nested subqueries (3+ levels)
            - Set operations (UNION, INTERSECT, EXCEPT)
            - Advanced date/time manipulations
            - Complex CASE WHEN with multiple conditions
            - Self-joins or recursive queries
            Examples: "Find top 5% customers by revenue using NTILE", "Calculate running totals with window functions"

            Question: {query}

            Return ONLY one word: EASY, MEDIUM, or HARD. No explanations.
            """
        )
        self.chain = self.prompt | self.llm

    def route(self, query: str) -> str:
        """Classifies the query complexity with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.chain.invoke({"query": query})
                complexity = extract_content(response).upper().strip()
                
                # Extract complexity from response (handle cases where LLM adds extra text)
                if "EASY" in complexity:
                    return "EASY"
                elif "MEDIUM" in complexity:
                    return "MEDIUM"
                elif "HARD" in complexity:
                    return "HARD"
                else:
                    # Try to find complexity in first few words
                    words = complexity.split()
                    for word in words[:3]:
                        if word in ["EASY", "MEDIUM", "HARD"]:
                            return word
                    
                    # Default to HARD if unclear
                    if attempt < self.max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    return "HARD"
                    
            except Exception as e:
                print(f"Error in routing (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return "HARD"  # Default to HARD for safety
        
        return "HARD"  # Fallback

if __name__ == "__main__":
    router = RouterAgent()
    print(router.route("Show me all employees."))
    print(router.route("Calculate the average salary per department for the last 5 years."))
