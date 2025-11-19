import json
import os
import sqlite3
import pandas as pd
from tqdm import tqdm
import time
from agents.single_agent import SingleAgent
from utils.evaluation import Evaluator

# Configuration
DATA_PATH = "data/spider2_lite/spider2-lite.jsonl"
DB_DIR = "data/spider2_lite/resource/databases/sqlite"
OUTPUT_FILE = "experiments/baseline/results.jsonl"
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
    # Initialize Agent
    agent = SingleAgent()
    
    # Load Data
    print(f"Loading data from {DATA_PATH}...")
    with open(DATA_PATH, 'r') as f:
        data = [json.loads(line) for line in f]
    
    results = []
    
    # Filter for SQLite databases
    sqlite_dbs = set(os.listdir(DB_DIR))
    
    print("Running Baseline on SQLite subset (TEST MODE: 5 items)...")
    for item in tqdm(data[:5]):
        db_id = item['db']
        instance_id = item['instance_id']
        question = item['question']
        
        # Check if DB directory exists
        if db_id not in sqlite_dbs:
            continue
            
        # Look for .sqlite file inside the directory
        db_folder = os.path.join(DB_DIR, db_id)
        sqlite_files = [f for f in os.listdir(db_folder) if f.endswith('.sqlite')]
        
        if not sqlite_files:
            print(f"Warning: No .sqlite file found in {db_folder}")
            continue
            
        db_path = os.path.join(db_folder, sqlite_files[0])
        
        # Get Schema
        schema = get_sqlite_schema(db_path)
        
        # Generate SQL
        generated_sql = agent.generate(question, schema)
        time.sleep(SLEEP_TIME)
        
        # Store Result
        results.append({
            "instance_id": instance_id,
            "question": question,
            "db_id": db_id,
            "generated_sql": generated_sql
        })
        
        # Save intermediate results
        with open(OUTPUT_FILE, 'a') as f:
            json.dump(results[-1], f)
            f.write('\n')

    print(f"Finished. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
