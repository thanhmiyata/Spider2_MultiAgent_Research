import json
import os
import sqlite3
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from datetime import datetime

# Configuration
GOLD_DIR = "data/spider2_lite/evaluation_suite/gold/sql"
DB_DIR = "data/spider2_lite/resource/databases/sqlite"

def execute_sql(db_path, sql):
    """Executes SQL and returns result as a set of tuples for comparison."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        return set(results)
    except Exception as e:
        return f"Error: {e}"

def evaluate_results(results_file, output_dir=None):
    """
    Evaluate results from a benchmark run.
    
    Args:
        results_file: Path to results JSONL file
        output_dir: Directory to save evaluation report (default: same as results file)
    """
    print(f"Running Evaluation on {results_file}...")
    
    if not os.path.exists(results_file):
        print(f"Results file not found: {results_file}")
        return None

    with open(results_file, 'r') as f:
        results = [json.loads(line) for line in f]

    # Deduplicate results, keeping the latest one for each instance_id
    latest_results = {}
    for item in results:
        latest_results[item['instance_id']] = item
    results = list(latest_results.values())

    correct_count = 0
    total_count = 0
    syntax_error_count = 0
    execution_error_count = 0
    empty_sql_count = 0
    
    details = []
    
    # Group by complexity and agent type
    by_complexity = {"EASY": {"total": 0, "correct": 0}, 
                     "MEDIUM": {"total": 0, "correct": 0}, 
                     "HARD": {"total": 0, "correct": 0}}
    by_agent = {"single": {"total": 0, "correct": 0}, 
                "multi": {"total": 0, "correct": 0}}

    for item in tqdm(results, desc="Evaluating"):
        instance_id = item['instance_id']
        db_id = item.get('db_id', '')
        generated_sql = item.get('generated_sql', '')
        complexity = item.get('complexity')
        agent_used = item.get('agent_used')
        
        # Clean generated SQL
        generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
        
        # Check for empty SQL
        if not generated_sql:
            empty_sql_count += 1
            details.append({
                "instance_id": instance_id,
                "is_correct": False,
                "error_type": "empty_sql",
                "error": "Empty SQL generated"
            })
            total_count += 1
            continue

        # Load Gold SQL
        gold_path = os.path.join(GOLD_DIR, f"{instance_id}.sql")
        if not os.path.exists(gold_path):
            continue
            
        with open(gold_path, 'r') as f:
            gold_sql = f.read().strip()

        # Locate DB
        db_folder = os.path.join(DB_DIR, db_id)
        if not os.path.exists(db_folder):
            continue
             
        sqlite_files = [f for f in os.listdir(db_folder) if f.endswith('.sqlite')]
        if not sqlite_files:
            continue
        db_path = os.path.join(db_folder, sqlite_files[0])

        # Execute
        pred_result = execute_sql(db_path, generated_sql)
        gold_result = execute_sql(db_path, gold_sql)

        # Analyze errors
        error_type = None
        error_msg = None
        
        if isinstance(pred_result, str) and pred_result.startswith("Error"):
            if "syntax" in pred_result.lower() or "near" in pred_result.lower():
                syntax_error_count += 1
                error_type = "syntax_error"
            else:
                execution_error_count += 1
                error_type = "execution_error"
            error_msg = pred_result

        # Compare results
        # CRITICAL FIX: If pred_result is an error, it is ALWAYS incorrect, 
        # even if gold_result is also an error (which would mean a bad test case).
        if isinstance(pred_result, str) and pred_result.startswith("Error"):
            is_correct = False
        else:
            is_correct = (pred_result == gold_result)
            
        if is_correct:
            correct_count += 1
        
        total_count += 1
        
        # Update statistics by complexity
        if complexity and complexity in by_complexity:
            by_complexity[complexity]["total"] += 1
            if is_correct:
                by_complexity[complexity]["correct"] += 1
        
        # Update statistics by agent
        if agent_used and agent_used in by_agent:
            by_agent[agent_used]["total"] += 1
            if is_correct:
                by_agent[agent_used]["correct"] += 1
        
        details.append({
            "instance_id": instance_id,
            "db_id": db_id,
            "is_correct": is_correct,
            "complexity": complexity,
            "agent_used": agent_used,
            "error_type": error_type,
            "error": error_msg,
            "latency": item.get('latency')
        })

    # Calculate metrics
    accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0
    
    # Calculate accuracy by complexity
    complexity_acc = {}
    for level, stats in by_complexity.items():
        if stats["total"] > 0:
            complexity_acc[level] = (stats["correct"] / stats["total"]) * 100
        else:
            complexity_acc[level] = 0
    
    # Calculate accuracy by agent
    agent_acc = {}
    for agent, stats in by_agent.items():
        if stats["total"] > 0:
            agent_acc[agent] = (stats["correct"] / stats["total"]) * 100
        else:
            agent_acc[agent] = 0
    
    # Print results
    print(f"\n{'='*60}")
    print("Evaluation Complete")
    print(f"{'='*60}")
    print(f"Total Evaluated: {total_count}")
    print(f"Correct: {correct_count}")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"\nError Breakdown:")
    print(f"  Empty SQL: {empty_sql_count}")
    print(f"  Syntax Errors: {syntax_error_count}")
    print(f"  Execution Errors: {execution_error_count}")
    
    if any(complexity_acc.values()):
        print(f"\nAccuracy by Complexity:")
        for level, acc in complexity_acc.items():
            count = by_complexity[level]["total"]
            print(f"  {level}: {acc:.2f}% ({by_complexity[level]['correct']}/{count})")
    
    if any(agent_acc.values()):
        print(f"\nAccuracy by Agent:")
        for agent, acc in agent_acc.items():
            count = by_agent[agent]["total"]
            print(f"  {agent}: {acc:.2f}% ({by_agent[agent]['correct']}/{count})")
    
    # Save detailed report
    if output_dir is None:
        output_dir = os.path.dirname(results_file)
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_dir, f"evaluation_report_{timestamp}.csv")
    pd.DataFrame(details).to_csv(report_file, index=False)
    print(f"\nDetailed report saved to: {report_file}")
    
    # Save summary JSON
    summary = {
        "total": total_count,
        "correct": correct_count,
        "accuracy": accuracy,
        "errors": {
            "empty_sql": empty_sql_count,
            "syntax_errors": syntax_error_count,
            "execution_errors": execution_error_count
        },
        "by_complexity": complexity_acc,
        "by_agent": agent_acc,
        "timestamp": timestamp
    }
    
    summary_file = os.path.join(output_dir, f"evaluation_summary_{timestamp}.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to: {summary_file}")
    
    return summary

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate benchmark results")
    parser.add_argument("--results", type=str, 
                       default="experiments/multi_agent/results.jsonl",
                       help="Path to results JSONL file")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory for reports")
    
    args = parser.parse_args()
    
    evaluate_results(args.results, args.output_dir)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
