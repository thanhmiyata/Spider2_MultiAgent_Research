import time
from agents.schema_linker import SchemaLinker
from agents.planner import Planner
from agents.generator import Generator
from agents.validator import Validator
from agents.knowledge_retriever import KnowledgeRetriever

class MultiAgentSystem:
    def __init__(self, enable_knowledge_retrieval=True):
        self.linker = SchemaLinker()
        self.planner = Planner()
        self.generator = Generator()
        self.validator = Validator()
        self.enable_knowledge_retrieval = enable_knowledge_retrieval
        
        # Initialize knowledge retriever if enabled
        if self.enable_knowledge_retrieval:
            try:
                self.knowledge_retriever = KnowledgeRetriever()
            except Exception as e:
                print(f"[MAS] Warning: Could not initialize KnowledgeRetriever: {e}")
                self.knowledge_retriever = None
                self.enable_knowledge_retrieval = False

    def run(self, question: str, schema: str, verbose=False) -> str:
        """
        Orchestrates the multi-step process with timing breakdown:
        0. Domain Knowledge Retrieval: Search for relevant business terms/formulas.
        1. Schema Linking: Reduce schema to relevant parts.
        2. Planning: Create a logical execution plan (with domain knowledge).
        3. Generation: Generate SQL based on plan and reduced schema (with domain knowledge).
        4. Validation: Check and correct the SQL.
        
        Returns:
            str: Generated and validated SQL query
        """
        start_total = time.time()
        timings = {}
        
        if verbose:
            print(f"  [MAS] Processing: {question[:80]}...")
        
        try:
            # Step 0: Knowledge Retrieval
            domain_knowledge = ""
            if self.enable_knowledge_retrieval and self.knowledge_retriever:
                if verbose:
                    print("  [MAS] Step 0: Domain Knowledge Retrieval...")
                start = time.time()
                domain_knowledge = self.knowledge_retriever.retrieve_and_inject(question)
                timings['knowledge_retrieval'] = round(time.time() - start, 2)
                if verbose:
                    if domain_knowledge:
                        print(f"  [MAS] Step 0 took {timings['knowledge_retrieval']}s | Found domain knowledge")
                        print(f"  [MAS] {domain_knowledge[:200]}...")
                    else:
                        print(f"  [MAS] Step 0 took {timings['knowledge_retrieval']}s | No domain knowledge found")
            
            # Step 1: Schema Linking
            if verbose:
                print("  [MAS] Step 1: Schema Linking...")
            start = time.time()
            linked_schema = self.linker.link(question, schema)
            if not linked_schema or len(linked_schema.strip()) < 10:
                linked_schema = schema  # Fallback to full schema
            timings['schema_linking'] = round(time.time() - start, 2)
            if verbose:
                print(f"  [MAS] Step 1 took {timings['schema_linking']}s | Linked Schema length: {len(linked_schema)} chars")

            # Step 2: Planning (with domain knowledge if available)
            if verbose:
                print("  [MAS] Step 2: Planning...")
            start = time.time()
            # Inject domain knowledge into planning context if available
            if domain_knowledge:
                enhanced_question = f"{question}\n\n{domain_knowledge}"
                plan = self.planner.plan(enhanced_question, linked_schema)
            else:
                plan = self.planner.plan(question, linked_schema)
            
            if not plan or len(plan.strip()) < 10:
                plan = "Generate SQL directly based on question and schema."
            timings['planning'] = round(time.time() - start, 2)
            if verbose:
                print(f"  [MAS] Step 2 took {timings['planning']}s | Plan length: {len(plan)} chars")

            # Step 3: Generation (with domain knowledge if available)
            if verbose:
                print("  [MAS] Step 3: SQL Generation...")
            start = time.time()
            # Inject domain knowledge into generation context if available
            if domain_knowledge:
                enhanced_question = f"{question}\n\n{domain_knowledge}"
                sql = self.generator.generate(enhanced_question, linked_schema, plan)
            else:
                sql = self.generator.generate(question, linked_schema, plan)
            
            if not sql:
                if verbose:
                    print("  [MAS] Warning: Generation failed, returning empty SQL")
                return ""
            timings['generation'] = round(time.time() - start, 2)
            if verbose:
                print(f"  [MAS] Step 3 took {timings['generation']}s | Generated SQL length: {len(sql)} chars")

            # Step 4: Validation
            if verbose:
                print("  [MAS] Step 4: Validation & Correction...")
            start = time.time()
            final_sql = self.validator.validate(question, linked_schema, sql)
            timings['validation'] = round(time.time() - start, 2)
            if verbose:
                print(f"  [MAS] Step 4 took {timings['validation']}s | Final SQL: {final_sql[:100]}...")
            
            timings['total'] = round(time.time() - start_total, 2)
            if verbose:
                print(f"\n  [MAS] ===== TIMING SUMMARY =====")
                if 'knowledge_retrieval' in timings:
                    print(f"  Knowledge Retrieval: {timings['knowledge_retrieval']}s")
                print(f"  Schema Linking: {timings.get('schema_linking', 0)}s")
                print(f"  Planning:       {timings.get('planning', 0)}s")
                print(f"  Generation:     {timings.get('generation', 0)}s")
                print(f"  Validation:     {timings.get('validation', 0)}s")
                print(f"  TOTAL:          {timings.get('total', 0)}s")
                print(f"  ============================\n")
            
            return final_sql
            
        except Exception as e:
            print(f"  [MAS] Error in multi-agent flow: {e}")
            return ""

if __name__ == "__main__":
    mas = MultiAgentSystem()
    print(mas.run("Test question", "Test schema"))
