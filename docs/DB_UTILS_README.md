# Database Utilities Module

## Overview

The `db_utils.py` module provides robust utilities for managing database connections and schema metadata for the Spider 2.0 Lite project. It includes comprehensive error handling, logging, and support for multiple JSON schema formats.

## Features

### 1. Database Connection Management (`get_connection`)

Connect to SQLite databases with automatic validation and error handling.

**Features:**
- Environment variable support (`SQLITE_DB_PATH`)
- Comprehensive path validation
- Connection validation by querying database structure
- Detailed error messages and logging

**Usage:**
```python
from utils.db_utils import get_connection

# Connect with explicit path
conn = get_connection('/path/to/database.sqlite')

# Or use environment variable
import os
os.environ['SQLITE_DB_PATH'] = '/path/to/database.sqlite'
conn = get_connection()

# Use the connection
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
results = cursor.fetchall()

# Always close when done
conn.close()
```

**Error Handling:**
- `FileNotFoundError`: Database file doesn't exist
- `ValueError`: Invalid path or no path provided
- `sqlite3.Error`: Database connection or validation failed

### 2. Schema Metadata Loading (`load_schema_metadata`)

Load and parse schema metadata from JSON files in various formats.

**Supported JSON Formats:**

1. **List Format:**
```json
[
  {
    "table_name": "users",
    "columns": ["id", "name", "email"],
    "description": "User accounts table",
    "column_descriptions": {
      "id": "Primary key",
      "name": "User full name"
    }
  }
]
```

2. **Dict Format:**
```json
{
  "users": {
    "columns": ["id", "name", "email"],
    "description": "User accounts"
  }
}
```

3. **Simple Dict Format:**
```json
{
  "users": ["id", "name", "email"],
  "products": ["id", "title", "price"]
}
```

**Usage:**
```python
from utils.db_utils import load_schema_metadata

# Load with explicit path
metadata = load_schema_metadata('/path/to/tables.json')

# Or use environment variable
import os
os.environ['TABLES_JSON_PATH'] = '/path/to/tables.json'
metadata = load_schema_metadata()

# Access table information
tables = list(metadata.keys())
user_columns = metadata['users']['columns']
user_description = metadata['users']['description']
column_desc = metadata['users']['column_descriptions']
```

**Error Handling:**
- `FileNotFoundError`: JSON file doesn't exist
- `ValueError`: Invalid path or invalid JSON structure
- `json.JSONDecodeError`: Malformed JSON

### 3. Direct Schema Extraction (`get_schema_from_db`)

Extract schema metadata directly from a SQLite database without requiring a JSON file.

**Usage:**
```python
from utils.db_utils import get_schema_from_db

# Extract schema
schema = get_schema_from_db('/path/to/database.sqlite')

# Access table and column information
for table_name, columns in schema.items():
    print(f"Table: {table_name}")
    print(f"Columns: {', '.join(columns)}")
```

**Returns:**
```python
{
    "users": ["id", "username", "email", "created_at"],
    "products": ["id", "name", "price", "stock"],
    "orders": ["id", "user_id", "product_id", "quantity"]
}
```

## Environment Variables

The module supports the following environment variables:

- `SQLITE_DB_PATH`: Default path for database connections
- `TABLES_JSON_PATH`: Default path for schema metadata JSON files

**Example:**
```bash
export SQLITE_DB_PATH="/path/to/database.sqlite"
export TABLES_JSON_PATH="/path/to/tables.json"
```

Or in Python:
```python
import os
os.environ['SQLITE_DB_PATH'] = '/path/to/database.sqlite'
os.environ['TABLES_JSON_PATH'] = '/path/to/tables.json'
```

## Logging

The module uses Python's standard logging facility with INFO level by default. All operations are logged with timestamps and context.

**Log Format:**
```
[YYYY-MM-DD HH:MM:SS] LEVEL - utils.db_utils - Message
```

**Example Logs:**
```
[2025-11-22 17:40:03] INFO - utils.db_utils - Attempting to connect to database: /path/to/db.sqlite
[2025-11-22 17:40:03] INFO - utils.db_utils - Successfully connected to database: /path/to/db.sqlite
[2025-11-22 17:40:03] INFO - utils.db_utils - Loading schema metadata from: /path/to/tables.json
[2025-11-22 17:40:03] INFO - utils.db_utils - Successfully loaded metadata for 3 tables
```

