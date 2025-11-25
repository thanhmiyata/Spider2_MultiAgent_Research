"""
Unit Tests for Execution Evaluator Module

Tests DataFrame-based SQL execution and comparison with edge case handling.
"""

import pytest
import pandas as pd
import numpy as np
import sqlite3
import tempfile
import os
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.execution_evaluator import (
    has_order_by,
    execute_sql_to_dataframe,
    normalize_dataframe,
    compare_dataframes,
    evaluate_sql_pair,
    remove_sql_comments_and_strings
)


class TestHasOrderBy:
    """Test ORDER BY detection"""
    
    def test_simple_order_by(self):
        assert has_order_by("SELECT * FROM t ORDER BY id") == True
    
    def test_no_order_by(self):
        assert has_order_by("SELECT * FROM t") == False
    
    def test_order_by_in_comment(self):
        assert has_order_by("SELECT * FROM t -- ORDER BY id") == False
    
    def test_order_by_in_string(self):
        assert has_order_by("SELECT 'ORDER BY' FROM t") == False
    
    def test_order_by_case_insensitive(self):
        assert has_order_by("SELECT * FROM t order by id") == True
        assert has_order_by("SELECT * FROM t OrDeR bY id") == True
    
    def test_order_by_with_multiple_columns(self):
        assert has_order_by("SELECT * FROM t ORDER BY id, name DESC") == True


class TestNormalizeDataFrame:
    """Test DataFrame normalization"""
    
    def test_sorting(self):
        df = pd.DataFrame({'a': [3, 1, 2], 'b': ['C', 'A', 'B']})
        normalized = normalize_dataframe(df, sort=True)
        
        # Should be sorted by column 'a' then 'b'
        assert normalized.iloc[0]['a'] == 1
        assert normalized.iloc[1]['a'] == 2
        assert normalized.iloc[2]['a'] == 3
    
    def test_no_sorting(self):
        df = pd.DataFrame({'a': [3, 1, 2]})
        normalized = normalize_dataframe(df, sort=False)
        
        # Order should be preserved
        assert normalized.iloc[0]['a'] == 3
        assert normalized.iloc[1]['a'] == 1
    
    def test_rounding(self):
        df = pd.DataFrame({'a': [0.333333, 0.666666]})
        normalized = normalize_dataframe(df, decimal_places=2)
        
        assert normalized.iloc[0]['a'] == 0.33
        assert normalized.iloc[1]['a'] == 0.67
    
    def test_rounding_4_decimals(self):
        df = pd.DataFrame({'a': [0.123456789]})
        normalized = normalize_dataframe(df, decimal_places=4)
        
        assert normalized.iloc[0]['a'] == 0.1235  # Rounded to 4 decimals
    
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        normalized = normalize_dataframe(df)
        
        assert normalized.empty


class TestCompareDataFrames:
    """Test DataFrame comparison"""
    
    def test_exact_match(self):
        df1 = pd.DataFrame({'a': [1, 2], 'b': ['A', 'B']})
        df2 = pd.DataFrame({'a': [1, 2], 'b': ['A', 'B']})
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == True
    
    def test_different_order(self):
        df1 = pd.DataFrame({'a': [2, 1], 'b': ['B', 'A']})
        df2 = pd.DataFrame({'a': [1, 2], 'b': ['A', 'B']})
        
        # Should match because auto_sort=True by default
        is_match, details = compare_dataframes(df1, df2, auto_sort=True)
        assert is_match == True
    
    def test_different_column_names(self):
        df1 = pd.DataFrame({'avg_price': [100], 'count': [5]})
        df2 = pd.DataFrame({'average': [100], 'total': [5]})
        
        # Should match because check_column_names=False by default
        is_match, details = compare_dataframes(df1, df2, check_column_names=False)
        assert is_match == True
    
    def test_column_names_checked(self):
        df1 = pd.DataFrame({'avg_price': [100]})
        df2 = pd.DataFrame({'average': [100]})
        
        # Should NOT match when checking column names
        is_match, details = compare_dataframes(df1, df2, check_column_names=True)
        assert is_match == False
        assert "Column names differ" in details
    
    def test_floating_point_tolerance(self):
        df1 = pd.DataFrame({'value': [0.333333]})
        df2 = pd.DataFrame({'value': [0.33]})
        
        # Should match with tolerance=0.01
        is_match, details = compare_dataframes(df1, df2, tolerance=0.01)
        assert is_match == True
    
    def test_floating_point_no_tolerance(self):
        df1 = pd.DataFrame({'value': [0.333333]})
        df2 = pd.DataFrame({'value': [0.33]})
        
        # Should NOT match with very small tolerance
        is_match, details = compare_dataframes(df1, df2, tolerance=1e-10)
        assert is_match == False
    
    def test_shape_mismatch_rows(self):
        df1 = pd.DataFrame({'a': [1, 2, 3]})
        df2 = pd.DataFrame({'a': [1, 2]})
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == False
        assert "Shape mismatch" in details
    
    def test_shape_mismatch_columns(self):
        df1 = pd.DataFrame({'a': [1], 'b': [2]})
        df2 = pd.DataFrame({'a': [1]})
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == False
        assert "Shape mismatch" in details
    
    def test_both_empty(self):
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == True
        assert "empty" in details.lower()
    
    def test_one_empty(self):
        df1 = pd.DataFrame({'a': [1]})
        df2 = pd.DataFrame()
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == False
        assert "empty" in details.lower()
    
    def test_mixed_types(self):
        df1 = pd.DataFrame({'a': [1, 'text', 3.14]})
        df2 = pd.DataFrame({'a': [1, 'text', 3.14]})
        
        is_match, details = compare_dataframes(df1, df2)
        assert is_match == True


