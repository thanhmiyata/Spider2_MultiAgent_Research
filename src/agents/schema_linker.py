import time
import re
import json
import numpy as np
from typing import Dict, List, Set, Optional
from langchain_core.prompts import PromptTemplate

# Try to import sklearn, provide helpful error if not available
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. RAG features will be disabled.")
    print("Install with: pip install scikit-learn")

from config import DEFAULT_MODEL, CLAUDE_MODEL, get_llm, extract_content
from utils.db_utils import load_schema_metadata, build_adjacency_list

# Table preference rules for selecting better tables over raw/staging versions
TABLE_PREFERENCE_RULES = {
    'prefer_prefixes': ['cleaned_', 'processed_', 'final_', 'prod_'],
    'avoid_prefixes': ['raw_', 'staging_', 'temp_', 'tmp_', 'test_'],
    'prefer_suffixes': ['_clean', '_processed', '_final'],
    'avoid_suffixes': ['_raw', '_staging', '_temp', '_test'],
    # Specific table replacements (raw -> preferred)
    'specific_replacements': {
        'weekly_sales': 'cleaned_weekly_sales',
        'sales': 'cleaned_weekly_sales',
        'transactions': 'cleaned_transactions',
    }
}

# Output format constants
MAX_PREVIEW_LENGTH = 100  # Maximum length for column preview in descriptions
MAX_PREVIEW_COLUMNS = 5   # Maximum number of columns to show in preview


