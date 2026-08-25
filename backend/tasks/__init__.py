"""
Celery tasks package.
All background tasks should be defined in this package.
"""

from backend.celery_app import celery_app
from backend.tasks.example_tasks import (
    add_task,
    long_running_task,
    process_file_task,
    send_notification_task,
)
from backend.tasks.pdf_tasks import process_pdf_task

__all__ = [
    "celery_app",
    "process_pdf_task",
    "add_task",
    "process_file_task",
    "long_running_task",
    "send_notification_task",
]
