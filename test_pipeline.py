#!/usr/bin/env python3
"""
Script đơn giản để test Multi-Agent pipeline và xem SQL được generate
"""
import sys
sys.path.insert(0, '/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/src')

from agents.multi_agent_flow import MultiAgentSystem
from utils.db_utils import get_schema_from_db
import json
import sqlite3

# Load một câu hỏi từ dataset
dataset_path = '/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/spider2-lite.jsonl'

with open(dataset_path, 'r') as f:
    for line in f:
        data = json.loads(line)
        if data['instance_id'] == 'local301':  # Câu hỏi về weekly sales
            question = data['question']
            db_id = data['db']  # Field name is 'db' not 'db_id'
            break

# Load schema
db_path = f'/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/resource/databases/sqlite/{db_id}/{db_id}.sqlite'

# Get schema as dict then convert to string
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
schema_parts = []
for row in cursor.fetchall():
    schema_parts.append(row[0])
schema = "\n\n".join(schema_parts)
conn.close()

print("="*80)
print("QUESTION:")
print(question)
print("\n" + "="*80)
print("SCHEMA:")
print(schema[:500] + "..." if len(schema) > 500 else schema)
print("\n" + "="*80)

# Run Multi-Agent System (bypass validator bằng cách modify code tạm thời)
mas = MultiAgentSystem(enable_knowledge_retrieval=True)

# Chạy từng bước để debug
print("\n[STEP 1] Schema Linking...")
linked_schema = mas.linker.link(question, schema)
print(f"Linked Schema: {linked_schema[:300]}...")

print("\n[STEP 2] Planning...")
plan = mas.planner.plan(question, linked_schema)
print(f"Plan: {plan[:300]}...")

print("\n[STEP 3] Generation...")
sql = mas.generator.generate(question, linked_schema, plan)
print(f"\nGENERATED SQL:\n{sql}")

# Load gold SQL
gold_sql_path = f'/Users/Krizpham/Thac si/Spider2_MultiAgent_Research/data/spider2_lite/evaluation_suite/gold/sql/local301.sql'
try:
    with open(gold_sql_path, 'r') as f:
        gold_sql = f.read().strip()
    print(f"\n" + "="*80)
    print("GOLD SQL:")
    print(gold_sql)
except Exception as e:
    print(f"\nCould not load gold SQL: {e}")

print("\n" + "="*80)
