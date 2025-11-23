import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DB_DIR = PROJECT_ROOT / "data/temp_db"
TARGET_DB_DIR = PROJECT_ROOT / "data/spider2_lite/resource/databases/sqlite"
TARGET_JSONL = PROJECT_ROOT / "data/spider2_lite/spider2-lite.jsonl"

def migrate():
    if not TEMP_DB_DIR.exists():
        print(f"Temp directory {TEMP_DB_DIR} does not exist.")
        return

    # Create target DB directory if it doesn't exist
    TARGET_DB_DIR.mkdir(parents=True, exist_ok=True)

    # Move SQLite files
    sqlite_files = list(TEMP_DB_DIR.glob("*.sqlite"))
    print(f"Found {len(sqlite_files)} SQLite files to migrate.")

    for sqlite_file in sqlite_files:
        db_name = sqlite_file.stem
        # Create specific folder for this DB
        db_folder = TARGET_DB_DIR / db_name
        db_folder.mkdir(exist_ok=True)
        
        target_path = db_folder / sqlite_file.name
        print(f"Moving {sqlite_file.name} -> {target_path}")
        shutil.move(str(sqlite_file), str(target_path))

    # Move JSONL file
    source_jsonl = TEMP_DB_DIR / "spider2-lite.jsonl"
    if source_jsonl.exists():
        print(f"Moving spider2-lite.jsonl -> {TARGET_JSONL}")
        shutil.move(str(source_jsonl), str(TARGET_JSONL))
    else:
        print("Warning: spider2-lite.jsonl not found in temp_db")

    # Cleanup
    # Check if temp_db is empty (ignoring .DS_Store or other hidden files if we want to be safe, 
    # but usually we can just leave it or delete it if empty)
    remaining = list(TEMP_DB_DIR.glob("*"))
    if not remaining or all(f.name.startswith('.') for f in remaining):
        print("Cleaning up temp_db...")
        shutil.rmtree(TEMP_DB_DIR)
    else:
        print(f"temp_db not empty, remaining files: {[f.name for f in remaining]}")

if __name__ == "__main__":
    migrate()
