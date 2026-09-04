from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

startup_error = None
_routers = []
settings = None
engine = None
Base = None

try:
    from app.config import settings
    from app.database import engine, Base
    from app import auth, billing, admin_api
    from app.routers import geo, audit, promotion
    _routers = [auth.router, geo.router, audit.router,
                promotion.router, billing.router, admin_api.router]
except Exception as e:
    startup_error = f"IMPORT ERROR → {type(e).__name__}: {e}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global startup_error
    if engine is not None and settings is not None and settings.AUTO_CREATE_TABLES:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            startup_error = None
        except Exception as e:
            err = str(e)
            if "already exists" in err or "duplicate key" in err:
                # Таблицы созданы параллельным воркером — это НЕ ошибка
                startup_error = None
            else:
                startup_error = f"DB ERROR → {type(e).__name__}: {e}"
    yield

app = FastAPI(title="AI-Visibility Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in _routers:
    app.include_router(r)

@app.get("/")
@app.get("/health")
async def health():
    payload = {"status": "healthy", "version": "1.2.0"}
    if startup_error:
        payload["startup_error"] = startup_error
    return payload