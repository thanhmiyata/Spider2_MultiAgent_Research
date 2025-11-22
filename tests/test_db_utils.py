"""
Unit tests for db_utils module.

Tests database connection management and schema metadata loading functionality.
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.db_utils import (
    get_connection,
    load_schema_metadata,
    get_schema_from_db,
    _parse_schema_json,
    _is_valid_table_name
)


class TestGetConnection(unittest.TestCase):
    """Test cases for get_connection function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary SQLite database for testing
        self.temp_db = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sqlite', delete=False
        )
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize the database with a simple table
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER
            )
        """)
        cursor.execute("INSERT INTO test_table VALUES (1, 'test', 100)")
        conn.commit()
        conn.close()
        
        # Store original env var if exists
        self.original_env = os.environ.get('SQLITE_DB_PATH')
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary database
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
        
        # Restore original environment variable
        if self.original_env is not None:
            os.environ['SQLITE_DB_PATH'] = self.original_env
        elif 'SQLITE_DB_PATH' in os.environ:
            del os.environ['SQLITE_DB_PATH']
    
    def test_connection_with_valid_path(self):
        """Test successful connection with valid database path."""
        conn = get_connection(self.temp_db_path)
        self.assertIsInstance(conn, sqlite3.Connection)
        
        # Verify connection works
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_table")
        results = cursor.fetchall()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], 'test')
        
        conn.close()
    
    def test_connection_with_environment_variable(self):
        """Test connection using environment variable."""
        os.environ['SQLITE_DB_PATH'] = self.temp_db_path
        
        conn = get_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        conn.close()
    
    def test_connection_with_nonexistent_file(self):
        """Test error handling for nonexistent database file."""
        nonexistent_path = "/path/to/nonexistent/database.sqlite"
        
        with self.assertRaises(FileNotFoundError) as context:
            get_connection(nonexistent_path)
        
        self.assertIn("not found", str(context.exception))
    
    def test_connection_with_directory_path(self):
        """Test error handling when path is a directory."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            with self.assertRaises(ValueError) as context:
                get_connection(temp_dir)
            
            self.assertIn("not a file", str(context.exception))
        finally:
            os.rmdir(temp_dir)
    
    def test_connection_without_path_or_env(self):
        """Test error handling when no path is provided."""
        # Ensure env var is not set
        if 'SQLITE_DB_PATH' in os.environ:
            del os.environ['SQLITE_DB_PATH']
        
        with self.assertRaises(ValueError) as context:
            get_connection()
        
        self.assertIn("No database path provided", str(context.exception))
    
    def test_connection_with_invalid_database_file(self):
        """Test error handling for invalid database file."""
        # Create a file with SQLite header but corrupted data
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.sqlite', delete=False
        )
        temp_file.write(b'SQLite format 3\x00' + b'corrupted' * 100)
        temp_file.close()
        
        try:
            # Should raise an error when trying to validate the connection
            with self.assertRaises(sqlite3.Error):
                conn = get_connection(temp_file.name)
        finally:
            os.unlink(temp_file.name)


