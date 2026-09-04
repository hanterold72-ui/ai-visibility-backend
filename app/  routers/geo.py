from fastapi import APIRouter, Depends, HTTPException
from app.auth import User, get_current_user
from app.models import GeoCheckRequest
from app.services.geo_tracker import GeoTrackerService

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])
tracker = GeoTrackerService()

@router.post("/check")
async def geo_check(req: GeoCheckRequest, user: User = Depends(get_current_user)):
    if not tracker.is_configured(req.engine):
        raise HTTPException(500, f"AI provider for {req.engine} not configured")
    result = await tracker.check(req.query, req.target_domain, req.engine)
    return {"query": req.query, "target_domain": req.target_domain, "engine": req.engine, "result": result.dict()}
