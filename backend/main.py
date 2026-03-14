from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from datetime import datetime
from typing import Dict, List, Optional, Any
from api.enka_service import EnkaService
from ai.chat_interface import ChatInterface
from data.character_cache import DynamicCharacterCache
from optimizer.solver import optimize_artifacts
from optimizer.models import Artifact, Substat, Weapon, Constraint
import logging
import os

# Load .env file only for local development; in production (e.g. Render),
# environment variables are already set and load_dotenv() is not needed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read and log API key status so it is easy to diagnose configuration issues
_api_key = os.environ.get("GROQ_API_KEY")
if _api_key:
    logger.info("✅ GROQ_API_KEY loaded successfully")
    logger.info(f"   Key starts with: {_api_key[:10]}...")
else:
    logger.warning("❌ GROQ_API_KEY not found in environment variables - chat will use template responses")

app = FastAPI(
    title="Genshin AI Coach",
    description="Personal AI Assistant for Genshin Impact",
    version="1.0.0"
)

# Add CORS middleware
logger.info("✅ CORS middleware enabled")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services, passing the API key explicitly so it is always sourced
# from os.environ regardless of how load_dotenv behaves in the environment.
logger.info("✅ EnkaService initialized")
enka_service = EnkaService()
character_cache = DynamicCharacterCache()
chat_interface = ChatInterface(api_key=_api_key, character_cache=character_cache)

@app.on_event("startup")
async def _preload_datasets():
    """Pre-warm character and artifact databases on startup to reduce first-request latency."""
    logger.info("🔄 Pre-loading character dataset (Enka + genshin.dev + jmsszkzlz)...")
    try:
        await enka_service._ensure_character_data()
        logger.info("✅ Character dataset loaded successfully")
    except Exception as exc:
        logger.warning(f"⚠️ Character dataset pre-load failed (will retry on first request): {exc}")
    logger.info("🔄 Pre-loading artifact set name database...")
    try:
        await enka_service._ensure_artifact_data()
        logger.info("✅ Artifact set database loaded successfully")
    except Exception as exc:
        logger.warning(f"⚠️ Artifact set database pre-load failed (will retry on first request): {exc}")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

