from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models import Project
from app.services.site_auditor import SiteAuditor

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

async def _run_all_audits():
    """Запускает аудит всех проектов в фоне"""
    auditor = SiteAuditor()
    async with async_session() as db:
        projects = (await db.execute(select(Project))).scalars().all()
        for p in projects:
            try:
                await auditor.full_audit(p.domain)
            except Exception as e:
                print(f"Audit failed for {p.domain}: {e}")
                continue

@router.post("/run-daily-audit")
async def run_daily_audit(background: BackgroundTasks, x_api_key: str = Header(None)):
    """Endpoint для внешнего cron (cron-job.org)"""
    if x_api_key != settings.SERVICE_API_KEY:
        raise HTTPException(403, "Forbidden")
    background.add_task(_run_all_audits)
    return {"status": "triggered", "message": "Daily audit started in background"}

@router.get("/stats")
async def admin_stats(x_api_key: str = Header(None)):
    """Простая статистика для админки"""
    if x_api_key != settings.SERVICE_API_KEY:
        raise HTTPException(403, "Forbidden")
    from app.database import async_session
    from app.models import Project, Audit, Optimization
    from sqlalchemy import func
    
    async with async_session() as db:
        projects_count = (await db.execute(select(func.count(Project.id)))).scalar() or 0
        audits_count = (await db.execute(select(func.count(Audit.id)))).scalar() or 0
        opts_count = (await db.execute(select(func.count(Optimization.id)))).scalar() or 0
    
    return {
        "total_projects": projects_count,
        "total_audits": audits_count,
        "total_optimizations": opts_count,
        "status": "healthy"
    }
