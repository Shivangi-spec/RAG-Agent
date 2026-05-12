from openai import AsyncOpenAI

print("Attempting to initialize OpenAI client for Ollama...")
try:
    client = AsyncOpenAI(
        base_url="http://localhost:11434/v1", 
        api_key="ollama"  
    )
    print("OpenAI client initialized successfully!")

except Exception as e:
    print(f"Error initializing OpenAI client or communicating with Ollama: {e}")