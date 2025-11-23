"""
Full Pipeline Script - Chạy toàn bộ quy trình từ benchmark đến evaluation
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

import sqlite3
import json
from agents.multi_agent_flow import MultiAgentSystem
from config import DEFAULT_MODEL

def verify_instance(instance_id):
    """
    Run pipeline for a specific instance, execute SQL, and compare with Gold.
    """
    print("\n" + "="*60)
    print(f"Step 0: Verifying Instance {instance_id}")
    print("="*60)
    
    # Load instance data
    data_path = "data/spider2_lite/spider2-lite.jsonl"
    target_instance = None
    
    try:
        with open(data_path, 'r') as f:
            for line in f:
                item = json.loads(line)
                if item['instance_id'] == instance_id:
                    target_instance = item
                    break
    except FileNotFoundError:
        print(f"Error: Data file not found at {data_path}")
        return

    if not target_instance:
        print(f"Error: Instance {instance_id} not found!")
        return

    print(f"Question: {target_instance['question']}")
    db_id = target_instance['db']
    print(f"Database: {db_id}")
    
    db_path = f"data/spider2_lite/resource/databases/sqlite/{db_id}/{db_id}.sqlite"
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    # Run Pipeline
    print("\n>>> Running Multi-Agent Pipeline...")
    
    # Extract schema
    from benchmark import get_optimized_schema
    schema_str = get_optimized_schema(db_path)
    
    mas = MultiAgentSystem()
    generated_sql = mas.run(target_instance['question'], schema_str, db_path=db_path)
    
    print("\n" + "-"*40)
    print("GENERATED SQL:")
    print("-"*40)
    print(generated_sql)
    
    # Get Gold SQL
    gold_path = f"data/spider2_lite/evaluation_suite/gold/sql/{instance_id}.sql"
    gold_sql = ""
    if os.path.exists(gold_path):
        with open(gold_path, 'r') as f:
            gold_sql = f.read()
        print("\n" + "-"*40)
        print("GOLD SQL:")
        print("-"*40)
        print(gold_sql)
    else:
        print(f"\nWarning: Gold SQL not found at {gold_path}")

    # Execute and Compare
    print("\n>>> Executing Queries...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute Generated
        gen_results = []
        gen_error = None
        try:
            cursor.execute(generated_sql)
            gen_results = cursor.fetchall()
        except Exception as e:
            gen_error = str(e)
            
        # Execute Gold
        gold_results = []
        gold_error = None
        if gold_sql:
            try:
                cursor.execute(gold_sql)
                gold_results = cursor.fetchall()
            except Exception as e:
                gold_error = str(e)
        
        conn.close()
        
        print("\n" + "="*60)
        print("EXECUTION RESULTS")
        print("="*60)
        
        if gen_error:
            print(f"[GENERATED] Error: {gen_error}")
        else:
            print(f"[GENERATED] Success. Rows returned: {len(gen_results)}")
            if len(gen_results) > 0:
                print(f"Sample (first 3 rows): {gen_results[:3]}")
                
        if gold_error:
            print(f"[GOLD] Error: {gold_error}")
        elif gold_sql:
            print(f"[GOLD] Success. Rows returned: {len(gold_results)}")
            if len(gold_results) > 0:
                print(f"Sample (first 3 rows): {gold_results[:3]}")
        
        # Comparison
        if not gen_error and not gold_error and gold_sql:
            if set(gen_results) == set(gold_results):
                print("\n>>> RESULT: MATCH ✅")
            else:
                print("\n>>> RESULT: MISMATCH ❌")
                print(f"Generated count: {len(gen_results)}, Gold count: {len(gold_results)}")
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

def run_baseline(max_items=None):
    """Chạy baseline single agent."""
    print("\n" + "="*60)
    print("Step 1: Running Baseline (Single Agent)")
    print("="*60)
    
    from main import main as run_main
    # Note: Cần modify main.py để support max_items parameter
    run_main()

def run_benchmark(mode, max_items=None):
    """Chạy benchmark."""
    print("\n" + "="*60)
    print(f"Step 2: Running {mode.upper()} Benchmark")
    print("="*60)
    
    from benchmark import run_benchmark as run_bench
    return run_bench(mode=mode, max_items=max_items)

def run_evaluation(results_file, output_dir=None):
    """Chạy evaluation."""
    print("\n" + "="*60)
    print("Step 3: Running Evaluation")
    print("="*60)
    
    from evaluate import evaluate_results
    return evaluate_results(results_file, output_dir)

def run_comparison(baseline_file, multi_agent_file, adaptive_file=None):
    """Chạy comparison."""
    print("\n" + "="*60)
    print("Step 4: Running Comparison")
    print("="*60)
    
    from compare_results import compare_results
    return compare_results(baseline_file, multi_agent_file, adaptive_file)

def main():
    parser = argparse.ArgumentParser(
        description="Run full pipeline: baseline -> benchmark -> evaluation -> comparison"
    )
    parser.add_argument("--verify-instance", type=str,
                       help="Run verification for a specific instance ID (bypasses full pipeline)")
    parser.add_argument("--skip-baseline", action="store_true",
                       help="Skip baseline run")
    parser.add_argument("--modes", nargs="+", 
                       choices=["single", "multi", "adaptive"],
                       default=["adaptive"],
                       help="Benchmark modes to run")
    parser.add_argument("--max-items", type=int, default=None,
                       help="Maximum items to process (for testing)")
    parser.add_argument("--skip-evaluation", action="store_true",
                       help="Skip evaluation step")
    parser.add_argument("--skip-comparison", action="store_true",
                       help="Skip comparison step")
    
    args = parser.parse_args()
    
    # Handle verification mode
    if args.verify_instance:
        verify_instance(args.verify_instance)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = f"experiments/pipeline_{timestamp}"
    os.makedirs(output_base, exist_ok=True)
    
    results_files = {}
    
    # Step 1: Baseline
    if not args.skip_baseline:
        run_baseline(args.max_items)
        baseline_file = "experiments/baseline/results.jsonl"
        if os.path.exists(baseline_file):
            results_files["baseline"] = baseline_file
    else:
        baseline_file = "experiments/baseline/results.jsonl"
        if os.path.exists(baseline_file):
            results_files["baseline"] = baseline_file
    
    # Step 2: Benchmark
    for mode in args.modes:
        results_file = run_benchmark(mode, args.max_items)
        if results_file:
            results_files[mode] = results_file
    
    # Step 3: Evaluation
    if not args.skip_evaluation:
        for name, results_file in results_files.items():
            eval_output = os.path.join(output_base, f"eval_{name}")
            run_evaluation(results_file, eval_output)
    
    # Step 4: Comparison
    if not args.skip_comparison:
        baseline = results_files.get("baseline")
        multi = results_files.get("multi")
        adaptive = results_files.get("adaptive")
        
        if baseline and (multi or adaptive):
            comparison_output = os.path.join(output_base, "comparison")
            run_comparison(baseline, multi, adaptive)
    
    print("\n" + "="*60)
    print("Pipeline Complete!")
    print("="*60)
    print(f"Results saved to: {output_base}")
    print("\nGenerated files:")
    for name, file in results_files.items():
        print(f"  {name}: {file}")

if __name__ == "__main__":
    main()

