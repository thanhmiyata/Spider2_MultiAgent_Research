import os
from dotenv import load_dotenv

load_dotenv()

print("Keys in env:")
for key in os.environ:
    if "API" in key or "KEY" in key or "CLAUDE" in key or "ANTHROPIC" in key:
        print(f"{key}: {'*' * 5}")
