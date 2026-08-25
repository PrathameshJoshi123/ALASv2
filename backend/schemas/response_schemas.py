"""
Response schemas for API endpoints.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class APIStatusResponse(BaseModel):
    """API status response."""
    
    status: str = Field(..., description="Status of the API")
    message: str = Field(..., description="Status message")
    version: str = Field(..., description="API version")


class UploadResponse(BaseModel):
    """File upload response."""
    
    status: str = Field(..., description="Upload status")
    filename: str = Field(..., description="Original filename")
    saved_path: str = Field(..., description="Path where file was saved")
    size: int = Field(..., description="File size in bytes")
    content_type: Optional[str] = Field(None, description="Content type of the file")
    description: Optional[str] = Field(None, description="Optional description")


class FileInfo(BaseModel):
    """File information."""
    
    name: str = Field(..., description="Filename")
    path: str = Field(..., description="Full path to file")
    size: int = Field(..., description="File size in bytes")


class FileListResponse(BaseModel):
    """List of uploaded files."""
    
    files: list[FileInfo] = Field(default_factory=list, description="List of files")


class ConfigResponse(BaseModel):
    """Configuration response."""
    
    app_name: str = Field(..., description="Application name")
    app_version: str = Field(..., description="Application version")
    debug: bool = Field(..., description="Debug mode status")
    upload_dir: str = Field(..., description="Upload directory path")
    output_dir: str = Field(..., description="Output directory path")
    features: dict[str, bool] = Field(default_factory=dict, description="Enabled features")
