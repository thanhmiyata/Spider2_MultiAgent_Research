"""
Logging and tracking utilities for token usage and latency
"""

import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

class MetricsTracker:
    """Tracks metrics for agent operations."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self.metrics = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "by_agent": {},
            "errors": []
        }
        self.start_times = {}
    
    def start_timer(self, operation_id: str):
        """Start timing an operation."""
        self.start_times[operation_id] = time.time()
    
    def end_timer(self, operation_id: str) -> float:
        """End timing and return duration."""
        if operation_id not in self.start_times:
            return 0.0
        
        duration = time.time() - self.start_times[operation_id]
        del self.start_times[operation_id]
        return duration
    
    def log_call(self, agent_name: str, latency: float, tokens: int = 0, 
                 success: bool = True, error: Optional[str] = None):
        """Log an agent call."""
        self.metrics["total_calls"] += 1
        self.metrics["total_latency"] += latency
        self.metrics["total_tokens"] += tokens
        
        if agent_name not in self.metrics["by_agent"]:
            self.metrics["by_agent"][agent_name] = {
                "calls": 0,
                "tokens": 0,
                "latency": 0.0,
                "success": 0,
                "errors": 0
            }
        
        agent_metrics = self.metrics["by_agent"][agent_name]
        agent_metrics["calls"] += 1
        agent_metrics["tokens"] += tokens
        agent_metrics["latency"] += latency
        
        if success:
            agent_metrics["success"] += 1
        else:
            agent_metrics["errors"] += 1
            if error:
                self.metrics["errors"].append({
                    "agent": agent_name,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
    
    def get_summary(self) -> Dict:
        """Get summary of all metrics."""
        summary = {
            "total_calls": self.metrics["total_calls"],
            "total_tokens": self.metrics["total_tokens"],
            "total_latency": round(self.metrics["total_latency"], 2),
            "avg_latency": round(
                self.metrics["total_latency"] / self.metrics["total_calls"], 2
            ) if self.metrics["total_calls"] > 0 else 0,
            "by_agent": {}
        }
        
        for agent, metrics in self.metrics["by_agent"].items():
            summary["by_agent"][agent] = {
                "calls": metrics["calls"],
                "tokens": metrics["tokens"],
                "total_latency": round(metrics["latency"], 2),
                "avg_latency": round(
                    metrics["latency"] / metrics["calls"], 2
                ) if metrics["calls"] > 0 else 0,
                "success_rate": round(
                    metrics["success"] / metrics["calls"] * 100, 2
                ) if metrics["calls"] > 0 else 0,
                "errors": metrics["errors"]
            }
        
        summary["error_count"] = len(self.metrics["errors"])
        
        return summary
    
    def save(self, file_path: Optional[str] = None):
        """Save metrics to file."""
        file_path = file_path or self.log_file
        if not file_path:
            return
        
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "summary": self.get_summary(),
            "detailed_errors": self.metrics["errors"],
            "timestamp": datetime.now().isoformat()
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def print_summary(self):
        """Print metrics summary."""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("Metrics Summary")
        print("="*60)
        print(f"Total Calls: {summary['total_calls']}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print(f"Total Latency: {summary['total_latency']:.2f}s")
        print(f"Average Latency: {summary['avg_latency']:.2f}s")
        print(f"Errors: {summary['error_count']}")
        
        if summary['by_agent']:
            print("\nBy Agent:")
            for agent, metrics in summary['by_agent'].items():
                print(f"  {agent}:")
                print(f"    Calls: {metrics['calls']}")
                print(f"    Tokens: {metrics['tokens']:,}")
                print(f"    Avg Latency: {metrics['avg_latency']:.2f}s")
                print(f"    Success Rate: {metrics['success_rate']:.2f}%")
                if metrics['errors'] > 0:
                    print(f"    Errors: {metrics['errors']}")

# Global tracker instance
_global_tracker = None

def get_tracker(log_file: Optional[str] = None) -> MetricsTracker:
    """Get or create global metrics tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MetricsTracker(log_file)
    return _global_tracker

def reset_tracker():
    """Reset global tracker."""
    global _global_tracker
    _global_tracker = None

