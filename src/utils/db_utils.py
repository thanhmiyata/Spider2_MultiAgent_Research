"""
Database connection and schema metadata management utilities for Spider 2.0 Lite.

This module provides robust utilities for:
- Managing SQLite database connections
- Loading and parsing schema metadata from JSON files
"""

import sqlite3
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Union


# Get logger for this module
# Note: Application should configure logging; we just get the logger
logger = logging.getLogger(__name__)


def _is_valid_table_name(name: str) -> bool:
    """
    Validate that a table name is safe to use in SQL queries.
    
    SQLite allows alphanumeric characters, underscores, and some special chars.
    This is a conservative check to prevent SQL injection.
    
    Args:
        name: Table name to validate
    
    Returns:
        bool: True if name is valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False
    
    # Allow alphanumeric, underscore, and must not start with digit
    # SQLite also allows some special chars but we're conservative
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    return bool(re.match(pattern, name))


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Connect to a SQLite database file.
    
    This function establishes a connection to a SQLite database, with support for
    environment variable configuration and comprehensive error handling.
    
    Args:
        db_path: Path to the SQLite database file. If None, attempts to read from
                environment variable 'SQLITE_DB_PATH' or uses a default path.
    
    Returns:
        sqlite3.Connection: An active connection object to the SQLite database.
    
    Raises:
        FileNotFoundError: If the database file does not exist at the specified path.
        sqlite3.Error: If there's an error establishing the database connection.
        ValueError: If no valid database path is provided or found.
    
    Example:
        >>> conn = get_connection('/path/to/database.sqlite')
        >>> cursor = conn.cursor()
        >>> # ... execute queries ...
        >>> conn.close()
        
        >>> # Using environment variable
        >>> os.environ['SQLITE_DB_PATH'] = '/path/to/database.sqlite'
        >>> conn = get_connection()
    """
    # Determine database path from parameters, environment, or default
    if db_path is None:
        db_path = os.getenv('SQLITE_DB_PATH')
        if db_path is None:
            error_msg = (
                "No database path provided. Please specify db_path parameter or "
                "set SQLITE_DB_PATH environment variable."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info(f"Using database path from environment variable: {db_path}")
    
    # Convert to Path object for better path handling
    db_path_obj = Path(db_path)
    
    # Check if file exists
    if not db_path_obj.exists():
        error_msg = f"Database file not found at path: {db_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Check if path is a file (not a directory)
    if not db_path_obj.is_file():
        error_msg = f"Path is not a file: {db_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Attempt to establish connection
    try:
        logger.info(f"Attempting to connect to database: {db_path}")
        connection = sqlite3.connect(str(db_path_obj))
        
        # Test connection by querying the database structure
        # This will fail if the file is not a valid SQLite database
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        cursor.fetchall()
        cursor.close()
        
        logger.info(f"Successfully connected to database: {db_path}")
        return connection
        
    except sqlite3.Error as e:
        error_msg = f"Failed to connect to database {db_path}: {str(e)}"
        logger.error(error_msg)
        raise sqlite3.Error(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error connecting to database {db_path}: {str(e)}"
        logger.error(error_msg)
        raise


def load_schema_metadata(json_path: Optional[str] = None) -> Dict[str, Dict[str, Union[List[str], str]]]:
    """
    Load and parse schema metadata from a tables.json file.
    
    This function reads a JSON file containing database schema metadata and parses it
    into a structured dictionary format for easy access to table and column information.
    
    Args:
        json_path: Path to the tables.json file. If None, attempts to read from
                  environment variable 'TABLES_JSON_PATH'.
    
    Returns:
        Dict[str, Dict[str, Union[List[str], str]]]: A dictionary mapping table names to their metadata.
        Structure:
        {
            "table_name": {
                "columns": ["col1", "col2", "col3", ...],
                "description": "Optional table description",
                "column_descriptions": {
                    "col1": "Description of col1",
                    "col2": "Description of col2",
                    ...
                }
            },
            ...
        }
    
    Raises:
        FileNotFoundError: If the JSON file does not exist at the specified path.
        ValueError: If no valid JSON path is provided or found, or if JSON is invalid.
        json.JSONDecodeError: If the JSON file is malformed.
        KeyError: If required keys are missing from the JSON structure.
    
    Example:
        >>> metadata = load_schema_metadata('/path/to/tables.json')
        >>> tables = list(metadata.keys())
        >>> columns = metadata['users']['columns']
        >>> desc = metadata['users'].get('description', 'No description')
    """
    # Determine JSON path from parameters or environment
    if json_path is None:
        json_path = os.getenv('TABLES_JSON_PATH')
        if json_path is None:
            error_msg = (
                "No JSON path provided. Please specify json_path parameter or "
                "set TABLES_JSON_PATH environment variable."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info(f"Using JSON path from environment variable: {json_path}")
    
    # Convert to Path object
    json_path_obj = Path(json_path)
    
    # Check if file exists
    if not json_path_obj.exists():
        error_msg = f"JSON file not found at path: {json_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Check if path is a file
    if not json_path_obj.is_file():
        error_msg = f"Path is not a file: {json_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Attempt to read and parse JSON
    try:
        logger.info(f"Loading schema metadata from: {json_path}")
        
        with open(json_path_obj, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate that data is a dictionary or list
        if not isinstance(data, (dict, list)):
            error_msg = f"Invalid JSON structure: expected dict or list, got {type(data).__name__}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Parse the schema metadata
        schema_metadata = _parse_schema_json(data)
        
        logger.info(f"Successfully loaded metadata for {len(schema_metadata)} tables")
        return schema_metadata
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON file {json_path}: {str(e)}"
        logger.error(error_msg)
        raise json.JSONDecodeError(
            f"Malformed JSON in {json_path}: {e.msg}",
            e.doc,
            e.pos
        ) from e
    except KeyError as e:
        error_msg = f"Missing required key in JSON structure: {str(e)}"
        logger.error(error_msg)
        raise KeyError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error loading schema metadata from {json_path}: {str(e)}"
        logger.error(error_msg)
        raise


def _parse_schema_json(data: Union[Dict, List]) -> Dict[str, Dict[str, Union[List[str], str]]]:
    """
    Parse raw JSON data into standardized schema metadata format.
    
    This internal function handles various JSON schema formats and converts them
    to a consistent structure.
    
    Args:
        data: Raw JSON data (dict or list) from tables.json
    
    Returns:
        Dict: Standardized schema metadata dictionary
    
    Raises:
        ValueError: If the JSON structure is not recognized or is invalid
    """
    schema_metadata = {}
    
    # Handle list format: [{"table_name": "...", "columns": [...], ...}, ...]
    if isinstance(data, list):
        # Check for empty list first
        if not data:
            error_msg = "No valid table metadata found in JSON (empty list)"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"Parsing list-format JSON with {len(data)} tables")
        for table_data in data:
            if not isinstance(table_data, dict):
                logger.warning(f"Skipping invalid table entry: {table_data}")
                continue
            
            table_name = table_data.get('table_name') or table_data.get('name')
            if not table_name:
                logger.warning(f"Skipping table entry without name: {table_data}")
                continue
            
            columns = table_data.get('columns', [])
            if not isinstance(columns, list):
                logger.warning(f"Invalid columns format for table {table_name}: {columns}")
                columns = []
            
            schema_metadata[table_name] = {
                'columns': columns,
                'description': table_data.get('description', ''),
                'column_descriptions': table_data.get('column_descriptions', {})
            }
    
    # Handle dict format: {"table_name": {"columns": [...], ...}, ...}
    elif isinstance(data, dict):
        # Check for empty dict first
        if not data:
            error_msg = "No valid table metadata found in JSON (empty dict)"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"Parsing dict-format JSON with {len(data)} tables")
        
        # First, check if all values are lists (simple format: {"table": ["col1", "col2"]})
        all_lists = all(isinstance(v, list) for v in data.values())
        
        if all_lists:
            # Simple format: {"table_name": ["col1", "col2", ...]}
            for table_name, columns in data.items():
                schema_metadata[table_name] = {
                    'columns': columns,
                    'description': '',
                    'column_descriptions': {}
                }
        else:
            # More complex formats
            for table_name, table_data in data.items():
                if isinstance(table_data, list):
                    # Mixed format: some tables have list format
                    schema_metadata[table_name] = {
                        'columns': table_data,
                        'description': '',
                        'column_descriptions': {}
                    }
                elif isinstance(table_data, dict):
                    # Standard format: {"table": {"columns": [...], ...}}
                    columns = table_data.get('columns', [])
                    if not isinstance(columns, list):
                        logger.warning(f"Invalid columns format for table {table_name}: {columns}")
                        columns = []
                    
                    schema_metadata[table_name] = {
                        'columns': columns,
                        'description': table_data.get('description', ''),
                        'column_descriptions': table_data.get('column_descriptions', {})
                    }
                else:
                    logger.warning(f"Skipping invalid table data for {table_name}: {table_data}")
    
    if not schema_metadata:
        error_msg = "No valid table metadata found in JSON"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return schema_metadata


def get_schema_from_db(db_path: str) -> Dict[str, List[str]]:
    """
    Extract schema metadata directly from a SQLite database.
    
    This utility function queries the database schema to extract table and column
    information without requiring a separate JSON file.
    
    Args:
        db_path: Path to the SQLite database file
    
    Returns:
        Dict[str, List[str]]: Dictionary mapping table names to lists of column names
    
    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If there's an error querying the database
    
    Example:
        >>> schema = get_schema_from_db('/path/to/database.sqlite')
        >>> tables = list(schema.keys())
        >>> columns = schema['users']
    """
    conn = None
    try:
        logger.info(f"Extracting schema from database: {db_path}")
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        schema = {}
        for table_tuple in tables:
            table_name = table_tuple[0]
            
            # Validate table name to prevent SQL injection
            if not _is_valid_table_name(table_name):
                logger.warning(f"Skipping table with invalid name: {table_name}")
                continue
            
            # Get column information for each table
            # SECURITY: Table name validated above - only alphanumeric and underscore allowed
            # PRAGMA statements don't support parameterized queries, but validation prevents injection
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Extract column names (index 1 in the PRAGMA result)
            column_names = [col[1] for col in columns]
            schema[table_name] = column_names
        
        logger.info(f"Successfully extracted schema for {len(schema)} tables from database")
        return schema
        
    except Exception as e:
        error_msg = f"Failed to extract schema from database {db_path}: {str(e)}"
        logger.error(error_msg)
        raise
    finally:
        if conn:
            conn.close()
