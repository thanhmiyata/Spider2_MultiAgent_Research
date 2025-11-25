"""
Execution Evaluator Module

Provides robust SQL execution and result comparison functionality with:
- DataFrame-based comparison
- Automatic ordering handling
- Column name independence
- Floating point tolerance
"""

import sqlite3
import re
import pandas as pd
import numpy as np
from typing import Tuple, Union
from pathlib import Path


def remove_sql_comments_and_strings(sql: str) -> str:
    """
    Remove SQL comments and string literals to avoid false positives in pattern matching.
    
    Args:
        sql: SQL query string
        
    Returns:
        Cleaned SQL string
    """
    # Remove single-line comments (-- ...)
    sql = re.sub(r'--[^\n]*', '', sql)
    
    # Remove multi-line comments (/* ... */)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    
    # Remove string literals (both single and double quotes)
    # This is a simplified approach - a full SQL parser would be more accurate
    sql = re.sub(r"'[^']*'", "''", sql)
    sql = re.sub(r'"[^"]*"', '""', sql)
    
    return sql


def has_order_by(sql: str) -> bool:
    """
    Detect if SQL query contains ORDER BY clause.
    
    Args:
        sql: SQL query string
        
    Returns:
        True if ORDER BY is present, False otherwise
    """
    if not sql:
        return False
    
    # Clean SQL to avoid false positives from comments/strings
    sql_clean = remove_sql_comments_and_strings(sql)
    
    # Check for ORDER BY (case-insensitive, whole word)
    return bool(re.search(r'\bORDER\s+BY\b', sql_clean, re.IGNORECASE))


def execute_sql_to_dataframe(db_path: str, sql: str) -> Tuple[bool, Union[pd.DataFrame, str]]:
    """
    Execute SQL query and return result as pandas DataFrame.
    
    Args:
        db_path: Path to SQLite database file
        sql: SQL query to execute
        
    Returns:
        Tuple of (success: bool, result: DataFrame or error message)
        
    Examples:
        >>> success, df = execute_sql_to_dataframe('/path/to/db.sqlite', 'SELECT * FROM users')
        >>> if success:
        ...     print(df.head())
    """
    if not sql or len(sql.strip()) == 0:
        return False, "Empty SQL query"
    
    try:
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return True, df
        
    except sqlite3.Error as e:
        return False, f"SQLite Error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def normalize_dataframe(
    df: pd.DataFrame, 
    sort: bool = True, 
    decimal_places: int = 4
) -> pd.DataFrame:
    """
    Normalize DataFrame for comparison:
    - Round floating point numbers to specified decimal places
    - Sort rows by all columns (if sort=True)
    - Reset index
    
    Args:
        df: Input DataFrame
        sort: Whether to sort rows (default: True)
        decimal_places: Number of decimal places for rounding (default: 4)
        
    Returns:
        Normalized DataFrame
        
    Examples:
        >>> df = pd.DataFrame({'a': [3.333333, 1.666666], 'b': ['B', 'A']})
        >>> normalized = normalize_dataframe(df, sort=True, decimal_places=2)
        >>> # Result: sorted by columns, floats rounded to 2 decimals
    """
    if df.empty:
        return df
    
    df_copy = df.copy()
    
    # Round numeric columns
    for col in df_copy.columns:
        if df_copy[col].dtype in ['float64', 'float32']:
            df_copy[col] = df_copy[col].round(decimal_places)
    
    # Sort if needed
    if sort and len(df_copy) > 0:
        try:
            # Sort by all columns
            df_copy = df_copy.sort_values(
                by=list(df_copy.columns),
                na_position='last'
            ).reset_index(drop=True)
        except Exception as e:
            # If sorting fails (e.g., mixed types), just reset index
            print(f"[Warning] Could not sort DataFrame: {e}")
            df_copy = df_copy.reset_index(drop=True)
    else:
        df_copy = df_copy.reset_index(drop=True)
    
    return df_copy


