"""
Full Benchmark Script for Spider 2.0 Lite
Runs both Single Agent and Multi-Agent systems on the full dataset
"""

import json
import os
import sqlite3
import time
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
import random

from agents.multi_agent_flow import MultiAgentSystem
from agents.router import RouterAgent
from agents.single_agent import SingleAgent
from config import DEFAULT_MODEL
from utils.dataset_filter import filter_data_by_gold_sql

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
DATA_PATH = PROJECT_ROOT / "data/spider2_lite/spider2-lite.jsonl"
DB_DIR = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite"
OUTPUT_DIR = PROJECT_ROOT / "experiments/benchmark"
SLEEP_TIME = 2  # Seconds between requests
MAX_ITEMS = None  # Set to None for full dataset, or a number for testing

def get_sqlite_schema(db_path):
    """Extracts schema from SQLite DB in a structured format."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        schema_parts = []
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Format: CREATE TABLE table_name (col1 TYPE, col2 TYPE, ...)
            col_defs = []
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                col_defs.append(f"`{col_name}` {col_type}")
            
            schema_parts.append(f"CREATE TABLE `{table_name}` (\n  {', '.join(col_defs)}\n);")
        
        conn.close()
        return "\n\n".join(schema_parts)
    except Exception as e:
        return f"Error reading schema: {e}"

def get_simple_schema(db_path):
    """Extracts schema in simple format (table: columns)."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
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

