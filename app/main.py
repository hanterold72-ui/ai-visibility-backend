from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import traceback

startup_error = None
debug_info = []
_routers = []

# Глобальные переменные для lifespan
_settings = None
_engine = None
_Base = None

try:
    debug_info.append("Importing config...")
    from app.config import settings as _settings
    
    debug_info.append("Importing database...")
    from app.database import engine as _engine, Base as _Base
    
    debug_info.append("Importing auth...")
    from app import auth
    
    debug_info.append("Importing billing...")
    from app import billing
    
    debug_info.append("Importing admin_api...")
    from app import admin_api
    
    debug_info.append("Importing routers.geo...")
    from app.routers import geo
    
    debug_info.append("Importing routers.audit...")
    from app.routers import audit
    
    debug_info.append("Importing routers.promotion...")
    from app.routers import promotion
    
    _routers = [auth.router, geo.router, audit.router,
                promotion.router, billing.router, admin_api.router]
    debug_info.append(f"SUCCESS: {_routers} routers loaded")
    
except Exception as e:
    startup_error = f"IMPORT ERROR at step: {debug_info[-1] if debug_info else 'unknown'} → {type(e).__name__}: {e}"
    debug_info.append(f"FAILED: {traceback.format_exc()}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global startup_error
    if _engine is not None and _settings is not None and _settings.AUTO_CREATE_TABLES:
        try:
            async with _engine.begin() as conn:
                await conn.run_sync(_Base.metadata.create_all)
            startup_error = None
        except Exception as e:
            err = str(e)
            if "already exists" in err or "duplicate key" in err:
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
    payload = {
        "status": "healthy",
        "version": "1.3.0-debug",
        "routers_loaded": len(_routers),
        "debug_info": debug_info
    }
    if startup_error:
        payload["startup_error"] = startup_error
    return payload