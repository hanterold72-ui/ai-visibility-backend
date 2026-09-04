from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import User, get_current_user
from app.database import get_db
from app.models import ApplyOptimizationRequest, Optimization

router = APIRouter(prefix="/api/v1/promotion", tags=["promotion"])

@router.get("/optimizations/{project_id}")
async def list_optimizations(project_id: int, status: str = None,
                             user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Optimization).where(Optimization.project_id == project_id)
    if status:
        query = query.where(Optimization.status == status)
    result = await db.execute(query)
    return [{"id": o.id, "page_url": o.page_url, "optimization_type": o.optimization_type,
             "description": o.description, "status": o.status, "changes": o.changes}
            for o in result.scalars().all()]

@router.post("/apply")
async def apply(req: ApplyOptimizationRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    opt = await db.get(Optimization, req.optimization_id)
    if not opt:
        raise HTTPException(404, "Optimization not found")
    opt.status = "applied"
    opt.applied_at = datetime.utcnow()
    await db.commit()
    return {"status": "applied", "optimization_id": opt.id}