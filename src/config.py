import os
from dotenv import load_dotenv

load_dotenv()

# Model Configuration
# User requested "flash 2.0 lte" or "1.5 flash lte". 
# "gemini-flash-latest" is the working alias for the latest Flash model.
DEFAULT_MODEL = "gemini-flash-latest" 

# API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
