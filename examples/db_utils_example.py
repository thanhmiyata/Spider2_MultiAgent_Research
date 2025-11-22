#!/usr/bin/env python3
"""
Example usage of db_utils module for Spider 2.0 Lite.

This script demonstrates:
1. Connecting to a SQLite database
2. Extracting schema metadata
3. Loading schema from JSON
4. Querying database with schema information
"""

import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.db_utils import get_connection, load_schema_metadata, get_schema_from_db


def example_1_basic_connection():
    """Example 1: Basic database connection."""
    print("\n" + "="*60)
    print("Example 1: Basic Database Connection")
    print("="*60)
    
    db_path = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    # Connect to database
    conn = get_connection(str(db_path))
    
    # Get list of tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\nFound {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
    conn.close()
    print("\n✓ Connection closed successfully")


def example_2_extract_schema():
    """Example 2: Extract schema from database."""
    print("\n" + "="*60)
    print("Example 2: Extract Schema from Database")
    print("="*60)
    
    db_path = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    # Extract schema
    schema = get_schema_from_db(str(db_path))
    
    print(f"\nExtracted schema for {len(schema)} tables:")
    for table_name, columns in schema.items():
        print(f"\nTable: {table_name}")
        print(f"  Columns ({len(columns)}): {', '.join(columns)}")


def example_3_load_json_schema():
    """Example 3: Load schema from JSON file."""
    print("\n" + "="*60)
    print("Example 3: Load Schema from JSON")
    print("="*60)
    
    json_path = PROJECT_ROOT / "tests/sample_tables.json"
    
    if not json_path.exists():
        print(f"JSON file not found at {json_path}")
        return
    
    # Load schema metadata
    metadata = load_schema_metadata(str(json_path))
    
    print(f"\nLoaded metadata for {len(metadata)} tables:")
    for table_name, table_data in metadata.items():
        print(f"\nTable: {table_name}")
        print(f"  Description: {table_data['description']}")
        print(f"  Columns ({len(table_data['columns'])}): {', '.join(table_data['columns'])}")
        
        if table_data['column_descriptions']:
            print(f"  Column Descriptions:")
            for col, desc in list(table_data['column_descriptions'].items())[:3]:
                print(f"    - {col}: {desc}")


def example_4_query_with_schema():
    """Example 4: Query database using schema information."""
    print("\n" + "="*60)
    print("Example 4: Query Database with Schema")
    print("="*60)
    
    db_path = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    # Get connection and schema
    conn = get_connection(str(db_path))
    schema = get_schema_from_db(str(db_path))
    
    print("\nQuerying database tables:")
    cursor = conn.cursor()
    
    for table_name, columns in schema.items():
        # Count rows
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        print(f"\n{table_name}:")
        print(f"  Row count: {count}")
        print(f"  Columns: {', '.join(columns)}")
        
        # Sample first row if table is not empty
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            sample = cursor.fetchone()
            print(f"  Sample data: {sample}")
    
    conn.close()
    print("\n✓ Query complete")


def example_5_error_handling():
    """Example 5: Error handling."""
    print("\n" + "="*60)
    print("Example 5: Error Handling")
    print("="*60)
    
    # Try to connect to nonexistent database
    try:
        conn = get_connection("/path/to/nonexistent.db")
    except FileNotFoundError as e:
        print(f"\n✓ Caught expected error: {e}")
    
    # Try to load nonexistent JSON
    try:
        metadata = load_schema_metadata("/path/to/nonexistent.json")
    except FileNotFoundError as e:
        print(f"✓ Caught expected error: {e}")
    
    # Try to connect without path
    try:
        conn = get_connection()
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    
    print("\n✓ All error handling tests passed")


def main():
    """Run all examples."""
    print("\n" + "#"*60)
    print("# DB Utils Module - Example Usage")
    print("#"*60)
    
    try:
        example_1_basic_connection()
        example_2_extract_schema()
        example_3_load_json_schema()
        example_4_query_with_schema()
        example_5_error_handling()
        
        print("\n" + "#"*60)
        print("# All examples completed successfully!")
        print("#"*60 + "\n")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
