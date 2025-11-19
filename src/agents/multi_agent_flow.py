# This is a placeholder for the Multi-Agent Flow
# We will implement the actual logic using CrewAI or LangGraph in Phase 2

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

    def run(self, question: str, schema: str) -> str:
        """
        Orchestrates the multi-step process:
        1. Schema Linking: Reduce schema to relevant parts.
        2. Planning: Create a logical execution plan.
        3. Generation: Generate SQL based on plan and reduced schema.
        4. Validation: Check and correct the SQL.
        """
        print(f"  [MAS] Processing: {question[:50]}...")
        
        # Step 1: Schema Linking
        linked_schema = self.linker.link(question, schema)
        # print(f"  [MAS] Linked Schema: {linked_schema[:50]}...")

        # Step 2: Planning
        plan = self.planner.plan(question, linked_schema)
        # print(f"  [MAS] Plan: {plan[:50]}...")

        # Step 3: Generation
        sql = self.generator.generate(question, linked_schema, plan)
        # print(f"  [MAS] Initial SQL: {sql[:50]}...")

        # Step 4: Validation
        final_sql = self.validator.validate(question, linked_schema, sql)
        print(f"  [MAS] Final SQL: {final_sql[:50]}...")
        
        return final_sql

if __name__ == "__main__":
    mas = MultiAgentSystem()
    print(mas.run("Test question", "Test schema"))
