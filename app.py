"""
Debug Interface for Spider 2.0 Multi-Agent System using Streamlit.

This interface provides visualization and debugging capabilities for the multi-agent pipeline.
"""

import streamlit as st
import time
import json
from pathlib import Path
import sys

# Add src to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from agents.multi_agent_flow import MultiAgentSystem
    from agents.single_agent import SingleAgent
    from utils.db_utils import get_schema_from_db
    MAS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import agents: {e}")
    MAS_AVAILABLE = False


st.set_page_config(
    page_title="Spider 2.0 Multi-Agent Debugger",
    page_icon="🕷️",
    layout="wide"
)

st.title("🕷️ Spider 2.0 Multi-Agent SQL Generator")
st.markdown("---")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    mode = st.selectbox(
        "Select Mode",
        ["Single Agent", "Multi-Agent", "Adaptive"],
        help="Choose execution mode"
    )
    
    enable_knowledge = st.checkbox(
        "Enable Domain Knowledge",
        value=True,
        help="Use knowledge retriever for business terms"
    )
    
    verbose = st.checkbox(
        "Verbose Output",
        value=True,
        help="Show detailed timing and intermediate results"
    )
    
    st.markdown("---")
    st.header("📊 Database")
    
    db_path = st.text_input(
        "Database Path",
        placeholder="e.g., data/spider2_lite/resource/databases/sqlite/E_commerce/E_commerce.sqlite"
    )
    
    use_sample_schema = st.checkbox(
        "Use Sample Schema",
        value=True,
        help="Use predefined sample schema for testing"
    )

# Main interface
col1, col2 = st.columns([1, 1])

with col1:
    st.header("💬 Question Input")
    
    question = st.text_area(
        "Enter your natural language question:",
        height=100,
        placeholder="e.g., What is the retention rate for users in January?"
    )
    
    if use_sample_schema:
        schema = """
Table: users
Columns: user_id (INTEGER), username (TEXT), email (TEXT), created_at (TIMESTAMP)

Table: user_activity
Columns: activity_id (INTEGER), user_id (INTEGER), activity_type (TEXT), activity_date (DATE)

Table: orders
Columns: order_id (INTEGER), user_id (INTEGER), order_date (DATE), total_amount (REAL)

Table: order_items
Columns: item_id (INTEGER), order_id (INTEGER), product_id (INTEGER), quantity (INTEGER), price (REAL)

Table: products
Columns: product_id (INTEGER), product_name (TEXT), category (TEXT), price (REAL)
"""
    else:
        schema = st.text_area(
            "Database Schema:",
            height=200,
            placeholder="Enter schema or load from database",
            value=""
        )
        
        if db_path and st.button("Load Schema from Database"):
            try:
                schema_dict = get_schema_from_db(db_path)
                schema_lines = []
                for table, columns in schema_dict.items():
                    schema_lines.append(f"Table: {table}")
                    schema_lines.append(f"Columns: {', '.join(columns)}")
                    schema_lines.append("")
                schema = "\n".join(schema_lines)
                st.success("Schema loaded successfully!")
            except Exception as e:
                st.error(f"Error loading schema: {e}")
    
    generate_button = st.button("🚀 Generate SQL", type="primary")

