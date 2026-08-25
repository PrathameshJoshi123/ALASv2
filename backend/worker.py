"""
Celery Worker Entry Point.

Run this script to start the Celery worker:
    celery -A backend.worker.celery_app worker --loglevel=info

Or with concurrent workers:
    celery -A backend.worker.celery_app worker --loglevel=info --concurrency=4

For production, use:
    celery -A backend.worker.celery_app worker --loglevel=info --concurrency=4 --max-tasks-per-child=100
"""

from backend.celery_app import celery_app

# This allows running with: celery -A backend.worker worker
celery = celery_app


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Celery worker")
    parser.add_argument("--concurrency", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--loglevel", type=str, default="info", help="Logging level")
    parser.add_argument("--queue", type=str, default="default", help="Queue to consume from")
    
    args = parser.parse_args()
    
    celery_app.worker_main(
        argv=[
            "worker",
            f"--loglevel={args.loglevel}",
            f"--concurrency={args.concurrency}",
            f"--queues={args.queue}",
        ]
    )