class SchemaLinker:
    """
    Enhanced Schema Linker with 3-step linking process:
    1. Initial Retrieval: TF-IDF/Vector Search for Top-K tables
    2. Graph Expansion: Add neighboring tables via foreign key relationships
    3. LLM Reranking: Refine selection to only strictly necessary tables
    """
    
    def __init__(self, model_name=CLAUDE_MODEL, max_retries=2, use_rag=True, top_k=5, 
                 metadata_path: Optional[str] = None, expansion_enabled=True,
                 enable_heuristic_fk=True):
        """
        Initialize SchemaLinker with optional metadata loading.
        
        Args:
            model_name: LLM model to use for reranking
            max_retries: Number of retries for LLM calls
            use_rag: Enable TF-IDF based retrieval
            top_k: Number of initial tables to retrieve
            metadata_path: Path to tables.json with foreign key information
            expansion_enabled: Enable graph expansion step
            enable_heuristic_fk: Enable heuristic foreign key detection for implicit relationships
        """
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.use_rag = use_rag and SKLEARN_AVAILABLE
        self.top_k = top_k
        self.expansion_enabled = expansion_enabled
        self.enable_heuristic_fk = enable_heuristic_fk
        
        # Schema metadata and adjacency list (loaded from tables.json if provided)
        self.schema_metadata: Optional[Dict] = None
        self.adjacency_list: Optional[Dict[str, List[str]]] = None
        
        if metadata_path:
            try:
                self.schema_metadata = load_schema_metadata(metadata_path)
                self.adjacency_list = build_adjacency_list(self.schema_metadata)
                print(f"[SchemaLinker] Loaded metadata for {len(self.schema_metadata)} tables with foreign key relationships")
            except Exception as e:
                print(f"[SchemaLinker] Warning: Could not load metadata from {metadata_path}: {e}")
                self.schema_metadata = None
                self.adjacency_list = None
        
        if use_rag and not SKLEARN_AVAILABLE:
            print("Warning: RAG requested but scikit-learn not available. RAG disabled.")
        
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
        else:
            self.vectorizer = None
        
        # LLM Reranking Prompt with Column Pruning
        self.reranking_prompt = PromptTemplate(
            input_variables=["question", "candidate_tables"],
            template="""
            You are a database expert. Given a user question and a list of candidate tables with descriptions,
            select ONLY the tables and columns that are strictly necessary to answer the question.
            
            User Question: {question}
            
            Candidate Tables:
            {candidate_tables}
            
            Instructions:
            - Select ONLY tables that are directly needed to answer the question
            - For each selected table, list ONLY the columns that are relevant to the question
            - Remove unnecessary columns (e.g., internal IDs, timestamps, metadata) that don't help answer the question
            - Consider JOIN paths - if tables need to be joined, include foreign key columns
            - Return a JSON object mapping table names to arrays of column names
            
            Example output: {{"orders": ["order_id", "customer_id", "total"], "customers": ["customer_id", "name", "email"]}}
            
            Output (JSON object only):
            """
        )
        self.reranking_chain = self.reranking_prompt | self.llm

    def _parse_schema_to_tables(self, schema: str) -> Dict[str, Dict]:
        """
        Parse schema string to extract tables with their columns and types.
        Returns: dict with table_name -> {'columns': [list of columns], 'text': 'searchable text'}
        """
        tables = {}
        current_table = None
        
        for line in schema.split('\n'):
            line = line.strip()
            
            # Detect table definitions
            if line.startswith('Table:'):
                table_name = line.replace('Table:', '').strip()
                current_table = table_name
                tables[current_table] = {'columns': [], 'text': table_name}
            
            # Detect columns
            elif current_table and line.startswith('Columns:'):
                columns_text = line.replace('Columns:', '').strip()
                tables[current_table]['columns_text'] = columns_text
                tables[current_table]['columns'] = [col.strip() for col in columns_text.split(',')]
                tables[current_table]['text'] = f"{current_table} {columns_text}"
            
            # Alternative schema format: CREATE TABLE with double quotes, backticks, or no quotes
            elif line.startswith('CREATE TABLE') or 'CREATE TABLE' in line.upper():
                # Match table names with backticks, double quotes, or no quotes
                match = re.search(r'CREATE TABLE\s+[`"\']?(\w+)[`"\']?', line, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    current_table = table_name
                    tables[current_table] = {'columns': [], 'text': table_name}
            
            # Extract column from CREATE TABLE format - handle double quotes, backticks, or no quotes
            elif current_table:
                # Try to match column definitions with various quote styles
                # Pattern: "column_name" TYPE or `column_name` TYPE or column_name TYPE
                match = re.search(r'[`"\']?(\w+)[`"\']?\s+(\w+)', line)
                if match and not line.upper().startswith('CREATE'):
                    col_name = match.group(1)
                    col_type = match.group(2)
                    
                    # Skip SQL keywords
                    if col_type.upper() not in ['TABLE', 'INDEX', 'VIEW', 'TRIGGER']:
                        col_entry = f"{col_name} ({col_type})"
                        tables[current_table]['columns'].append(col_entry)
                        tables[current_table]['text'] += f" {col_name}"
        
        return tables

    def _step1_initial_retrieval(self, question: str, schema: str) -> Set[str]:
        """
        Step 1: Initial Retrieval using TF-IDF to get Top-K relevant tables.
        
        Returns: Set of initially selected table names
        """
        if not self.use_rag:
            # If RAG disabled, return all tables
            tables = self._parse_schema_to_tables(schema)
            print(f"[SchemaLinker Step 1] RAG disabled, returning all {len(tables)} tables")
            return set(tables.keys())
        
        tables = self._parse_schema_to_tables(schema)
        
        print(f"[SchemaLinker Step 1] Parsed {len(tables)} tables from schema")
        print(f"[SchemaLinker Step 1] Table names: {list(tables.keys())[:10]}...")  # Show first 10
        
        if not tables or len(tables) <= self.top_k:
            print(f"[SchemaLinker Step 1] Table count ({len(tables)}) <= top_k ({self.top_k}), returning all")
            return set(tables.keys())
        
        try:
            # Prepare documents: question + all table texts
            table_names = list(tables.keys())
            table_texts = [tables[name]['text'] for name in table_names]
            
            print(f"[SchemaLinker Step 1] Question: {question[:100]}...")
            print(f"[SchemaLinker Step 1] Sample table texts:")
            for i, (name, text) in enumerate(zip(table_names[:3], table_texts[:3])):
                print(f"  - {name}: {text[:80]}...")
            
            # Create TF-IDF matrix
            all_docs = [question] + table_texts
            tfidf_matrix = self.vectorizer.fit_transform(all_docs)
            
            print(f"[SchemaLinker Step 1] TF-IDF matrix shape: {tfidf_matrix.shape}")
            
            # Calculate cosine similarity between question and each table
            question_vector = tfidf_matrix[0:1]
            table_vectors = tfidf_matrix[1:]
            similarities = cosine_similarity(question_vector, table_vectors)[0]
            
            print(f"[SchemaLinker Step 1] Similarities shape: {similarities.shape}")
            print(f"[SchemaLinker Step 1] Similarity range: [{similarities.min():.4f}, {similarities.max():.4f}]")
            print(f"[SchemaLinker Step 1] Top 5 similarities: {sorted(similarities, reverse=True)[:5]}")
            
            # Get top-k table indices
            top_indices = np.argsort(similarities)[-self.top_k:][::-1]
            initial_set = {table_names[i] for i in top_indices}
            
            print(f"[SchemaLinker Step 1] Top {self.top_k} indices: {top_indices}")
            print(f"[SchemaLinker Step 1] Top {self.top_k} tables with scores:")
            for idx in top_indices:
                print(f"  - {table_names[idx]}: {similarities[idx]:.4f}")
            
            print(f"[SchemaLinker Step 1] Initial retrieval selected {len(initial_set)} tables: {initial_set}")
            return initial_set
            
        except Exception as e:
            print(f"[SchemaLinker Step 1] TF-IDF retrieval failed: {e}, using all tables")
            import traceback
            traceback.print_exc()
            return set(tables.keys())

    def _detect_implicit_fks(self, schema: str) -> Dict[str, List[str]]:
        """
        Heuristically detect implicit foreign key relationships based on column name matching.
        
        This addresses the "Implicit Foreign Keys" vulnerability where FK relationships
        are not explicitly defined in metadata but exist logically (e.g., user_logs.uid -> users.id).
        
        Args:
            schema: Full schema string
            
        Returns: Dictionary mapping table names to lists of related tables (soft links)
        """
        if not self.enable_heuristic_fk:
            return {}
        
        # Parse schema to extract tables and their columns with types
        tables_info = self._parse_schema_to_tables(schema)
        
        # Build map of column names to tables that have them
        column_to_tables: Dict[str, List[tuple]] = {}  # column_name -> [(table_name, col_type), ...]
        
        for table_name, table_data in tables_info.items():
            columns = table_data.get('columns', [])
            for col in columns:
                # Extract column name and type
                col_name = col.split('(')[0].strip() if '(' in col else col.strip()
                col_type = col.split('(')[1].split(')')[0].strip() if '(' in col else 'UNKNOWN'
                
                if col_name not in column_to_tables:
                    column_to_tables[col_name] = []
                column_to_tables[col_name].append((table_name, col_type))
        
        # Detect potential FK relationships
        soft_links: Dict[str, Set[str]] = {}
        for table in tables_info.keys():
            soft_links[table] = set()
        
        # Common FK patterns to check
        fk_patterns = [
            ('id', 'INTEGER'),  # id is often a primary key
            ('_id', ''),  # columns ending in _id are often FKs
            ('_ID', ''),
        ]
        
        for col_name, table_type_pairs in column_to_tables.items():
            # Only consider if column appears in 2+ tables
            if len(table_type_pairs) < 2:
                continue
            
            # Check if this looks like a foreign key relationship
            is_potential_fk = (
                col_name.endswith('_id') or 
                col_name.endswith('_ID') or
                col_name.endswith('Id') or
                col_name == 'id' or
                col_name in ['customer_id', 'user_id', 'product_id', 'order_id', 'uid']
            )
            
            if is_potential_fk:
                # Create bidirectional soft links between tables sharing this column
                for i, (table1, type1) in enumerate(table_type_pairs):
                    for table2, type2 in table_type_pairs[i+1:]:
                        # Only link if types match (if known)
                        if type1 != 'UNKNOWN' and type2 != 'UNKNOWN' and type1 != type2:
                            continue
                        
                        soft_links[table1].add(table2)
                        soft_links[table2].add(table1)
                        print(f"[SchemaLinker] Detected implicit FK: {table1}.{col_name} <-> {table2}.{col_name}")
        
        # Convert sets to lists for consistency
        return {table: list(links) for table, links in soft_links.items()}

    def _step2_graph_expansion(self, initial_tables: Set[str], schema: str = None) -> Set[str]:
        """
        Step 2: Graph Expansion - Add neighboring tables via foreign key relationships.
        Now includes heuristic detection of implicit FKs.
        
        Args:
            initial_tables: Set of initially selected tables
            schema: Optional schema string for implicit FK detection
            
        Returns: Expanded set of candidate tables (initial + neighbors)
        """
        if not self.expansion_enabled:
            print(f"[SchemaLinker Step 2] Graph expansion disabled")
            return initial_tables
        
        candidate_set = set(initial_tables)
        
        # Build enhanced adjacency list with explicit + implicit FKs
        enhanced_adjacency = {}
        
        # Start with explicit FKs from metadata
        if self.adjacency_list:
            enhanced_adjacency = {k: list(v) for k, v in self.adjacency_list.items()}
        
        # Add implicit FKs through heuristic detection
        if self.enable_heuristic_fk and schema:
            implicit_fks = self._detect_implicit_fks(schema)
            for table, neighbors in implicit_fks.items():
                if table not in enhanced_adjacency:
                    enhanced_adjacency[table] = []
                for neighbor in neighbors:
                    if neighbor not in enhanced_adjacency[table]:
                        enhanced_adjacency[table].append(neighbor)
        
        # Add all direct neighbors (explicit + implicit)
        for table in initial_tables:
            neighbors = enhanced_adjacency.get(table, [])
            candidate_set.update(neighbors)
        
        print(f"[SchemaLinker Step 2] Graph expansion: {len(initial_tables)} -> {len(candidate_set)} tables")
        print(f"[SchemaLinker Step 2] Candidate set: {candidate_set}")
        return candidate_set

    def _get_available_tables(self, schema: str) -> Set[str]:
        """
        Get all available table names from schema.
        
        Args:
            schema: Full schema string
            
        Returns: Set of all table names
        """
        all_tables = self._parse_schema_to_tables(schema)
        return set(all_tables.keys())

    def _apply_table_preferences(self, tables: Set[str], schema: str) -> Set[str]:
        """
        Apply preference rules to select better tables over raw/staging versions.
        
        This implements heuristic-based table selection to prefer:
        - cleaned_ over raw tables
        - processed_ over unprocessed
        - Specific replacements (e.g., weekly_sales -> cleaned_weekly_sales)
        
        Args:
            tables: Set of initially selected table names
            schema: Full schema string (to check availability)
            
        Returns: Set of preferred table names
        """
        available_tables = self._get_available_tables(schema)
        preferred_tables = set(tables)
        
        # Apply specific replacements first (highest priority)
        for raw_table, preferred_table in TABLE_PREFERENCE_RULES['specific_replacements'].items():
            if raw_table in preferred_tables and preferred_table in available_tables:
                print(f"[SchemaLinker] Table preference: {raw_table} -> {preferred_table}")
                preferred_tables.remove(raw_table)
                preferred_tables.add(preferred_table)
        
        # Apply prefix-based preferences
        for table in list(preferred_tables):
            # Check if this table should be replaced by a cleaned version
            for prefix in TABLE_PREFERENCE_RULES['prefer_prefixes']:
                cleaned_version = prefix + table
                if cleaned_version in available_tables:
                    print(f"[SchemaLinker] Table preference: {table} -> {cleaned_version}")
                    preferred_tables.remove(table)
                    preferred_tables.add(cleaned_version)
                    break
        
        # Remove tables with avoid prefixes/suffixes if better alternatives exist
        tables_to_remove = set()
        for table in preferred_tables:
            # Check avoid prefixes
            for prefix in TABLE_PREFERENCE_RULES['avoid_prefixes']:
                if table.startswith(prefix):
                    # Try to find non-prefixed version
                    clean_name = table[len(prefix):]
                    if clean_name in available_tables:
                        print(f"[SchemaLinker] Avoiding {table}, using {clean_name}")
                        tables_to_remove.add(table)
                        preferred_tables.add(clean_name)
                        break
            
            # Check avoid suffixes
            for suffix in TABLE_PREFERENCE_RULES['avoid_suffixes']:
                if table.endswith(suffix):
                    # Try to find non-suffixed version
                    clean_name = table[:-len(suffix)]
                    if clean_name in available_tables:
                        print(f"[SchemaLinker] Avoiding {table}, using {clean_name}")
                        tables_to_remove.add(table)
                        preferred_tables.add(clean_name)
                        break
        
        preferred_tables -= tables_to_remove
        
        return preferred_tables

    def _step3_llm_reranking(self, question: str, candidate_tables: Set[str], schema: str) -> Dict[str, List[str]]:
        """
        Step 3: LLM Reranking - Refine selection to only strictly necessary tables and columns.
        Now returns a dictionary mapping table names to lists of relevant columns (Column Pruning).
        
        Args:
            question: User's question
            candidate_tables: Set of candidate table names from expansion
            schema: Full schema string
            
        Returns: Dictionary mapping selected table names to lists of relevant column names
                 Example: {'orders': ['order_id', 'customer_id', 'total'], 'customers': ['customer_id', 'name']}
        """
        if not candidate_tables:
            return {}
        
        # Apply table preferences BEFORE LLM reranking
        candidate_tables = self._apply_table_preferences(candidate_tables, schema)
        
        # Parse schema to get table descriptions
        all_tables = self._parse_schema_to_tables(schema)
        
        # Build candidate description
        candidate_desc_lines = []
        for table_name in candidate_tables:
            if table_name in all_tables:
                table_data = all_tables[table_name]
                desc = f"- {table_name}"
                
                # Add description from metadata if available
                if self.schema_metadata and table_name in self.schema_metadata:
                    table_meta = self.schema_metadata[table_name]
                    if table_meta.get('description'):
                        desc += f": {table_meta['description']}"
                
                # Add columns preview
                if 'columns_text' in table_data:
                    desc += f" (columns: {table_data['columns_text'][:MAX_PREVIEW_LENGTH]}...)"
                elif table_data.get('columns'):
                    cols_preview = ', '.join(table_data['columns'][:MAX_PREVIEW_COLUMNS])
                    desc += f" (columns: {cols_preview}...)"
                
                candidate_desc_lines.append(desc)
        
        candidate_desc = '\n'.join(candidate_desc_lines)
        
        # Call LLM for reranking with column pruning
        for attempt in range(self.max_retries):
            try:
                response = self.reranking_chain.invoke({
                    "question": question,
                    "candidate_tables": candidate_desc
                })
                result_text = extract_content(response).strip()
                
                # Parse JSON response - try to extract JSON object
                # Handle markdown code blocks
                if '```' in result_text:
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                    if match:
                        result_text = match.group(1)
                
                # Try to parse JSON
                try:
                    selected_data = json.loads(result_text)
                except json.JSONDecodeError:
                    # If direct parse fails, try to extract just the object
                    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_text, re.DOTALL)
                    if match:
                        result_text = match.group(0)
                        selected_data = json.loads(result_text)
                    else:
                        raise
                
                # Validate and filter the result
                if isinstance(selected_data, dict):
                    # Filter to only include tables that were in candidate_tables
                    filtered_result = {}
                    for table, columns in selected_data.items():
                        if table in candidate_tables:
                            if isinstance(columns, list):
                                # Ensure numeric columns are included for aggregations
                                all_table_cols = all_tables.get(table, {}).get('columns', [])
                                
                                # Detect if question involves aggregations
                                aggregation_keywords = ['sum', 'total', 'average', 'avg', 'count', 'max', 'min', 
                                                       'calculate', 'percentage', 'change', 'sales', 'revenue']
                                needs_aggregation = any(kw in question.lower() for kw in aggregation_keywords)
                                
                                if needs_aggregation:
                                    # Find numeric columns in this table
                                    numeric_types = ['INTEGER', 'REAL', 'NUMERIC', 'FLOAT', 'DOUBLE']
                                    numeric_cols = []
                                    for col in all_table_cols:
                                        col_name = col.split('(')[0].strip()
                                        col_type = col.split('(')[1].split(')')[0].strip() if '(' in col else ''
                                        if col_type.upper() in numeric_types:
                                            numeric_cols.append(col_name)
                                    
                                    # Add missing numeric columns
                                    for num_col in numeric_cols:
                                        if num_col not in columns:
                                            columns.append(num_col)
                                            print(f"[SchemaLinker] Added essential numeric column for aggregation: {table}.{num_col}")
                                
                                filtered_result[table] = columns
                            else:
                                # Fallback: if not a list, include all columns
                                if table in all_tables:
                                    filtered_result[table] = all_tables[table].get('columns', [])
                    
                    if filtered_result:
                        print(f"[SchemaLinker Step 3] LLM reranking: {len(candidate_tables)} -> {len(filtered_result)} tables")
                        print(f"[SchemaLinker Step 3] Selected with columns: {filtered_result}")
                        return filtered_result
                    else:
                        # Fallback: return all candidates with all columns
                        print(f"[SchemaLinker Step 3] No valid tables in result, using all candidates")
                        return {t: all_tables.get(t, {}).get('columns', []) for t in candidate_tables if t in all_tables}
                
                # Handle legacy format (list of table names) - for backwards compatibility
                elif isinstance(selected_data, list):
                    print(f"[SchemaLinker Step 3] Legacy format detected, converting to new format")
                    result_dict = {}
                    for table in selected_data:
                        if table in candidate_tables and table in all_tables:
                            result_dict[table] = all_tables[table].get('columns', [])
                    return result_dict if result_dict else {t: all_tables.get(t, {}).get('columns', []) for t in candidate_tables if t in all_tables}
                
            except Exception as e:
                print(f"[SchemaLinker Step 3] LLM reranking failed (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)
        
        # Fallback: return all candidate tables with all columns
        print(f"[SchemaLinker Step 3] LLM reranking failed, using all candidates with all columns")
        return {t: all_tables.get(t, {}).get('columns', []) for t in candidate_tables if t in all_tables}

    def _format_output(self, question: str, selected_data: Dict[str, List[str]], schema: str) -> str:
        """
        Format the output in rich format including relationships and pruned columns.
        
        Args:
            question: User's question
            selected_data: Dictionary mapping table names to lists of relevant columns
            schema: Full schema string
        
        Output format:
        User Question: ...
        Selected Tables:
        1. table_name (description)
           - col1: description
           - col2: description
        [Relationships]
        - table_A.id = table_B.a_id
        """
        all_tables = self._parse_schema_to_tables(schema)
        
        output_lines = [f"User Question: {question}", "", "Selected Tables:"]
        
        # Format each selected table with pruned columns
        for idx, (table_name, selected_columns) in enumerate(sorted(selected_data.items()), 1):
            if table_name not in all_tables:
                continue
            
            table_data = all_tables[table_name]
            
            # Table header with description
            desc = ""
            if self.schema_metadata and table_name in self.schema_metadata:
                desc = self.schema_metadata[table_name].get('description', '')
            
            if desc:
                output_lines.append(f"{idx}. {table_name} ({desc})")
            else:
                output_lines.append(f"{idx}. {table_name}")
            
            # Only show selected columns (Column Pruning)
            if selected_columns:
                if self.schema_metadata and table_name in self.schema_metadata:
                    table_meta = self.schema_metadata[table_name]
                    col_descs = table_meta.get('column_descriptions', {})
                    
                    for col_name in selected_columns:
                        col_desc = col_descs.get(col_name, '')
                        output_lines.append(f"   - {col_name}: {col_desc}")
                else:
                    # Fallback: just list column names
                    output_lines.append(f"   Columns: {', '.join(selected_columns)}")
            else:
                # Fallback to all columns if none selected
                if 'columns_text' in table_data:
                    output_lines.append(f"   Columns: {table_data['columns_text']}")
                elif table_data.get('columns'):
                    output_lines.append(f"   Columns: {', '.join(table_data['columns'])}")
            
            output_lines.append("")
        
        # Add relationships section
        if self.schema_metadata:
            output_lines.append("[Relationships]")
            relationships = []
            
            for table_name in selected_data.keys():
                if table_name in self.schema_metadata:
                    table_meta = self.schema_metadata[table_name]
                    foreign_keys = table_meta.get('foreign_keys', [])
                    
                    for fk in foreign_keys:
                        from_col = fk.get('from', '')
                        to_ref = fk.get('to', '')
                        
                        if '.' in to_ref:
                            ref_table = to_ref.split('.')[0]
                            # Only include if both tables are selected
                            if ref_table in selected_data:
                                relationships.append(f"- {table_name}.{from_col} = {to_ref}")
            
            if relationships:
                output_lines.extend(relationships)
            else:
                output_lines.append("- No explicit foreign key relationships in selected tables")
        
        return '\n'.join(output_lines)

    def link(self, question: str, schema: str, return_format: str = "dict") -> str:
        """
        Main linking method implementing the 3-step process with implicit FK detection and column pruning.
        
        Args:
            question: User's natural language question
            schema: Database schema string
            return_format: "dict" (new format with pruned columns) or "legacy" (backward compatible)
            
        Returns: Linked schema in rich format with pruned columns
        """
        print(f"\n[SchemaLinker] Starting 3-step schema linking process...")
        
        try:
            # Step 1: Initial Retrieval
            initial_tables = self._step1_initial_retrieval(question, schema)
            
            # Step 2: Graph Expansion (with implicit FK detection)
            candidate_tables = self._step2_graph_expansion(initial_tables, schema)
            
            # Step 3: LLM Reranking (with column pruning)
            selected_data = self._step3_llm_reranking(question, candidate_tables, schema)
            
            # Format output with pruned columns
            if selected_data:
                linked_schema = self._format_output(question, selected_data, schema)
            else:
                # Fallback to original schema
                linked_schema = schema
            
            print(f"[SchemaLinker] Linking complete. Selected {len(selected_data)} tables.\n")
            return linked_schema
            
        except Exception as e:
            print(f"[SchemaLinker] Error in schema linking: {e}")
            return schema  # Fallback to full schema
    
    def get_selected_tables_and_columns(self, question: str, schema: str) -> Dict[str, List[str]]:
        """
        Get selected tables and columns as a dictionary (new API).
        
        Args:
            question: User's natural language question
            schema: Database schema string
            
        Returns: Dictionary mapping table names to lists of relevant columns
        """
        try:
            initial_tables = self._step1_initial_retrieval(question, schema)
            candidate_tables = self._step2_graph_expansion(initial_tables, schema)
            selected_data = self._step3_llm_reranking(question, candidate_tables, schema)
            return selected_data
        except Exception as e:
            print(f"[SchemaLinker] Error getting tables and columns: {e}")
            return {}