def compare_dataframes(
    pred_df: pd.DataFrame, 
    gold_df: pd.DataFrame,
    tolerance: float = 1e-4,
    check_column_names: bool = False,
    auto_sort: bool = True
) -> Tuple[bool, str]:
    """
    Compare two DataFrames with robust handling of edge cases.
    
    Handles:
    - Different row ordering (auto-sorts by default)
    - Different column names (ignores by default)
    - Floating point precision (uses tolerance)
    - Mixed data types
    
    Args:
        pred_df: Predicted results DataFrame
        gold_df: Gold standard results DataFrame
        tolerance: Relative/absolute tolerance for floating point comparison (default: 1e-4)
        check_column_names: Whether to check column names match (default: False)
        auto_sort: Whether to auto-sort before comparison (default: True)
        
    Returns:
        Tuple of (is_match: bool, details: str)
        
    Examples:
        >>> pred = pd.DataFrame({'avg': [0.333333], 'cnt': [100]})
        >>> gold = pd.DataFrame({'average': [0.33], 'count': [100]})
        >>> is_match, details = compare_dataframes(pred, gold, tolerance=0.01)
        >>> # is_match = True (ignores column names, tolerates float diff)
    """
    # Check if both are empty
    if pred_df.empty and gold_df.empty:
        return True, "Both DataFrames are empty (match)"
    
    # Check if one is empty
    if pred_df.empty or gold_df.empty:
        return False, f"One DataFrame is empty (pred: {len(pred_df)} rows, gold: {len(gold_df)} rows)"
    
    # Check dimensions
    if pred_df.shape != gold_df.shape:
        return False, f"Shape mismatch: pred {pred_df.shape} vs gold {gold_df.shape}"
    
    # Check column names if requested
    if check_column_names:
        if list(pred_df.columns) != list(gold_df.columns):
            return False, f"Column names differ: pred {list(pred_df.columns)} vs gold {list(gold_df.columns)}"
    
    # Normalize both DataFrames
    pred_norm = normalize_dataframe(pred_df, sort=auto_sort, decimal_places=4)
    gold_norm = normalize_dataframe(gold_df, sort=auto_sort, decimal_places=4)
    
    # Compare values only (ignore column names by using .values)
    pred_values = pred_norm.values
    gold_values = gold_norm.values
    
    # Try numeric comparison with tolerance
    try:
        # Check if all values are numeric
        pred_numeric = pd.DataFrame(pred_values).apply(pd.to_numeric, errors='coerce')
        gold_numeric = pd.DataFrame(gold_values).apply(pd.to_numeric, errors='coerce')
        
        # If both are fully numeric, use np.allclose
        if not pred_numeric.isna().any().any() and not gold_numeric.isna().any().any():
            if np.allclose(pred_numeric.values, gold_numeric.values, 
                          rtol=tolerance, atol=tolerance, equal_nan=True):
                return True, "Match (numeric comparison with tolerance)"
            else:
                # Find differences
                diff_mask = ~np.isclose(pred_numeric.values, gold_numeric.values, 
                                       rtol=tolerance, atol=tolerance, equal_nan=True)
                diff_count = diff_mask.sum()
                
                # Get sample of differences
                diff_positions = np.argwhere(diff_mask)
                if len(diff_positions) > 0:
                    sample_pos = diff_positions[0]
                    row, col = sample_pos[0], sample_pos[1]
                    sample_diff = f"Example: row {row}, col {col}: pred={pred_values[row, col]}, gold={gold_values[row, col]}"
                else:
                    sample_diff = ""
                
                return False, f"Value mismatch: {diff_count} cells differ. {sample_diff}"
        
    except (ValueError, TypeError):
        pass  # Fall through to exact comparison
    
    # Fall back to exact comparison for mixed types
    try:
        # Convert to string for comparison to handle mixed types
        pred_str = pred_norm.astype(str).values
        gold_str = gold_norm.astype(str).values
        
        if np.array_equal(pred_str, gold_str):
            return True, "Match (exact string comparison)"
        else:
            # Find first difference
            diff_mask = pred_str != gold_str
            diff_positions = np.argwhere(diff_mask)
            
            if len(diff_positions) > 0:
                sample_pos = diff_positions[0]
                row, col = sample_pos[0], sample_pos[1]
                sample_diff = f"Example: row {row}, col {col}: pred='{pred_values[row, col]}', gold='{gold_values[row, col]}'"
            else:
                sample_diff = ""
            
            diff_count = diff_mask.sum()
            return False, f"Value mismatch: {diff_count} cells differ. {sample_diff}"
            
    except Exception as e:
        return False, f"Comparison error: {str(e)}"


