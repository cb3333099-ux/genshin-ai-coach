from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
import logging
import os
import sys

# ------------------------------------------------
# Load environment variables
# ------------------------------------------------
from dotenv import load_dotenv

# Load from backend/.env first
backend_dir = Path(__file__).parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger(__name__)
if env_path.exists():
    logger.info(f"✅ Loaded .env from: {env_path}")
else:
    logger.warning(f"⚠️ .env not found at: {env_path}")

# ------------------------------------------------
# Project imports
# ------------------------------------------------
from api.enka_service import EnkaService
from ai.chat_interface import ChatInterface
from optimizer.solver import optimize_artifacts
from optimizer.models import Artifact, Substat, Weapon, Constraint

# ------------------------------------------------
# Logging
# ------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------------------------------------
# Check GROQ API KEY
# ------------------------------------------------
_api_key = os.getenv("GROQ_API_KEY")

if _api_key:
    logger.info("✅ GROQ_API_KEY loaded successfully")
    logger.info(f"   Key starts with: {_api_key[:10]}...")
else:
    logger.warning("⚠️ GROQ_API_KEY missing. AI responses will use template responses")
    logger.warning(f"   Make sure .env file exists at: {env_path}")

# ------------------------------------------------
# FastAPI app
# ------------------------------------------------
app = FastAPI(
    title="Genshin AI Coach",
    description="Personal AI Assistant for Genshin Impact",
    version="1.0.0"
)

# ------------------------------------------------
# CORS - MUST BE FIRST MIDDLEWARE
# ------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("✅ CORS middleware enabled")

# ------------------------------------------------
# Services
# ------------------------------------------------
try:
    enka_service = EnkaService()
    logger.info("✅ EnkaService initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize EnkaService: {e}")
    enka_service = None

try:
    chat_interface = ChatInterface(api_key=_api_key)
    logger.info("✅ ChatInterface initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize ChatInterface: {e}")
    chat_interface = None

# ------------------------------------------------
# Frontend directory
# ------------------------------------------------
FRONTEND_DIR = backend_dir.parent / "frontend"

logger.info(f"Frontend directory: {FRONTEND_DIR}")
logger.info(f"Frontend exists: {FRONTEND_DIR.exists()}")

