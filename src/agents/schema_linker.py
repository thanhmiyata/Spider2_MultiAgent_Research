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
                 metadata_path: Optional[str] = None, expansion_enabled=True):
        """
        Initialize SchemaLinker with optional metadata loading.
        
        Args:
            model_name: LLM model to use for reranking
            max_retries: Number of retries for LLM calls
            use_rag: Enable TF-IDF based retrieval
            top_k: Number of initial tables to retrieve
            metadata_path: Path to tables.json with foreign key information
            expansion_enabled: Enable graph expansion step
        """
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.use_rag = use_rag and SKLEARN_AVAILABLE
        self.top_k = top_k
        self.expansion_enabled = expansion_enabled
        
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
        
        # LLM Reranking Prompt
        self.reranking_prompt = PromptTemplate(
            input_variables=["question", "candidate_tables"],
            template="""
            You are a database expert. Given a user question and a list of candidate tables with descriptions,
            select ONLY the tables that are strictly necessary to answer the question.
            
            User Question: {question}
            
            Candidate Tables:
            {candidate_tables}
            
            Instructions:
            - Select ONLY tables that are directly needed to answer the question
            - Consider JOIN paths - if tables need to be joined, include intermediate tables
            - Return ONLY a JSON list of table names, nothing else
            
            Example output: ["orders", "customers", "order_items"]
            
            Output (JSON list only):
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
            
            # Alternative schema format: CREATE TABLE
            elif line.startswith('CREATE TABLE'):
                match = re.search(r'CREATE TABLE\s+`?(\w+)`?', line, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    current_table = table_name
                    tables[current_table] = {'columns': [], 'text': table_name}
            
            # Extract column from CREATE TABLE format
            elif current_table and '`' in line:
                match = re.search(r'`(\w+)`\s+(\w+)', line)
                if match:
                    col_name = match.group(1)
                    col_type = match.group(2)
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
            return set(tables.keys())
        
        tables = self._parse_schema_to_tables(schema)
        
        if not tables or len(tables) <= self.top_k:
            return set(tables.keys())
        
        try:
            # Prepare documents: question + all table texts
            table_names = list(tables.keys())
            table_texts = [tables[name]['text'] for name in table_names]
            
            # Create TF-IDF matrix
            all_docs = [question] + table_texts
            tfidf_matrix = self.vectorizer.fit_transform(all_docs)
            
            # Calculate cosine similarity between question and each table
            question_vector = tfidf_matrix[0:1]
            table_vectors = tfidf_matrix[1:]
            similarities = cosine_similarity(question_vector, table_vectors)[0]
            
            # Get top-k table indices
            top_indices = np.argsort(similarities)[-self.top_k:][::-1]
            initial_set = {table_names[i] for i in top_indices}
            
            print(f"[SchemaLinker Step 1] Initial retrieval selected {len(initial_set)} tables: {initial_set}")
            return initial_set
            
        except Exception as e:
            print(f"[SchemaLinker Step 1] TF-IDF retrieval failed: {e}, using all tables")
            return set(tables.keys())

    def _step2_graph_expansion(self, initial_tables: Set[str]) -> Set[str]:
        """
        Step 2: Graph Expansion - Add neighboring tables via foreign key relationships.
        
        Args:
            initial_tables: Set of initially selected tables
            
        Returns: Expanded set of candidate tables (initial + neighbors)
        """
        if not self.expansion_enabled or not self.adjacency_list:
            print(f"[SchemaLinker Step 2] Graph expansion disabled or no adjacency list available")
            return initial_tables
        
        candidate_set = set(initial_tables)
        
        # Add all direct neighbors
        for table in initial_tables:
            neighbors = self.adjacency_list.get(table, [])
            candidate_set.update(neighbors)
        
        print(f"[SchemaLinker Step 2] Graph expansion: {len(initial_tables)} -> {len(candidate_set)} tables")
        print(f"[SchemaLinker Step 2] Candidate set: {candidate_set}")
        return candidate_set

    def _step3_llm_reranking(self, question: str, candidate_tables: Set[str], schema: str) -> Set[str]:
        """
        Step 3: LLM Reranking - Refine selection to only strictly necessary tables.
        
        Args:
            question: User's question
            candidate_tables: Set of candidate table names from expansion
            schema: Full schema string
            
        Returns: Refined set of selected table names
        """
        if not candidate_tables:
            return candidate_tables
        
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
        
        # Call LLM for reranking
        for attempt in range(self.max_retries):
            try:
                response = self.reranking_chain.invoke({
                    "question": question,
                    "candidate_tables": candidate_desc
                })
                result_text = extract_content(response).strip()
                
                # Parse JSON response - try to extract JSON array
                # Handle markdown code blocks
                if '```' in result_text:
                    match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', result_text, re.DOTALL)
                    if match:
                        result_text = match.group(1)
                
                # Try to parse JSON
                try:
                    selected_tables = json.loads(result_text)
                except json.JSONDecodeError:
                    # If direct parse fails, try to extract just the array
                    match = re.search(r'\[([^\[\]]+)\]', result_text)
                    if match:
                        result_text = '[' + match.group(1) + ']'
                        selected_tables = json.loads(result_text)
                    else:
                        raise
                
                if isinstance(selected_tables, list):
                    selected_set = {t for t in selected_tables if t in candidate_tables}
                    print(f"[SchemaLinker Step 3] LLM reranking: {len(candidate_tables)} -> {len(selected_set)} tables")
                    print(f"[SchemaLinker Step 3] Selected: {selected_set}")
                    return selected_set if selected_set else candidate_tables
                
            except Exception as e:
                print(f"[SchemaLinker Step 3] LLM reranking failed (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)
        
        # Fallback: return all candidate tables
        print(f"[SchemaLinker Step 3] LLM reranking failed, using all candidates")
        return candidate_tables

    def _format_output(self, question: str, selected_tables: Set[str], schema: str) -> str:
        """
        Format the output in rich format including relationships.
        
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
        
        # Format each selected table
        for idx, table_name in enumerate(sorted(selected_tables), 1):
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
            
            # Columns with descriptions
            if self.schema_metadata and table_name in self.schema_metadata:
                table_meta = self.schema_metadata[table_name]
                col_descs = table_meta.get('column_descriptions', {})
                
                for col_name in table_meta.get('columns', []):
                    col_desc = col_descs.get(col_name, '')
                    output_lines.append(f"   - {col_name}: {col_desc}")
            else:
                # Fallback to parsed columns
                if 'columns_text' in table_data:
                    output_lines.append(f"   Columns: {table_data['columns_text']}")
                elif table_data.get('columns'):
                    output_lines.append(f"   Columns: {', '.join(table_data['columns'])}")
            
            output_lines.append("")
        
        # Add relationships section
        if self.schema_metadata:
            output_lines.append("[Relationships]")
            relationships = []
            
            for table_name in selected_tables:
                if table_name in self.schema_metadata:
                    table_meta = self.schema_metadata[table_name]
                    foreign_keys = table_meta.get('foreign_keys', [])
                    
                    for fk in foreign_keys:
                        from_col = fk.get('from', '')
                        to_ref = fk.get('to', '')
                        
                        if '.' in to_ref:
                            ref_table = to_ref.split('.')[0]
                            # Only include if both tables are selected
                            if ref_table in selected_tables:
                                relationships.append(f"- {table_name}.{from_col} = {to_ref}")
            
            if relationships:
                output_lines.extend(relationships)
            else:
                output_lines.append("- No explicit foreign key relationships in selected tables")
        
        return '\n'.join(output_lines)

    def link(self, question: str, schema: str) -> str:
        """
        Main linking method implementing the 3-step process.
        
        Args:
            question: User's natural language question
            schema: Database schema string
            
        Returns: Linked schema in rich format
        """
        print(f"\n[SchemaLinker] Starting 3-step schema linking process...")
        
        try:
            # Step 1: Initial Retrieval
            initial_tables = self._step1_initial_retrieval(question, schema)
            
            # Step 2: Graph Expansion
            candidate_tables = self._step2_graph_expansion(initial_tables)
            
            # Step 3: LLM Reranking
            selected_tables = self._step3_llm_reranking(question, candidate_tables, schema)
            
            # Format output
            if selected_tables:
                linked_schema = self._format_output(question, selected_tables, schema)
            else:
                # Fallback to original schema
                linked_schema = schema
            
            print(f"[SchemaLinker] Linking complete. Selected {len(selected_tables)} tables.\n")
            return linked_schema
            
        except Exception as e:
            print(f"[SchemaLinker] Error in schema linking: {e}")
            return schema  # Fallback to full schema
