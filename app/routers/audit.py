from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import User, get_current_user
from app.database import get_db, async_session
from app.models import Audit, AuditRequest, Project
from app.services.site_auditor import SiteAuditor

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
auditor = SiteAuditor()

async def _run_audit(domain: str, audit_id: int):
    async with async_session() as db:
        try:
            result = await auditor.full_audit(domain)
            audit = await db.get(Audit, audit_id)
            audit.status = "completed"
            audit.results = result.model_dump(mode="json")
        except Exception as e:
            audit = await db.get(Audit, audit_id)
            audit.status = "failed"
            audit.results = {"error": str(e)}
        await db.commit()

@router.post("/full")
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

@router.get("/{audit_id}")
async def get_audit(audit_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    audit = await db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
    return {"id": audit.id, "status": audit.status, "results": audit.results}