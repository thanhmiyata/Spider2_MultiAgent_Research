import time
import re
import numpy as np
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

class SchemaLinker:
    def __init__(self, model_name=CLAUDE_MODEL, max_retries=2, use_rag=True, top_k=5):
        self.llm = get_llm(model_name=model_name, temperature=0, timeout=30)
        self.max_retries = max_retries
        self.use_rag = use_rag and SKLEARN_AVAILABLE  # Disable RAG if sklearn not available
        self.top_k = top_k
        
        if use_rag and not SKLEARN_AVAILABLE:
            print("Warning: RAG requested but scikit-learn not available. RAG disabled.")
        
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
        else:
            self.vectorizer = None
            
        self.prompt = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            You are an expert database architect specializing in schema analysis for SQL generation.
            Your task is to identify ONLY the relevant tables and columns from the given schema that are needed to answer the user's question.
            
            CRITICAL RULES:
            1. **Minimal Selection**: Only include tables and columns that are DIRECTLY needed for:
               - SELECT clause (columns to return)
               - WHERE clause (filtering conditions)
               - JOIN conditions (foreign keys)
               - GROUP BY / ORDER BY clauses
               - Aggregations and calculations
            
            2. **Always Include Keys**: For ANY table you select, ALWAYS include:
               - Primary Key (usually `id` or `{{table_name}}_id`)
               - Foreign Keys (to enable JOINs with other selected tables)
               - Even if not mentioned in the question, keys are essential for JOINs
            
            3. **Time-Related Columns**: If the question mentions:
               - Dates, years, months, days → Include ALL date/time columns
               - "recent", "last", "first", "since" → Include timestamp columns
               - Duration, period → Include start/end date columns
            
            4. **Data Types**: Include data types for all columns in format: `column_name (TYPE)`
            
            5. **Table Relationships**: If you select multiple tables, ensure they can be joined via foreign keys.
            
            Schema:
            {schema}

            Question: {question}

            Output Format (EXACTLY):
            Table: {{table_name}}
            Columns: col1 (TYPE), col2 (TYPE), col3 (TYPE)
            
            Table: {{another_table}}
            Columns: col1 (TYPE), col2 (TYPE)
            
            Return ONLY the relevant schema subset in the format above. No explanations, no markdown.
            """
        )
        self.chain = self.prompt | self.llm

    def _parse_schema_to_tables(self, schema: str) -> dict:
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
                # Store both as string (for text) and parse into list for later use
                tables[current_table]['columns_text'] = columns_text
                tables[current_table]['columns'] = [col.strip() for col in columns_text.split(',')]
                # Create searchable text: table name + column names
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

    def _select_top_k_tables_with_tfidf(self, question: str, schema: str) -> str:
        """
        Use TF-IDF to select top-k most relevant tables based on question.
        Returns: Filtered schema containing only top-k relevant tables.
        """
        # Parse schema into tables
        tables = self._parse_schema_to_tables(schema)
        
        if not tables:
            return schema  # Fallback if parsing fails
        
        # If we have fewer tables than top_k, return all
        if len(tables) <= self.top_k:
            return schema
        
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
            top_tables = [table_names[i] for i in top_indices]
            
            # Reconstruct schema with only top-k tables
            filtered_schema = ""
            for table_name in top_tables:
                filtered_schema += f"Table: {table_name}\n"
                # Use the original columns_text if available, otherwise join the list
                if 'columns_text' in tables[table_name]:
                    filtered_schema += f"Columns: {tables[table_name]['columns_text']}\n\n"
                elif tables[table_name]['columns']:
                    filtered_schema += f"Columns: {', '.join(tables[table_name]['columns'])}\n\n"
            
            return filtered_schema.strip()
            
        except Exception as e:
            print(f"[SchemaLinker] TF-IDF selection failed: {e}")
            return schema  # Fallback to full schema

    def link(self, question: str, schema: str) -> str:
        """Returns the relevant schema subset with RAG-based filtering and retry logic."""
        
        # Apply TF-IDF filtering if enabled
        if self.use_rag:
            schema = self._select_top_k_tables_with_tfidf(question, schema)
        
        for attempt in range(self.max_retries):
            try:
                response = self.chain.invoke({"question": question, "schema": schema})
                linked_schema = extract_content(response)
                
                # Basic validation: check if we got something meaningful
                if len(linked_schema.strip()) < 10:
                    if attempt < self.max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return schema  # Fallback to full schema
                
                return linked_schema
                
            except Exception as e:
                print(f"[SchemaLinker] Error in schema linking (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)  # Fixed wait time instead of exponential
                else:
                    return schema  # Fallback to full schema
        
        return schema  # Final fallback
