"""
API Routes package.
All FastAPI route modules should be defined here.
"""

from backend.routes.api import router as api_router
from backend.routes.contracts import router as contracts_router
from backend.routes.tasks import router as tasks_router

# Import chunking router if available
try:
    from backend.routes.chunking import router as chunking_router
    _HAS_CHUNKING = True
except ImportError:
    chunking_router = None
    _HAS_CHUNKING = False

__all__ = ["api_router", "contracts_router", "tasks_router"]
if _HAS_CHUNKING:
    __all__.append("chunking_router")
