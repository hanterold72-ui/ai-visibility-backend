from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import time
from app.auth import User, get_current_user
from app.database import get_db, async_session
from app.models import Audit, AuditRequest, Project
from app.services.site_auditor import SiteAuditor

router = APIRouter(prefix="/api/v1", tags=["audit"])
auditor = SiteAuditor()

_last_public = {}

async def _run_audit(domain: str, audit_id: int):
    async with async_session() as db:
        try:
            result = await auditor.full_audit(domain)
            audit = await db.get(Audit, audit_id)
            audit.status = "completed"
            audit.results = result
        except Exception as e:
            audit = await db.get(Audit, audit_id)
            audit.status = "failed"
            audit.results = {"error": str(e)}
        await db.commit()

@router.post("/public/audit")
async def public_audit(req: AuditRequest, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    if now - _last_public.get(ip, 0) < 10:
        raise HTTPException(429, "Слишком часто. Подождите 10 секунд.")
    _last_public[ip] = now

    project_result = await db.execute(select(Project).where(Project.domain == req.domain))
    project = project_result.scalar_one_or_none()
    if not project:
        project = Project(name=req.domain, domain=req.domain)
        db.add(project)
        await db.commit()
        await db.refresh(project)

    audit = Audit(project_id=project.id, audit_type="full", status="running")
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(_run_audit, req.domain, audit.id)
    return {"audit_id": audit.id, "status": "running"}

@router.get("/public/audit/{audit_id}")
async def public_get_audit(audit_id: int, db: AsyncSession = Depends(get_db)):
    audit = await db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
    return {"id": audit.id, "status": audit.status, "results": audit.results}

@router.get("/audit/history")
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Audit, Project.domain)
        .join(Project, Audit.project_id == Project.id)
        .where(Project.user_id == user.id)
        .order_by(desc(Audit.created_at))
        .limit(50)
    )).all()
    return [
        {
            "id": a.id,
            "domain": d,
            "status": a.status,
            "score": (a.results or {}).get("overall_score"),
            "created_at": str(a.created_at),
        }
        for a, d in rows
    ]

@router.post("/audit/full")
async def run_full_audit(req: AuditRequest, background_tasks: BackgroundTasks,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    project_result = await db.execute(select(Project).where(Project.domain == req.domain))
    project = project_result.scalar_one_or_none()
    if not project:
        project = Project(name=req.domain, domain=req.domain, user_id=user.id)
        db.add(project)
        await db.commit()
        await db.refresh(project)

    audit = Audit(project_id=project.id, audit_type="full", status="running")
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(_run_audit, req.domain, audit.id)
    return {"audit_id": audit.id, "status": "running"}

@router.get("/audit/{audit_id}")
async def get_audit(audit_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    audit = await db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
    return {"id": audit.id, "status": audit.status, "results": audit.results}