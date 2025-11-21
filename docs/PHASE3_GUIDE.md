# Phase 3: Benchmark & Optimization Guide

## Tổng quan

Phase 3 tập trung vào việc chạy benchmark đầy đủ, tối ưu hóa hệ thống, và so sánh kết quả giữa các phương pháp.

## Các cải tiến đã thực hiện

### 1. Cải thiện Prompts
- **Router Agent**: Prompts chi tiết hơn với examples cụ thể
- **Schema Linker**: Hướng dẫn rõ ràng về việc chọn columns và keys
- **Planner**: Cấu trúc planning rõ ràng với các bước cụ thể
- **Generator**: Rules nghiêm ngặt về aliases và column qualification
- **Validator**: Iterative validation với self-correction

### 2. Error Handling & Retry Logic
- Tất cả agents đều có retry logic (max 3 lần)
- Exponential backoff cho retries
- Fallback mechanisms khi agents fail
- Better error messages và logging

### 3. Scripts mới

#### `benchmark.py` - Chạy benchmark đầy đủ
```bash
# Chạy adaptive mode (recommended)
python src/benchmark.py --mode adaptive

# Chạy single agent baseline
python src/benchmark.py --mode single

# Chạy multi-agent only
python src/benchmark.py --mode multi

# Test với số lượng giới hạn
python src/benchmark.py --mode adaptive --max-items 10
```

#### `evaluate.py` - Đánh giá kết quả chi tiết
```bash
# Đánh giá kết quả
python src/evaluate.py --results experiments/benchmark/adaptive_results_*.jsonl

# Chỉ định output directory
python src/evaluate.py --results <file> --output-dir experiments/evaluation
```

#### `compare_results.py` - So sánh các phương pháp
```bash
# So sánh baseline vs multi-agent vs adaptive
python src/compare_results.py \
    --baseline experiments/baseline/results.jsonl \
    --multi-agent experiments/multi_agent/results.jsonl \
    --adaptive experiments/benchmark/adaptive_results_*.jsonl
```

## Workflow đề xuất

### Bước 1: Pre-Benchmark Verification (Quan trọng)
Để đảm bảo data integrity và tránh lỗi "no such table" trên tập dữ liệu lớn:
1. Chọn 1 Database có số lượng câu hỏi lớn (> 50).
2. Random 5 câu hỏi từ Database này.
3. Chạy thử nghiệm để verify pipeline:
```bash
# Chạy test trên 1 DB cụ thể với 5 câu hỏi ngẫu nhiên
python src/benchmark.py --mode adaptive --db-id <selected_db> --random 5
```

### Bước 2: Chạy Baseline
```bash
cd src
python main.py  # Chạy single agent baseline
```

### Bước 2: Chạy Multi-Agent Benchmark
```bash
python benchmark.py --mode multi --max-items 50  # Test với 50 items
python benchmark.py --mode multi  # Chạy full dataset
```

### Bước 3: Chạy Adaptive Benchmark
```bash
python benchmark.py --mode adaptive --max-items 50  # Test
python benchmark.py --mode adaptive  # Full dataset
```

### Bước 4: Đánh giá kết quả
```bash
# Đánh giá từng phương pháp
python evaluate.py --results experiments/baseline/results.jsonl
python evaluate.py --results experiments/benchmark/multi_results_*.jsonl
python evaluate.py --results experiments/benchmark/adaptive_results_*.jsonl
```

### Bước 5: So sánh
```bash
python compare_results.py \
    --baseline experiments/baseline/results.jsonl \
    --multi-agent experiments/benchmark/multi_results_*.jsonl \
    --adaptive experiments/benchmark/adaptive_results_*.jsonl
```

## Metrics được track

### Execution Metrics
- **Accuracy**: Tỷ lệ SQL đúng (execution result match)
- **By Complexity**: Accuracy theo EASY/MEDIUM/HARD
- **By Agent**: Accuracy của Single Agent vs Multi-Agent

### Error Analysis
- **Empty SQL**: Số lượng SQL rỗng
- **Syntax Errors**: Lỗi cú pháp
- **Execution Errors**: Lỗi khi chạy SQL

### Performance Metrics
- **Latency**: Thời gian xử lý mỗi query
- **Token Usage**: (Cần implement tracking từ LLM responses)
- **Success Rate**: Tỷ lệ thành công của mỗi agent

## Output Files

### Results Files
- `experiments/benchmark/{mode}_results_{timestamp}.jsonl`: Kết quả chi tiết
- `experiments/benchmark/{mode}_summary_{timestamp}.json`: Tóm tắt thống kê

### Evaluation Files
- `experiments/benchmark/evaluation_report_{timestamp}.csv`: Chi tiết từng instance
- `experiments/benchmark/evaluation_summary_{timestamp}.json`: Tóm tắt đánh giá

### Comparison Files
- `experiments/comparison/comparison_{timestamp}.csv`: Bảng so sánh

## Tối ưu hóa tiếp theo

### 1. Token Tracking
- Implement token counting từ LLM responses
- Track cost per query
- Analyze token usage patterns

### 2. Advanced Error Analysis
- Phân loại lỗi chi tiết hơn
- Identify common failure patterns
- Create error correction strategies

### 3. Performance Optimization
- Cache schema linking results
- Optimize prompt lengths
- Batch processing where possible

### 4. Evaluation Improvements
- Add semantic equivalence checking (LLM-as-a-Judge)
- Support for BigQuery/Snowflake evaluation
- More detailed error categorization

## Troubleshooting

### Vấn đề: Out of memory
- Giảm `--max-items` để test
- Tăng `SLEEP_TIME` trong benchmark.py

### Vấn đề: API rate limits
- Tăng `SLEEP_TIME` giữa các requests
- Sử dụng multiple API keys nếu có

### Vấn đề: Empty SQL results
- Kiểm tra API keys trong `.env`
- Xem logs để tìm lỗi cụ thể
- Thử với model khác (Gemini vs Claude)

## Next Steps

Sau khi hoàn thành Phase 3:
1. Phân tích kết quả chi tiết
2. Identify improvement opportunities
3. Tinh chỉnh prompts dựa trên error analysis
4. Chuẩn bị cho Phase 4: Paper Writing

