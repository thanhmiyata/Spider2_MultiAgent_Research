# 📊 Dataset Recommendations - Các Dataset Phù Hợp

## Yêu Cầu
- ✅ >100 câu hỏi trên mỗi database
- ✅ Có gold.sql (truy vấn chuẩn)
- ✅ Đã có databases SQLite/Snowflake/BigQuery
- ✅ Phù hợp để benchmark

---

## 🎯 Top Recommendations (Top 4)

### 1. **Spider 2.0 (Full) - RECOMMENDED ⭐⭐⭐⭐⭐**

| Thuộc tính | Giá trị |
|-----------|--------|
| **Total Questions** | 632 |
| **Total Databases** | ~100+ |
| **Questions per DB** | 5-10 (varies) |
| **Supported DBs** | BigQuery, Snowflake, PostgreSQL, ClickHouse, SQLite, DuckDB |
| **Gold SQL** | ✅ Có |
| **Official Site** | https://spider2-sql.github.io |
| **Download** | Request access at official site |
| **Format** | JSONL + SQL files |

**Ưu điểm:**
- ✅ Newest, most realistic enterprise scenarios
- ✅ Multi-database support
- ✅ Complex real-world queries
- ✅ Official benchmark for 2024-2025

**Nhược điểm:**
- ❌ Cần request access
- ❌ Mỗi DB ít câu (5-10), không>100/DB

---

### 2. **Spider 1.0 - Good Baseline ⭐⭐⭐⭐**

| Thuộc tính | Giá trị |
|-----------|--------|
| **Total Questions** | 10,181 |
| **Total Databases** | 200 |
| **Questions per DB** | ~50-100 |
| **Supported DBs** | SQLite (local) |
| **Gold SQL** | ✅ Có |
| **Official Site** | https://yale-lily.github.io/spider |
| **GitHub Link** | https://github.com/taolusi/spider |
| **Download** | Direct download from github |
| **Format** | JSON + SQL files |

**Ưu điểm:**
- ✅ Nhiều databases (200)
- ✅ Tổng cộng 10k+ questions
- ✅ Có nhiều questions mỗi DB
- ✅ Easy to download
- ✅ Well-established benchmark

**Nhược điểm:**
- ⚠️ Cũ hơn (2018), queries không phức tạp bằng Spider 2.0
- ⚠️ Chỉ SQLite, không có Snowflake/BigQuery

---

### 3. **SParC Dataset - Context-Dependent ⭐⭐⭐⭐**

| Thuộc tính | Giá trị |
|-----------|--------|
| **Total Questions** | 12,000+ |
| **Total Databases** | 200 |
| **Questions per DB** | ~60 |
| **Supported DBs** | SQLite (local) |
| **Gold SQL** | ✅ Có |
| **Official Site** | https://yale-lily.github.io/sparc |
| **GitHub Link** | https://github.com/taolusi/sparc |
| **Download** | Direct download from github |
| **Format** | JSON + SQL files |

**Ưu điểm:**
- ✅ Largest dataset (12k questions)
- ✅ 200 databases
- ✅ Contextual queries (multi-turn)
- ✅ Realistic interactions

**Nhược điểm:**
- ⚠️ Contextual format (harder to process)
- ⚠️ SQLite only
- ⚠️ Older dataset

---

### 4. **BIRD Benchmark - Enterprise Focus ⭐⭐⭐⭐**

| Thuộc tính | Giá trị |
|-----------|--------|
| **Total Questions** | 1,000+ |
| **Total Databases** | 80+ |
| **Questions per DB** | ~12-15 |
| **Supported DBs** | SQLite, PostgreSQL, MySQL |
| **Gold SQL** | ✅ Có |
| **GitHub Link** | https://github.com/AlibabaResearchOfficial/BIRD |
| **Download** | Direct download from github |
| **Format** | JSON + SQL files |

**Ưu điểm:**
- ✅ Enterprise databases
- ✅ Multiple DB types
- ✅ Real-world complexity
- ✅ Good for cross-DB testing

