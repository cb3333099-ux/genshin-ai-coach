from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from api.enka_service import EnkaService
from ai.chat_interface import ChatInterface
from optimizer.models import (
    Artifact,
    Constraint,
    Substat,
    Weapon,
)
from optimizer.solver import optimize_artifacts
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
    logger.info("GROQ_API_KEY loaded successfully")
else:
    logger.warning("GROQ_API_KEY not found in environment variables - chat will use template responses")

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

# Initialize services, passing the API key explicitly so it is always sourced
# from os.environ regardless of how load_dotenv behaves in the environment.
enka_service = EnkaService()
chat_interface = ChatInterface(api_key=_api_key)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str
    uid: str = None


class SubstatModel(BaseModel):
    stat: str
    value: float


class ArtifactModel(BaseModel):
    id: str
    slot: str
    set_key: str
    rarity: int = 5
    level: int = 20
    main_stat: str
    main_stat_value: float
    substats: List[SubstatModel] = []


class WeaponModel(BaseModel):
    key: str
    level: int = 90
    ascension: int = 6
    refinement: int = 1
    base_atk: float = 0.0
    sub_stat: str = ""
    sub_stat_value: float = 0.0


class ConstraintModel(BaseModel):
    type: str
    slot: Optional[str] = None
    value: Optional[str] = None
    threshold: Optional[float] = None


class OptimizeRequest(BaseModel):
    uid: Optional[str] = None
    character: str
    artifacts: List[ArtifactModel]
    target_stats: Dict[str, float]
    constraints: List[ConstraintModel] = []
    weapon: Optional[WeaponModel] = None
    buffs: Optional[Dict[str, float]] = None
    top_n: int = 5


class RecommendedBuildRequest(BaseModel):
    uid: Optional[str] = None
    character: str
    artifacts: List[ArtifactModel]
    weapon: Optional[WeaponModel] = None
    buffs: Optional[Dict[str, float]] = None
    top_n: int = 5


class OptimizeTeamRequest(BaseModel):
    uid: Optional[str] = None
    team: List[str]
    artifacts_by_character: Dict[str, List[ArtifactModel]]
    target_stats_by_character: Optional[Dict[str, Dict[str, float]]] = None
    weapons_by_character: Optional[Dict[str, WeaponModel]] = None
    buffs_by_character: Optional[Dict[str, Dict[str, float]]] = None
    top_n: int = 3

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

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

# ---------------------------------------------------------------------------
# Helper – convert Pydantic models to optimizer domain objects
# ---------------------------------------------------------------------------

def _to_artifact(a: ArtifactModel) -> Artifact:
    return Artifact(
        id=a.id,
        slot=a.slot,
        set_key=a.set_key,
        rarity=a.rarity,
        level=a.level,
        main_stat=a.main_stat,
        main_stat_value=a.main_stat_value,
        substats=[Substat(stat=s.stat, value=s.value) for s in a.substats],
    )


def _to_weapon(w: Optional[WeaponModel]) -> Optional[Weapon]:
    if w is None:
        return None
    return Weapon(
        key=w.key,
        level=w.level,
        ascension=w.ascension,
        refinement=w.refinement,
        base_atk=w.base_atk,
        sub_stat=w.sub_stat,
        sub_stat_value=w.sub_stat_value,
    )


def _to_constraint(c: ConstraintModel) -> Constraint:
    return Constraint(
        type=c.type,
        slot=c.slot,
        value=c.value,
        threshold=c.threshold,
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


@app.post("/api/optimize")
async def optimize(request: OptimizeRequest):
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
        logger.info(f"Optimizing artifacts for {request.character}")
        domain_artifacts = [_to_artifact(a) for a in request.artifacts]
        domain_weapon = _to_weapon(request.weapon)
        domain_constraints = [_to_constraint(c) for c in request.constraints]

        builds = optimize_artifacts(
            character_key=request.character,
            available_artifacts=domain_artifacts,
            target_stats=request.target_stats,
            constraints=domain_constraints,
            weapon=domain_weapon,
            buffs=request.buffs,
            top_n=request.top_n,
        )

        return {
            "success": True,
            "character": request.character,
            "builds": [b.to_dict() for b in builds],
            "total_builds_found": len(builds),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error optimizing artifacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recommended-build")
async def recommended_build(request: RecommendedBuildRequest):
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
        logger.info(f"Fetching recommended build for {request.character}")
        target_stats = DEFAULT_TARGET_STATS.get(
            request.character,
            DEFAULT_TARGET_STATS["_default"],
        )
        domain_artifacts = [_to_artifact(a) for a in request.artifacts]
        domain_weapon = _to_weapon(request.weapon)

        builds = optimize_artifacts(
            character_key=request.character,
            available_artifacts=domain_artifacts,
            target_stats=target_stats,
            weapon=domain_weapon,
            buffs=request.buffs,
            top_n=request.top_n,
        )

        return {
            "success": True,
            "character": request.character,
            "target_stats": target_stats,
            "builds": [b.to_dict() for b in builds],
            "total_builds_found": len(builds),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting recommended build: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimize-team")
async def optimize_team(request: OptimizeTeamRequest):
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
        logger.info(f"Optimizing team: {request.team}")
        team_results = {}

        for character in request.team:
            raw_artifacts = request.artifacts_by_character.get(character, [])
            domain_artifacts = [_to_artifact(a) for a in raw_artifacts]

            target_stats = (request.target_stats_by_character or {}).get(
                character,
                DEFAULT_TARGET_STATS.get(character, DEFAULT_TARGET_STATS["_default"]),
            )

            raw_weapon = (request.weapons_by_character or {}).get(character)
            domain_weapon = _to_weapon(raw_weapon)

            team_buffs = (request.buffs_by_character or {}).get(character)

            builds = optimize_artifacts(
                character_key=character,
                available_artifacts=domain_artifacts,
                target_stats=target_stats,
                weapon=domain_weapon,
                buffs=team_buffs,
                top_n=request.top_n,
            )

            team_results[character] = {
                "target_stats": target_stats,
                "builds": [b.to_dict() for b in builds],
            }

        return {
            "success": True,
            "team": request.team,
            "results": team_results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error optimizing team: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount frontend static files (CSS, JS, etc.) - must be after API routes
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)