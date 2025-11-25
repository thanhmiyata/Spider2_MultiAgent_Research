#!/usr/bin/env python3
"""
Integration test: Run pipeline và evaluate với enhanced DataFrame comparison
"""
import sys
sys.path.insert(0, '/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/src')

from agents.multi_agent_flow import MultiAgentSystem
from utils.execution_evaluator import evaluate_sql_pair
import json
import sqlite3

# Load câu hỏi local301
dataset_path = '/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/spider2-lite.jsonl'

with open(dataset_path, 'r') as f:
    for line in f:
        data = json.loads(line)
        if data['instance_id'] == 'local301':
            question = data['question']
            db_id = data['db']
            break

# Load schema
db_path = f'/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/resource/databases/sqlite/{db_id}/{db_id}.sqlite'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
schema_parts = []
for row in cursor.fetchall():
    schema_parts.append(row[0])
schema = "\n\n".join(schema_parts)
conn.close()

print("="*80)
print("INTEGRATION TEST: Enhanced Evaluation System")
print("="*80)
print(f"\nQuestion: {question[:100]}...")
print(f"Database: {db_id}")

# Run Multi-Agent System
print("\n" + "="*80)
print("STEP 1: Running Multi-Agent System")
print("="*80)

mas = MultiAgentSystem(enable_knowledge_retrieval=True)

# Run từng bước
print("\n[1] Schema Linking...")
linked_schema = mas.linker.link(question, schema)
print(f"✓ Linked schema: {len(linked_schema)} chars")

print("\n[2] Planning...")
plan = mas.planner.plan(question, linked_schema)
print(f"✓ Plan created: {len(plan)} chars")

print("\n[3] Generating SQL...")
generated_sql = mas.generator.generate(question, linked_schema, plan)
print(f"✓ Generated SQL:\n{generated_sql}\n")

# Load gold SQL
gold_sql_path = '/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/evaluation_suite/gold/sql/local301.sql'
with open(gold_sql_path, 'r') as f:
    gold_sql = f.read().strip()

print("="*80)
print("STEP 2: Enhanced Evaluation with DataFrame Comparison")
print("="*80)

# Evaluate with enhanced system
is_correct, error_type, details = evaluate_sql_pair(
    db_path,
    generated_sql,
    gold_sql,
    tolerance=1e-4
)

print(f"\n{'='*80}")
print("EVALUATION RESULTS")
print(f"{'='*80}")
print(f"Is Correct: {is_correct}")
print(f"Error Type: {error_type}")
print(f"\nDetails:")
for key, value in details.items():
    print(f"  {key}: {value}")

if is_correct:
    print("\n✅ SUCCESS: Generated SQL matches Gold SQL!")
else:
    print(f"\n❌ FAILED: {error_type}")
    print(f"   {details.get('comparison_details', 'No details')}")

print(f"\n{'='*80}")