**Nhược điểm:**
- ⚠️ Ít databases (80+)
- ⚠️ Không nhiều questions/DB (<15)

---

## 📥 Download Links Chính

| Dataset | Official | GitHub | Format |
|---------|----------|--------|--------|
| **Spider 2.0** | https://spider2-sql.github.io | N/A (need request) | JSONL |
| **Spider 1.0** | https://yale-lily.github.io/spider | https://github.com/taolusi/spider | JSON |
| **SParC** | https://yale-lily.github.io/sparc | https://github.com/taolusi/sparc | JSON |
| **BIRD** | N/A | https://github.com/AlibabaResearchOfficial/BIRD | JSON |

---

## 🎯 Recommend Solution For Your Needs

### Nếu muốn **Maximum Coverage**:
👉 **Download Spider 1.0** 
- 10,181 questions trên 200 databases
- Easy to process
- Good baseline

### Nếu muốn **Newest Enterprise Scenarios**:
👉 **Request Spider 2.0 Full**
- 632 questions, multi-DB support
- Most realistic
- Current SOTA benchmark

### Nếu muốn **Largest Dataset**:
👉 **Download SParC**
- 12,000+ questions
- 200 databases
- Contextual queries (good for testing reasoning)

### Nếu muốn **Multi-Database Testing**:
👉 **Download BIRD**
- SQLite + PostgreSQL + MySQL
- Good for cross-DB evaluation

---

## 📋 Quick Comparison Table

| Metric | Spider 1.0 | Spider 2.0 | SParC | BIRD |
|--------|-----------|-----------|-------|------|
| Questions | 10,181 | 632 | 12,000+ | 1,000+ |
| Databases | 200 | 100+ | 200 | 80+ |
| Avg Q/DB | ~50 | ~6 | ~60 | ~12 |
| Database Types | SQLite | Multi* | SQLite | Multi |
| Gold SQL | ✅ | ✅ | ✅ | ✅ |
| Complexity | Medium | High | Medium-High | High |
| Download | Easy | Request | Easy | Easy |
| **Score** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

*Spider 2.0: BigQuery, Snowflake, PostgreSQL, ClickHouse, SQLite, DuckDB

---

## 🚀 My Personal Recommendation

**Best Overall: Spider 1.0 + Spider 2.0**

1. **Phase 1**: Download Spider 1.0
   - Easy to start
   - 200 databases, 10k questions
   - Good for initial testing

2. **Phase 2**: Request Spider 2.0
   - More realistic
   - Enterprise scenarios
   - Latest benchmark standard

3. **Phase 3**: Add BIRD if need multi-DB
   - PostgreSQL, MySQL support
   - Cross-database evaluation

---

## ⚙️ Integration Steps

### For Spider 1.0 (Recommended to start):

```bash
# 1. Download
git clone https://github.com/taolusi/spider.git
cd spider
# Extract: database/*, json/train_spider.json, json/dev.json

# 2. Copy to your project
cp -r database ~/path/to/Spider2_MultiAgent_Research/data/spider_1_0/
cp json/train_spider.json ~/path/to/Spider2_MultiAgent_Research/data/spider_1_0/
cp json/dev.json ~/path/to/Spider2_MultiAgent_Research/data/spider_1_0/

# 3. Process & integrate with your benchmark script
```

### For Spider 2.0:

```bash
# 1. Go to https://spider2-sql.github.io
# 2. Request access and download the dataset
# 3. Extract and copy similar to Spider 1.0
```

---

## 📊 Expected Benchmark Results After Integration

**With Spider 1.0 (200 DBs, 10k questions):**
- Full benchmark: ~2-3 hours (with optimized models)
- Database coverage: 200 different domains
- Result validity: Very high (standard benchmark)

**With Spider 2.0 (100+ DBs, 632 questions):**
- Full benchmark: ~1-2 hours
- Database coverage: Enterprise real-world scenarios
- Result validity: Highest (latest standard)

---

**Last Updated**: 2025-11-22
**Status**: ✅ Ready for integration

