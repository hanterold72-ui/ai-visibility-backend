from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Конвертируем URL и чиним параметры под asyncpg
url = settings.DATABASE_URL
url = url.replace("postgresql://", "postgresql+asyncpg://")
url = url.replace("postgres://", "postgresql+asyncpg://")
url = url.replace("sslmode=require", "ssl=require")          # ← главное исправление
url = url.replace("&channel_binding=require", "")            # ← asyncpg это тоже не любит
url = url.replace("?channel_binding=require", "")

engine = create_async_engine(
    url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()