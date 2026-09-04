from fastapi import APIRouter
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

@router.get("/plans")
async def get_plans():
    return [
        {"name": "starter", "price": 49, "features": ["1 проект", "50 AI-запросов/мес"]},
        {"name": "pro", "price": 149, "features": ["Безлимит проектов", "500 AI-запросов/мес"]},
        {"name": "agency", "price": 399, "features": ["Всё из Pro", "2000 AI-запросов/мес"]}
    ]
