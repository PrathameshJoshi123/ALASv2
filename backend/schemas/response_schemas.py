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
    original_filename: Optional[str] = Field(None, description="Original filename of the document")
    markdown_file: Optional[str] = Field(None, description="Associated markdown filename")
    storage_link: str = Field(..., description="Path to the stored PDF file")
    date_created: str = Field(..., description="Timestamp when document was created")
    created_at: Optional[str] = Field(None, description="Timestamp ISO string")
    counterparty_name: Optional[str] = Field(None, description="Counterparty name")
    company_name: Optional[str] = Field(None, description="Company name")
    contract_type: Optional[str] = Field(None, description="Contract type")
    status: str = Field("UPLOADED", description="Document processing status")
    live: Optional[dict[str, Any]] = Field(default_factory=dict, description="Live worker status")
    overall_risk_score: Optional[float] = Field(0.0, description="Overall risk score percentage")
    critical_issues: Optional[int] = Field(0, description="Critical issues count")
    high_issues: Optional[int] = Field(0, description="High issues count")
    medium_issues: Optional[int] = Field(0, description="Medium issues count")
    low_issues: Optional[int] = Field(0, description="Low issues count")
    analysis_summary: Optional[str] = Field("", description="Summary of contract analysis")
    recommended_actions: Optional[list[str]] = Field(default_factory=list, description="Recommended actions")
    clauses: Optional[list[dict[str, Any]]] = Field(default_factory=list, description="Clauses analysis list")
    analysis: Optional[dict[str, Any]] = Field(None, description="Raw DB analysis dictionary")
    analysis_markdown: Optional[str] = Field(None, description="Markdown content of contract or analysis")


class DocumentUploadResponse(BaseModel):
    """Response for document upload endpoint."""
    
    status: str = Field(..., description="Upload status")
    document_id: str = Field(..., description="Unique document identifier")
    document_name: str = Field(..., description="Name of the uploaded document")
    storage_path: str = Field(..., description="Path where file was stored")
    task_id: Optional[str] = Field(None, description="Celery task ID for background analysis")
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
