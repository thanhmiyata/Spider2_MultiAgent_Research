# Spider 2.0 Multi-Agent Debug Interface

This is a Streamlit-based web interface for debugging and visualizing the Spider 2.0 Multi-Agent SQL generation pipeline.

## Features

### 🎯 Multi-Mode Support
- **Single Agent**: Fast execution using a single LLM call
- **Multi-Agent**: Full pipeline with schema linking, planning, generation, and validation
- **Adaptive**: Automatically selects the best mode based on question complexity

### 🔍 Pipeline Visualization
The interface shows detailed information for each step:
- **Step 0: Domain Knowledge Retrieval** - Searches glossary for business terms
- **Step 1: Schema Linking** - Reduces schema to relevant tables/columns
- **Step 2: Planning** - Creates execution plan
- **Step 3: SQL Generation** - Generates SQL query
- **Step 4: Validation** - Validates and corrects SQL

### 📊 Features
- Real-time timing breakdown for each step
- Intermediate results display
- Domain knowledge injection visualization
- SQL download functionality
- Debug information panel
- Sample schema for quick testing

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
# Create .env file with your API keys
GOOGLE_API_KEY=your_gemini_api_key
CLAUDE_API_KEY=your_anthropic_api_key
```

## Usage

### Running the Interface

```bash
streamlit run app.py
```

The interface will open in your browser at `http://localhost:8501`

### Using the Interface

1. **Select Mode**: Choose between Single Agent, Multi-Agent, or Adaptive
2. **Enable Domain Knowledge**: Toggle to use business term definitions
3. **Enter Question**: Type your natural language question
4. **Provide Schema**: 
   - Use sample schema (checkbox)
   - Paste custom schema
   - Load from database file
5. **Generate SQL**: Click the button to run the pipeline
6. **View Results**: 
   - See generated SQL in the first tab
   - View pipeline steps with timing in the second tab
   - Check detailed timing in the third tab
   - Review debug info in the fourth tab

### Example Questions

With sample schema enabled:
- "What is the retention rate for users in January?"
- "Show the top 10 products by revenue"
- "Calculate the average order value per customer"
- "Find users who placed orders but haven't been active in the last 30 days"

## Domain Knowledge

The system includes a glossary of business terms in `data/glossary.txt`. When enabled:
- System searches for relevant terms in the question
- Injects definitions into planner and generator prompts
- Helps with complex business metrics like:
  - Retention Rate
  - Churn Rate
  - Customer Lifetime Value
  - Average Order Value
  - And more...

## Improvements Implemented

### 1. Implicit Foreign Key Detection
The schema linker now automatically detects relationships between tables based on column names (e.g., `user_id` in different tables), even when not explicitly defined in metadata.

### 2. Column Pruning
The schema linker filters out irrelevant columns to reduce context pollution, keeping only columns needed to answer the question.

### 3. Validator Soft Warning
The validator now distinguishes between SQL errors and valid empty results (e.g., querying for future data), preventing unnecessary retry loops.

## Architecture

```
Question Input
    ↓
[Knowledge Retrieval] → Searches glossary for business terms
    ↓
[Schema Linking] → Reduces schema + detects implicit FKs
    ↓
[Planning] → Creates execution plan (with domain knowledge)
    ↓
[SQL Generation] → Generates SQL (with domain knowledge)
    ↓
[Validation] → Validates and corrects SQL (with soft warnings)
    ↓
Final SQL Output
```

## Tips

1. **For Complex Queries**: Use Multi-Agent mode with Domain Knowledge enabled
2. **For Simple Queries**: Use Single Agent mode for faster results
3. **For Testing**: Use the sample schema with various business questions
4. **For Production**: Load schema from your actual database file

## Troubleshooting

### "Multi-Agent System not available"
- Install all dependencies: `pip install -r requirements.txt`
- Check that API keys are set in `.env`

### "Schema loading failed"
- Verify database file path is correct
- Ensure database is SQLite format
- Check file permissions

### "Generation timed out"
- Increase timeout in `src/config.py`
- Try with a smaller schema
- Check API key quotas

## Development

To extend the interface:
1. Add new tabs in the main interface
2. Modify `MultiAgentSystem.run()` to capture more intermediate data
3. Update pipeline visualization in `app.py`
4. Add new metrics to the timing breakdown

## Credits

Part of the Spider 2.0 Multi-Agent Research project.