with col2:
    st.header("📝 Generated SQL")
    
    if not MAS_AVAILABLE:
        st.error("Multi-Agent System not available. Please install dependencies.")
        st.stop()
    
    if generate_button:
        if not question:
            st.warning("Please enter a question.")
        elif not schema:
            st.warning("Please provide a database schema.")
        else:
            with st.spinner("Generating SQL..."):
                start_time = time.time()
                
                # Create tabs for different views
                tabs = st.tabs(["SQL Result", "Pipeline Steps", "Timing", "Debug Info"])
                
                try:
                    if mode == "Multi-Agent":
                        mas = MultiAgentSystem(enable_knowledge_retrieval=enable_knowledge)
                        
                        # Capture intermediate results
                        with tabs[1]:
                            st.subheader("Pipeline Execution")
                            
                            # Step 0: Knowledge Retrieval
                            if enable_knowledge and mas.knowledge_retriever:
                                with st.expander("Step 0: Domain Knowledge Retrieval", expanded=True):
                                    step_start = time.time()
                                    knowledge = mas.knowledge_retriever.retrieve_and_inject(question)
                                    step_time = time.time() - step_start
                                    
                                    if knowledge:
                                        st.success(f"Found domain knowledge ({step_time:.2f}s)")
                                        st.code(knowledge, language="text")
                                    else:
                                        st.info(f"No domain knowledge found ({step_time:.2f}s)")
                            
                            # Step 1: Schema Linking
                            with st.expander("Step 1: Schema Linking", expanded=True):
                                step_start = time.time()
                                linked_schema = mas.linker.link(question, schema)
                                step_time = time.time() - step_start
                                
                                st.success(f"Schema linked ({step_time:.2f}s)")
                                st.text_area("Linked Schema", linked_schema, height=150)
                            
                            # Step 2: Planning
                            with st.expander("Step 2: Planning", expanded=True):
                                step_start = time.time()
                                if enable_knowledge and mas.knowledge_retriever:
                                    knowledge = mas.knowledge_retriever.retrieve_and_inject(question)
                                    enhanced_q = f"{question}\n\n{knowledge}" if knowledge else question
                                    plan = mas.planner.plan(enhanced_q, linked_schema)
                                else:
                                    plan = mas.planner.plan(question, linked_schema)
                                step_time = time.time() - step_start
                                
                                st.success(f"Plan created ({step_time:.2f}s)")
                                st.text_area("Execution Plan", plan, height=150)
                            
                            # Step 3: Generation
                            with st.expander("Step 3: SQL Generation", expanded=True):
                                step_start = time.time()
                                if enable_knowledge and mas.knowledge_retriever:
                                    knowledge = mas.knowledge_retriever.retrieve_and_inject(question)
                                    enhanced_q = f"{question}\n\n{knowledge}" if knowledge else question
                                    sql = mas.generator.generate(enhanced_q, linked_schema, plan)
                                else:
                                    sql = mas.generator.generate(question, linked_schema, plan)
                                step_time = time.time() - step_start
                                
                                st.success(f"SQL generated ({step_time:.2f}s)")
                                st.code(sql, language="sql")
                            
                            # Step 4: Validation
                            with st.expander("Step 4: Validation", expanded=True):
                                step_start = time.time()
                                final_sql = mas.validator.validate(question, linked_schema, sql)
                                step_time = time.time() - step_start
                                
                                if final_sql == sql:
                                    st.success(f"SQL validated - no changes needed ({step_time:.2f}s)")
                                else:
                                    st.warning(f"SQL corrected ({step_time:.2f}s)")
                                st.code(final_sql, language="sql")
                        
                        # Generate full SQL with verbose=False for clean result
                        sql_result = mas.run(question, schema, verbose=False)
                        
                    elif mode == "Single Agent":
                        agent = SingleAgent()
                        sql_result = agent.run(question, schema)
                    
                    else:  # Adaptive mode
                        st.info("Adaptive mode not yet implemented. Using Multi-Agent.")
                        mas = MultiAgentSystem(enable_knowledge_retrieval=enable_knowledge)
                        sql_result = mas.run(question, schema, verbose=False)
                    
                    total_time = time.time() - start_time
                    
                    # Display final SQL in first tab
                    with tabs[0]:
                        st.code(sql_result, language="sql")
                        st.download_button(
                            "📥 Download SQL",
                            sql_result,
                            file_name="generated_query.sql",
                            mime="text/plain"
                        )
                    
                    # Display timing in third tab
                    with tabs[2]:
                        st.metric("Total Time", f"{total_time:.2f}s")
                        st.info("See 'Pipeline Steps' tab for detailed timing breakdown")
                    
                    # Display debug info in fourth tab
                    with tabs[3]:
                        st.subheader("Configuration")
                        st.json({
                            "mode": mode,
                            "enable_knowledge": enable_knowledge,
                            "verbose": verbose,
                            "question_length": len(question),
                            "schema_length": len(schema),
                            "result_length": len(sql_result)
                        })
                        
                        st.subheader("Question Analysis")
                        st.write(f"- Question length: {len(question)} characters")
                        st.write(f"- Word count: {len(question.split())}")
                        
                        # Detect keywords
                        keywords = []
                        if any(word in question.lower() for word in ['retention', 'churn', 'lifetime']):
                            keywords.append("Business Metrics")
                        if any(word in question.lower() for word in ['join', 'combine', 'with']):
                            keywords.append("Multiple Tables")
                        if any(word in question.lower() for word in ['average', 'sum', 'count', 'max', 'min']):
                            keywords.append("Aggregation")
                        
                        if keywords:
                            st.write(f"- Detected patterns: {', '.join(keywords)}")
                
                except Exception as e:
                    st.error(f"Error generating SQL: {e}")
                    st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
### 📚 Usage Tips
1. **Single Agent**: Fast, suitable for simple queries
2. **Multi-Agent**: More accurate, uses full pipeline with schema linking, planning, generation, and validation
3. **Adaptive**: Automatically chooses between Single and Multi-Agent based on question complexity

**Domain Knowledge**: When enabled, the system will search for business term definitions (e.g., Retention Rate, Churn Rate) 
and inject them into the prompts to improve accuracy.
""")
