"""
Celery Beat Scheduler Entry Point.

Run this script to start the Celery beat scheduler for periodic tasks:
    celery -A backend.celery_app.celery_app beat --loglevel=info

Or run as module:
    python -m backend.beat

For production, consider using a separate process or container for the scheduler.
"""

from backend.celery_app import celery_app

if __name__ == "__main__":
    import os
    import sys
    
    # Execute the celery beat command
    os.system("celery -A backend.celery_app.celery_app beat --loglevel=info")
