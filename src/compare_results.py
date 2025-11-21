"""
Compare Baseline vs Multi-Agent vs Adaptive results
"""

import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

def load_results(results_file):
    """Load results from JSONL file."""
    if not os.path.exists(results_file):
        return None
    
    results = {}
    with open(results_file, 'r') as f:
        for line in f:
            item = json.loads(line)
            results[item['instance_id']] = item
    
    return results

def compare_results(baseline_file, multi_agent_file, adaptive_file=None, output_dir="experiments/comparison"):
    """
    Compare results from different approaches.
    
    Args:
        baseline_file: Path to baseline results
        multi_agent_file: Path to multi-agent results
        adaptive_file: Path to adaptive results (optional)
        output_dir: Output directory for comparison report
    """
    print("Loading results...")
    
    baseline = load_results(baseline_file)
    multi_agent = load_results(multi_agent_file) if multi_agent_file else None
    adaptive = load_results(adaptive_file) if adaptive_file else None
    
    if not baseline:
        print(f"Error: Baseline file not found: {baseline_file}")
        return
    
    if not multi_agent and not adaptive:
        print(f"Error: No comparison targets found (neither multi-agent nor adaptive)")
        return
    
    # Get common instance IDs
    common_ids = set(baseline.keys()) & set(multi_agent.keys())
    if adaptive:
        common_ids = common_ids & set(adaptive.keys())
    
    print(f"Found {len(common_ids)} common instances")
    
    # Load evaluation results if available
    from evaluate import evaluate_results
    
    print("\nEvaluating Baseline...")
    baseline_summary = evaluate_results(baseline_file, output_dir)
    
    print("\nEvaluating Multi-Agent...")
    multi_agent_summary = evaluate_results(multi_agent_file, output_dir)
    
    if adaptive:
        print("\nEvaluating Adaptive...")
        adaptive_summary = evaluate_results(adaptive_file, output_dir)
    
    # Create comparison table
    comparison = {
        "Approach": ["Baseline (Single Agent)", "Multi-Agent", "Adaptive (Router)"],
        "Total": [
            baseline_summary["total"] if baseline_summary else 0,
            multi_agent_summary["total"] if multi_agent_summary else 0,
            adaptive_summary["total"] if adaptive else 0
        ],
        "Correct": [
            baseline_summary["correct"] if baseline_summary else 0,
            multi_agent_summary["correct"] if multi_agent_summary else 0,
            adaptive_summary["correct"] if adaptive else 0
        ],
        "Accuracy (%)": [
            baseline_summary["accuracy"] if baseline_summary else 0,
            multi_agent_summary["accuracy"] if multi_agent_summary else 0,
            adaptive_summary["accuracy"] if adaptive else 0
        ]
    }
    
    df = pd.DataFrame(comparison)
    
    # Save comparison
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    comparison_file = os.path.join(output_dir, f"comparison_{timestamp}.csv")
    df.to_csv(comparison_file, index=False)
    
    print(f"\n{'='*60}")
    print("Comparison Results")
    print(f"{'='*60}")
    print(df.to_string(index=False))
    print(f"\nComparison saved to: {comparison_file}")
    
    # Calculate improvements
    if baseline_summary and multi_agent_summary:
        improvement = multi_agent_summary["accuracy"] - baseline_summary["accuracy"]
        print(f"\nMulti-Agent vs Baseline: {improvement:+.2f}% improvement")
    
    if adaptive and baseline_summary and adaptive_summary:
        improvement = adaptive_summary["accuracy"] - baseline_summary["accuracy"]
        print(f"Adaptive vs Baseline: {improvement:+.2f}% improvement")
    
    if adaptive and multi_agent_summary and adaptive_summary:
        improvement = adaptive_summary["accuracy"] - multi_agent_summary["accuracy"]
        print(f"Adaptive vs Multi-Agent: {improvement:+.2f}% improvement")
    
    return df

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument("--baseline", type=str,
                       default="experiments/baseline/results.jsonl",
                       help="Path to baseline results")
    parser.add_argument("--multi-agent", type=str,
                       default="experiments/multi_agent/results.jsonl",
                       help="Path to multi-agent results")
    parser.add_argument("--adaptive", type=str, default=None,
                       help="Path to adaptive results (optional)")
    parser.add_argument("--output-dir", type=str,
                       default="experiments/comparison",
                       help="Output directory")
    
    args = parser.parse_args()
    
    compare_results(
        args.baseline,
        getattr(args, 'multi_agent'),
        args.adaptive,
        args.output_dir
    )

