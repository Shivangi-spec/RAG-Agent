# main.py

import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
import aiomysql

# Import the core agent processing function from agent.py file

from agent import process_user_query, llm_client, SYSTEM_PROMPT 

app = FastAPI(title="Federal Register RAG Agent API")

# Global variable for the database pool, will be initialized at startup
db_pool = None

# --- Pydantic Models for Request and Response ---
class ChatRequest(BaseModel):
    user_message: str
    # Optional: chat_id: str (To implement conversation history later)

class ChatResponse(BaseModel):
    agent_response: str

# --- FastAPI Lifespan Events (for DB pool and other resources) ---
@app.on_event("startup")
async def startup_event():
    global db_pool
    print("FastAPI app starting up...")
    loop = asyncio.get_event_loop()
    # Database configuration
    
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': '123456', 
        'db': 'federal_register_db',
        'autocommit': True, 
        'loop': loop
    }
    try:
        db_pool = await aiomysql.create_pool(**db_config)
        print("Database connection pool created successfully.")
        # Also initialize other resources here if needed,

    except Exception as e:
        print(f"Error creating database connection pool: {e}")
        # Handle error appropriately, maybe exit or prevent app from fully starting
        db_pool = None


@app.on_event("shutdown")
async def shutdown_event():
    global db_pool
    print("FastAPI app shutting down...")
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("Database connection pool closed.")

# --- API Endpoint ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global db_pool
    global llm_client # Assuming this is imported from agent.py
    
    if not db_pool:
        return ChatResponse(agent_response="Error: Database connection is not available.")
    if not llm_client: # Should be initialized when agent.py is imported
        return ChatResponse(agent_response="Error: LLM client is not available.")

    print(f"Received user message: {request.user_message}")
    
    try:
        agent_reply = await process_user_query(
            user_message=request.user_message,
            db_pool=db_pool,
            chat_history=None # Or manage chat history if you add that feature
        )
        print(f"Agent reply: {agent_reply}")
        return ChatResponse(agent_response=agent_reply)
    except Exception as e:
        print(f"Error during agent processing: {e}")
        import traceback
        traceback.print_exc()
        return ChatResponse(agent_response="I'm sorry, an error occurred while processing your request with the agent.")

