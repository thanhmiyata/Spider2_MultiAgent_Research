import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# Load .env from project root (with error handling)
try:
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    else:
        load_dotenv()  # Fallback to default search
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    load_dotenv()  # Fallback to default search

# Model Configuration
# Updated to fastest models: Claude 3.5 Haiku and Gemini 2.0 Flash (or fallback to gemini-flash-latest)
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"  # Claude 3.5 Sonnet (User Requested)
GEMINI_MODEL = "gemini-2.5-flash"           # Gemini 2.5 Flash (User Requested)
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"   # Claude 3.5 Sonnet (User Requested)

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("CLAUDE_API_KEY")

def get_llm(model_name=DEFAULT_MODEL, temperature=0, timeout=60):
    """Factory function to get the LLM instance based on model name with timeout and fallback."""
    if "gemini" in model_name.lower():
        try:
            return ChatGoogleGenerativeAI(
                model=model_name, 
                temperature=temperature,
                request_timeout=timeout
            )
        except Exception as e:
            print(f"Warning: Model {model_name} not available: {e}")
            print(f"Falling back to gemini-1.5-flash")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash", 
                temperature=temperature,
                request_timeout=timeout
            )
    elif "claude" in model_name.lower():
        try:
            return ChatAnthropic(
                model=model_name, 
                temperature=temperature, 
                api_key=ANTHROPIC_API_KEY,
                timeout=timeout
            )
        except Exception as e:
            print(f"Warning: Model {model_name} not available: {e}")
            print(f"Falling back to claude-3-5-sonnet-latest")
            return ChatAnthropic(
                model="claude-3-5-sonnet-latest", 
                temperature=temperature, 
                api_key=ANTHROPIC_API_KEY,
                timeout=timeout
            )
    else:
        # Default to Gemini if unknown
        print(f"Warning: Unknown model {model_name}, defaulting to Gemini 1.5 Flash.")
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            temperature=temperature,
            request_timeout=timeout
        )

def extract_content(response, max_depth=5) -> str:
    """
    Extracts text content from LLM response with safety guards.
    Handles: string, list of blocks, BaseMessage objects.
    Includes depth limit to prevent infinite loops.
    """
    def _extract(obj, depth=0):
        if depth > max_depth:
            return ""
        
        # Handle string
        if isinstance(obj, str):
            return obj.strip()
        
        # Handle objects with .content attribute (BaseMessage, etc)
        if hasattr(obj, 'content'):
            return _extract(obj.content, depth + 1)
        
        # Handle lists
        if isinstance(obj, list):
            text_parts = []
            for block in obj:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif hasattr(block, "text"):
                    text_parts.append(block.text)
                elif isinstance(block, str):
                    text_parts.append(block)
                else:
                    text_parts.append(str(block))
            return "".join(text_parts).strip()
        
        # Fallback
        return str(obj).strip()
    
    try:
        return _extract(response)
    except Exception as e:
        print(f"Warning: Error extracting content: {e}")
        return ""