class TestLoadSchemaMetadata(unittest.TestCase):
    """Test cases for load_schema_metadata function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary JSON files for testing
        self.temp_json = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        self.temp_json_path = self.temp_json.name
        
        # Store original env var if exists
        self.original_env = os.environ.get('TABLES_JSON_PATH')
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary JSON file
        if os.path.exists(self.temp_json_path):
            os.unlink(self.temp_json_path)
        
        # Restore original environment variable
        if self.original_env is not None:
            os.environ['TABLES_JSON_PATH'] = self.original_env
        elif 'TABLES_JSON_PATH' in os.environ:
            del os.environ['TABLES_JSON_PATH']
    
    def test_load_schema_list_format(self):
        """Test loading schema from list-format JSON."""
        schema_data = [
            {
                "table_name": "users",
                "columns": ["id", "name", "email"],
                "description": "User accounts table",
                "column_descriptions": {
                    "id": "Primary key",
                    "name": "User full name",
                    "email": "User email address"
                }
            },
            {
                "table_name": "orders",
                "columns": ["id", "user_id", "total"],
                "description": "Orders table"
            }
        ]
        
        with open(self.temp_json_path, 'w') as f:
            json.dump(schema_data, f)
        
        metadata = load_schema_metadata(self.temp_json_path)
        
        self.assertEqual(len(metadata), 2)
        self.assertIn('users', metadata)
        self.assertIn('orders', metadata)
        self.assertEqual(metadata['users']['columns'], ["id", "name", "email"])
        self.assertEqual(metadata['users']['description'], "User accounts table")
        self.assertEqual(len(metadata['users']['column_descriptions']), 3)
    
    def test_load_schema_dict_format(self):
        """Test loading schema from dict-format JSON."""
        schema_data = {
            "products": {
                "columns": ["id", "name", "price", "stock"],
                "description": "Products catalog",
                "column_descriptions": {
                    "id": "Product ID",
                    "name": "Product name"
                }
            },
            "categories": {
                "columns": ["id", "name"],
                "description": "Product categories"
            }
        }
        
        with open(self.temp_json_path, 'w') as f:
            json.dump(schema_data, f)
        
        metadata = load_schema_metadata(self.temp_json_path)
        
        self.assertEqual(len(metadata), 2)
        self.assertIn('products', metadata)
        self.assertIn('categories', metadata)
        self.assertEqual(len(metadata['products']['columns']), 4)
        self.assertEqual(metadata['categories']['description'], "Product categories")
    
    def test_load_schema_simple_dict_format(self):
        """Test loading schema from simple dict-format JSON."""
        schema_data = {
            "users": ["id", "name", "email"],
            "products": ["id", "title", "price"]
        }
        
        with open(self.temp_json_path, 'w') as f:
            json.dump(schema_data, f)
        
        metadata = load_schema_metadata(self.temp_json_path)
        
        self.assertEqual(len(metadata), 2)
        self.assertEqual(metadata['users']['columns'], ["id", "name", "email"])
        self.assertEqual(metadata['products']['columns'], ["id", "title", "price"])
    
    def test_load_schema_with_environment_variable(self):
        """Test loading schema using environment variable."""
        schema_data = [{"table_name": "test", "columns": ["id"]}]
        
        with open(self.temp_json_path, 'w') as f:
            json.dump(schema_data, f)
        
        os.environ['TABLES_JSON_PATH'] = self.temp_json_path
        
        metadata = load_schema_metadata()
        self.assertEqual(len(metadata), 1)
        self.assertIn('test', metadata)
    
    def test_load_schema_nonexistent_file(self):
        """Test error handling for nonexistent JSON file."""
        nonexistent_path = "/path/to/nonexistent/tables.json"
        
        with self.assertRaises(FileNotFoundError) as context:
            load_schema_metadata(nonexistent_path)
        
        self.assertIn("not found", str(context.exception))
    
    def test_load_schema_malformed_json(self):
        """Test error handling for malformed JSON."""
        with open(self.temp_json_path, 'w') as f:
            f.write("{ invalid json here")
        
        with self.assertRaises(json.JSONDecodeError):
            load_schema_metadata(self.temp_json_path)
    
    def test_load_schema_invalid_structure(self):
        """Test error handling for invalid JSON structure."""
        # JSON with no valid table data
        with open(self.temp_json_path, 'w') as f:
            json.dump([], f)
        
        with self.assertRaises(ValueError) as context:
            load_schema_metadata(self.temp_json_path)
        
        self.assertIn("No valid table metadata", str(context.exception))
    
    def test_load_schema_without_path_or_env(self):
        """Test error handling when no path is provided."""
        if 'TABLES_JSON_PATH' in os.environ:
            del os.environ['TABLES_JSON_PATH']
        
        with self.assertRaises(ValueError) as context:
            load_schema_metadata()
        
        self.assertIn("No JSON path provided", str(context.exception))


class TestGetSchemaFromDB(unittest.TestCase):
    """Test cases for get_schema_from_db function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary SQLite database
        self.temp_db = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sqlite', delete=False
        )
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Create tables with various structures
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
    
    def test_extract_schema_from_database(self):
        """Test extracting schema from a database."""
        schema = get_schema_from_db(self.temp_db_path)
        
        # Check all tables are present
        self.assertEqual(len(schema), 3)
        self.assertIn('users', schema)
        self.assertIn('products', schema)
        self.assertIn('orders', schema)
        
        # Check column counts
        self.assertEqual(len(schema['users']), 4)  # id, username, email, created_at
        self.assertEqual(len(schema['products']), 4)  # id, name, price, stock
        self.assertEqual(len(schema['orders']), 4)  # id, user_id, product_id, quantity
        
        # Check specific columns
        self.assertIn('id', schema['users'])
        self.assertIn('username', schema['users'])
        self.assertIn('email', schema['users'])
        self.assertIn('name', schema['products'])
        self.assertIn('price', schema['products'])
    
    def test_extract_schema_from_nonexistent_db(self):
        """Test error handling for nonexistent database."""
        with self.assertRaises(FileNotFoundError):
            get_schema_from_db("/path/to/nonexistent.db")


