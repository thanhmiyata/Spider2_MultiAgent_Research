"""
Main Workflow Script for Spider 2.0 Lite Multi-Agent System
Implements the complete pipeline with Router-based adaptive workflow
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from tqdm import tqdm

from agents.router import RouterAgent
from agents.schema_linker import SchemaLinker
from agents.planner import Planner
from agents.generator import Generator
from agents.validator import Validator
from agents.single_agent import SingleAgent

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
DATA_PATH = PROJECT_ROOT / "data/spider2_lite/spider2-lite.jsonl"
DB_DIR = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite"
OUTPUT_FILE = PROJECT_ROOT / "experiments/main_workflow/results.jsonl"
SLEEP_TIME = 2  # Seconds to wait between requests

def get_sqlite_schema(db_path):
    """Extracts schema from SQLite DB in simple format."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        schema_str = ""
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            col_names = [col[1] for col in columns]
            schema_str += f"Table: {table_name}\nColumns: {', '.join(col_names)}\n\n"
            
        conn.close()
        return schema_str
    except Exception as e:
        return f"Error reading schema: {e}"

def process_question(question, schema, router, schema_linker, planner, generator, validator, single_agent, verbose=True):
    """
    Process a single question through the complete multi-agent workflow.
    
    Workflow:
    1. Router classifies question (EASY/MEDIUM/HARD)
    2. If EASY: Router → Schema Linker → Generator → Validator
    3. If MEDIUM/HARD: Router → Schema Linker → Planner → Generator → Validator
    
    Args:
        question: Natural language question
        schema: Database schema
        router: RouterAgent instance
        schema_linker: SchemaLinker instance
        planner: Planner instance
        generator: Generator instance
        validator: Validator instance
        single_agent: SingleAgent instance (for easy questions)
        verbose: Whether to print detailed logs
        
    Returns:
        dict: Result containing SQL, complexity, agent_used, and step details
    """
    step_times = {}
    total_start = time.time()
    
    if verbose:
        print("\n" + "="*80)
        print(f"[MAIN] Processing Question: {question[:100]}...")
        print("="*80)
    
    # Step 1: Router - Classify complexity
    if verbose:
        print("\n[STEP 1: ROUTER] Analyzing question complexity...")
    step_start = time.time()
    
    try:
        complexity = router.route(question)
        step_times['router'] = round(time.time() - step_start, 2)
        
        if verbose:
            print(f"[ROUTER] ✓ Classification: {complexity}")
            print(f"[ROUTER] ⏱️  Time: {step_times['router']}s")
    except Exception as e:
        if verbose:
            print(f"[ROUTER] ✗ Error: {e}")
        complexity = "HARD"  # Default to HARD on error
        step_times['router'] = round(time.time() - step_start, 2)
    
    # Determine workflow path
    if complexity == "EASY":
        # Easy Path: Router → Schema Linker → Generator → Validator
        if verbose:
            print(f"\n[WORKFLOW] Selected: EASY PATH (Schema Linker → Generator → Validator)")
        
        # Step 2: Schema Linker
        if verbose:
            print("\n[STEP 2: SCHEMA LINKER] Filtering relevant tables and columns...")
        step_start = time.time()
        
        try:
            linked_schema = schema_linker.link(question, schema)
            if not linked_schema or len(linked_schema.strip()) < 10:
                linked_schema = schema  # Fallback to full schema
            step_times['schema_linker'] = round(time.time() - step_start, 2)
            
            if verbose:
                print(f"[SCHEMA LINKER] ✓ Filtered schema ({len(linked_schema)} chars)")
                print(f"[SCHEMA LINKER] ⏱️  Time: {step_times['schema_linker']}s")
        except Exception as e:
            if verbose:
                print(f"[SCHEMA LINKER] ✗ Error: {e}, using full schema")
            linked_schema = schema
            step_times['schema_linker'] = round(time.time() - step_start, 2)
        
        # Step 3: Generator (no planning for easy questions)
        if verbose:
            print("\n[STEP 3: GENERATOR] Generating SQL directly...")
        step_start = time.time()
        
        try:
            plan = "Direct SQL generation for easy question"
            generated_sql = generator.generate(question, linked_schema, plan)
            step_times['generator'] = round(time.time() - step_start, 2)
            
            if verbose:
                print(f"[GENERATOR] ✓ SQL Generated ({len(generated_sql)} chars)")
                print(f"[GENERATOR] ⏱️  Time: {step_times['generator']}s")
                print(f"[GENERATOR] SQL Preview: {generated_sql[:100]}...")
        except Exception as e:
            if verbose:
                print(f"[GENERATOR] ✗ Error: {e}")
            generated_sql = ""
            step_times['generator'] = round(time.time() - step_start, 2)
        
        agent_used = "easy_path"
        
    else:
        # Hard Path: Router → Schema Linker → Planner → Generator → Validator
        if verbose:
            print(f"\n[WORKFLOW] Selected: HARD PATH (Schema Linker → Planner → Generator → Validator)")
        
        # Step 2: Schema Linker
        if verbose:
            print("\n[STEP 2: SCHEMA LINKER] Filtering relevant tables and columns...")
        step_start = time.time()
        
        try:
            linked_schema = schema_linker.link(question, schema)
            if not linked_schema or len(linked_schema.strip()) < 10:
                linked_schema = schema  # Fallback to full schema
            step_times['schema_linker'] = round(time.time() - step_start, 2)
            
            if verbose:
                print(f"[SCHEMA LINKER] ✓ Filtered schema ({len(linked_schema)} chars)")
                print(f"[SCHEMA LINKER] ⏱️  Time: {step_times['schema_linker']}s")
        except Exception as e:
            if verbose:
                print(f"[SCHEMA LINKER] ✗ Error: {e}, using full schema")
            linked_schema = schema
            step_times['schema_linker'] = round(time.time() - step_start, 2)
        
        # Step 3: Planner
        if verbose:
            print("\n[STEP 3: PLANNER] Creating execution plan...")
        step_start = time.time()
        
        try:
            plan = planner.plan(question, linked_schema)
            if not plan or len(plan.strip()) < 10:
                plan = "Generate SQL directly based on question and schema."
            step_times['planner'] = round(time.time() - step_start, 2)
            
            if verbose:
                print(f"[PLANNER] ✓ Plan Created ({len(plan)} chars)")
                print(f"[PLANNER] ⏱️  Time: {step_times['planner']}s")
                print(f"[PLANNER] Plan Preview: {plan[:150]}...")
        except Exception as e:
            if verbose:
                print(f"[PLANNER] ✗ Error: {e}")
            plan = "Generate SQL directly based on question and schema."
            step_times['planner'] = round(time.time() - step_start, 2)
        
        # Step 4: Generator
        if verbose:
            print("\n[STEP 4: GENERATOR] Generating SQL based on plan...")
        step_start = time.time()
        
        try:
            generated_sql = generator.generate(question, linked_schema, plan)
            step_times['generator'] = round(time.time() - step_start, 2)
            
            if verbose:
                print(f"[GENERATOR] ✓ SQL Generated ({len(generated_sql)} chars)")
                print(f"[GENERATOR] ⏱️  Time: {step_times['generator']}s")
                print(f"[GENERATOR] SQL Preview: {generated_sql[:100]}...")
        except Exception as e:
            if verbose:
                print(f"[GENERATOR] ✗ Error: {e}")
            generated_sql = ""
            step_times['generator'] = round(time.time() - step_start, 2)
        
        agent_used = "hard_path"
    
    # Final Step: Validator (for both paths)
    if verbose:
        print("\n[FINAL STEP: VALIDATOR] Validating and correcting SQL...")
    step_start = time.time()
    
    try:
        final_sql = validator.validate(question, linked_schema if 'linked_schema' in locals() else schema, generated_sql)
        step_times['validator'] = round(time.time() - step_start, 2)
        
        if verbose:
            print(f"[VALIDATOR] ✓ SQL Validated")
            print(f"[VALIDATOR] ⏱️  Time: {step_times['validator']}s")
            print(f"[VALIDATOR] Final SQL: {final_sql[:100]}...")
    except Exception as e:
        if verbose:
            print(f"[VALIDATOR] ✗ Error: {e}, using unvalidated SQL")
        final_sql = generated_sql
        step_times['validator'] = round(time.time() - step_start, 2)
    
    # Calculate total time
    total_time = round(time.time() - total_start, 2)
    step_times['total'] = total_time
    
    if verbose:
        print("\n" + "="*80)
        print("[TIMING SUMMARY]")
        print("="*80)
        print(f"Router:        {step_times.get('router', 0):>6.2f}s")
        print(f"Schema Linker: {step_times.get('schema_linker', 0):>6.2f}s")
        if 'planner' in step_times:
            print(f"Planner:       {step_times.get('planner', 0):>6.2f}s")
        print(f"Generator:     {step_times.get('generator', 0):>6.2f}s")
        print(f"Validator:     {step_times.get('validator', 0):>6.2f}s")
        print(f"{'='*80}")
        print(f"TOTAL:         {total_time:>6.2f}s")
        print("="*80 + "\n")
    
    return {
        "sql": final_sql,
        "complexity": complexity,
        "agent_used": agent_used,
        "step_times": step_times
    }

