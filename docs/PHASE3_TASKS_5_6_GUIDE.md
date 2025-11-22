# Phase 3 Usage Guide: Main Workflow and Evaluation

## Overview

This guide covers the usage of the newly implemented Task 5 (Main Workflow) and Task 6 (Evaluation Script) for the Spider 2.0 Lite Multi-Agent System.

## Task 5: Main Workflow (`src/main.py`)

### Description

The main workflow script implements a complete router-based adaptive multi-agent system:

- **Router Agent**: Classifies questions as EASY, MEDIUM, or HARD
- **Easy Path**: Router → Schema Linker → Generator → Validator (skips Planner)
- **Hard Path**: Router → Schema Linker → Planner → Generator → Validator (full pipeline)

### Features

- ✅ Clear terminal-visible logs showing each step's progress
- ✅ Detailed timing breakdown for performance analysis
- ✅ SQL preview and intermediate results display
- ✅ Error handling with fallback mechanisms
- ✅ Configurable test size via command-line arguments

### Usage

```bash
cd src

# Run with default (5 questions)
python main.py

# Run with custom number of questions
python main.py --max-items 10

# Run full evaluation
python main.py --max-items 100
```

### Expected Output

```
================================================================================
[INITIALIZATION] Loading Multi-Agent System...
================================================================================
[INITIALIZATION] ✓ All agents loaded successfully

================================================================================
[MAIN] Processing Question: How many distinct pseudo users had positive...
================================================================================

[STEP 1: ROUTER] Analyzing question complexity...
[ROUTER] ✓ Classification: HARD
[ROUTER] ⏱️  Time: 2.15s

[WORKFLOW] Selected: HARD PATH (Schema Linker → Planner → Generator → Validator)

[STEP 2: SCHEMA LINKER] Filtering relevant tables and columns...
[SCHEMA LINKER] ✓ Filtered schema (450 chars)
[SCHEMA LINKER] ⏱️  Time: 3.21s

[STEP 3: PLANNER] Creating execution plan...
[PLANNER] ✓ Plan Created (280 chars)
[PLANNER] ⏱️  Time: 8.54s
[PLANNER] Plan Preview: 1. Filter events table for engagement_time_msec > 0...

[STEP 4: GENERATOR] Generating SQL based on plan...
[GENERATOR] ✓ SQL Generated (320 chars)
[GENERATOR] ⏱️  Time: 5.62s
[GENERATOR] SQL Preview: SELECT COUNT(DISTINCT user_pseudo_id) FROM events WHERE...

[FINAL STEP: VALIDATOR] Validating and correcting SQL...
[VALIDATOR] ✓ SQL Validated
[VALIDATOR] ⏱️  Time: 2.77s
[VALIDATOR] Final SQL: SELECT COUNT(DISTINCT user_pseudo_id) FROM events WHERE...

================================================================================
[TIMING SUMMARY]
================================================================================
Router:        2.15s
Schema Linker: 3.21s
Planner:       8.54s
Generator:     5.62s
Validator:     2.77s
================================================================================
TOTAL:         22.29s
================================================================================
```

### Output Files

- **Location**: `experiments/main_workflow/results.jsonl`
- **Format**: One JSON object per line containing:
  - `instance_id`: Question identifier
  - `question`: Natural language question
  - `db_id`: Database identifier
  - `generated_sql`: Final SQL query
  - `complexity`: Router classification (EASY/MEDIUM/HARD)
  - `agent_used`: Which path was taken (easy_path/hard_path)
  - `latency`: Total processing time
  - `step_times`: Breakdown of timing for each step

---

## Task 6: Evaluation Script (`tests/evaluate_spider_lite.py`)

### Description

The evaluation script assesses system accuracy using execution accuracy methodology:

1. Loads questions from `spider2-lite.jsonl`
2. Loads gold SQL from `evaluation_suite/gold/sql/`
3. Executes both predicted and gold SQL on SQLite databases
4. Compares results using sorted set comparison
5. Calculates accuracy and generates failure analysis

### Features

- ✅ Execution accuracy comparison (not just SQL text matching)
- ✅ Proper result sorting to avoid order-based mismatches
- ✅ Comprehensive error categorization
- ✅ Failure analysis CSV export
- ✅ Auto-detection of results files

### Usage

```bash
cd tests

# Evaluate specific results file
python evaluate_spider_lite.py --results ../experiments/main_workflow/results.jsonl

# Auto-detect latest results
python evaluate_spider_lite.py

# Disable failure analysis export
python evaluate_spider_lite.py --results <path> --no-failures
```

