# Tests Directory

This directory contains evaluation and testing scripts for the Spider 2.0 Lite Multi-Agent System.

## Files

### `evaluate_spider_lite.py`

**Purpose**: Evaluate system accuracy using execution accuracy methodology.

**Key Features**:
- Loads questions from spider2-lite.jsonl
- Compares generated SQL with gold SQL by executing both
- Uses sorted set comparison to avoid order-based mismatches
- Generates failure analysis CSV with detailed error information
- Provides comprehensive accuracy metrics

**Usage**:
```bash
# Basic usage (auto-detects results file)
python evaluate_spider_lite.py

# With specific results file
python evaluate_spider_lite.py --results ../experiments/main_workflow/results.jsonl

# Without failure analysis export
python evaluate_spider_lite.py --results <path> --no-failures
```

**Output**:
- Console: Accuracy metrics and error breakdown
- CSV: `experiments/evaluation/failure_analysis_<timestamp>.csv`

## Running Tests

```bash
cd tests
python evaluate_spider_lite.py --results ../experiments/main_workflow/results.jsonl
```

## See Also

- [Phase 3 Tasks 5 & 6 Guide](../docs/PHASE3_TASKS_5_6_GUIDE.md) - Detailed usage guide
- [Main README](../README.md) - Project overview