def get_optimized_schema(db_path, max_tables=15, max_columns_per_table=20):
    """
    Extracts optimized schema with limits to reduce API latency.
    Tradeoff: Slightly reduced accuracy for much faster response time.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        # Limit number of tables
        tables = tables[:max_tables]
        
        schema_str = ""
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            # Limit columns per table
            columns = columns[:max_columns_per_table]
            col_names = [col[1] for col in columns]
            schema_str += f"Table: {table_name}\nColumns: {', '.join(col_names)}\n\n"
        
        conn.close()
        return schema_str
    except Exception as e:
        return f"Error reading schema: {e}"

def run_benchmark(mode="adaptive", max_items=None, db_id=None, random_n=None, auto_select_db=False, run_eval=True, filter_gold_sql=True):
    """
    Run benchmark in specified mode.
    
    Args:
        mode: "single", "multi", or "adaptive"
        max_items: Maximum number of items to process (None for all)
        db_id: Filter by specific database ID
        random_n: Randomly sample N items (used with db_id)
        auto_select_db: If True, automatically pick a DB with > 5 questions and sample N
        run_eval: If True, run evaluation after benchmark
        filter_gold_sql: If True, only include instances with gold SQL files (default: True)
    """
    # Initialize components
    mas = MultiAgentSystem()
    router = RouterAgent()
    single = SingleAgent()
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load Data
    print(f"Loading data from {DATA_PATH}...")
    with open(str(DATA_PATH), 'r') as f:
        data = [json.loads(line) for line in f]
    
    # Filter by gold SQL availability
    if filter_gold_sql:
        print("Filtering for instances with gold SQL files...")
        data = filter_data_by_gold_sql(data)
        if not data:
            print("Error: No instances with gold SQL found. Exiting.")
            return
    
    # Filter for SQLite databases
    if not DB_DIR.exists():
        print(f"Error: DB Directory {DB_DIR} not found.")
        return
    
    available_dbs = set(os.listdir(str(DB_DIR)))
    print(f"Found {len(available_dbs)} available databases")
    
    # Filter data to only SQLite databases
    sqlite_data = [d for d in data if d['db'] in available_dbs]
    
    # Auto Select DB Logic
    if auto_select_db:
        print("Auto-selecting database...")
        from collections import Counter
        db_counts = Counter(d['db'] for d in sqlite_data)
        
        if not db_counts:
            print("No SQLite data found.")
            return

        # Try to find DB > 5
        valid_dbs = [db for db, count in db_counts.items() if count > 5]
        
        if valid_dbs:
            selected_db = random.choice(valid_dbs)
            print(f"Selected Database ( > 10 questions): {selected_db} (Total: {db_counts[selected_db]})")
        else:
            # Fallback to largest
            selected_db = db_counts.most_common(1)[0][0]
            print(f"Warning: No DB with > 10 questions found. Falling back to largest available: {selected_db} (Total: {db_counts[selected_db]})")
        
        # Filter for this DB
        sqlite_data = [d for d in sqlite_data if d['db'] == selected_db]
        
        # Sample 5 or take all
        if len(sqlite_data) > 1:
            sqlite_data = random.sample(sqlite_data, 1)
            print(f"Randomly sampled 1 questions from {selected_db}")
        else:
            print(f"Database has only {len(sqlite_data)} questions. Using all.")
        
    # Apply DB filter (Manual)
    elif db_id:
        sqlite_data = [d for d in sqlite_data if d['db'] == db_id]
        print(f"Filtered for DB '{db_id}': {len(sqlite_data)} items found")
        
        if not sqlite_data:
            print(f"No items found for DB '{db_id}'")
            return

    # Apply Random Sampling (Manual)
    if random_n and len(sqlite_data) > 0:
        if random_n > len(sqlite_data):
            print(f"Warning: Requested {random_n} items but only {len(sqlite_data)} available. Using all.")
        else:
            sqlite_data = random.sample(sqlite_data, random_n)
            print(f"Randomly sampled {len(sqlite_data)} items")
    
    # Apply Max Items (if not random, just take first N)
    elif max_items and not auto_select_db:
        sqlite_data = sqlite_data[:max_items]
        print(f"Running benchmark on {len(sqlite_data)} items (limited)")
    else:
        print(f"Running benchmark on {len(sqlite_data)} items")
    
    # Output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"{mode}_results_{timestamp}.jsonl"
    
    results = []
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "single_agent": 0,
        "multi_agent": 0,
        "routing": {"EASY": 0, "MEDIUM": 0, "HARD": 0}
    }
    
    print(f"\n{'='*60}")
    print(f"Running {mode.upper()} mode benchmark")
    print(f"{'='*60}\n")
    
    for idx, item in enumerate(tqdm(sqlite_data, desc="Processing")):
        db_id = item['db']
        instance_id = item['instance_id']
        question = item['question']
        
        stats["total"] += 1
        
        # Locate the SQLite file
        db_folder = DB_DIR / db_id
        if not db_folder.exists():
            continue
            
        sqlite_files = [f for f in os.listdir(str(db_folder)) if f.endswith('.sqlite')]
        if not sqlite_files:
            continue
        
        db_path = db_folder / sqlite_files[0]
        
        # Get schema (use optimized format for faster API calls)
        # Use get_simple_schema() for full accuracy or get_optimized_schema() for speed
        schema = get_optimized_schema(db_path, max_tables=15, max_columns_per_table=20)
        
        start_time = time.time()
        generated_sql = ""
        complexity = None
        agent_used = None
        error = None
        
        try:
            if mode == "single":
                # Always use single agent
                print(f"  [Single] Processing: {question[:60]}...")
                generated_sql = single.generate(question, schema)
                agent_used = "single"
                stats["single_agent"] += 1
                
            elif mode == "multi":
                # Always use multi-agent
                print(f"  [Multi] Processing: {question[:60]}...")
                generated_sql = mas.run(question, schema, verbose=False)
                agent_used = "multi"
                stats["multi_agent"] += 1
                
            elif mode == "adaptive":
                # Use router to decide
                print(f"  [Router] Analyzing: {question[:60]}...")
                complexity = router.route(question)
                print(f"  [Router] Classified as: {complexity}")
                stats["routing"][complexity] = stats["routing"].get(complexity, 0) + 1
                
                if complexity == "EASY":
                    print(f"  [Single] Processing EASY question...")
                    generated_sql = single.generate(question, schema)
                    agent_used = "single"
                    stats["single_agent"] += 1
                else:
                    print(f"  [Multi] Processing {complexity} question...")
                    generated_sql = mas.run(question, schema, verbose=True)  # Enable verbose for timing
                    agent_used = "multi"
                    stats["multi_agent"] += 1
            
            latency = time.time() - start_time
            
            if generated_sql:
                stats["success"] += 1
            else:
                stats["failed"] += 1
                error = "Empty SQL generated"
            
        except Exception as e:
            stats["failed"] += 1
            error = str(e)
            latency = time.time() - start_time
            print(f"  [ERROR] {error}")
        
        # Store result
        result = {
            "instance_id": instance_id,
            "question": question,
            "db_id": db_id,
            "generated_sql": generated_sql,
            "complexity": complexity,
            "agent_used": agent_used,
            "latency": round(latency, 2),
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        results.append(result)
        
        # Save intermediate results
        with open(str(output_file), 'a') as f:
            json.dump(result, f)
            f.write('\n')
        
        # Progress update every 10 items
        if (idx + 1) % 10 == 0:
            print(f"\nProgress: {idx + 1}/{len(sqlite_data)}")
            print(f"  Success: {stats['success']}, Failed: {stats['failed']}")
            if mode == "adaptive":
                print(f"  Routing: {stats['routing']}")
            print(f"  Single: {stats['single_agent']}, Multi: {stats['multi_agent']}")
        
        # Rate limiting
        if idx < len(sqlite_data) - 1:  # Don't sleep after last item
            time.sleep(SLEEP_TIME)
    
    # Final statistics
    print(f"\n{'='*60}")
    print("Benchmark Complete!")
    print(f"{'='*60}")
    print(f"Total processed: {stats['total']}")
    if stats['total'] > 0:
        print(f"Success: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
        print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    else:
        print("No items processed.")

    if mode == "adaptive":
        print(f"\nRouting Distribution:")
        for level, count in stats['routing'].items():
            print(f"  {level}: {count}")
    print(f"\nAgent Usage:")
    print(f"  Single Agent: {stats['single_agent']}")
    print(f"  Multi-Agent: {stats['multi_agent']}")
    print(f"\nResults saved to: {output_file}")
    
    # Save summary
    summary_file = OUTPUT_DIR / f"{mode}_summary_{timestamp}.json"
    with open(str(summary_file), 'w') as f:
        json.dump({
            "mode": mode,
            "stats": stats,
            "output_file": str(output_file),
            "timestamp": timestamp
        }, f, indent=2)
    
    # Automatic Evaluation
    if run_eval:
        print(f"\n{'='*60}")
        print("Running Automatic Evaluation")
        print(f"{'='*60}\n")
        from evaluate import evaluate_results
        evaluate_results(str(output_file))

    return str(output_file)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run benchmark on Spider 2.0 Lite")
    parser.add_argument("--mode", choices=["single", "multi", "adaptive"], 
                       default="adaptive", help="Benchmark mode")
    parser.add_argument("--max-items", type=int, default=None,
                       help="Maximum number of items to process (for testing)")
    parser.add_argument("--db-id", type=str, default=None,
                       help="Filter by specific database ID")
    parser.add_argument("--random", type=int, default=None,
                       help="Randomly sample N items (useful with --db-id)")
    parser.add_argument("--auto-select-db", action="store_true",
                       help="Automatically select a DB with > 10 questions and run 5 random questions")
    parser.add_argument("--no-eval", action="store_true",
                       help="Skip automatic evaluation")
    
    args = parser.parse_args()
    
    run_benchmark(mode=args.mode, max_items=args.max_items, db_id=args.db_id, 
                 random_n=args.random, auto_select_db=args.auto_select_db, 
                 run_eval=not args.no_eval)

