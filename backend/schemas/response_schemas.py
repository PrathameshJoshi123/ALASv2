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


class DocumentResponse(BaseModel):
    """Document information response."""
    
    id: str = Field(..., description="Unique document identifier")
    name: str = Field(..., description="Name of the document")
    storage_link: str = Field(..., description="Path to the stored PDF file")
    date_created: str = Field(..., description="Timestamp when document was created")


class DocumentUploadResponse(BaseModel):
    """Response for document upload endpoint."""
    
    status: str = Field(..., description="Upload status")
    document_id: str = Field(..., description="Unique document identifier")
    document_name: str = Field(..., description="Name of the uploaded document")
    storage_path: str = Field(..., description="Path where file was stored")
    message: Optional[str] = Field(None, description="Additional message")


class PDFElementResponse(BaseModel):
    """Response for a single PDF element."""
    
    type: str = Field(..., description="Type of element (Title, NarrativeText, Table, etc.)")
    text: str = Field(..., description="Text content of the element")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Element metadata")


class PDFProcessingResponse(BaseModel):
    """Response for PDF processing endpoint."""
    
    status: str = Field(..., description="Processing status")
    document_id: str = Field(..., description="Unique document identifier")
    elements_count: int = Field(..., description="Number of elements extracted")
    elements: list[PDFElementResponse] = Field(default_factory=list, description="List of extracted elements")
    message: Optional[str] = Field(None, description="Additional message")
