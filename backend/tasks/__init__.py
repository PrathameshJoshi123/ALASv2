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
from backend.tasks.pdf_tasks import process_pdf_task, process_and_chunk_task, run_agent_analysis_task
from backend.tasks.drafting_tasks import run_agent_drafting_task
from backend.tasks.chunking_tasks import chunk_document_task, rechunk_document_task
from backend.tasks.context_tasks import analyze_chunks_context_task
from backend.tasks.entity_mention_tasks import (
    analyze_single_chunk_entities_task,
    analyze_document_entities_task,
)

__all__ = [
    "celery_app",
    "process_pdf_task",
    "process_and_chunk_task",
    "run_agent_analysis_task",
    "run_agent_drafting_task",
    "chunk_document_task",
    "rechunk_document_task",
    "analyze_chunks_context_task",
    "analyze_single_chunk_entities_task",
    "analyze_document_entities_task",
    "add_task",
    "process_file_task",
    "long_running_task",
    "send_notification_task",
]
