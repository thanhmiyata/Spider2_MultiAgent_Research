import time
from agents.schema_linker import SchemaLinker
from agents.planner import Planner
from agents.generator import Generator
from agents.validator import Validator

class MultiAgentSystem:
    def __init__(self):
        self.linker = SchemaLinker()
        self.planner = Planner()
        self.generator = Generator()
        self.validator = Validator()

    def run(self, question: str, schema: str, verbose=False) -> str:
        """
        Orchestrates the multi-step process:
        1. Schema Linking: Reduce schema to relevant parts.
        2. Planning: Create a logical execution plan.
        3. Generation: Generate SQL based on plan and reduced schema.
        4. Validation: Check and correct the SQL.
        
        Returns:
            str: Generated and validated SQL query
        """
        if verbose:
            print(f"  [MAS] Processing: {question[:80]}...")
        
        try:
            # Step 1: Schema Linking
            if verbose:
                print("  [MAS] Step 1: Schema Linking...")
            linked_schema = self.linker.link(question, schema)
            if not linked_schema or len(linked_schema.strip()) < 10:
                linked_schema = schema  # Fallback to full schema
            if verbose:
                print(f"  [MAS] Linked Schema length: {len(linked_schema)} chars")

            # Step 2: Planning
            if verbose:
                print("  [MAS] Step 2: Planning...")
            plan = self.planner.plan(question, linked_schema)
            if not plan or len(plan.strip()) < 10:
                plan = "Generate SQL directly based on question and schema."
            if verbose:
                print(f"  [MAS] Plan length: {len(plan)} chars")

            # Step 3: Generation
            if verbose:
                print("  [MAS] Step 3: SQL Generation...")
            sql = self.generator.generate(question, linked_schema, plan)
            if not sql:
                if verbose:
                    print("  [MAS] Warning: Generation failed, returning empty SQL")
                return ""
            if verbose:
                print(f"  [MAS] Generated SQL length: {len(sql)} chars")

            # Step 4: Validation
            if verbose:
                print("  [MAS] Step 4: Validation & Correction...")
            final_sql = self.validator.validate(question, linked_schema, sql)
            if verbose:
                print(f"  [MAS] Final SQL: {final_sql[:100]}...")
            
            return final_sql
            
        except Exception as e:
            print(f"  [MAS] Error in multi-agent flow: {e}")
            return ""

if __name__ == "__main__":
    mas = MultiAgentSystem()
    print(mas.run("Test question", "Test schema"))
