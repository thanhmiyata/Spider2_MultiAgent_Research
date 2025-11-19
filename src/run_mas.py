import json
import os
import sqlite3
import time
from tqdm import tqdm
from agents.multi_agent_flow import MultiAgentSystem
from agents.router import RouterAgent
from agents.single_agent import SingleAgent
from config import DEFAULT_MODEL

# Configuration
DATA_PATH = "data/spider2_lite/spider2-lite.jsonl"
DB_DIR = "data/spider2_lite/resource/databases/sqlite"
OUTPUT_FILE = "experiments/multi_agent/results.jsonl"
SLEEP_TIME = 5 # Seconds to wait between requests

def get_sqlite_schema(db_path):
    """Extracts schema from SQLite DB."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
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

def main():
    # Initialize components
    mas = MultiAgentSystem()
    router = RouterAgent()
    single = SingleAgent()
    
    # Load Data
    print(f"Loading data from {DATA_PATH}...")
    with open(DATA_PATH, 'r') as f:
        data = [json.loads(line) for line in f]
    
    # Filter for SQLite databases
    if not os.path.exists(DB_DIR):
        print(f"Error: DB Directory {DB_DIR} not found.")
        return

    available_dbs = set(os.listdir(DB_DIR))
    print(f"Available Databases: {available_dbs}")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Test specific instances that are known to be SQLite AND have Gold SQL
    target_ids = ["local002", "local003", "local004"]
    
    # Filter target_ids to only those with available DBs
    valid_target_ids = []
    for tid in target_ids:
        item = next((i for i in data if i['instance_id'] == tid), None)
        if item and item['db'] in available_dbs:
            valid_target_ids.append(tid)
        elif item:
            print(f"Skipping {tid} (DB '{item['db']}' not found)")
            
    test_data = [d for d in data if d['instance_id'] in valid_target_ids]
    
    print(f"Running Multi-Agent System ({DEFAULT_MODEL}) on {len(test_data)} valid items...")

    for item in tqdm(test_data):
        db_id = item['db']
        instance_id = item['instance_id']
        question = item['question']
        
        # Locate the SQLite file for this DB
        db_folder = os.path.join(DB_DIR, db_id)
        sqlite_files = [f for f in os.listdir(db_folder) if f.endswith('.sqlite')]
        if not sqlite_files:
            print(f"Warning: No .sqlite file found for {db_id}")
            continue
            
        db_path = os.path.join(db_folder, sqlite_files[0])
        schema = get_sqlite_schema(db_path)

        # Determine which agent to use based on query complexity
        complexity = router.route(question)
        
        try:
            if complexity == "EASY":
                # Use SingleAgent for simple queries
                generated_sql = single.generate(question, schema)
            else:
                # Use Multi-Agent System for MEDIUM/HARD
                generated_sql = mas.run(question, schema)
                
            print(f"[MAS] Final SQL: {generated_sql}")
            
            # Save result
            result = {
                "instance_id": instance_id,
                "question": question,
                "db_id": db_id,
                "generated_sql": generated_sql
            }
            
            with open(OUTPUT_FILE, 'a') as f:
                json.dump(result, f)
                f.write('\n')
                
        except Exception as e:
            print(f"Error processing {instance_id}: {e}")

        time.sleep(SLEEP_TIME)

    print(f"Finished. Results saved to {OUTPUT_FILE}")
    
    # Run Evaluation
    print("\n" + "="*30)
    print("Running Automated Evaluation...")
    print("="*30)
    import evaluate
    evaluate.main()

if __name__ == "__main__":
    main()