## Integration with Spider 2.0 Lite

### Working with E_commerce Database

```python
from pathlib import Path
from utils.db_utils import get_connection, get_schema_from_db

# Path to Spider 2.0 Lite database
project_root = Path(__file__).parent.parent
db_path = project_root / "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"

# Connect to database
conn = get_connection(str(db_path))

# Extract schema
schema = get_schema_from_db(str(db_path))

# Use the connection
cursor = conn.cursor()
for table_name in schema.keys():
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"{table_name}: {count} rows")

conn.close()
```

### Creating tables.json for a Database

```python
import json
from pathlib import Path
from utils.db_utils import get_schema_from_db

# Extract schema from database
db_path = "data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
schema = get_schema_from_db(db_path)

# Convert to JSON format
schema_data = []
for table_name, columns in schema.items():
    schema_data.append({
        "table_name": table_name,
        "columns": columns,
        "description": f"{table_name} table",
        "column_descriptions": {col: f"{col} column" for col in columns}
    })

# Save to JSON file
output_path = Path("tables.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(schema_data, f, indent=2)

print(f"Created {output_path} with {len(schema_data)} tables")
```

## Testing

The module includes comprehensive unit tests in `tests/test_db_utils.py`:

**Run tests:**
```bash
cd /path/to/Spider2_MultiAgent_Research
python tests/test_db_utils.py
```

**Test Coverage:**
- Connection with valid/invalid paths
- Connection with environment variables
- Error handling for nonexistent/invalid files
- Schema loading in multiple JSON formats
- Error handling for malformed JSON
- Direct schema extraction from databases
- Integration tests with real Spider 2.0 Lite databases

**All 24 tests passing successfully ✓**

## Best Practices

1. **Always close connections:**
```python
conn = get_connection(db_path)
try:
    # Use connection
    pass
finally:
    conn.close()
```

2. **Use context managers when possible:**
```python
import sqlite3
db_path = "database.sqlite"
conn = get_connection(db_path)
# Note: get_connection returns a regular connection, not a context manager
# For context manager support, use sqlite3.connect directly or wrap it
```

3. **Handle errors appropriately:**
```python
from utils.db_utils import get_connection
import sqlite3

try:
    conn = get_connection(db_path)
    # Use connection
except FileNotFoundError:
    print("Database file not found")
except sqlite3.Error as e:
    print(f"Database error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

4. **Validate schema metadata:**
```python
from utils.db_utils import load_schema_metadata

metadata = load_schema_metadata(json_path)

# Check if expected tables exist
required_tables = ['users', 'products', 'orders']
for table in required_tables:
    if table not in metadata:
        raise ValueError(f"Missing required table: {table}")
    
    # Check columns
    if not metadata[table]['columns']:
        raise ValueError(f"Table {table} has no columns")
```

## API Reference

### `get_connection(db_path: Optional[str] = None) -> sqlite3.Connection`

**Parameters:**
- `db_path` (str, optional): Path to SQLite database file

**Returns:**
- `sqlite3.Connection`: Active database connection

**Raises:**
- `FileNotFoundError`: Database file not found
- `ValueError`: Invalid or missing path
- `sqlite3.Error`: Connection error

### `load_schema_metadata(json_path: Optional[str] = None) -> Dict[str, Dict[str, Union[List[str], str]]]`

**Parameters:**
- `json_path` (str, optional): Path to tables.json file

**Returns:**
- `Dict`: Schema metadata dictionary

**Raises:**
- `FileNotFoundError`: JSON file not found
- `ValueError`: Invalid path or structure
- `json.JSONDecodeError`: Malformed JSON

### `get_schema_from_db(db_path: str) -> Dict[str, List[str]]`

**Parameters:**
- `db_path` (str): Path to SQLite database file

**Returns:**
- `Dict[str, List[str]]`: Dictionary mapping table names to column lists

**Raises:**
- `FileNotFoundError`: Database file not found
- `sqlite3.Error`: Database error

## Contributing

When modifying this module:

1. Maintain backward compatibility
2. Add tests for new functionality
3. Update this documentation
4. Follow existing code style and logging patterns
5. Ensure all tests pass before committing

## License

This module is part of the Spider2_MultiAgent_Research project.