class TestParseSchemaJson(unittest.TestCase):
    """Test cases for _parse_schema_json internal function."""
    
    def test_parse_list_format(self):
        """Test parsing list-format JSON."""
        data = [
            {"table_name": "users", "columns": ["id", "name"]},
            {"name": "products", "columns": ["id", "title"]}
        ]
        
        result = _parse_schema_json(data)
        
        self.assertEqual(len(result), 2)
        self.assertIn('users', result)
        self.assertIn('products', result)
    
    def test_parse_dict_format(self):
        """Test parsing dict-format JSON."""
        data = {
            "users": {"columns": ["id", "name"]},
            "products": {"columns": ["id", "title"]}
        }
        
        result = _parse_schema_json(data)
        
        self.assertEqual(len(result), 2)
        self.assertIn('users', result)
        self.assertIn('products', result)
    
    def test_parse_simple_dict_format(self):
        """Test parsing simple dict-format JSON."""
        data = {
            "users": ["id", "name"],
            "products": ["id", "title"]
        }
        
        result = _parse_schema_json(data)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result['users']['columns'], ["id", "name"])
    
    def test_parse_empty_data(self):
        """Test error handling for empty data."""
        with self.assertRaises(ValueError):
            _parse_schema_json([])
        
        with self.assertRaises(ValueError):
            _parse_schema_json({})
    
    def test_parse_invalid_list_entries(self):
        """Test handling of invalid entries in list format."""
        data = [
            {"table_name": "users", "columns": ["id"]},
            "invalid_entry",
            {"table_name": "products", "columns": ["id"]}
        ]
        
        result = _parse_schema_json(data)
        
        # Should skip invalid entry
        self.assertEqual(len(result), 2)
        self.assertIn('users', result)
        self.assertIn('products', result)


class TestTableNameValidation(unittest.TestCase):
    """Test cases for _is_valid_table_name function."""
    
    def test_valid_table_names(self):
        """Test that valid table names are accepted."""
        valid_names = [
            'users',
            'user_accounts',
            'Users',
            'TABLE_NAME',
            '_private_table',
            'table123',
            'order_items_2023'
        ]
        
        for name in valid_names:
            with self.subTest(name=name):
                self.assertTrue(_is_valid_table_name(name))
    
    def test_invalid_table_names(self):
        """Test that invalid table names are rejected."""
        invalid_names = [
            '',  # Empty string
            '123table',  # Starts with digit
            'table name',  # Contains space
            'table-name',  # Contains hyphen
            'table.name',  # Contains dot
            'table;DROP TABLE users;',  # SQL injection attempt
            'table--comment',  # SQL comment
            "table'OR'1'='1",  # SQL injection
            None,  # None value
            123,  # Not a string
        ]
        
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(_is_valid_table_name(name))
    
    def test_sql_injection_attempts(self):
        """Test that SQL injection attempts are blocked."""
        injection_attempts = [
            "users; DROP TABLE users;",
            "users' OR '1'='1",
            "users--",
            "users/*comment*/",
            "users UNION SELECT * FROM passwords",
        ]
        
        for attempt in injection_attempts:
            with self.subTest(attempt=attempt):
                self.assertFalse(_is_valid_table_name(attempt))


class TestIntegrationWithRealDatabase(unittest.TestCase):
    """Integration tests with the actual Spider 2.0 Lite database."""
    
    def setUp(self):
        """Set up test with real database path."""
        self.project_root = Path(__file__).parent.parent
        self.db_path = (
            self.project_root / 
            "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
        )
        self.sample_json_path = self.project_root / "tests/sample_tables.json"
    
    def test_connection_to_real_database(self):
        """Test connection to the actual E_commerce database."""
        if not self.db_path.exists():
            self.skipTest(f"Database not found at {self.db_path}")
        
        conn = get_connection(str(self.db_path))
        self.assertIsInstance(conn, sqlite3.Connection)
        
        # Verify we can query it
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        self.assertGreater(len(tables), 0)
        
        conn.close()
    
    def test_extract_schema_from_real_database(self):
        """Test schema extraction from actual database."""
        if not self.db_path.exists():
            self.skipTest(f"Database not found at {self.db_path}")
        
        schema = get_schema_from_db(str(self.db_path))
        
        # Should have at least one table
        self.assertGreater(len(schema), 0)
        
        # Each table should have columns
        for table_name, columns in schema.items():
            self.assertIsInstance(columns, list)
            self.assertGreater(len(columns), 0)
    
    def test_load_sample_json(self):
        """Test loading the sample tables.json file."""
        if not self.sample_json_path.exists():
            self.skipTest(f"Sample JSON not found at {self.sample_json_path}")
        
        metadata = load_schema_metadata(str(self.sample_json_path))
        
        # Should have at least one table
        self.assertGreater(len(metadata), 0)
        
        # Check structure
        for table_name, table_data in metadata.items():
            self.assertIn('columns', table_data)
            self.assertIsInstance(table_data['columns'], list)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestGetConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestLoadSchemaMetadata))
    suite.addTests(loader.loadTestsFromTestCase(TestGetSchemaFromDB))
    suite.addTests(loader.loadTestsFromTestCase(TestParseSchemaJson))
    suite.addTests(loader.loadTestsFromTestCase(TestTableNameValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWithRealDatabase))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
