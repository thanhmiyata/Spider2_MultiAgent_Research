"""
Evaluation Script for Spider 2.0 Lite Dataset
Assesses system accuracy using execution accuracy match methodology
"""

import json
import os
import sqlite3
import csv
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
DATA_PATH = PROJECT_ROOT / "data/spider2_lite/spider2-lite.jsonl"
GOLD_SQL_DIR = PROJECT_ROOT / "data/spider2_lite/evaluation_suite/gold/sql"
DB_DIR = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite"
OUTPUT_DIR = PROJECT_ROOT / "experiments/evaluation"

def load_dataset():
    """
    Load Spider 2.0 Lite dataset from JSONL file.
    
    Returns:
        list: List of dictionaries containing question and metadata
    """
    print(f"[DATA] Loading dataset from {DATA_PATH}...")
    
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")
    
    with open(str(DATA_PATH), 'r') as f:
        data = [json.loads(line) for line in f]
    
    print(f"[DATA] ✓ Loaded {len(data)} questions")
    return data

def load_gold_sql(instance_id):
    """
    Load gold SQL for a specific instance.
    
    Args:
        instance_id: Instance identifier
        
    Returns:
        str: Gold SQL query or None if not found
    """
    gold_path = GOLD_SQL_DIR / f"{instance_id}.sql"
    
    if not gold_path.exists():
        return None
    
    with open(str(gold_path), 'r') as f:
        return f.read().strip()

def execute_sql(db_path, sql):
    """
    Execute SQL query on database and return sorted results.
    
    Args:
        db_path: Path to SQLite database
        sql: SQL query to execute
        
    Returns:
        tuple: (success: bool, result: set or error message)
    """
    if not sql or len(sql.strip()) == 0:
        return False, "Empty SQL query"
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        
        # Convert to sorted list of tuples for comparison
        # Sort to avoid order-based mismatches
        sorted_results = sorted(results)
        
        return True, set(map(tuple, sorted_results))
        
    except Exception as e:
        return False, str(e)

def clean_sql(sql):
    """
    Clean SQL query by removing markdown formatting and extra whitespace.
    
    Args:
        sql: SQL query string
        
    Returns:
        str: Cleaned SQL query
    """
    if not sql:
        return ""
    
    # Remove markdown code blocks
    sql = sql.replace("```sql", "").replace("```", "")
    
    # Remove common prefixes
    prefixes = ["Here is", "Here's", "The SQL query is:", "SQL:", "Query:"]
    for prefix in prefixes:
        if sql.strip().lower().startswith(prefix.lower()):
            sql = sql[len(prefix):].strip()
    
    return sql.strip()

def compare_results(pred_result, gold_result):
    """
    Compare predicted and gold SQL execution results.
    
    Args:
        pred_result: tuple (success, result/error)
        gold_result: tuple (success, result/error)
        
    Returns:
        tuple: (is_correct: bool, error_type: str or None, details: str)
    """
    pred_success, pred_data = pred_result
    gold_success, gold_data = gold_result
    
    # If predicted SQL failed to execute
    if not pred_success:
        error_type = "execution_error"
        if "syntax" in pred_data.lower() or "near" in pred_data.lower():
            error_type = "syntax_error"
        return False, error_type, pred_data
    
    # If gold SQL failed (shouldn't happen, but handle it)
    if not gold_success:
        return False, "gold_sql_error", f"Gold SQL failed: {gold_data}"
    
    # Compare results
    if pred_data == gold_data:
        return True, None, "Results match"
    else:
        return False, "result_mismatch", f"Results differ (pred: {len(pred_data)} rows, gold: {len(gold_data)} rows)"

