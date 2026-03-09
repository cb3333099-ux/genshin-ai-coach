from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from api.enka_service import EnkaService
from ai.chat_interface import ChatInterface
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Genshin AI Coach",
    description="Personal AI Assistant for Genshin Impact",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
enka_service = EnkaService()
chat_interface = ChatInterface()

# Request models
class ChatRequest(BaseModel):
    query: str
    uid: str = None

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Genshin AI Coach!",
        "status": "Online",
        "endpoints": {
            "health": "/health",
            "account": "/api/account/{uid}",
            "chat": "/api/chat",
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/account/{uid}")
async def get_account(uid: str):
    """
    Fetch player account data from Enka.Network
    
    Example: http://127.0.0.1:8000/api/account/123456789
    """
    try:
        logger.info(f"Fetching account data for UID: {uid}")
        account_data = await enka_service.fetch_account(uid)
        
        return {
            "success": True,
            "data": account_data,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        logger.error(f"Invalid UID: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat with the Genshin AI Coach
    
    Example request:
    {
        "query": "What should I farm today?",
        "uid": "123456789"
    }
    """
    try:
        logger.info(f"Chat query: {request.query}")
        
        # Get account data if UID provided
        account_data = None
        if request.uid:
            try:
                account_data = await enka_service.fetch_account(request.uid)
            except:
                pass  # Continue without account data
        
        # Get AI response
        response = await chat_interface.chat(request.query, account_data)
        
        return {
            "success": True,
            "query": request.query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)