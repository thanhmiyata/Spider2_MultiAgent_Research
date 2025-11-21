import json
from collections import Counter
import os

file_path = 'data/spider2_lite/spider2-lite.jsonl'

try:
    with open(file_path, 'r') as f:
        db_counts = Counter()
        for line in f:
            try:
                data = json.loads(line)
                if 'db' in data:
                    db_counts[data['db']] += 1
            except json.JSONDecodeError:
                continue
                
    print("Databases with > 50 questions:")
    found = False
    for db, count in db_counts.items():
        if count > 50:
            print(f"- {db}: {count}")
            found = True
            
    if not found:
        print("No databases found with > 50 questions.")
        print("Top 5 databases by count:")
        for db, count in db_counts.most_common(5):
            print(f"- {db}: {count}")

except FileNotFoundError:
    print(f"File not found: {file_path}")
