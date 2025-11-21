"""
Full Pipeline Script - Chạy toàn bộ quy trình từ benchmark đến evaluation
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

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

