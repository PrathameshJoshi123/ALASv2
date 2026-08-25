"""
FastAPI Application Entry Point.

This module creates and configures the FastAPI application with:
- API routes
- Database integration
- Celery task support
- CORS configuration
- Error handling
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.celery_app import celery_app
from backend.config import settings
from backend.database import Base, init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    Uses asyncio.to_thread for sync database operations.
    """
    # Startup
    logger.info("Starting application...")
    
    # Ensure directories exist
    settings.ensure_directories()
    logger.info(f"Storage directories created")
    
    # Initialize database (sync function run in thread)
    try:
        await asyncio.to_thread(init_db)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database URL: {settings.database_url}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        await asyncio.to_thread(close_db)
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Database shutdown failed: {e}")
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MajorProject Backend API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path("backend/static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "type": type(exc).__name__,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "app_name": settings.APP_NAME,
    }


# Celery health check
@app.get("/celery/health", tags=["health", "celery"])
async def celery_health() -> dict:
    """Check Celery worker connectivity."""
    try:
        # Test Celery connection by pinging the broker
        from celery.app.control import Inspect
        
        inspector = Inspect(app=celery_app)
        workers = inspector.active()
        
        return {
            "status": "healthy",
            "workers": list(workers.keys()) if workers else [],
            "broker_url": settings.CELERY_BROKER_URL,
        }
    except Exception as e:
        logger.warning(f"Celery health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# Database health check
@app.get("/db/health", tags=["health", "database"])
async def db_health() -> dict:
    """Check database connectivity."""
    try:
        from sqlalchemy import text
        from backend.database import SessionLocal
        
        def check_db():
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        
        await asyncio.to_thread(check_db)
        return {
            "status": "healthy",
            "database_url": settings.database_url,
        }
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# API Info endpoint
@app.get("/info", tags=["info"])
async def api_info() -> dict:
    """API information endpoint."""
    return {
        "app_name": settings.APP_NAME,
        "version": __version__,
        "debug": settings.DEBUG,
        "features": {
            "contract_analysis": settings.CONTRACT_ANALYSIS_ENABLED,
            "web_research": settings.WEB_RESEARCH_ENABLED,
        },
        "storage": {
            "upload_dir": str(settings.UPLOAD_DIR),
            "output_dir": str(settings.OUTPUT_DIR),
            "chroma_dir": str(settings.CHROMA_DIR),
        },
    }


# Include API routers
from backend.routes import api_router, contracts_router, tasks_router

app.include_router(api_router, prefix="/api/v1", tags=["api"])
app.include_router(contracts_router, prefix="/api/v1", tags=["contracts"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])

# Include chunking router if available
try:
    from backend.routes import chunking_router
    if chunking_router:
        app.include_router(chunking_router, prefix="/api/v1", tags=["chunking"])
        logger.info("Chunking routes mounted")
except ImportError:
    pass


# Root endpoint
@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": __version__,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
