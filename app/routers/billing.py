from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import User, get_current_user
from app.database import get_db
from app.config import settings
import httpx
import uuid

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

PLANS = [
    {"id": "free", "name": "Бесплатный", "price": 0, "features": ["3 аудита/день", "Базовая AI-проверка", "История 7 дней"]},
    {"id": "pro", "name": "Pro", "price": 990, "currency": "RUB", "features": ["Безлимитные аудиты", "Все AI-провайдеры", "История 1 год", "Приоритетная поддержка"]},
    {"id": "business", "name": "Business", "price": 2990, "currency": "RUB", "features": ["Всё из Pro", "API доступ", "Командный кабинет", "Персональный менеджер"]},
]

@router.get("/plans")
async def get_plans():
    return PLANS

@router.post("/create-payment/yookassa")
async def create_yookassa_payment(plan_id: str, request: Request, user: User = Depends(get_current_user)):
    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan or plan["price"] == 0:
        raise HTTPException(400, "Неверный тариф")

    shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
    secret = getattr(settings, "YOOKASSA_SECRET_KEY", "")
    if not shop_id or not secret:
        raise HTTPException(500, "ЮKassa не настроена")

    origin = request.headers.get("origin", "https://ai-visibility-frontend.vercel.app")
    payload = {
        "amount": {"value": f"{plan['price']:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": f"{origin}/dashboard?payment=success"},
        "description": f"Тариф {plan['name']} — AI-Visibility",
        "metadata": {"user_id": user.id, "plan_id": plan_id},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            auth=(shop_id, secret),
            headers={"Idempotence-Key": str(uuid.uuid4())},
        )
        resp.raise_for_status()
        data = resp.json()

    return {"confirmation_url": data["confirmation"]["confirmation_url"], "payment_id": data["id"]}

@router.post("/create-payment/stripe")
async def create_stripe_payment(plan_id: str, request: Request, user: User = Depends(get_current_user)):
    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan or plan["price"] == 0:
        raise HTTPException(400, "Неверный тариф")

    stripe_key = getattr(settings, "STRIPE_SECRET_KEY", "")
    if not stripe_key:
        raise HTTPException(500, "Stripe не настроен")

    origin = request.headers.get("origin", "https://ai-visibility-frontend.vercel.app")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data={
                "mode": "payment",
                "line_items[0][price_data][currency]": "rub",
                "line_items[0][price_data][unit_amount]": plan["price"] * 100,
                "line_items[0][price_data][product_data][name]": f"Тариф {plan['name']}",
                "line_items[0][quantity]": 1,
                "success_url": f"{origin}/dashboard?payment=success",
                "cancel_url": f"{origin}/pricing?payment=cancelled",
                "metadata[user_id]": user.id,
                "metadata[plan_id]": plan_id,
            },
            headers={"Authorization": f"Bearer {stripe_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    return {"checkout_url": data["url"], "session_id": data["id"]}