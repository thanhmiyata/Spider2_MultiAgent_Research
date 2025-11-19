# Adaptive Multi-Agent Framework for Spider 2.0 NL2SQL

## 📋 Tổng quan Dự án (Project Overview)

Dự án này tập trung nghiên cứu và phát triển hệ thống **Natural Language to SQL (NL2SQL)** thế hệ mới, sử dụng kiến trúc **Adaptive Multi-Agent** để giải quyết các thách thức của benchmark **Spider 2.0** (Real-world Enterprise Text-to-SQL).

### 🎯 Mục tiêu Nghiên cứu
1.  **Chinh phục Spider 2.0**: Vượt qua giới hạn của các mô hình Single Agent (như GPT-4, Gemini Pro) vốn chỉ đạt độ chính xác thấp (~17%) trên dataset này.
2.  **Cơ chế Adaptive (Thích ứng)**: Chứng minh tính hiệu quả của việc tự động điều phối (routing) câu hỏi dựa trên độ khó:
    *   *Easy Questions* -> Single Agent (Nhanh, Rẻ).
    *   *Hard Questions* -> Multi-Agent Reasoning (Chính xác cao).
3.  **Hybrid Evaluation**: Đề xuất phương pháp đánh giá lai giữa **Execution Accuracy** (cho SQLite) và **LLM-as-a-Judge** (cho BigQuery/Snowflake) để đảm bảo tính khoa học mà không cần hạ tầng Cloud phức tạp.

---

## 🏗️ Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế với các module chính:

### 1. Router Agent (The "Brain")
*   **Nhiệm vụ**: Phân tích câu hỏi đầu vào.
*   **Output**: Phân loại độ khó (Easy/Medium/Hard) và chọn pipeline xử lý phù hợp.

### 2. Processing Pipelines
*   **Fast Track (Single Agent)**:
    *   Sử dụng Gemini 2.0 Flash LTE với Prompt tối ưu.
    *   Phù hợp cho câu hỏi đơn giản, ít bảng.
*   **Deep Reasoning Track (Multi-Agent)**:
    *   **Step 1: Schema Linker**: Sử dụng RAG để tìm đúng bảng/cột liên quan trong hàng nghìn cột của Spider 2.0.
    *   **Step 2: Planner**: Lên kế hoạch các bước logic (CTE, Subquery).
    *   **Step 3: Generator**: Viết code SQL chuẩn dialect (BigQuery/Snowflake/SQLite).
    *   **Step 4: Validator (Self-Correction)**: Kiểm tra cú pháp và logic, tự sửa lỗi nếu cần.

---

## 🧪 Chiến lược Thực nghiệm & Đánh giá (Evaluation Strategy)

Chúng ta sử dụng dataset **Spider 2.0 Lite** (547 cặp câu hỏi-SQL) và chia thành 2 nhóm đánh giá:

| Nhóm Dữ liệu | Số lượng | Phương pháp Đánh giá | Công cụ |
| :--- | :--- | :--- | :--- |
| **SQLite Subset** | ~135 | **Execution Accuracy** | Chạy thực thi trên SQLite DB cục bộ. So sánh kết quả trả về với Gold SQL. |
| **Cloud Subset** | ~412 | **LLM-as-a-Judge** | Sử dụng Gemini 1.5 Pro / GPT-4o để chấm điểm ngữ nghĩa (Semantic Equivalence) giữa Generated SQL và Gold SQL. |

---

## 📂 Cấu trúc Thư mục (Directory Structure)

```
Spider2_MultiAgent_Research/
├── data/                   # Chứa dataset Spider 2.0 Lite (JSONL, SQLite DBs)
├── src/                    # Source code chính
│   ├── agents/             # Code cho từng Agent (Router, Linker, Generator...)
│   ├── utils/              # Các hàm tiện ích (DB connection, Evaluation...)
│   └── main.py             # Entry point của hệ thống
├── experiments/            # Các script chạy thực nghiệm và logs
│   ├── baseline/           # Code chạy Single Agent Baseline
│   └── multi_agent/        # Code chạy Adaptive Framework
├── docs/                   # Tài liệu nghiên cứu, nháp bài báo
└── requirements.txt        # Các thư viện cần thiết (CrewAI, LangChain...)
```

---

## 🚀 Lộ trình Thực hiện (Roadmap)

1.  **Phase 1: Setup & Baseline**
    *   Tải dữ liệu Spider 2.0 Lite.
    *   Xây dựng Evaluation Script (Hybrid Mode).
    *   Chạy Baseline với Single Agent để lấy số liệu so sánh.

2.  **Phase 2: Multi-Agent Development**
    *   Implement Router Agent.
    *   Implement Schema Linker (RAG).
    *   Implement Generator & Validator.

3.  **Phase 3: Benchmark & Optimization**
    *   Chạy toàn bộ tập test.
    *   Tinh chỉnh Prompt và Flow.
    *   So sánh kết quả: Single vs. Adaptive Multi-Agent.

4.  **Phase 4: Paper Writing**
    *   Tổng hợp số liệu.
    *   Viết báo cáo khoa học theo chuẩn IMRAD.
