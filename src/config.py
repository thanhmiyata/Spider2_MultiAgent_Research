import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# Load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Model Configuration
# Model Configuration
DEFAULT_MODEL = "claude-3-haiku-20240307" 
GEMINI_MODEL = "gemini-flash-latest"
CLAUDE_MODEL = "claude-3-haiku-20240307"

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("CLAUDE_API_KEY") 
print(f"DEBUG: Loaded ANTHROPIC_API_KEY: {ANTHROPIC_API_KEY}")

def get_llm(model_name=DEFAULT_MODEL, temperature=0):
    """Factory function to get the LLM instance based on model name."""
    if "gemini" in model_name.lower():
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    elif "claude" in model_name.lower():
        return ChatAnthropic(model=model_name, temperature=temperature, api_key=ANTHROPIC_API_KEY)
    else:
        # Default to Gemini if unknown, or raise error
        print(f"Warning: Unknown model {model_name}, defaulting to Gemini Flash.")
        return ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=temperature)

def extract_content(response) -> str:
    """Extracts text content from LLM response, handling string or list of blocks."""
    content = response.content
    if isinstance(content, str):
        return content.strip()
    
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                text_parts.append(block.text)
            elif isinstance(block, str):
                text_parts.append(block)
            else:
                text_parts.append(str(block))
        return "".join(text_parts).strip()
    
    return str(content).strip()
