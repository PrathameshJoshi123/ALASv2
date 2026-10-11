"""
Celery Worker Entry Point.

Run this script to start the Celery worker:
    celery -A backend.celery_app.celery_app worker --loglevel=info -P solo

Or run as module:
    python -m backend.worker
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.celery_app import celery_app

if __name__ == "__main__":
    import os
    import sys
    
    # Execute the celery worker command
    os.system("celery -A backend.celery_app.celery_app worker --loglevel=info -P solo")
