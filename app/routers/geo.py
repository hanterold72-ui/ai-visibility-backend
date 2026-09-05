from fastapi import APIRouter, Depends, HTTPException
from app.auth import User, get_current_user
from app.config import settings
from app.models import GeoCheckRequest
from app.services.geo_tracker import GeoTrackerService

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])
tracker = GeoTrackerService()

def _valid_key(value: str, prefix: str) -> bool:
    if not value:
        return False
    if "ваш" in value.lower():
        return False
    return value.startswith(prefix)

def _auto_engine():
    if _valid_key(settings.GOOGLE_GEMINI_API_KEY, "AIza"):
        return "gemini"
    if _valid_key(settings.PERPLEXITY_API_KEY, "pplx-"):
        return "perplexity"
    return None

@router.post("/public/check")
async def public_check(req: GeoCheckRequest):
    engine = req.engine if req.engine != "auto" else _auto_engine()
    if not engine or not tracker.is_configured(engine):
        return {
            "query": req.query,
            "target_domain": req.target_domain,
            "engine": None,
            "result": {
                "is_cited": False,
                "citation_context": None,
                "source_url": None,
                "raw_answer_snippet": "AI-провайдер не настроен. Добавьте ключ Gemini в Render.",
                "engine_used": None,
            },
        }
    result = await tracker.check(req.query, req.target_domain, engine)
    return {"query": req.query, "target_domain": req.target_domain, "engine": engine, "result": result.dict()}

@router.post("/check")
async def geo_check(req: GeoCheckRequest, user: User = Depends(get_current_user)):
    engine = req.engine if req.engine != "auto" else (_auto_engine() or "gemini")
    if not tracker.is_configured(engine):
        raise HTTPException(500, f"AI provider for {engine} not configured")
    result = await tracker.check(req.query, req.target_domain, engine)
    return {"query": req.query, "target_domain": req.target_domain, "engine": engine, "result": result.dict()}