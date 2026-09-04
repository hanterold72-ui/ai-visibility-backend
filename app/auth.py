import os
import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from jose import jwt, JWTError
from app.database import get_db, Base

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SECRET_KEY = os.environ.get("JWT_SECRET", "change-me")
ALGORITHM = "HS256"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex() == h
    except:
        return False

def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except:
        raise HTTPException(401, "Invalid token")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    user = User(email=req.email, name=req.name, password_hash=hash_password(req.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"token": create_token(user.id), "user": {"id": user.id, "email": user.email, "name": user.name}}

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"token": create_token(user.id), "user": {"id": user.id, "email": user.email, "name": user.name}}

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}
