"""
Celery application configuration.
Handles background task processing with Redis as the message broker.
"""

from celery import Celery
from celery.schedules import crontab

from backend.config import settings


def create_celery_app() -> Celery:
    """
    Create and configure the Celery application.
    
    Returns:
        Configured Celery instance.
    """
        
    # Create Celery app
    app = Celery(
        main="backend",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    
    # Configure app settings
    app.conf.update(
        # Task settings
        task_serializer=settings.CELERY_TASK_SERIALIZER,
        result_serializer=settings.CELERY_RESULT_SERIALIZER,
        accept_content=settings.CELERY_ACCEPT_CONTENT,
        timezone=settings.CELERY_TIMEZONE,
        enable_utc=settings.CELERY_ENABLE_UTC,
        
        # Performance settings
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        worker_max_memory_per_child=300000,  # 300MB
        
        # Result settings
        result_expires=3600,  # 1 hour
        result_extended=True,
        result_compression="gzip",
        
        # Import settings
        imports=(
            "backend.tasks",
        ),
        
        # Schedule settings
        beat_schedule={
            # Example scheduled tasks (add your own)
            # "cleanup-old-files": {
            #     "task": "backend.tasks.cleanup_old_files",
            #     "schedule": crontab(hour=2, minute=30),  # Daily at 2:30 AM
            # },
        },
        
        # Retry settings
        task_acks_late=True,
        task_retry_limit=3,
        task_default_retry_delay=60,
        task_max_retries=3,
        
        # Queue settings
        task_default_queue="default",
        
        # Logging
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_log_level="INFO",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s",
    )
    
    return app


# Create Celery instance
celery_app = create_celery_app()


# Optional: Configure logging
import logging
from celery.signals import setup_logging


@setup_logging.connect
def configure_logging(*args, **kwargs):
    """Configure logging for Celery workers."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


__all__ = ["celery_app", "create_celery_app"]
