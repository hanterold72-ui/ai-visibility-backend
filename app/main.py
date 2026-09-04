from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

startup_error = None
_routers = []
_settings = None
_engine = None
_Base = None

try:
    from app.config import settings as _settings
    from app.database import engine as _engine, Base as _Base
    from app import auth, billing, admin_api
    from app.routers import geo, audit, promotion
    _routers = [auth.router, geo.router, audit.router,
                promotion.router, billing.router, admin_api.router]
except Exception as e:
    startup_error = f"{type(e).__name__}: {e}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global startup_error
    if _engine is not None and _settings is not None and _settings.AUTO_CREATE_TABLES:
        try:
            async with _engine.begin() as conn:
                await conn.run_sync(_Base.metadata.create_all)
            startup_error = None
        except Exception as e:
            if "already exists" not in str(e) and "duplicate key" not in str(e):
                startup_error = f"DB: {type(e).__name__}: {e}"
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
    return {"status": "healthy", "version": "1.0.0"}