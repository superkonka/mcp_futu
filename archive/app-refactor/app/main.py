from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from app.config import settings
from app.services.futu_service import futu_service
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import quote, analysis, market, tools, dashboard, stubs

# ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await futu_service.connect()
    yield
    # Shutdown
    await futu_service.disconnect()
    logger.info("Service stopped")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(quote.router, prefix="/api/quote", tags=["Quote"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(stubs.router, prefix="/api", tags=["Stubs"])

# SSE Alias for frontend compatibility
@app.get("/web/api/stream/{session_id}")
async def stream_alias(session_id: str, request: Request):
    from app.api.endpoints.dashboard import sse_endpoint
    return await sse_endpoint(session_id, request)

from fastapi.responses import RedirectResponse

# ...

# Static Files
app.mount("/web", StaticFiles(directory="web/dashboard-app/dist", html=True), name="web")

@app.get("/")
async def root():
    return RedirectResponse(url="/web/index.html")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "futu_connected": futu_service.quote_ctx is not None,
        "version": settings.app_version
    }
