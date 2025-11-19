import os
import shutil

SOURCE_DIR = "data/temp_db"
TARGET_DIR = "data/spider2_lite/resource/databases/sqlite"

files = [f for f in os.listdir(SOURCE_DIR) if f.endswith('.sqlite')]

for filename in files:
    db_name = filename.replace('.sqlite', '')
    # Handle special case if any (e.g. case sensitivity)
    # The folders seem to match the filenames exactly based on previous ls
    
    target_folder = os.path.join(TARGET_DIR, db_name)
    
    # Check for case-insensitive match if direct match fails
    if not os.path.exists(target_folder):
        # Try to find folder ignoring case
        all_folders = os.listdir(TARGET_DIR)
        match = next((f for f in all_folders if f.lower() == db_name.lower()), None)
        if match:
            target_folder = os.path.join(TARGET_DIR, match)
        else:
            print(f"Warning: Folder for {db_name} not found.")
            continue
            
    source_path = os.path.join(SOURCE_DIR, filename)
    target_path = os.path.join(target_folder, filename)
    
    shutil.move(source_path, target_path)
    print(f"Moved {filename} to {target_folder}")

print("Distribution complete.")
