"""
Celery Task routes.
Endpoints for submitting and checking Celery tasks.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.celery_app import celery_app
from backend.config import settings
from backend.schemas import task_schemas

router = APIRouter(prefix="", tags=["tasks"])


@router.post(
    "/submit/add",
    response_model=task_schemas.TaskSubmitResponse,
    summary="Submit addition task",
)
async def submit_add_task(
    request: task_schemas.AddTaskRequest,
) -> dict:
    """
    Submit a task to add two numbers.
    """
    try:
        from backend.tasks.example_tasks import add_task
        
        # Submit task to Celery
        task = add_task.delay(request.a, request.b)
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": "Task submitted successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/submit/process-file",
    response_model=task_schemas.TaskSubmitResponse,
    summary="Submit file processing task",
)
async def submit_process_file_task(
    request: task_schemas.ProcessFileTaskRequest,
) -> dict:
    """
    Submit a task to process a file in the background.
    """
    try:
        from backend.tasks.example_tasks import process_file_task
        
        task = process_file_task.delay(
            file_path=request.file_path,
            output_dir=str(settings.OUTPUT_DIR),
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": "File processing task submitted",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/submit/long-running",
    response_model=task_schemas.TaskSubmitResponse,
    summary="Submit long running task",
)
async def submit_long_running_task(
    duration: int = 10,
) -> dict:
    """
    Submit a long-running task.
    """
    try:
        from backend.tasks.example_tasks import long_running_task
        
        task = long_running_task.delay(duration=duration)
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Long running task submitted for {duration} seconds",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{task_id}/status",
    response_model=task_schemas.TaskStatusResponse,
    summary="Check task status",
)
async def get_task_status(task_id: str) -> dict:
    """
    Check the status of a submitted task.
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "state": str(result.state),
            "successful": result.successful(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{task_id}/result",
    response_model=task_schemas.TaskResultResponse,
    summary="Get task result",
)
async def get_task_result(task_id: str) -> dict:
    """
    Get the result of a completed task.
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id, app=celery_app)
        
        if not result.ready():
            raise HTTPException(
                status_code=400,
                detail="Task not ready yet",
            )
        
        if not result.successful():
            raise HTTPException(
                status_code=400,
                detail=f"Task failed: {result.result}",
            )
        
        return {
            "task_id": task_id,
            "result": result.result,
            "status": "completed",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{task_id}/revoke",
    response_model=task_schemas.TaskActionResponse,
    summary="Revoke a task",
)
async def revoke_task(task_id: str) -> dict:
    """
    Revoke (cancel) a running task.
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)
        
        return {
            "task_id": task_id,
            "action": "revoked",
            "message": "Task revocation requested",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/queue",
    response_model=task_schemas.QueueStatusResponse,
    summary="Get queue status",
)
async def get_queue_status() -> dict:
    """
    Get information about the Celery task queue.
    """
    try:
        from celery.app.control import Inspect
        
        inspector = Inspect(app=celery_app)
        
        active_tasks = inspector.active() or {}
        scheduled_tasks = inspector.scheduled() or {}
        reserved_tasks = inspector.reserved() or {}
        
        workers = inspector.ping() or {}
        
        return {
            "active_workers": list(workers.keys()),
            "active_tasks": {k: [str(t) for t in v] for k, v in active_tasks.items()},
            "scheduled_tasks": scheduled_tasks,
            "reserved_tasks": reserved_tasks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
