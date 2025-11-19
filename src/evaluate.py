import json
import os
import sqlite3
import pandas as pd
from tqdm import tqdm

# Configuration
RESULTS_FILE = "experiments/multi_agent/results.jsonl"
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

def main():
    print("Running Evaluation...")
    
    if not os.path.exists(RESULTS_FILE):
        print(f"Results file not found: {RESULTS_FILE}")
        return

    with open(RESULTS_FILE, 'r') as f:
        results = [json.loads(line) for line in f]

    # Deduplicate results, keeping the latest one for each instance_id
    latest_results = {}
    for item in results:
        latest_results[item['instance_id']] = item
    results = list(latest_results.values())

    correct_count = 0
    total_count = 0
    
    details = []

    for item in tqdm(results):
        instance_id = item['instance_id']
        db_id = item['db_id']
        generated_sql = item['generated_sql']
        
        # Clean generated SQL
        generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()

        # Load Gold SQL
        gold_path = os.path.join(GOLD_DIR, f"{instance_id}.sql")
        if not os.path.exists(gold_path):
            print(f"Gold SQL not found for {instance_id}")
            continue
            
        with open(gold_path, 'r') as f:
            gold_sql = f.read().strip()

        # Locate DB
        db_folder = os.path.join(DB_DIR, db_id)
        if not os.path.exists(db_folder):
             # print(f"DB folder not found for {db_id}, skipping...")
             continue
             
        sqlite_files = [f for f in os.listdir(db_folder) if f.endswith('.sqlite')]
        if not sqlite_files:
            # print(f"DB file not found in {db_folder}, skipping...")
            continue
        db_path = os.path.join(db_folder, sqlite_files[0])

        # Execute
        pred_result = execute_sql(db_path, generated_sql)
        gold_result = execute_sql(db_path, gold_sql)

        # Compare
        is_correct = (pred_result == gold_result)
        if is_correct:
            correct_count += 1
        
        total_count += 1
        
        details.append({
            "instance_id": instance_id,
            "is_correct": is_correct,
            "error": pred_result if isinstance(pred_result, str) and pred_result.startswith("Error") else None
        })

    accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0
    print(f"\nEvaluation Complete.")
    print(f"Total Evaluated: {total_count}")
    print(f"Correct: {correct_count}")
    print(f"Accuracy: {accuracy:.2f}%")
    
    # Save detailed report
    pd.DataFrame(details).to_csv("experiments/multi_agent/evaluation_report.csv", index=False)
    print("Detailed report saved to experiments/multi_agent/evaluation_report.csv")

if __name__ == "__main__":
    main()
