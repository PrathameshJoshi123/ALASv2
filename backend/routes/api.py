"""
Main API routes.
Add your application-specific endpoints here.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.schemas import response_schemas

router = APIRouter(prefix="", tags=["api"])


@router.get("/", response_model=response_schemas.APIStatusResponse)
async def api_root() -> dict:
    """API root endpoint."""
    return {
        "status": "ok",
        "message": "API is running",
        "version": "1.0.0",
    }


@router.post("/upload", response_model=response_schemas.UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
) -> dict:
    """
    Upload a file to the uploads directory.
    """
    # Ensure upload directory exists
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = upload_dir / file.filename
    
    # Handle duplicate filenames
    counter = 1
    while file_path.exists():
        file_path = upload_dir / f"{Path(file.filename).stem}_{counter}{Path(file.filename).suffix}"
        counter += 1
    
    # Write file
    with file_path.open("wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {
        "status": "success",
        "filename": file.filename,
        "saved_path": str(file_path),
        "size": len(content),
        "content_type": file.content_type,
        "description": description,
    }


@router.get("/files", response_model=response_schemas.FileListResponse)
async def list_files() -> dict:
    """
    List all uploaded files.
    """
    upload_dir = settings.UPLOAD_DIR
    
    if not upload_dir.exists():
        return {"files": []}
    
    files = []
    for file_path in upload_dir.iterdir():
        if file_path.is_file():
            files.append({
                "name": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
            })
    
    return {"files": files}


@router.get("/config", response_model=response_schemas.ConfigResponse)
async def get_config() -> dict:
    """
    Get current configuration (non-sensitive settings only).
    """
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "upload_dir": str(settings.UPLOAD_DIR),
        "output_dir": str(settings.OUTPUT_DIR),
        "features": {
            "contract_analysis": settings.CONTRACT_ANALYSIS_ENABLED,
            "web_research": settings.WEB_RESEARCH_ENABLED,
        },
    }
