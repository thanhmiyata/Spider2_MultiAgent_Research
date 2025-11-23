"""
Tests for enhanced SchemaLinker and Planner with foreign key support.
"""

import os
import sys
import json
import unittest
import tempfile
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.db_utils import load_schema_metadata, build_adjacency_list

# Try to import Planner, skip tests if dependencies not available
try:
    from agents.planner import Planner, MissingTableError
    PLANNER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Planner: {e}")
    PLANNER_AVAILABLE = False
    # Define dummy classes for skipped tests
    MissingTableError = type('MissingTableError', (Exception,), {})
    Planner = type('Planner', (), {})


class TestForeignKeyParsing(unittest.TestCase):
    """Test foreign key parsing and adjacency list building."""
    
    def setUp(self):
        """Create test metadata with foreign keys."""
        self.test_metadata = [
            {
                "table_name": "customers",
                "columns": ["customer_id", "name", "email"],
                "description": "Customer information",
                "column_descriptions": {
                    "customer_id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "email": "TEXT"
                }
            },
            {
                "table_name": "orders",
                "columns": ["order_id", "customer_id", "order_date"],
                "description": "Customer orders",
                "column_descriptions": {
                    "order_id": "INTEGER PRIMARY KEY",
                    "customer_id": "INTEGER",
                    "order_date": "TEXT"
                },
                "foreign_keys": [
                    {"from": "customer_id", "to": "customers.customer_id"}
                ]
            },
            {
                "table_name": "products",
                "columns": ["product_id", "product_name", "price"],
                "description": "Products catalog"
            },
            {
                "table_name": "order_items",
                "columns": ["item_id", "order_id", "product_id", "quantity"],
                "description": "Items in orders",
                "foreign_keys": [
                    {"from": "order_id", "to": "orders.order_id"},
                    {"from": "product_id", "to": "products.product_id"}
                ]
            }
        ]
        
        # Create temporary JSON file
        self.temp_json = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_metadata, self.temp_json)
        self.temp_json.close()
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
    
    def test_load_metadata_with_foreign_keys(self):
        """Test that foreign keys are correctly parsed."""
        metadata = load_schema_metadata(self.temp_json.name)
        
        # Check that metadata was loaded
        self.assertEqual(len(metadata), 4)
        
        # Check foreign keys for orders
        orders_fks = metadata['orders'].get('foreign_keys', [])
        self.assertEqual(len(orders_fks), 1)
        self.assertEqual(orders_fks[0]['from'], 'customer_id')
        self.assertEqual(orders_fks[0]['to'], 'customers.customer_id')
        
        # Check foreign keys for order_items
        order_items_fks = metadata['order_items'].get('foreign_keys', [])
        self.assertEqual(len(order_items_fks), 2)
        
        # Check tables without foreign keys
        customers_fks = metadata['customers'].get('foreign_keys', [])
        self.assertEqual(len(customers_fks), 0)
    
    def test_build_adjacency_list(self):
        """Test adjacency list construction from foreign keys."""
        metadata = load_schema_metadata(self.temp_json.name)
        adj_list = build_adjacency_list(metadata)
        
        # Check that all tables are in the adjacency list
        self.assertEqual(len(adj_list), 4)
        
        # Check bidirectional relationships
        self.assertIn('customers', adj_list['orders'])
        self.assertIn('orders', adj_list['customers'])
        
        self.assertIn('orders', adj_list['order_items'])
        self.assertIn('order_items', adj_list['orders'])
        
        self.assertIn('products', adj_list['order_items'])
        self.assertIn('order_items', adj_list['products'])
        
        # Check that products is connected to order_items
        self.assertIn('order_items', adj_list['products'])
    
    def test_adjacency_list_graph_structure(self):
        """Test that adjacency list forms correct graph structure."""
        metadata = load_schema_metadata(self.temp_json.name)
        adj_list = build_adjacency_list(metadata)
        
        # Test path exists: customers -> orders -> order_items -> products
        # Starting from customers
        self.assertIn('orders', adj_list['customers'])
        # From orders
        self.assertIn('order_items', adj_list['orders'])
        # From order_items
        self.assertIn('products', adj_list['order_items'])
        
        # Test that we can traverse the graph
        visited = set(['customers'])
        to_visit = list(adj_list['customers'])
        
        while to_visit:
            current = to_visit.pop(0)
            if current not in visited:
                visited.add(current)
                to_visit.extend([t for t in adj_list[current] if t not in visited])
        
        # Should be able to reach all tables from customers
        self.assertEqual(len(visited), 4)


