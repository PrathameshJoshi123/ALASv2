import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models.cases import Case, CaseDocument, CaseTimeline, CaseAnalysis, CaseAgentMemory
from backend.tasks.case_tasks import process_case_document_task, analyze_case_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


# ============================================================
# Schemas
# ============================================================

class CaseCreateRequest(BaseModel):
    title: str = Field(..., example="State of Maharashtra vs. John Doe")
    description: Optional[str] = Field(None, example="Homicide case involving circumstantial evidence")

class CaseResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CaseDocumentResponse(BaseModel):
    id: str
    case_id: str
    name: str
    storage_link: str
    file_type: str
    document_type: Optional[str]
    status: str
    date_created: datetime
    
    class Config:
        from_attributes = True

class CaseUploadResponse(BaseModel):
    status: str
    document_id: str
    document_name: str
    storage_path: str
    message: str

class CaseListItemResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    documents_count: int = 0
    has_analysis: bool = False

    class Config:
        from_attributes = True

class CaseDetailResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    documents: List[CaseDocumentResponse] = []
    has_analysis: bool = False
    timeline_count: int = 0

    class Config:
        from_attributes = True

class QARequest(BaseModel):
    question: str = Field(..., example="What time did the incident happen according to the FIR?")

class QAResponse(BaseModel):
    answer: str
    citations: list[dict]


# ============================================================
# Routes
# ============================================================

@router.get(
    "",
    response_model=List[CaseListItemResponse],
    summary="List all legal cases"
)
def list_cases(
    db: Session = Depends(get_db)
) -> List[CaseListItemResponse]:
    """
    Fetch all legal cases ordered by creation date descending.
    """
    try:
        cases = db.execute(
            select(Case).order_by(Case.created_at.desc())
        ).scalars().all()
        
        response = []
        for c in cases:
            doc_count = len(c.documents) if c.documents else 0
            has_analysis = any(a.analysis_type == "full_case_analysis" for a in c.analyses) if c.analyses else False
            response.append(CaseListItemResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                status=c.status,
                created_at=c.created_at,
                documents_count=doc_count,
                has_analysis=has_analysis
            ))
        return response
    except Exception as e:
        logger.error(f"Failed to fetch cases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cases: {e}"
        )


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    summary="Get case details"
)
def get_case(
    case_id: str,
    db: Session = Depends(get_db)
) -> CaseDetailResponse:
    """
    Get detailed information for a single case including attached documents.
    """
    case = db.execute(
        select(Case).where(Case.id == case_id)
    ).scalar_one_or_none()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found"
        )
        
    has_analysis = any(a.analysis_type == "full_case_analysis" for a in case.analyses) if case.analyses else False
    timeline_count = len(case.timelines) if case.timelines else 0
    
    doc_responses = [
        CaseDocumentResponse(
            id=d.id,
            case_id=d.case_id,
            name=d.name,
            storage_link=d.storage_link,
            file_type=d.file_type,
            document_type=d.document_type,
            status=d.status,
            date_created=d.date_created
        )
        for d in (case.documents or [])
    ]
    
    return CaseDetailResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        documents=doc_responses,
        has_analysis=has_analysis,
        timeline_count=timeline_count
    )


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new legal case"
)
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db)
) -> CaseResponse:
    """
    Create a new Case record.
    """
    try:
        new_case = Case(
            id=str(uuid.uuid4()),
            title=request.title,
            description=request.description,
            status="created"
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)
        logger.info(f"Created case: {new_case.id}")
        return new_case
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create case: {e}"
        )


@router.post(
    "/{case_id}/upload",
    response_model=CaseUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a case document"
)
def upload_case_document(
    case_id: str,
    file: UploadFile = File(..., description="PDF or Image file to upload"),
    db: Session = Depends(get_db)
) -> CaseUploadResponse:
    """
    Upload a document (PDF or Image) under a specific Case ID and queue it for parsing and visual analysis.
    """
    # Verify case exists
    case = db.execute(
        select(Case).where(Case.id == case_id)
    ).scalar_one_or_none()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found"
        )
        
    filename = file.filename
    suffix = Path(filename).suffix.lower()
    
    # Supported files: PDF and Images
    supported_suffixes = [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".webp"]
    if suffix not in supported_suffixes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported files: {supported_suffixes}"
        )
        
    document_id = str(uuid.uuid4())
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file on disk
    storage_filename = f"{document_id}{suffix}"
    storage_path = upload_dir / storage_filename
    
    try:
        content = file.file.read()
        with storage_path.open("wb") as buffer:
            buffer.write(content)
        logger.info(f"Saved case document file to: {storage_path}")
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}"
        )
        
    # Store document record
    try:
        content_type = file.content_type or ("application/pdf" if suffix == ".pdf" else "image/jpeg")
        document = CaseDocument(
            id=document_id,
            case_id=case_id,
            name=filename,
            storage_link=str(storage_path),
            file_type=content_type,
            status="uploaded"
        )
        db.add(document)
        db.commit()
        logger.info(f"Created CaseDocument database record: {document_id}")
    except Exception as e:
        logger.error(f"Failed to create document record: {e}")
        if storage_path.exists():
            storage_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create database record: {e}"
        )
        
    # Trigger Celery parsing task asynchronously
    try:
        process_case_document_task.delay(document_id)
        logger.info(f"Queued process task for document: {document_id}")
    except Exception as e:
        logger.error(f"Failed to trigger Celery task: {e}")
        # Keep DB record but set status to error
        document.status = "error"
        db.commit()
        
    return CaseUploadResponse(
        status="success",
        document_id=document_id,
        document_name=filename,
        storage_path=str(storage_path),
        message="Document uploaded and queued for processing successfully"
    )


