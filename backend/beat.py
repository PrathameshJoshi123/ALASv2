"""
Celery Beat Scheduler Entry Point.

Run this to start the Celery beat scheduler for periodic tasks:
    celery -A backend.beat.celery_app beat --loglevel=info

For production, consider using a separate process or container for the scheduler.
"""

from backend.celery_app import celery_app

# This allows running with: celery -A backend.beat beat
celery = celery_app


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Celery beat scheduler")
    parser.add_argument("--loglevel", type=str, default="info", help="Logging level")
    parser.add_argument("--schedule", type=str, default="./celerybeat-schedule", help="Schedule file path")
    
    args = parser.parse_args()
    
    celery_app.worker_main(
        argv=[
            "beat",
            f"--loglevel={args.loglevel}",
            f"--schedule={args.schedule}",
        ]
    )
