from fastapi import APIRouter
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/stats")
async def admin_stats():
    return {"total_users": 0, "total_projects": 0, "mrr": 0}