def main(max_items=5):
    """
    Main workflow script that processes questions through the multi-agent system.
    
    Args:
        max_items: Maximum number of items to process (default: 5 for testing)
    """
    # Initialize agents
    print("\n" + "="*80)
    print("[INITIALIZATION] Loading Multi-Agent System...")
    print("="*80)
    
    router = RouterAgent()
    schema_linker = SchemaLinker()
    planner = Planner()
    generator = Generator()
    validator = Validator()
    single_agent = SingleAgent()
    
    print("[INITIALIZATION] ✓ All agents loaded successfully\n")
    
    # Create output directory
    output_dir = OUTPUT_FILE.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load Data
    print(f"[DATA] Loading data from {DATA_PATH}...")
    with open(str(DATA_PATH), 'r') as f:
        data = [json.loads(line) for line in f]
    
    # Filter for SQLite databases
    if not DB_DIR.exists():
        print(f"[ERROR] DB Directory {DB_DIR} not found.")
        return
    
    available_dbs = set(os.listdir(str(DB_DIR)))
    sqlite_data = [d for d in data if d['db'] in available_dbs]
    
    # Limit to max_items for testing
    sqlite_data = sqlite_data[:max_items]
    
    print(f"[DATA] ✓ Loaded {len(sqlite_data)} SQLite questions (limited to {max_items})")
    print(f"[DATA] Available databases: {len(available_dbs)}\n")
    
    results = []
    
    # Process each question
    for idx, item in enumerate(tqdm(sqlite_data, desc="[PROGRESS]")):
        db_id = item['db']
        instance_id = item['instance_id']
        question = item['question']
        
        # Locate database file
        db_folder = DB_DIR / db_id
        if not db_folder.exists():
            print(f"[WARNING] Database folder not found: {db_id}")
            continue
            
        sqlite_files = [f for f in os.listdir(str(db_folder)) if f.endswith('.sqlite')]
        if not sqlite_files:
            print(f"[WARNING] No .sqlite file found in {db_folder}")
            continue
        
        db_path = db_folder / sqlite_files[0]
        
        # Get schema
        schema = get_sqlite_schema(db_path)
        
        # Process question through workflow
        start_time = time.time()
        try:
            result = process_question(
                question=question,
                schema=schema,
                router=router,
                schema_linker=schema_linker,
                planner=planner,
                generator=generator,
                validator=validator,
                single_agent=single_agent,
                verbose=True
            )
            
            latency = time.time() - start_time
            
            # Store result
            output = {
                "instance_id": instance_id,
                "question": question,
                "db_id": db_id,
                "generated_sql": result["sql"],
                "complexity": result["complexity"],
                "agent_used": result["agent_used"],
                "latency": round(latency, 2),
                "step_times": result["step_times"]
            }
            
            results.append(output)
            
            # Save intermediate results
            with open(str(OUTPUT_FILE), 'a') as f:
                json.dump(output, f)
                f.write('\n')
                
        except Exception as e:
            print(f"\n[ERROR] Failed to process {instance_id}: {e}\n")
            continue
        
        # Rate limiting
        if idx < len(sqlite_data) - 1:
            time.sleep(SLEEP_TIME)
    
    # Final summary
    print("\n" + "="*80)
    print("[SUMMARY] Workflow Complete!")
    print("="*80)
    print(f"Total processed: {len(results)}")
    print(f"Results saved to: {OUTPUT_FILE}")
    
    if results:
        avg_latency = sum(r['latency'] for r in results) / len(results)
        print(f"Average latency: {avg_latency:.2f}s")
        
        complexity_counts = {}
        for r in results:
            comp = r.get('complexity', 'UNKNOWN')
            complexity_counts[comp] = complexity_counts.get(comp, 0) + 1
        
        print("\nComplexity Distribution:")
        for comp, count in complexity_counts.items():
            print(f"  {comp}: {count}")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run main workflow on Spider 2.0 Lite")
    parser.add_argument("--max-items", type=int, default=5,
                       help="Maximum number of items to process (default: 5)")
    
    args = parser.parse_args()
    
    main(max_items=args.max_items)