class TestExecuteSQLToDataFrame:
    """Test SQL execution"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        
        # Create table and insert data
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                salary REAL
            )
        ''')
        cursor.execute("INSERT INTO users VALUES (1, 'Alice', 30, 50000.50)")
        cursor.execute("INSERT INTO users VALUES (2, 'Bob', 25, 45000.75)")
        cursor.execute("INSERT INTO users VALUES (3, 'Charlie', 35, 60000.00)")
        conn.commit()
        conn.close()
        
        yield path
        
        # Cleanup
        os.unlink(path)
    
    def test_simple_select(self, temp_db):
        success, df = execute_sql_to_dataframe(temp_db, "SELECT * FROM users")
        
        assert success == True
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df.columns) == ['id', 'name', 'age', 'salary']
    
    def test_select_with_where(self, temp_db):
        success, df = execute_sql_to_dataframe(temp_db, "SELECT name FROM users WHERE age > 30")
        
        assert success == True
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Charlie'
    
    def test_aggregation(self, temp_db):
        success, df = execute_sql_to_dataframe(temp_db, "SELECT AVG(salary) as avg_salary FROM users")
        
        assert success == True
        assert len(df) == 1
        assert 'avg_salary' in df.columns
        # Average of 50000.50, 45000.75, 60000.00 = 51667.08333...
        assert abs(df.iloc[0]['avg_salary'] - 51667.08) < 1
    
    def test_syntax_error(self, temp_db):
        success, error = execute_sql_to_dataframe(temp_db, "SELCT * FROM users")
        
        assert success == False
        assert "syntax" in error.lower() or "error" in error.lower()
    
    def test_empty_sql(self, temp_db):
        success, error = execute_sql_to_dataframe(temp_db, "")
        
        assert success == False
        assert "Empty" in error
    
    def test_table_not_found(self, temp_db):
        success, error = execute_sql_to_dataframe(temp_db, "SELECT * FROM nonexistent_table")
        
        assert success == False
        assert "no such table" in error.lower() or "error" in error.lower()


class TestEvaluateSQLPair:
    """Test end-to-end SQL pair evaluation"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE products (
                id INTEGER,
                name TEXT,
                price REAL
            )
        ''')
        cursor.execute("INSERT INTO products VALUES (1, 'Apple', 1.50)")
        cursor.execute("INSERT INTO products VALUES (2, 'Banana', 0.75)")
        cursor.execute("INSERT INTO products VALUES (3, 'Orange', 2.00)")
        conn.commit()
        conn.close()
        
        yield path
        os.unlink(path)
    
    def test_identical_queries(self, temp_db):
        sql = "SELECT * FROM products"
        is_correct, error_type, details = evaluate_sql_pair(temp_db, sql, sql)
        
        assert is_correct == True
        assert error_type is None
    
    def test_equivalent_queries_different_order(self, temp_db):
        pred_sql = "SELECT * FROM products ORDER BY id DESC"
        gold_sql = "SELECT * FROM products ORDER BY id ASC"
        
        is_correct, error_type, details = evaluate_sql_pair(temp_db, pred_sql, gold_sql)
        
        # Should NOT match because ORDER BY gives different results
        assert is_correct == False
        assert error_type == "result_mismatch"
    
    def test_equivalent_queries_no_order(self, temp_db):
        pred_sql = "SELECT id, name FROM products WHERE id IN (1, 2)"
        gold_sql = "SELECT id, name FROM products WHERE id < 3"
        
        is_correct, error_type, details = evaluate_sql_pair(temp_db, pred_sql, gold_sql)
        
        # Should match (same results, auto-sorted)
        assert is_correct == True
    
    def test_pred_syntax_error(self, temp_db):
        pred_sql = "SELCT * FROM products"
        gold_sql = "SELECT * FROM products"
        
        is_correct, error_type, details = evaluate_sql_pair(temp_db, pred_sql, gold_sql)
        
        assert is_correct == False
        assert error_type == "syntax_error"
    
    def test_different_results(self, temp_db):
        pred_sql = "SELECT * FROM products WHERE price > 1.0"
        gold_sql = "SELECT * FROM products WHERE price > 2.0"
        
        is_correct, error_type, details = evaluate_sql_pair(temp_db, pred_sql, gold_sql)
        
        assert is_correct == False
        assert error_type == "result_mismatch"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