def run_evaluation(results_file, save_failures=True):
    """
    Run evaluation on a results file.
    
    Args:
        results_file: Path to JSONL file containing generated results
        save_failures: Whether to save failure analysis to CSV
        
    Returns:
        dict: Evaluation metrics
    """
    print("\n" + "="*80)
    print("[EVALUATION] Spider 2.0 Lite Evaluation")
    print("="*80)
    
    # Load dataset for questions
    dataset = load_dataset()
    question_map = {item['instance_id']: item for item in dataset}
    
    # Load generated results
    if not Path(results_file).exists():
        print(f"[ERROR] Results file not found: {results_file}")
        return None
    
    print(f"[DATA] Loading results from {results_file}...")
    with open(results_file, 'r') as f:
        results = [json.loads(line) for line in f]
    
    # Deduplicate by keeping latest result for each instance_id
    latest_results = {}
    for item in results:
        latest_results[item['instance_id']] = item
    results = list(latest_results.values())
    
    print(f"[DATA] ✓ Loaded {len(results)} results\n")
    
    # Initialize counters
    total = 0
    correct = 0
    errors = {
        "empty_sql": 0,
        "syntax_error": 0,
        "execution_error": 0,
        "result_mismatch": 0,
        "no_gold_sql": 0,
        "no_database": 0
    }
    
    failures = []
    
    # Process each result
    print("[EVALUATION] Processing results...")
    for item in tqdm(results, desc="Evaluating"):
        instance_id = item['instance_id']
        db_id = item.get('db_id', '')
        question = item.get('question', '')
        generated_sql = item.get('generated_sql', '')
        
        # Clean SQL
        generated_sql = clean_sql(generated_sql)
        
        # Check for empty SQL
        if not generated_sql:
            errors["empty_sql"] += 1
            failures.append({
                "instance_id": instance_id,
                "question": question,
                "db_id": db_id,
                "generated_sql": "",
                "gold_sql": "",
                "error_type": "empty_sql",
                "error_message": "Empty SQL generated"
            })
            total += 1
            continue
        
        # Load gold SQL
        gold_sql = load_gold_sql(instance_id)
        if not gold_sql:
            errors["no_gold_sql"] += 1
            continue  # Don't count in total if no gold SQL available
        
        # Locate database
        db_folder = DB_DIR / db_id
        if not db_folder.exists():
            errors["no_database"] += 1
            continue  # Don't count in total if database not available
        
        sqlite_files = [f for f in os.listdir(str(db_folder)) if f.endswith('.sqlite')]
        if not sqlite_files:
            errors["no_database"] += 1
            continue
        
        db_path = db_folder / sqlite_files[0]
        
        # Execute both SQLs
        pred_result = execute_sql(db_path, generated_sql)
        gold_result = execute_sql(db_path, gold_sql)
        
        # Compare results
        is_correct, error_type, details = compare_results(pred_result, gold_result)
        
        total += 1
        
        if is_correct:
            correct += 1
        else:
            if error_type:
                errors[error_type] = errors.get(error_type, 0) + 1
            
            # Record failure
            failures.append({
                "instance_id": instance_id,
                "question": question,
                "db_id": db_id,
                "generated_sql": generated_sql,
                "gold_sql": gold_sql,
                "error_type": error_type,
                "error_message": details
            })
    
    # Calculate accuracy
    accuracy = (correct / total * 100) if total > 0 else 0
    
    # Print results
    print("\n" + "="*80)
    print("[RESULTS] Evaluation Summary")
    print("="*80)
    print(f"Total Evaluated:    {total}")
    print(f"Correct:            {correct}")
    print(f"Incorrect:          {total - correct}")
    print(f"Accuracy:           {accuracy:.2f}%")
    print("\nError Breakdown:")
    print(f"  Empty SQL:         {errors['empty_sql']}")
    print(f"  Syntax Errors:     {errors['syntax_error']}")
    print(f"  Execution Errors:  {errors['execution_error']}")
    print(f"  Result Mismatches: {errors['result_mismatch']}")
    print("\nSkipped (Not Counted):")
    print(f"  No Gold SQL:       {errors['no_gold_sql']}")
    print(f"  No Database:       {errors['no_database']}")
    print("="*80 + "\n")
    
    # Save failure analysis
    if save_failures and failures:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failure_file = OUTPUT_DIR / f"failure_analysis_{timestamp}.csv"
        
        print(f"[OUTPUT] Saving failure analysis to {failure_file}...")
        
        with open(str(failure_file), 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'instance_id', 'question', 'db_id', 'generated_sql', 
                'gold_sql', 'error_type', 'error_message'
            ])
            writer.writeheader()
            writer.writerows(failures)
        
        print(f"[OUTPUT] ✓ Saved {len(failures)} failure cases\n")
    
    # Return metrics
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "errors": errors,
        "failures": len(failures)
    }