@app.get("/")
async def read_root():
    """Serve the frontend HTML with proper CSP headers"""
    try:
        file_path = os.path.join(FRONTEND_DIR, "index.html")
        if not os.path.exists(FRONTEND_DIR):
            logger.error(f"Frontend directory not found at {FRONTEND_DIR}")
            return HTMLResponse("<h1>Frontend directory not found</h1>", status_code=500)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Security-Policy": "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "SAMEORIGIN",
                "X-XSS-Protection": "1; mode=block"
            }
        )
    except FileNotFoundError:
        logger.error(f"index.html not found at {FRONTEND_DIR}")
        return HTMLResponse("<h1>Frontend files not found</h1>", status_code=500)
    except Exception as e:
        logger.error(f"Error reading index.html: {e}")
        return HTMLResponse(f"<h1>Error loading page</h1><p>{str(e)}</p>", status_code=500)

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
            "character_count": len(account_data.get("characters", [])),
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        logger.error(f"Invalid UID: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(request: dict):
    """
    Chat with the Genshin AI Coach
    
    Example request:
    {
        "query": "What should I farm today?",
        "uid": "123456789"
    }
    """
    try:
        query = request.get("query", "")
        uid = request.get("uid")
        
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        logger.info(f"Chat query: {query}")
        
        # Get account data if UID provided
        account_data = None
        if uid:
            try:
                account_data = await enka_service.fetch_account(uid)
            except:
                pass  # Continue without account data
        
        # Get AI response
        result = await chat_interface.chat(query, account_data)
        
        return {
            "success": True,
            "query": query,
            "response": result["response"],
            "sources_used": result.get("sources_used", []),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Helper – convert dict to optimizer domain objects
# ---------------------------------------------------------------------------

def _to_substat(s: dict) -> Substat:
    return Substat(stat=s.get("stat", ""), value=float(s.get("value", 0)))

def _to_artifact(a: dict) -> Artifact:
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
    if w is None:
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
    return Constraint(
        type=c.get("type", ""),
        slot=c.get("slot"),
        value=c.get("value"),
        threshold=c.get("threshold"),
    )

# ---------------------------------------------------------------------------
# Default target stats per character (used by /api/recommended-build)
# Based on community-accepted optimal build targets.
# ---------------------------------------------------------------------------

DEFAULT_TARGET_STATS: Dict[str, Dict[str, float]] = {
    "Ganyu":         {"Crit Rate": 0.70, "Crit DMG": 1.40, "ATK%": 0.50},
    "Hu Tao":        {"Crit Rate": 0.65, "Crit DMG": 1.30, "HP%": 0.50},
    "Raiden Shogun": {"Energy Recharge": 2.00, "Crit Rate": 0.55, "Crit DMG": 1.10},
    "Zhongli":       {"HP%": 0.50, "DEF%": 0.30},
    "Kazuha":        {"Elemental Mastery": 800.0, "Energy Recharge": 1.60},
    "Nahida":        {"Elemental Mastery": 900.0, "Crit Rate": 0.55, "Crit DMG": 1.10},
    "_default":      {"Crit Rate": 0.60, "Crit DMG": 1.20, "ATK%": 0.40},
}

# ---------------------------------------------------------------------------
# Artifact optimizer endpoints
# ---------------------------------------------------------------------------

@app.post("/api/optimize")
async def optimize(request: dict):
    """
    Find the best artifact combinations for a character.

    Example request:
    {
        "character": "Ganyu",
        "artifacts": [...],
        "target_stats": {"Crit Rate": 0.7, "Crit DMG": 1.4},
        "top_n": 5
    }
    """
    try:
        character = request.get("character", "")
        artifacts_raw = request.get("artifacts", [])
        target_stats = request.get("target_stats", {})
        constraints_raw = request.get("constraints", [])
        weapon_raw = request.get("weapon")
        buffs = request.get("buffs")
        top_n = int(request.get("top_n", 5))

        if not character:
            raise HTTPException(status_code=400, detail="Character is required")

        logger.info(f"Optimizing artifacts for {character}")
        domain_artifacts = [_to_artifact(a) for a in artifacts_raw]
        domain_weapon = _to_weapon(weapon_raw)
        domain_constraints = [_to_constraint(c) for c in constraints_raw]

        builds = optimize_artifacts(
            character_key=character,
            available_artifacts=domain_artifacts,
            target_stats=target_stats,
            constraints=domain_constraints,
            weapon=domain_weapon,
            buffs=buffs,
            top_n=top_n,
        )

        return {
            "success": True,
            "character": character,
            "builds": [b.to_dict() for b in builds],
            "total_builds_found": len(builds),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error optimizing artifacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recommended-build")
async def recommended_build(request: dict):
    """
    Optimize artifacts against community-recommended stat targets for a character.

    Example request:
    {
        "character": "Ganyu",
        "artifacts": [...],
        "top_n": 3
    }
    """
    try:
        character = request.get("character", "")
        artifacts_raw = request.get("artifacts", [])
        weapon_raw = request.get("weapon")
        buffs = request.get("buffs")
        top_n = int(request.get("top_n", 5))

        if not character:
            raise HTTPException(status_code=400, detail="Character is required")

        logger.info(f"Fetching recommended build for {character}")
        target_stats = DEFAULT_TARGET_STATS.get(
            character,
            DEFAULT_TARGET_STATS["_default"],
        )
        domain_artifacts = [_to_artifact(a) for a in artifacts_raw]
        domain_weapon = _to_weapon(weapon_raw)

        builds = optimize_artifacts(
            character_key=character,
            available_artifacts=domain_artifacts,
            target_stats=target_stats,
            weapon=domain_weapon,
            buffs=buffs,
            top_n=top_n,
        )

        return {
            "success": True,
            "character": character,
            "target_stats": target_stats,
            "builds": [b.to_dict() for b in builds],
            "total_builds_found": len(builds),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting recommended build: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimize-team")
async def optimize_team(request: dict):
    """
    Optimize artifact builds for each character in a team independently.

    Example request:
    {
        "team": ["Ganyu", "Zhongli", "Fischl", "Kokomi"],
        "artifacts_by_character": {
            "Ganyu": [...],
            "Zhongli": [...]
        }
    }
    """
    try:
        team = request.get("team", [])
        artifacts_by_character = request.get("artifacts_by_character", {})
        target_stats_by_character = request.get("target_stats_by_character", {})
        weapons_by_character = request.get("weapons_by_character", {})
        buffs_by_character = request.get("buffs_by_character", {})
        top_n = int(request.get("top_n", 3))

        if not team:
            raise HTTPException(status_code=400, detail="Team list is required")

        logger.info(f"Optimizing team: {team}")
        team_results = {}

        for character in team:
            raw_artifacts = artifacts_by_character.get(character, [])
            domain_artifacts = [_to_artifact(a) for a in raw_artifacts]

            target_stats = target_stats_by_character.get(
                character,
                DEFAULT_TARGET_STATS.get(character, DEFAULT_TARGET_STATS["_default"]),
            )

            raw_weapon = weapons_by_character.get(character)
            domain_weapon = _to_weapon(raw_weapon)

            team_buffs = buffs_by_character.get(character)

            builds = optimize_artifacts(
                character_key=character,
                available_artifacts=domain_artifacts,
                target_stats=target_stats,
                weapon=domain_weapon,
                buffs=team_buffs,
                top_n=top_n,
            )

            team_results[character] = {
                "target_stats": target_stats,
                "builds": [b.to_dict() for b in builds],
            }

        return {
            "success": True,
            "team": team,
            "results": team_results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error optimizing team: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
    logger.info(f"Frontend exists: {os.path.exists(FRONTEND_DIR)}")
    logger.info(f"✅ Static files mounted from: {FRONTEND_DIR}")
    logger.info(f"GROQ API Key: {'✅ Configured' if _api_key else '❌ Missing'}")
    logger.info(f"Chat Interface: {'✅ Ready' if chat_interface else '❌ Failed'}")
    logger.info("=" * 60)


# Mount frontend static files (CSS, JS, etc.) - must be AFTER all API routes!
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)