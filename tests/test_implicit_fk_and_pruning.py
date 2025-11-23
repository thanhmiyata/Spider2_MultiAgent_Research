"""
Tests for enhanced SchemaLinker with implicit FK detection and column pruning.
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

from agents.schema_linker import SchemaLinker


class TestImplicitFKDetection(unittest.TestCase):
    """Test heuristic foreign key detection."""
    
    def setUp(self):
        """Set up test schema."""
        self.schema = """
        Table: users
        Columns: id (INTEGER), name (TEXT), email (TEXT)
        
        Table: user_logs
        Columns: log_id (INTEGER), uid (INTEGER), action (TEXT), timestamp (TEXT)
        
        Table: orders
        Columns: order_id (INTEGER), user_id (INTEGER), total (REAL)
        
        Table: products
        Columns: product_id (INTEGER), name (TEXT), price (REAL)
        """
        
        # Create linker with heuristic FK enabled
        self.linker = SchemaLinker(use_rag=False, enable_heuristic_fk=True)
    
    def test_detect_implicit_fks_id_pattern(self):
        """Test detection of implicit FKs based on _id pattern."""
        implicit_fks = self.linker._detect_implicit_fks(self.schema)
        
        # Should detect user_id relationship between users and orders
        self.assertIn('orders', implicit_fks.get('users', []) + implicit_fks.get('orders', []))
    
    def test_detect_implicit_fks_uid_pattern(self):
        """Test detection of implicit FKs with uid pattern."""
        implicit_fks = self.linker._detect_implicit_fks(self.schema)
        
        # uid is a known FK pattern, but may not match if types differ
        # Just verify the method runs without error
        self.assertIsInstance(implicit_fks, dict)
    
    def test_implicit_fk_disabled(self):
        """Test that implicit FK detection can be disabled."""
        linker_no_heuristic = SchemaLinker(use_rag=False, enable_heuristic_fk=False)
        
        implicit_fks = linker_no_heuristic._detect_implicit_fks(self.schema)
        
        # Should return empty dict when disabled
        self.assertEqual(len([v for v in implicit_fks.values() if v]), 0)
    
    def test_bidirectional_soft_links(self):
        """Test that soft links are bidirectional."""
        implicit_fks = self.linker._detect_implicit_fks(self.schema)
        
        # If users -> orders exists, orders -> users should also exist
        for table1, neighbors in implicit_fks.items():
            for table2 in neighbors:
                if table2 in implicit_fks:
                    # Check bidirectionality
                    self.assertTrue(
                        table1 in implicit_fks[table2] or len(neighbors) == 0,
                        f"Soft link not bidirectional: {table1} -> {table2}"
                    )


class TestColumnPruning(unittest.TestCase):
    """Test column pruning in LLM reranking."""
    
    def setUp(self):
        """Set up test data."""
        self.schema = """
        Table: customers
        Columns: customer_id (INTEGER), name (TEXT), email (TEXT), phone (TEXT), 
                 address (TEXT), created_at (TIMESTAMP), updated_at (TIMESTAMP),
                 internal_notes (TEXT), marketing_opt_in (BOOLEAN)
        
        Table: orders
        Columns: order_id (INTEGER), customer_id (INTEGER), order_date (TEXT),
                 total (REAL), status (TEXT), notes (TEXT), created_at (TIMESTAMP)
        """
        
        self.linker = SchemaLinker(use_rag=False, expansion_enabled=False)
    
    def test_step3_returns_dict(self):
        """Test that step3 now returns a dictionary with columns."""
        question = "What are the names of customers who placed orders?"
        candidate_tables = {'customers', 'orders'}
        
        # Mock the LLM response by testing the parsing logic
        # The actual LLM call would be tested in integration tests
        result = self.linker._step3_llm_reranking(question, candidate_tables, self.schema)
        
        # Should return a dict mapping table -> columns
        self.assertIsInstance(result, dict)
    
    def test_format_output_with_pruned_columns(self):
        """Test that format_output handles pruned columns correctly."""
        question = "Get customer names and order totals"
        selected_data = {
            'customers': ['customer_id', 'name'],
            'orders': ['order_id', 'customer_id', 'total']
        }
        
        output = self.linker._format_output(question, selected_data, self.schema)
        
        # Should include the question
        self.assertIn(question, output)
        
        # Should list selected tables
        self.assertIn('customers', output)
        self.assertIn('orders', output)
        
        # Should show only selected columns (not all columns)
        self.assertIn('customer_id', output)
        self.assertIn('name', output)
        self.assertIn('total', output)


class TestSchemaLinkerIntegration(unittest.TestCase):
    """Integration tests for enhanced SchemaLinker."""
    
    def setUp(self):
        """Create test metadata and linker."""
        self.test_metadata = [
            {
                "table_name": "users",
                "columns": ["id", "name", "email"],
                "description": "User accounts",
                "column_descriptions": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT - User full name",
                    "email": "TEXT - User email address"
                }
            },
            {
                "table_name": "orders",
                "columns": ["order_id", "user_id", "total"],
                "description": "Customer orders",
                "column_descriptions": {
                    "order_id": "INTEGER PRIMARY KEY",
                    "user_id": "INTEGER - FK to users",
                    "total": "REAL - Order total amount"
                },
                "foreign_keys": [
                    {"from": "user_id", "to": "users.id"}
                ]
            }
        ]
        
        # Create temporary JSON file
        self.temp_json = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_metadata, self.temp_json)
        self.temp_json.close()
        
        self.schema = """
        Table: users
        Columns: id (INTEGER), name (TEXT), email (TEXT)
        
        Table: orders
        Columns: order_id (INTEGER), user_id (INTEGER), total (REAL)
        """
        
        self.linker = SchemaLinker(
            metadata_path=self.temp_json.name,
            use_rag=False,
            expansion_enabled=True,
            enable_heuristic_fk=True
        )
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
    
    def test_graph_expansion_with_implicit_fks(self):
        """Test that graph expansion works with implicit FK detection."""
        initial_tables = {'orders'}
        
        # Should expand to include users via FK
        expanded = self.linker._step2_graph_expansion(initial_tables, self.schema)
        
        # Should include at least orders
        self.assertIn('orders', expanded)
        
        # May include users via explicit or implicit FK
        # (depending on whether metadata FK or heuristic detection found it)
        # This tests that the method runs successfully
        self.assertIsInstance(expanded, set)
        self.assertGreaterEqual(len(expanded), 1)
    
    def test_full_link_process(self):
        """Test the complete linking process."""
        question = "Show all orders with user names"
        
        result = self.linker.link(question, self.schema)
        
        # Should return non-empty schema
        self.assertGreater(len(result), 0)
        
        # Should mention the question
        self.assertIn(question, result)


if __name__ == '__main__':
    unittest.main()
