"""
Task-related schemas for Celery task management.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskSubmitResponse(BaseModel):
    """Response when a task is submitted."""
    
    task_id: str = Field(..., description="Unique task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")


class TaskStatusResponse(BaseModel):
    """Response with task status information."""
    
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Current task status")
    result: Optional[Any] = Field(None, description="Task result if completed")
    state: str = Field(..., description="Task state")
    successful: bool = Field(..., description="Whether task completed successfully")


class TaskResultResponse(BaseModel):
    """Response with task result."""
    
    task_id: str = Field(..., description="Task ID")
    result: Any = Field(..., description="Task result")
    status: str = Field(..., description="Task status")


class TaskActionResponse(BaseModel):
    """Response for task actions (revoke, etc.)."""
    
    task_id: str = Field(..., description="Task ID")
    action: str = Field(..., description="Action performed")
    message: str = Field(..., description="Action message")


class QueueStatusResponse(BaseModel):
    """Response with queue status information."""
    
    active_workers: list[str] = Field(default_factory=list, description="Active worker names")
    active_tasks: dict[str, list[str]] = Field(default_factory=dict, description="Active tasks per worker")
    scheduled_tasks: dict[str, Any] = Field(default_factory=dict, description="Scheduled tasks")
    reserved_tasks: dict[str, Any] = Field(default_factory=dict, description="Reserved tasks")


# Request schemas
class AddTaskRequest(BaseModel):
    """Request to submit an addition task."""
    
    a: int = Field(..., description="First number to add")
    b: int = Field(..., description="Second number to add")


class ProcessFileTaskRequest(BaseModel):
    """Request to submit a file processing task."""
    
    file_path: str = Field(..., description="Path to the file to process")
