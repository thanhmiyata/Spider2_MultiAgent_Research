from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from config import DEFAULT_MODEL

load_dotenv()

print(f"Testing model: {DEFAULT_MODEL}")

try:
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)
    response = llm.invoke("Say hello")
    print(f"Response: {response.content}")
except Exception as e:
    print(f"Error: {e}")