def evaluate_sql_pair(
    db_path: str,
    pred_sql: str,
    gold_sql: str,
    tolerance: float = 1e-4
) -> Tuple[bool, str, dict]:
    """
    Evaluate a pair of SQL queries (predicted vs gold) on the same database.
    
    This is a convenience function that combines execution and comparison.
    
    Args:
        db_path: Path to SQLite database
        pred_sql: Predicted SQL query
        gold_sql: Gold standard SQL query
        tolerance: Tolerance for floating point comparison
        
    Returns:
        Tuple of (is_correct: bool, error_type: str or None, details: dict)
        
    Examples:
        >>> is_correct, error_type, details = evaluate_sql_pair(
        ...     '/path/to/db.sqlite',
        ...     'SELECT AVG(price) FROM products',
        ...     'SELECT AVG(price) FROM products'
        ... )
    """
    # Execute predicted SQL
    pred_success, pred_result = execute_sql_to_dataframe(db_path, pred_sql)
    
    if not pred_success:
        error_type = "execution_error"
        if "syntax" in pred_result.lower() or "near" in pred_result.lower():
            error_type = "syntax_error"
        
        return False, error_type, {
            "error_message": pred_result,
            "pred_executed": False,
            "gold_executed": False
        }
    
    # Execute gold SQL
    gold_success, gold_result = execute_sql_to_dataframe(db_path, gold_sql)
    
    if not gold_success:
        return False, "gold_sql_error", {
            "error_message": f"Gold SQL failed: {gold_result}",
            "pred_executed": True,
            "gold_executed": False
        }
    
    # Detect if we should sort
    should_sort = not (has_order_by(pred_sql) or has_order_by(gold_sql))
    
    # Compare results
    is_match, comparison_details = compare_dataframes(
        pred_result,
        gold_result,
        tolerance=tolerance,
        check_column_names=False,
        auto_sort=should_sort
    )
    
    details = {
        "pred_executed": True,
        "gold_executed": True,
        "pred_shape": pred_result.shape,
        "gold_shape": gold_result.shape,
        "comparison_details": comparison_details,
        "auto_sorted": should_sort,
        "has_order_by": not should_sort
    }
    
    if is_match:
        return True, None, details
    else:
        return False, "result_mismatch", details


if __name__ == "__main__":
    # Simple test
    print("Testing execution_evaluator module...")
    
    # Test has_order_by
    assert has_order_by("SELECT * FROM t ORDER BY id") == True
    assert has_order_by("SELECT * FROM t") == False
    assert has_order_by("SELECT * FROM t -- ORDER BY id") == False
    print("✓ has_order_by tests passed")
    
    # Test normalize_dataframe
    df = pd.DataFrame({'a': [3.333333, 1.666666], 'b': ['B', 'A']})
    normalized = normalize_dataframe(df, sort=True, decimal_places=2)
    assert normalized.iloc[0]['a'] == 1.67  # Sorted and rounded
    print("✓ normalize_dataframe tests passed")
    
    # Test compare_dataframes
    pred = pd.DataFrame({'avg': [0.333333], 'cnt': [100]})
    gold = pd.DataFrame({'average': [0.33], 'count': [100]})
    is_match, details = compare_dataframes(pred, gold, tolerance=0.01)
    assert is_match == True
    print("✓ compare_dataframes tests passed")
    
    print("\nAll basic tests passed! ✅")
