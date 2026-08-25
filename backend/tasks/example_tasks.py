"""
Example Celery tasks for demonstration.
Replace with your actual background task implementations.
"""

import time
from pathlib import Path

from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

from backend.config import settings

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="example_add_task")
def add_task(self, a: int, b: int) -> int:
    """
    Example task: Add two numbers.
    Demonstrates basic task execution.
    """
    logger.info(f"Adding {a} + {b}")
    result = a + b
    logger.info(f"Result: {result}")
    return result


@celery_app.task(bind=True, name="example_process_file_task")
def process_file_task(self, file_path: str, output_dir: str) -> dict:
    """
    Example task: Process a file in the background.
    Simulates long-running file processing.
    """
    logger.info(f"Processing file: {file_path}")
    
    # Simulate work
    time.sleep(5)
    
    input_path = Path(file_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Copy file (simulating processing)
    output_file = output_path / input_path.name
    output_file.write_text(input_path.read_text())
    
    logger.info(f"File processed and saved to: {output_file}")
    
    return {
        "status": "completed",
        "input_file": str(input_path),
        "output_file": str(output_file),
        "size": input_path.stat().st_size,
    }


@celery_app.task(bind=True, name="example_long_running_task")
def long_running_task(self, duration: int = 10) -> str:
    """
    Example task: Simulate a long-running operation.
    """
    logger.info(f"Starting long task for {duration} seconds")
    
    for i in range(duration):
        time.sleep(1)
        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": duration, "status": "Processing..."}
        )
    
    logger.info("Long task completed")
    return f"Slept for {duration} seconds"


@celery_app.task(bind=True, name="example_send_notification_task")
def send_notification_task(self, message: str, recipient: str) -> dict:
    """
    Example task: Simulate sending a notification.
    """
    logger.info(f"Sending notification to {recipient}: {message}")
    
    # Simulate API call
    time.sleep(2)
    
    return {
        "status": "sent",
        "message": message,
        "recipient": recipient,
        "timestamp": time.time(),
    }


__all__ = [
    "add_task",
    "process_file_task",
    "long_running_task",
    "send_notification_task",
]
