# Enhanced Schema Linker and Planner

## Overview

This document describes the enhancements made to the Schema Linker and Planner modules to improve schema linking accuracy and prevent downstream errors.

## Key Changes

### 1. Enhanced Database Utils (`src/utils/db_utils.py`)

#### Foreign Key Support
- **`load_schema_metadata()`** now extracts `foreign_keys` from `tables.json`
- Each table's metadata can include a `foreign_keys` array:
  ```json
  {
    "table_name": "orders",
    "columns": [...],
    "foreign_keys": [
      {"from": "customer_id", "to": "customers.customer_id"}
    ]
  }
  ```

#### Adjacency List
- **`build_adjacency_list()`** creates a graph representation of table relationships
- Returns a dictionary mapping each table to its connected tables:
  ```python
  {
    "orders": ["customers", "order_items"],
    "customers": ["orders", "reviews"]
  }
  ```
- Relationships are bidirectional

### 2. Refactored Schema Linker (`src/agents/schema_linker.py`)

#### 3-Step Linking Process

**Step 1: Initial Retrieval**
- Uses TF-IDF vector search to select Top-K most relevant tables
- Configurable via `top_k` parameter (default: 5)
- Forms the `Initial_Set`

**Step 2: Graph Expansion**
- Expands the initial set by including neighboring tables
- Uses the adjacency list to find tables with foreign key relationships
- Creates a `Candidate_Set` (typically 10-15 tables)
- Ensures intermediate tables aren't missed

**Step 3: LLM Reranking**
- Refines the candidate set using LLM
- Prompt asks LLM to select ONLY strictly necessary tables
- Returns JSON list of selected table names
- Forms the final `Selected_Schema`

#### Rich Output Format

The linker now outputs structured information:

```
User Question: Find customers who bought products
Selected Tables:
1. customers (Customer information)
   - customer_id: INTEGER PRIMARY KEY
   - name: TEXT
   - email: TEXT

2. orders (Customer orders)
   - order_id: INTEGER PRIMARY KEY
   - customer_id: INTEGER - FK to customers
   - order_date: TEXT

3. order_items (Items in orders)
   - item_id: INTEGER PRIMARY KEY
   - order_id: INTEGER - FK to orders
   - product_id: INTEGER - FK to products

[Relationships]
- orders.customer_id = customers.customer_id
- order_items.order_id = orders.order_id
```

#### Initialization

```python
# Without metadata (backward compatible)
linker = SchemaLinker()

# With metadata for enhanced features
linker = SchemaLinker(
    metadata_path='/path/to/tables.json',
    top_k=5,
    expansion_enabled=True
)
```

### 3. Enhanced Planner (`src/agents/planner.py`)

#### Schema Validity Check

The planner now validates that required tables exist in the provided schema:

```python
planner = Planner(enable_schema_validation=True)

try:
    plan = planner.plan(question, schema)
except MissingTableError as e:
    print(f"Schema validation failed: {e}")
    # Handle error: retry with schema linker, or request more tables
```

#### New Exception

```python
class MissingTableError(Exception):
    """Raised when required tables are missing from schema"""
    pass
```

#### Error Message Format

```
MISSING_TABLE: Required tables {'order_items'} not found in provided schema. 
Available tables: {'customers', 'orders', 'products'}
```

#### Validation Methods

- `_extract_tables_from_schema()`: Parses schema to find available tables
- `_extract_required_tables_from_plan()`: Parses plan to find required tables
- `_validate_schema()`: Compares required vs available tables

## Usage Examples

### Example 1: Basic Usage (Backward Compatible)

```python
from agents.schema_linker import SchemaLinker

linker = SchemaLinker()
question = "Find total orders per customer"
schema = get_database_schema()

linked_schema = linker.link(question, schema)
```

### Example 2: With Foreign Key Metadata

```python
from agents.schema_linker import SchemaLinker

# Initialize with metadata
linker = SchemaLinker(
    metadata_path='data/tables.json',
    top_k=5,
    expansion_enabled=True
)

question = "Which products were bought by customers in California?"
schema = get_database_schema()

# Will use 3-step process with graph expansion
linked_schema = linker.link(question, schema)
```

### Example 3: Schema Validation

```python
from agents.planner import Planner, MissingTableError

planner = Planner(enable_schema_validation=True)

try:
    plan = planner.plan(question, linked_schema)
    # Plan is valid, proceed to generation
    sql = generator.generate(question, linked_schema, plan)
except MissingTableError as e:
    # Handle missing tables
    print(f"Error: {e}")
    # Option 1: Disable validation and proceed
    planner_no_val = Planner(enable_schema_validation=False)
    plan = planner_no_val.plan(question, linked_schema)
    # Option 2: Request better schema from linker
```

## Testing

### Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run only schema linking tests
python -m pytest tests/test_schema_linking.py -v

# Run only db_utils tests
python -m pytest tests/test_db_utils.py -v
```

### Run Demonstration

```bash
python demo_schema_linker.py
```

## Tables.json Format

The enhanced schema linker supports tables.json with foreign keys:

```json
[
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
  }
]
```

### Foreign Keys Format

- `from`: Column name in the current table
- `to`: Referenced column in format `table_name.column_name`

## Backward Compatibility

All changes are backward compatible:

- Schema Linker works without metadata_path
- Planner validation can be disabled
- Old code continues to work without modifications
- New features are opt-in

## Performance Considerations

- **Step 1 (TF-IDF)**: Fast, O(n) where n is number of tables
- **Step 2 (Graph Expansion)**: O(k) where k is size of initial set
- **Step 3 (LLM Reranking)**: Adds one LLM call (~1-2 seconds)

Total overhead: ~1-3 seconds per query (mostly from LLM call)

## Benefits

1. **Improved Accuracy**: Graph expansion prevents missing intermediate tables
2. **Better Context**: Rich output format helps downstream agents
3. **Error Prevention**: Schema validation catches issues early
4. **Maintainability**: Clear separation of concerns
5. **Testability**: Comprehensive test coverage

## Migration Guide

### For Existing Code

No changes required. The enhanced features are opt-in.

### To Use New Features

1. Create or update `tables.json` with foreign key information
2. Pass `metadata_path` to SchemaLinker
3. Enable schema validation in Planner
4. Handle MissingTableError exceptions

```python
# Before
linker = SchemaLinker()
planner = Planner()

# After
linker = SchemaLinker(metadata_path='data/tables.json')
planner = Planner(enable_schema_validation=True)
```

## Troubleshooting

### "No module named 'langchain_core'"

Install dependencies:
```bash
pip install -r requirements.txt
```

### "MISSING_TABLE error"

The planner detected that required tables are missing from the schema. Options:
1. Improve schema linking to include more tables
2. Disable validation: `Planner(enable_schema_validation=False)`
3. Add missing tables to the schema manually

### Graph expansion includes too many tables

Reduce the initial top_k value:
```python
linker = SchemaLinker(top_k=3)  # Default is 5
```

### LLM reranking fails

The linker falls back to all candidate tables if LLM fails. Check:
1. API keys are configured
2. Model is available
3. Network connectivity

## Future Enhancements

- Support for more complex foreign key patterns
- Caching of adjacency lists
- Parallel LLM calls for large schemas
- Custom graph expansion strategies
- Integration with query execution feedback
