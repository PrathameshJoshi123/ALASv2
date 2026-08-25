"""
API Routes package.
All FastAPI route modules should be defined here.
"""

from backend.routes.api import router as api_router
from backend.routes.tasks import router as tasks_router

__all__ = ["api_router", "tasks_router"]