### Expected Output

```
================================================================================
[EVALUATION] Spider 2.0 Lite Evaluation
================================================================================
[DATA] Loading dataset from data/spider2_lite/spider2-lite.jsonl...
[DATA] ✓ Loaded 547 questions
[DATA] Loading results from experiments/main_workflow/results.jsonl...
[DATA] ✓ Loaded 5 results

[EVALUATION] Processing results...
Evaluating: 100%|████████████████████████████████| 5/5 [00:01<00:00,  3.21it/s]

================================================================================
[RESULTS] Evaluation Summary
================================================================================
Total Evaluated:    5
Correct:            3
Incorrect:          2
Accuracy:           60.00%

Error Breakdown:
  Empty SQL:         0
  Syntax Errors:     1
  Execution Errors:  0
  Result Mismatches: 1

Skipped (Not Counted):
  No Gold SQL:       0
  No Database:       0
================================================================================

[OUTPUT] Saving failure analysis to experiments/evaluation/failure_analysis_20251122_150645.csv...
[OUTPUT] ✓ Saved 2 failure cases

[SUCCESS] Evaluation complete!
```

### Output Files

1. **Failure Analysis CSV**: `experiments/evaluation/failure_analysis_<timestamp>.csv`
   - Contains all mismatched cases with:
     - `instance_id`: Question identifier
     - `question`: Natural language question
     - `db_id`: Database identifier
     - `generated_sql`: Predicted SQL
     - `gold_sql`: Gold standard SQL
     - `error_type`: Category of error (syntax_error, execution_error, result_mismatch)
     - `error_message`: Detailed error message

### Error Types

- **empty_sql**: No SQL was generated
- **syntax_error**: SQL has syntax errors
- **execution_error**: SQL failed during execution
- **result_mismatch**: SQL executed but results differ from gold standard
- **no_gold_sql**: No gold SQL available (skipped)
- **no_database**: Database not available (skipped)

---

## Complete Workflow Example

Here's how to run a complete end-to-end evaluation:

```bash
# Step 1: Run main workflow to generate predictions
cd src
python main.py --max-items 10

# Step 2: Evaluate the results
cd ../tests
python evaluate_spider_lite.py --results ../experiments/main_workflow/results.jsonl

# Step 3: Review failure analysis
cat ../experiments/evaluation/failure_analysis_*.csv
```

---

## Integration with Existing Scripts

The new scripts integrate seamlessly with existing tools:

### Using with benchmark.py

```bash
# Generate results using benchmark
cd src
python benchmark.py --mode adaptive --max-items 10

# Evaluate using the new evaluation script
cd ../tests
python evaluate_spider_lite.py --results ../experiments/benchmark/adaptive_results_*.jsonl
```

### Using with existing evaluate.py

Both evaluation scripts can coexist. The new `evaluate_spider_lite.py` in `tests/` focuses on pure execution accuracy, while `src/evaluate.py` provides additional metrics and comparisons.

---

## Performance Notes

- **Main Workflow**: ~20-25 seconds per question with optimized settings
- **Evaluation**: ~3-5 questions per second (depends on SQL complexity)
- **Recommended Batch Size**: Start with 5-10 questions for testing, scale to full dataset

---

## Troubleshooting

### Issue: API Keys Not Found

**Solution**: Ensure `.env` file exists with:
```
GOOGLE_API_KEY=your_key_here
CLAUDE_API_KEY=your_key_here
```

### Issue: Module Not Found

**Solution**: Install requirements:
```bash
pip install -r requirements.txt
```

### Issue: Database Not Found

**Solution**: Ensure SQLite databases are in:
```
data/spider2_lite/resource/databases/sqlite/
```

### Issue: Gold SQL Not Found

**Solution**: Ensure gold SQL files are in:
```
data/spider2_lite/evaluation_suite/gold/sql/
```

---

## Future Enhancements

Potential improvements for these scripts:

1. **Parallel Processing**: Process multiple questions simultaneously
2. **Caching**: Cache schema and routing decisions
3. **Streaming Output**: Real-time progress updates
4. **HTML Reports**: Generate visual evaluation reports
5. **Comparison Mode**: Compare multiple runs side-by-side

---

## Summary

✅ **Task 5 Complete**: Main workflow with router-based adaptive system and detailed logging
✅ **Task 6 Complete**: Evaluation script with execution accuracy and failure analysis

Both scripts are production-ready and provide clear, actionable feedback for system improvement.
