"""
Dataset filtering utilities for Spider 2.0 Lite benchmark.
"""
import os
from pathlib import Path
from typing import List, Set

PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLD_SQL_DIR = PROJECT_ROOT / "data/spider2_lite/evaluation_suite/gold/sql"

def get_instances_with_gold_sql() -> Set[str]:
    """
    Scan the gold SQL directory and return a set of instance IDs that have gold SQL files.
    
    Returns:
        Set of instance IDs (e.g., {'bq001', 'bq002', ...})
    """
    if not GOLD_SQL_DIR.exists():
        print(f"Warning: Gold SQL directory not found: {GOLD_SQL_DIR}")
        return set()
    
    instance_ids = set()
    for sql_file in GOLD_SQL_DIR.glob("*.sql"):
        # Extract instance_id from filename (e.g., "bq001.sql" -> "bq001")
        instance_id = sql_file.stem
        instance_ids.add(instance_id)
    
    print(f"Found {len(instance_ids)} instances with gold SQL files")
    return instance_ids

def filter_data_by_gold_sql(data: List[dict]) -> List[dict]:
    """
    Filter dataset to only include instances that have gold SQL files.
    
    Args:
        data: List of dataset items (each with 'instance_id' key)
    
    Returns:
        Filtered list containing only items with gold SQL
    """
    gold_instances = get_instances_with_gold_sql()
    
    if not gold_instances:
        print("Warning: No gold SQL files found. Returning empty list.")
        return []
    
    filtered = [item for item in data if item.get('instance_id') in gold_instances]
    print(f"Filtered {len(data)} items -> {len(filtered)} items with gold SQL")
    
    return filtered