class TestPlannerSchemaValidation(unittest.TestCase):
    """Test Planner's schema validity check."""
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def setUp(self):
        """Set up test schema and planner."""
        self.schema = """
        Table: customers
        Columns: customer_id (INTEGER), name (TEXT), email (TEXT)
        
        Table: orders
        Columns: order_id (INTEGER), customer_id (INTEGER), order_date (TEXT)
        
        Table: products
        Columns: product_id (INTEGER), product_name (TEXT), price (REAL)
        """
        
        self.planner = Planner(enable_schema_validation=True)
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def test_extract_tables_from_schema(self):
        """Test extraction of table names from schema."""
        tables = self.planner._extract_tables_from_schema(self.schema)
        
        self.assertEqual(len(tables), 3)
        self.assertIn('customers', tables)
        self.assertIn('orders', tables)
        self.assertIn('products', tables)
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def test_extract_required_tables_from_plan(self):
        """Test extraction of required tables from plan."""
        plan = """
        1. Join orders table with customers table
        2. Filter on orders.order_date
        3. Select from products table
        """
        
        required = self.planner._extract_required_tables_from_plan(plan)
        
        self.assertIn('orders', required)
        self.assertIn('customers', required)
        self.assertIn('products', required)
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def test_validate_schema_success(self):
        """Test that validation passes when all tables exist."""
        plan = """
        1. Join orders table with customers table on customer_id
        2. Filter orders where order_date > '2023-01-01'
        """
        
        # Should not raise any exception
        try:
            self.planner._validate_schema(plan, self.schema)
        except MissingTableError:
            self.fail("Schema validation raised MissingTableError unexpectedly")
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def test_validate_schema_missing_table(self):
        """Test that validation fails when required table is missing."""
        plan = """
        1. Join orders table with customers table
        2. Join with order_items table to get product details
        """
        
        # order_items is not in the schema, should raise MissingTableError
        with self.assertRaises(MissingTableError) as context:
            self.planner._validate_schema(plan, self.schema)
        
        self.assertIn('MISSING_TABLE', str(context.exception))
        self.assertIn('order_items', str(context.exception))
    
    @unittest.skipIf(not PLANNER_AVAILABLE, "Planner dependencies not available")
    def test_validation_disabled(self):
        """Test that validation can be disabled."""
        planner_no_validation = Planner(enable_schema_validation=False)
        
        plan = """
        Join with nonexistent_table
        """
        
        # Should not raise any exception when validation is disabled
        try:
            planner_no_validation._validate_schema(plan, self.schema)
        except MissingTableError:
            self.fail("Validation should be disabled but raised error")


class TestSchemaLinkerIntegration(unittest.TestCase):
    """Integration tests for SchemaLinker with foreign keys."""
    
    def setUp(self):
        """Create test data."""
        self.test_metadata = [
            {
                "table_name": "customers",
                "columns": ["customer_id", "name", "email"],
                "description": "Customer information",
                "column_descriptions": {
                    "customer_id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "email": "TEXT"
                }
            },
            {
                "table_name": "orders",
                "columns": ["order_id", "customer_id", "order_date", "total"],
                "description": "Customer orders",
                "column_descriptions": {
                    "order_id": "INTEGER PRIMARY KEY",
                    "customer_id": "INTEGER - FK to customers",
                    "order_date": "TEXT",
                    "total": "REAL"
                },
                "foreign_keys": [
                    {"from": "customer_id", "to": "customers.customer_id"}
                ]
            },
            {
                "table_name": "products",
                "columns": ["product_id", "product_name", "price"],
                "description": "Product catalog",
                "column_descriptions": {
                    "product_id": "INTEGER PRIMARY KEY",
                    "product_name": "TEXT",
                    "price": "REAL"
                }
            },
            {
                "table_name": "order_items",
                "columns": ["item_id", "order_id", "product_id", "quantity"],
                "description": "Items in each order",
                "column_descriptions": {
                    "item_id": "INTEGER PRIMARY KEY",
                    "order_id": "INTEGER - FK to orders",
                    "product_id": "INTEGER - FK to products",
                    "quantity": "INTEGER"
                },
                "foreign_keys": [
                    {"from": "order_id", "to": "orders.order_id"},
                    {"from": "product_id", "to": "products.product_id"}
                ]
            }
        ]
        
        self.temp_json = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_metadata, self.temp_json)
        self.temp_json.close()
    
    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
    
    def test_adjacency_list_expansion(self):
        """Test that adjacency list correctly represents relationships."""
        metadata = load_schema_metadata(self.temp_json.name)
        adj_list = build_adjacency_list(metadata)
        
        # If we start with orders, we should be able to reach:
        # - customers (via FK)
        # - order_items (reverse FK)
        # - products (via order_items)
        
        neighbors_of_orders = adj_list['orders']
        self.assertIn('customers', neighbors_of_orders)
        self.assertIn('order_items', neighbors_of_orders)
        
        # From order_items, we should reach products
        neighbors_of_order_items = adj_list['order_items']
        self.assertIn('products', neighbors_of_order_items)
        self.assertIn('orders', neighbors_of_order_items)


if __name__ == '__main__':
    unittest.main()
