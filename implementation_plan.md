# Implementation Plan - Transition to Spider 1.0

## Goal
Enable the Multi-Agent NL2SQL system to benchmark against the Spider 1.0 dataset.

## User Review Required
> [!IMPORTANT]
> This plan creates a **separate** benchmark script (`benchmark_spider1.py`) instead of modifying the existing `benchmark.py`. This ensures we don't break the existing Spider 2.0 functionality and allows for easy comparison.

## Proposed Changes

### [NEW] `src/benchmark_spider1.py`
Create a new benchmark script specifically for Spider 1.0.
- **Data Loading**: Load `data/spider/dev.json` (standard JSON list) instead of `spider2-lite.jsonl`.
- **Paths**:
    - Dataset: `data/spider/dev.json`
    - Databases: `data/spider/database/`
- **Logic Updates**:
    - Iterate through the JSON list.
    - Extract `db_id`, `question`, and `query` (Gold SQL).
    - Reuse `get_optimized_schema` (compatible with any SQLite DB).
    - Reuse `MultiAgentSystem`, `RouterAgent`, `SingleAgent`.
    - **Inline Evaluation**: Since Gold SQL is present in the dataset, perform execution evaluation immediately after generation using `evaluate_sql_pair`.

## Verification Plan

### Automated Tests
1. **Quick Smoke Test**:
   ```bash
   python src/benchmark_spider1.py --max-items 1
   ```
   *Verify that the script runs without errors and produces a result.*

2. **Single Agent Test**:
   ```bash
   python src/benchmark_spider1.py --mode single --max-items 5
   ```
   *Verify Single Agent performance on Spider 1.0.*

3. **Adaptive Mode Test**:
   ```bash
   python src/benchmark_spider1.py --mode adaptive --max-items 5
   ```
   *Verify Router and Multi-Agent flow on Spider 1.0.*
