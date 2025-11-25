import json
import os
import sqlite3
import pandas as pd
import csv
from tqdm import tqdm
from pathlib import Path
from datetime import datetime

# Import enhanced execution evaluator
from utils.execution_evaluator import (
    execute_sql_to_dataframe,
    compare_dataframes,
    evaluate_sql_pair,
    has_order_by
)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
GOLD_DIR = PROJECT_ROOT / "data/spider2_lite/evaluation_suite/gold/sql"
GOLD_RESULT_DIR = PROJECT_ROOT / "data/spider2_lite/evaluation_suite/gold/exec_result"
METADATA_PATH = PROJECT_ROOT / "data/spider2_lite/evaluation_suite/gold/spider2lite_eval.jsonl"
DB_DIR = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite"

def execute_sql(db_path, sql):
    """
    DEPRECATED: Use execute_sql_to_dataframe instead.
    Kept for backward compatibility with CSV comparison.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        return set(results)
    except Exception as e:
        return f"Error: {e}"

def load_metadata():
    """Loads metadata from spider2lite_eval.jsonl."""
    metadata = {}
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            for line in f:
                item = json.loads(line)
                metadata[item['instance_id']] = item
    return metadata

def normalize_val(val):
    """Normalize value for comparison."""
    if val is None:
        return "none"
    try:
        # Try converting to float for numeric comparison
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return f"{f_val:.4f}" # Round to 4 decimals
    except (ValueError, TypeError):
        return str(val).strip().lower()

def normalize_set(s):
    """Normalize a set of tuples."""
    norm = set()
    for row in s:
        if not isinstance(row, (list, tuple)):
            row = (row,)
        norm_row = tuple(normalize_val(x) for x in row)
        norm.add(norm_row)
    return norm

def compare_with_csv(pred_result, instance_id, metadata_item):
    """
    Compares predicted result with gold CSVs.
    Returns True if any match is found.
    """
    condition_cols = metadata_item.get('condition_cols', [])
    
    # If pred_result is an error, it's wrong
    if isinstance(pred_result, str) and pred_result.startswith("Error"):
        return False
        
    suffixes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
    
    # If no condition cols, maybe just check 'a' or no suffix?
    # But usually condition_cols is present if there are CSVs.
    # If condition_cols is empty but CSV exists, we assume all cols.
    
    # Check for plain CSV first
    plain_csv = GOLD_RESULT_DIR / f"{instance_id}.csv"
    if plain_csv.exists():
        csv_paths = [plain_csv]
        target_cols_list = [[]] # All cols
    else:
        csv_paths = []
        target_cols_list = []
        for idx, suffix in enumerate(suffixes):
            csv_path = GOLD_RESULT_DIR / f"{instance_id}_{suffix}.csv"
            if csv_path.exists():
                csv_paths.append(csv_path)
                if idx < len(condition_cols):
                    target_cols_list.append(condition_cols[idx])
                else:
                    target_cols_list.append([]) # Default to all?
    
    if not csv_paths:
        return False
        
    for i, csv_path in enumerate(csv_paths):
        target_cols = target_cols_list[i] if i < len(target_cols_list) else []
        
        try:
            # Read CSV
            gold_df = pd.read_csv(csv_path)
            
            if not target_cols:
                # Compare all columns
                gold_set = set(tuple(x) for x in gold_df.to_records(index=False))
            else:
                # Select specific columns by index
                gold_subset = gold_df.iloc[:, target_cols]
                gold_set = set(tuple(x) for x in gold_subset.to_records(index=False))
            
            norm_pred = normalize_set(pred_result)
            norm_gold = normalize_set(gold_set)
            
            if norm_pred == norm_gold:
                return True
                
        except Exception as e:
            print(f"Error comparing with CSV {csv_path}: {e}")
            continue
            
    return False

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

    # Load Metadata
    metadata = load_metadata()

    # Deduplicate results, keeping the latest one for each instance_id
    latest_results = {}
    for item in results:
        latest_results[item['instance_id']] = item
    results = list(latest_results.values())

    total = 0
    syntax_error_count = 0
    execution_error_count = 0
    empty_sql_count = 0
    
    # Statistics
    total = 0
    correct = 0
    failed = 0
    by_complexity = {
        "EASY": {"total": 0, "correct": 0},
        "MEDIUM": {"total": 0, "correct": 0},
        "HARD": {"total": 0, "correct": 0}
    }
    by_agent = {
        "single": {"total": 0, "correct": 0},
        "multi": {"total": 0, "correct": 0}
    }
    
    # Details list for failure analysis
    failure_details = []
    
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
            total += 1
            continue

        # Locate DB
        db_folder = DB_DIR / db_id
        if not db_folder.exists():
            print(f"DB folder not found: {db_folder}")
            continue
             
        sqlite_files = [f for f in os.listdir(db_folder) if f.endswith('.sqlite')]
        if not sqlite_files:
            print(f"No sqlite file in {db_folder}")
            continue
        db_path = db_folder / sqlite_files[0]

        # Execute Predicted SQL
        pred_result = execute_sql(db_path, generated_sql)
        
        # Analyze errors (pre-comparison)
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

        # Determine Correctness using DataFrame comparison
        is_correct = False
        error_type = None
        error_msg = None
        comparison_details = {}
        
        # 1. Try Gold SQL File with DataFrame comparison
        gold_path = GOLD_DIR / f"{instance_id}.sql"
        if gold_path.exists():
            with open(gold_path, 'r') as f:
                gold_sql = f.read().strip()
            
            # Use enhanced evaluation
            is_correct, error_type, details = evaluate_sql_pair(
                str(db_path),
                generated_sql,
                gold_sql,
                tolerance=1e-4
            )
            
            comparison_details = details
            
            if not is_correct and error_type:
                error_msg = details.get('error_message', details.get('comparison_details', 'Unknown error'))
        
        # 2. Fallback to CSV Comparison (for backward compatibility)
        elif instance_id in metadata:
            pred_result = execute_sql(db_path, generated_sql)
            is_correct = compare_with_csv(pred_result, instance_id, metadata[instance_id])
            if not is_correct:
                error_type = "result_mismatch"
                error_msg = "CSV comparison failed"
        
        else:
            # No gold standard found
            print(f"Warning: No gold standard found for {instance_id}")
            continue

        if is_correct:
            correct += 1
        
        total += 1
        
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
        
        failure_details.append({
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
    accuracy = (correct / total) * 100 if total > 0 else 0
    
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
    print(f"Total Evaluated: {total}")
    print(f"Correct: {correct}")
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
        "total": total,
        "correct": correct,
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