# ------------------------------------------------
# Root
# ------------------------------------------------
@app.get("/")
def read_root():
    """Serve index.html"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        logger.warning(f"index.html not found at {index_path}")
        return {"error": "Frontend not found"}

# ------------------------------------------------
# Health check
# ------------------------------------------------
@app.get("/health")
def health_check():
    """Health check endpoint"""
    groq_ready = (chat_interface is not None and 
                  hasattr(chat_interface, 'client') and 
                  chat_interface.client is not None)
    
    return {
        "status": "healthy",
        "groq_configured": bool(_api_key),
        "groq_initialized": groq_ready
    }

# ------------------------------------------------
# Fetch account data
# ------------------------------------------------
@app.get("/api/account/{uid}")
async def get_account(uid: str):
    """Fetch account data from Enka Network"""
    try:
        logger.info(f"Fetching account data for UID: {uid}")

        if not enka_service:
            raise HTTPException(status_code=500, detail="EnkaService not initialized")

        account_data = await enka_service.fetch_account(uid)

        return {
            "success": True,
            "data": account_data,
            "character_count": len(account_data.get("characters", [])),
            "timestamp": datetime.now().isoformat()
        }

    except ValueError as e:
        logger.error(f"Invalid UID: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Error fetching account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------
# Chat with AI coach
# ------------------------------------------------
@app.post("/api/chat")
async def chat(request: dict):
    """Chat endpoint with AI coach"""
    try:
        query = request.get("query")
        uid = request.get("uid")

        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        logger.info(f"Chat query: {query[:50]}...")

        account_data = None

        if uid:
            try:
                logger.info(f"Fetching account data for UID: {uid}")
                if enka_service:
                    account_data = await enka_service.fetch_account(uid)
            except Exception as e:
                logger.warning(f"Failed to fetch account data: {e}")

        # Get response from chat interface
        if chat_interface:
            response = await chat_interface.chat(query, account_data)
        else:
            logger.warning("ChatInterface not initialized, using fallback")
            response = "Chat interface not available. Please check server logs."

        return {
            "success": True,
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------
# Helper conversion functions
# ------------------------------------------------
def _to_substat(s: dict) -> Substat:
    """Convert dict to Substat"""
    return Substat(stat=s.get("stat", ""), value=float(s.get("value", 0)))


def _to_artifact(a: dict) -> Artifact:
    """Convert dict to Artifact"""
    return Artifact(
        id=a.get("id", ""),
        slot=a.get("slot", ""),
        set_key=a.get("set_key", ""),
        rarity=int(a.get("rarity", 5)),
        level=int(a.get("level", 20)),
        main_stat=a.get("main_stat", ""),
        main_stat_value=float(a.get("main_stat_value", 0)),
        substats=[_to_substat(s) for s in a.get("substats", [])],
    )


def _to_weapon(w: Optional[dict]) -> Optional[Weapon]:
    """Convert dict to Weapon"""
    if not w:
        return None

    return Weapon(
        key=w.get("key", ""),
        level=int(w.get("level", 90)),
        ascension=int(w.get("ascension", 6)),
        refinement=int(w.get("refinement", 1)),
        base_atk=float(w.get("base_atk", 0)),
        sub_stat=w.get("sub_stat", ""),
        sub_stat_value=float(w.get("sub_stat_value", 0)),
    )


def _to_constraint(c: dict) -> Constraint:
    """Convert dict to Constraint"""
    return Constraint(
        type=c.get("type", ""),
        slot=c.get("slot"),
        value=c.get("value"),
        threshold=c.get("threshold"),
    )

# ------------------------------------------------
# Default target stats
# ------------------------------------------------
DEFAULT_TARGET_STATS: Dict[str, Dict[str, float]] = {
    "Ganyu": {"Crit Rate": 0.70, "Crit DMG": 1.40, "ATK%": 0.50},
    "Hu Tao": {"Crit Rate": 0.65, "Crit DMG": 1.30, "HP%": 0.50},
    "Raiden Shogun": {"Energy Recharge": 2.00, "Crit Rate": 0.55, "Crit DMG": 1.10},
    "Zhongli": {"HP%": 0.50, "DEF%": 0.30},
    "Kazuha": {"Elemental Mastery": 800.0, "Energy Recharge": 1.60},
    "Nahida": {"Elemental Mastery": 900.0, "Crit Rate": 0.55, "Crit DMG": 1.10},
    "_default": {"Crit Rate": 0.60, "Crit DMG": 1.20, "ATK%": 0.40},
}

# ------------------------------------------------
# Artifact optimizer endpoint
# ------------------------------------------------
@app.post("/api/optimize")
async def optimize(request: dict):
    """Optimize artifact builds"""
    try:
        character = request.get("character")
        artifacts_raw = request.get("artifacts", [])
        target_stats = request.get("target_stats", {})
        weapon_raw = request.get("weapon")
        constraints_raw = request.get("constraints", [])
        buffs = request.get("buffs")
        top_n = int(request.get("top_n", 5))

        if not character:
            raise HTTPException(status_code=400, detail="Character is required")

        logger.info(f"Optimizing artifacts for {character}")

        artifacts = [_to_artifact(a) for a in artifacts_raw]
        weapon = _to_weapon(weapon_raw)
        constraints = [_to_constraint(c) for c in constraints_raw]

        builds = optimize_artifacts(
            character_key=character,
            available_artifacts=artifacts,
            target_stats=target_stats,
            constraints=constraints,
            weapon=weapon,
            buffs=buffs,
            top_n=top_n
        )

        return {
            "success": True,
            "character": character,
            "builds": [b.to_dict() for b in builds],
            "total_builds_found": len(builds),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------
# Static frontend
# ------------------------------------------------
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

logger.info(f"✅ Static files mounted from: {FRONTEND_DIR}")

# ------------------------------------------------
# Startup event
# ------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """Run on startup"""
    logger.info("=" * 60)
    logger.info("🚀 GENSHIN AI COACH - STARTING UP")
    logger.info("=" * 60)
    logger.info(f"Frontend Dir: {FRONTEND_DIR}")
    logger.info(f"GROQ API Key: {'✅ Configured' if _api_key else '❌ Missing'}")
    logger.info(f"Chat Interface: {'✅ Ready' if chat_interface else '❌ Failed'}")
    logger.info("=" * 60)

# ------------------------------------------------
# Run locally
# ------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=True
    )