def run_multi_agent_evaluation(question, schema, db_path):
    """
    Run the multi-agent system on a single question and evaluate.
    This function is used to generate predictions if not already available.
    
    Args:
        question: Natural language question
        schema: Database schema
        db_path: Path to database file
        
    Returns:
        str: Generated SQL query
    """
    # Import here to avoid circular dependencies
    from agents.router import RouterAgent
    from agents.schema_linker import SchemaLinker
    from agents.planner import Planner
    from agents.generator import Generator
    from agents.validator import Validator
    
    # Initialize agents
    router = RouterAgent()
    schema_linker = SchemaLinker()
    planner = Planner()
    generator = Generator()
    validator = Validator()
    
    # Classify complexity
    complexity = router.route(question)
    
    # Schema linking
    linked_schema = schema_linker.link(question, schema)
    if not linked_schema or len(linked_schema.strip()) < 10:
        linked_schema = schema
    
    # Generate SQL
    if complexity == "EASY":
        # Easy path: skip planner
        plan = "Direct SQL generation"
        sql = generator.generate(question, linked_schema, plan)
    else:
        # Hard path: use planner
        plan = planner.plan(question, linked_schema)
        sql = generator.generate(question, linked_schema, plan)
    
    # Validate
    final_sql = validator.validate(question, linked_schema, sql)
    
    return final_sql

def main():
    """Main entry point for evaluation script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Evaluate Spider 2.0 Lite results using execution accuracy"
    )
    parser.add_argument(
        "--results", 
        type=str,
        help="Path to results JSONL file"
    )
    parser.add_argument(
        "--no-failures",
        action="store_true",
        help="Don't save failure analysis CSV"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate predictions using multi-agent system (slow)"
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to evaluate"
    )
    
    args = parser.parse_args()
    
    if args.generate:
        print("\n[MODE] Running in generation mode (will generate predictions)")
        print("[WARNING] This will be slow. Consider using benchmark.py instead.\n")
        # TODO: Implement generation mode if needed
        print("[ERROR] Generation mode not yet implemented.")
        print("[INFO] Use 'python benchmark.py' to generate results first.")
        return
    
    if not args.results:
        # Try to find latest results file
        possible_paths = [
            PROJECT_ROOT / "experiments/main_workflow/results.jsonl",
            PROJECT_ROOT / "experiments/benchmark/adaptive_results_*.jsonl",
            PROJECT_ROOT / "experiments/multi_agent/results.jsonl"
        ]
        
        results_file = None
        for path_pattern in possible_paths:
            if '*' in str(path_pattern):
                # Handle wildcards
                import glob
                matches = glob.glob(str(path_pattern))
                if matches:
                    # Get most recent
                    results_file = max(matches, key=os.path.getctime)
                    break
            elif path_pattern.exists():
                results_file = str(path_pattern)
                break
        
        if not results_file:
            print("[ERROR] No results file specified and no default found.")
            print("[INFO] Use --results <path> to specify results file.")
            print("[INFO] Or run 'python main.py' or 'python benchmark.py' first.")
            return
        
        print(f"[INFO] Using results file: {results_file}\n")
    else:
        results_file = args.results
    
    # Run evaluation
    metrics = run_evaluation(results_file, save_failures=not args.no_failures)
    
    if metrics:
        print("[SUCCESS] Evaluation complete!")
    else:
        print("[ERROR] Evaluation failed.")

if __name__ == "__main__":
    main()
