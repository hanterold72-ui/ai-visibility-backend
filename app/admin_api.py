from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import User, get_current_user
from app.database import get_db
from app.models import Project, Audit, CitationTracking, Optimization
from app.config import settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ADMIN_EMAILS = ["admin@ai-visibility.ru"]

async def require_admin(user: User = Depends(get_current_user)):
    if user.email not in ADMIN_EMAILS:
        raise HTTPException(403, "Доступ запрещён")
    return user

@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    projects_count = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    audits_count = (await db.execute(select(func.count(Audit.id)))).scalar() or 0
    citations_count = (await db.execute(select(func.count(CitationTracking.id)))).scalar() or 0
    
    recent_audits = (await db.execute(
        select(Audit, Project.domain)
        .join(Project, Audit.project_id == Project.id)
        .order_by(desc(Audit.created_at))
        .limit(10)
    )).all()
    
    return {
        "users": users_count,
        "projects": projects_count,
        "audits": audits_count,
        "citations": citations_count,
        "recent_audits": [
            {"id": a.id, "domain": d, "status": a.status, "created_at": str(a.created_at)}
            for a, d in recent_audits
        ],
    }

@router.get("/users")
async def list_users(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(desc(User.created_at)).offset(skip).limit(limit))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "is_verified": u.is_verified,
            "created_at": str(u.created_at),
        }
        for u in users
    ]

@router.get("/settings")
async def get_settings(admin: User = Depends(require_admin)):
    return {
        "perplexity_key_set": bool(settings.PERPLEXITY_API_KEY and "ваш" not in settings.PERPLEXITY_API_KEY.lower()),
        "gemini_key_set": bool(settings.GOOGLE_GEMINI_API_KEY and "ваш" not in settings.GOOGLE_GEMINI_API_KEY.lower()),
        "openai_key_set": bool(settings.OPENAI_API_KEY and "ваш" not in settings.OPENAI_API_KEY.lower()),
        "yookassa_shop_id": getattr(settings, "YOOKASSA_SHOP_ID", ""),
        "yookassa_secret_set": bool(getattr(settings, "YOOKASSA_SECRET_KEY", "")),
        "stripe_key_set": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
        "site_title": getattr(settings, "SITE_TITLE", "AI-Visibility"),
        "site_description": getattr(settings, "SITE_DESCRIPTION", ""),
        "admin_emails": ADMIN_EMAILS,
    }

@router.post("/run-daily-audit")
async def run_daily_audit(admin: User = Depends(require_admin)):
    return {"message": "Ежедневный аудит запущен", "triggered_by": admin.email}