@router.post(
    "/{case_id}/analyze",
    summary="Trigger multi-agent case file analysis"
)
def analyze_case(
    case_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Queue background task to run CaseOrchestrator to perform complete multi-agent legal analysis.
    """
    case = db.execute(
        select(Case).where(Case.id == case_id)
    ).scalar_one_or_none()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found"
        )
        
    try:
        analyze_case_task.delay(case_id)
        logger.info(f"Queued analysis task for case: {case_id}")
        return {
            "status": "success",
            "message": "Case file analysis task triggered successfully"
        }
    except Exception as e:
        logger.error(f"Failed to trigger analysis task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue analysis: {e}"
        )


@router.get(
    "/{case_id}/analysis",
    summary="Retrieve structured case analysis results"
)
def get_case_analysis(
    case_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Fetch the completed multi-agent analysis report for a case.
    """
    analysis = db.execute(
        select(CaseAnalysis)
        .where(CaseAnalysis.case_id == case_id)
        .where(CaseAnalysis.analysis_type == "full_case_analysis")
    ).scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case analysis report not found or still processing"
        )
        
    return {
        "case_id": case_id,
        "analysis_type": "full_case_analysis",
        "created_at": analysis.created_at,
        "content": analysis.content
    }


@router.get(
    "/{case_id}/timeline",
    summary="Retrieve chronological timeline events"
)
def get_case_timeline(
    case_id: str,
    db: Session = Depends(get_db)
) -> list:
    """
    Get all chronological events saved for a legal case.
    """
    result = db.execute(
        select(CaseTimeline)
        .where(CaseTimeline.case_id == case_id)
        .order_by(CaseTimeline.event_date)
    )
    timelines = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "event_date": t.event_date.isoformat(),
            "event_description": t.event_description,
            "source_document_id": t.source_document_id,
            "source_page": t.source_page,
            "citation_quote": t.citation_quote
        }
        for t in timelines
    ]


@router.post(
    "/{case_id}/qa",
    response_model=QAResponse,
    summary="Submit query to the Case QA Agent"
)
def query_case_qa(
    case_id: str,
    request: QARequest,
    db: Session = Depends(get_db)
) -> QAResponse:
    """
    Query the Case QA Agent with hybrid search over document chunks.
    """
    # Verify case exists
    case = db.execute(
        select(Case).where(Case.id == case_id)
    ).scalar_one_or_none()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found"
        )
        
    try:
        from backend.agents.case_qa_agent import create_case_qa_agent
        from langchain_core.messages import HumanMessage
        
        qa_agent = create_case_qa_agent()
        
        # Inject case_id context to instruct QA agent where to query
        user_msg = f"In case_id: {case_id}, answer this question: {request.question}"
        
        # Invoke agent
        response = qa_agent.invoke({"messages": [HumanMessage(content=user_msg)]})
        
        # Parse output
        ans_data = None
        if hasattr(response, "model_dump"):
            ans_data = response.model_dump()
        elif isinstance(response, dict):
            ans_data = response
        else:
            ans_data = getattr(response, "content", str(response))
            
        if isinstance(ans_data, str):
            import json
            try:
                ans_data = json.loads(ans_data)
            except ValueError:
                ans_data = {"answer": ans_data, "citations": []}
                
        return QAResponse(
            answer=ans_data.get("answer", ""),
            citations=ans_data.get("citations", [])
        )
        
    except Exception as e:
        logger.error(f"Failed to query QA agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QA query processing failed: {e}"
        )


@router.get(
    "/{case_id}/logs",
    summary="Retrieve live agent activity logs"
)
def get_case_agent_logs(
    case_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Fetch all persistent agent thinking steps, tool calls, and subagent logs for a case.
    Reads directly from storage log file if available, with DB fallback.
    """
    log_file_path = Path("backend/storage/logs") / f"{case_id}_case_agent_execution.log"
    all_logs = []
    
    if log_file_path.exists():
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    line_str = line.strip()
                    if not line_str or line_str.startswith("="):
                        continue
                    
                    log_type = "info"
                    if "Tool Call:" in line_str or "Tool '" in line_str or "🛠️" in line_str:
                        log_type = "tool_call"
                    elif "THINKING:" in line_str or "Step:" in line_str or "🧠" in line_str:
                        log_type = "thinking"
                    elif "FINDING:" in line_str or "Response" in line_str:
                        log_type = "finding"

                    all_logs.append({
                        "agent_name": "CaseOrchestrator",
                        "timestamp": "",
                        "type": log_type,
                        "detail": line_str
                    })
        except Exception as e:
            logger.warning(f"Error reading log file: {e}")

    # Fallback to DB memories if log file is empty/missing
    if not all_logs:
        memories = db.execute(
            select(CaseAgentMemory)
            .where(CaseAgentMemory.case_id == case_id)
            .where(CaseAgentMemory.memory_key == "activity_log")
        ).scalars().all()
        
        for mem in memories:
            logs = mem.memory_value.get("logs", [])
            for log in logs:
                all_logs.append({
                    "agent_name": mem.agent_name,
                    "timestamp": log.get("timestamp"),
                    "type": log.get("type"),
                    "detail": log.get("detail")
                })
                
    return {
        "case_id": case_id,
        "total_logs": len(all_logs),
        "logs": all_logs
    }

