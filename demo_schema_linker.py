"""
Demonstration script for the enhanced SchemaLinker and Planner functionality.

This script demonstrates:
1. Loading metadata with foreign keys
2. Building adjacency list for table relationships
3. Schema linking with 3-step process (without LLM calls for demo)
4. Schema validation in Planner
"""

import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.db_utils import load_schema_metadata, build_adjacency_list

print("="*80)
print("ENHANCED SCHEMA LINKER AND PLANNER DEMONSTRATION")
print("="*80)

# Load test metadata
print("\n1. Loading metadata with foreign keys from test data...")
try:
    metadata = load_schema_metadata('/tmp/test_tables.json')
    print(f"   ✓ Loaded metadata for {len(metadata)} tables")
    
    # Show foreign keys
    print("\n2. Foreign Key Relationships:")
    for table_name, table_data in metadata.items():
        fks = table_data.get('foreign_keys', [])
        if fks:
            print(f"   {table_name}:")
            for fk in fks:
                print(f"      - {fk['from']} -> {fk['to']}")
    
    # Build adjacency list
    print("\n3. Building adjacency list (table relationship graph)...")
    adj_list = build_adjacency_list(metadata)
    print(f"   ✓ Built adjacency list for {len(adj_list)} tables")
    
    print("\n   Adjacency List (neighbors):")
    for table, neighbors in sorted(adj_list.items()):
        if neighbors:
            print(f"   {table} -> {neighbors}")
    
    # Demonstrate graph expansion
    print("\n4. Graph Expansion Example:")
    print("   Starting with: ['orders']")
    initial = {'orders'}
    expanded = set(initial)
    for table in initial:
        neighbors = adj_list.get(table, [])
        expanded.update(neighbors)
    print(f"   After expansion: {expanded}")
    print(f"   Added {len(expanded) - len(initial)} neighboring tables")
    
    # Demonstrate schema validation
    print("\n5. Schema Validation Example:")
    print("   Schema contains: customers, orders, products, order_items, reviews")
    
    test_cases = [
        ("Join orders with customers", ["orders", "customers"], True),
        ("Join orders with order_items and products", ["orders", "order_items", "products"], True),
        ("Join orders with shipments", ["orders", "shipments"], False),
    ]
    
    for description, tables, should_pass in test_cases:
        available = set(metadata.keys())
        required = set(tables)
        missing = required - available
        
        if not missing:
            print(f"   ✓ PASS: {description}")
            print(f"      All required tables {required} are available")
        else:
            print(f"   ✗ FAIL: {description}")
            print(f"      Missing tables: {missing}")
    
    print("\n6. Rich Output Format Example:")
    print("   Schema linker now outputs:")
    print("   " + "-"*70)
    sample_output = """
User Question: Find total revenue per customer
Selected Tables:
1. customers (Customer information)
   - customer_id: INTEGER PRIMARY KEY
   - name: TEXT
   - email: TEXT

2. orders (Customer orders)
   - order_id: INTEGER PRIMARY KEY
   - customer_id: INTEGER - FK to customers
   - order_date: TEXT
   - total: REAL

[Relationships]
- orders.customer_id = customers.customer_id
    """.strip()
    print("   " + sample_output.replace("\n", "\n   "))
    print("   " + "-"*70)
    
    print("\n" + "="*80)
    print("DEMONSTRATION COMPLETE")
    print("="*80)
    print("\nKey Improvements:")
    print("✓ Schema Linker now understands table relationships via foreign keys")
    print("✓ Graph expansion ensures intermediate tables aren't missed")
    print("✓ Rich output format provides context for downstream agents")
    print("✓ Planner validates that required tables are present in schema")
    print("✓ MissingTableError is raised if validation fails")
    print("\nAll changes are backward compatible with existing code!")
    
except FileNotFoundError:
    print("\n⚠ Test data not found. Creating test data...")
    print("Run the following command first:")
    print("python -c \"from tests.test_schema_linking import TestForeignKeyParsing; t = TestForeignKeyParsing(); t.setUp()\"")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
