import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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
            select(Case)
            .options(
                selectinload(Case.documents),
                selectinload(Case.analyses),
            )
            .order_by(Case.created_at.desc())
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
        select(Case)
        .options(
            selectinload(Case.documents),
            selectinload(Case.analyses),
            selectinload(Case.timelines),
        )
        .where(Case.id == case_id)
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
        select(Case)
        .options(
            selectinload(Case.documents),
            selectinload(Case.analyses),
            selectinload(Case.timelines),
        )
        .where(Case.id == case_id)
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
        select(Case)
        .options(
            selectinload(Case.documents),
            selectinload(Case.analyses),
            selectinload(Case.timelines),
        )
        .where(Case.id == case_id)
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
        select(Case)
        .options(
            selectinload(Case.documents),
            selectinload(Case.analyses),
            selectinload(Case.timelines),
        )
        .where(Case.id == case_id)
    ).scalar_one_or_none()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found"
        )
        
    try:
        from backend.agents.case_qa_agent import create_case_qa_agent
        from langchain_core.messages import HumanMessage
        from backend.utils.llm_utils import execute_with_exponential_backoff
        
        qa_agent = create_case_qa_agent()
        
        # Inject case_id context to instruct QA agent where to query
        user_msg = f"In case_id: {case_id}, answer this question: {request.question}"
        
        # Invoke agent with resilient backoff for rate limits
        response = execute_with_exponential_backoff(
            qa_agent.invoke,
            {"messages": [HumanMessage(content=user_msg)]}
        )
        
        # Parse output
        ans_data = None
        if hasattr(response, "model_dump"):
            ans_data = response.model_dump()
        elif isinstance(response, dict):
            if "structured_response" in response and response["structured_response"]:
                sr = response["structured_response"]
                ans_data = sr.model_dump() if hasattr(sr, "model_dump") else sr
            elif "messages" in response and response["messages"]:
                last_msg = response["messages"][-1]
                content = getattr(last_msg, "content", "")
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        if isinstance(tc.get("args"), dict):
                            ans_data = tc["args"]
                            break
                if not ans_data:
                    ans_data = {"answer": content, "citations": []}
            else:
                ans_data = response
        else:
            ans_data = getattr(response, "content", str(response))

        if isinstance(ans_data, str):
            import json
            try:
                ans_data = json.loads(ans_data)
            except ValueError:
                ans_data = {"answer": ans_data, "citations": []}

        final_answer = ans_data.get("answer", "") if isinstance(ans_data, dict) else str(ans_data)
        final_citations = ans_data.get("citations", []) if isinstance(ans_data, dict) else []

        return QAResponse(
            answer=final_answer,
            citations=final_citations
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



# ============================================================
# Pre-Trial Adversarial Debate Endpoints
# ============================================================

from fastapi.responses import StreamingResponse
from backend.services.debate_stream_service import DebateStreamService
from backend.agents.trial_debate_langgraph import (
    build_trial_debate_graph,
    autonomous_kanoon_research,
    TrialDebateState,
    _call_resilient_llm_text,
)


class DebateStartRequest(BaseModel):
    mode: Optional[str] = "adversarial"
    represented_side: Optional[str] = "petitioner"


class DebateTurnRequest(BaseModel):
    custom_argument: str = Field(..., example="Plead lack of Section 65B certificate under Arjun Panditrao Khotkar.")
    represented_side: Optional[str] = "petitioner"


@router.post(
    "/{case_id}/debate/start",
    summary="Initialize or restart pre-trial adversarial debate simulation"
)
def start_case_debate(
    case_id: str,
    payload: Optional[DebateStartRequest] = None,
    db: Session = Depends(get_db)
) -> dict:
    """
    Kicks off the pre-trial moot simulation using LangGraph.
    Frames issues, runs opening round, and stores initial state.
    """
    case = db.execute(select(Case).where(Case.id == case_id)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    title = case.title or "Litigation Matter Dossier"
    mode = payload.mode if payload else "adversarial"
    side = payload.represented_side if payload else "petitioner"

    # Compile and execute initial graph stage
    graph = build_trial_debate_graph()
    initial_state: TrialDebateState = {
        "case_id": case_id,
        "matter_title": title,
        "case_facts": "",
        "framed_issues": [],
        "current_round": 1,
        "max_rounds": 3,
        "active_speaker": "petitioner",
        "debate_turns": [],
        "bench_queries": [],
        "all_citations": [],
        "momentum_petitioner": 55,
        "human_intervention_pending": False,
        "user_custom_argument": None,
        "user_represented_side": side,
        "is_completed": False,
        "final_combat_brief": {},
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        logger.error(f"Error executing debate graph for case {case_id}: {e}")
        final_state = initial_state

    # Save to CaseAgentMemory
    mem = db.execute(
        select(CaseAgentMemory)
        .where(CaseAgentMemory.case_id == case_id)
        .where(CaseAgentMemory.memory_key == "active_debate_state")
    ).scalar_one_or_none()

    save_payload = {
        "case_id": case_id,
        "matter_title": title,
        "current_round": final_state.get("current_round", 1),
        "framed_issues": final_state.get("framed_issues", []),
        "debate_turns": final_state.get("debate_turns", []),
        "bench_queries": final_state.get("bench_queries", []),
        "all_citations": final_state.get("all_citations", []),
        "momentum_petitioner": final_state.get("momentum_petitioner", 55),
        "is_completed": final_state.get("is_completed", False),
    }

    if mem:
        mem.memory_value = save_payload
        mem.updated_at = datetime.now()
    else:
        new_mem = CaseAgentMemory(
            case_id=case_id,
            agent_name="trial_debate_orchestrator",
            memory_key="active_debate_state",
            memory_value=save_payload,
        )
        db.add(new_mem)
    db.commit()

    return save_payload


@router.get(
    "/{case_id}/debate/status",
    summary="Retrieve current debate state and argumentation ledger"
)
def get_case_debate_status(
    case_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """Returns active debate state from DB or memory fallback."""
    mem = db.execute(
        select(CaseAgentMemory)
        .where(CaseAgentMemory.case_id == case_id)
        .where(CaseAgentMemory.memory_key == "active_debate_state")
    ).scalar_one_or_none()

    if mem:
        return mem.memory_value

    return {
        "case_id": case_id,
        "status": "not_started",
        "debate_turns": [],
        "bench_queries": [],
        "all_citations": [],
    }


@router.post(
    "/{case_id}/debate/turn",
    summary="Inject human lawyer argument and trigger dynamic opposing pivot"
)
def submit_case_debate_turn(
    case_id: str,
    payload: DebateTurnRequest,
    db: Session = Depends(get_db)
) -> dict:
    """
    Processes human lawyer intervention:
    1. Injects argument into debate state.
    2. Opposing agent queries Indian Kanoon to counter the specific argument.
    3. Emits stream events and updates DB.
    """
    case = db.execute(select(Case).where(Case.id == case_id)).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    mem = db.execute(
        select(CaseAgentMemory)
        .where(CaseAgentMemory.case_id == case_id)
        .where(CaseAgentMemory.memory_key == "active_debate_state")
    ).scalar_one_or_none()

    state = mem.memory_value if mem else {
        "case_id": case_id,
        "matter_title": case.title or "Litigation Matter",
        "current_round": 2,
        "debate_turns": [],
        "bench_queries": [],
        "all_citations": [],
        "momentum_petitioner": 55,
    }

    side = payload.represented_side or "petitioner"
    opposing_side = "respondent" if side == "petitioner" else "petitioner"
    custom_arg = payload.custom_argument.strip()

    # Determine dynamic round number based on existing exchanges
    existing_turns = state.get("debate_turns", [])
    current_round_num = (len(existing_turns) // 2) + 1

    # User submission turn
    user_turn = {
        "id": f"turn_user_{int(datetime.now().timestamp())}",
        "turn_number": len(existing_turns) + 1,
        "round_number": current_round_num,
        "speaker": "user",
        "speaker_side": side,
        "title": f"Lead Counsel Intervention ({side.capitalize()})",
        "argument_text": custom_arg,
        "citations": [],
        "doctrine_tags": ["Human Steer", "Custom Doctrine"],
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }

    # Autonomous Opponent Kanoon Research
    citations = autonomous_kanoon_research(custom_arg[:50], opposing_side, max_results=1)

    # Dynamic Opponent LLM Counter-Pivot
    matter_title = state.get("matter_title", "Litigation Matter")
    cit_meta = citations[0] if citations else {}
    pivot_prompt = (
        f"You are the Senior Advocate representing the {opposing_side.capitalize()} before the High Court of Delhi in '{matter_title}'.\n"
        f"Human Lead Counsel representing the {side.capitalize()} has just made the following submission:\n"
        f"\"{custom_arg}\"\n\n"
        f"Your retrieved legal authority from Indian Kanoon:\n"
        f"Title: {cit_meta.get('title', 'Supreme Court Precedent')}\n"
        f"Ratio Decidendi: {cit_meta.get('ratio_decidendi', 'Preliminary inquiries are strictly governed by statutory thresholds.')}\n"
        f"Statutory Sections: {cit_meta.get('statutory_sections', ['Section 482 CrPC', 'Section 65B Evidence Act'])}\n\n"
        f"Deliver a direct, highly intelligent, aggressive oral counter-rebuttal (100-150 words). "
        f"Directly dismantle lead counsel's specific proposition, expose its procedural or factual flaw under Indian law, "
        f"anchor in {cit_meta.get('title', 'settled Supreme Court precedent')}, and demand that the court rule in your favor."
    )
    fallback_counter = (
        f"Responding directly to lead counsel's submission: The proposition cannot stand. "
        f"Under {cit_meta.get('title', 'settled Supreme Court authority')}, "
        "the judicial inquiry at this preliminary threshold is strictly bounded by the four corners of the record. "
        "Counsel's argument introduces factual disputes that can only be resolved through cross-examination."
    )
    counter_arg_text = _call_resilient_llm_text(pivot_prompt, fallback=fallback_counter)

    counter_turn = {
        "id": f"turn_pivot_{int(datetime.now().timestamp())}",
        "turn_number": len(existing_turns) + 2,
        "round_number": current_round_num,
        "speaker": opposing_side,
        "speaker_side": opposing_side,
        "title": f"Autonomous Counter-Rebuttal ({opposing_side.capitalize()})",
        "argument_text": counter_arg_text,
        "citations": citations,
        "doctrine_tags": ["Autonomous Counter-Pivot", "Indian Kanoon Real-Time Grounding"],
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }

    turns = list(existing_turns)
    turns.extend([user_turn, counter_turn])
    state["debate_turns"] = turns
    state["current_round"] = current_round_num

    existing_cits = state.get("all_citations", [])
    for c in citations:
        if not any(ec.get("doc_id") == c.get("doc_id") for ec in existing_cits):
            existing_cits.append(c)
    state["all_citations"] = existing_cits

    state["momentum_petitioner"] = max(30, min(85, state.get("momentum_petitioner", 55) + (4 if side == "petitioner" else -4)))

    # Save to DB
    if mem:
        mem.memory_value = state
        mem.updated_at = datetime.now()
    else:
        new_mem = CaseAgentMemory(
            case_id=case_id,
            agent_name="trial_debate_orchestrator",
            memory_key="active_debate_state",
            memory_value=state,
        )
        db.add(new_mem)
    db.commit()

    # Publish stream event
    DebateStreamService.publish_event(
        case_id=case_id,
        event_type="HUMAN_INTERVENTION_REBUTTAL",
        speaker=opposing_side,
        message=f"{opposing_side.capitalize()} counsel delivered immediate counter-rebuttal to human lead counsel.",
        round_number=current_round_num,
        details={"user_turn": user_turn, "counter_turn": counter_turn, "round_number": current_round_num},
    )

    return state


@router.get(
    "/{case_id}/debate/brief",
    summary="Download or inspect compiled Pre-Trial Combat Pack"
)
def get_case_debate_brief(
    case_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """Returns compiled pre-trial brief from DB."""
    mem = db.execute(
        select(CaseAgentMemory)
        .where(CaseAgentMemory.case_id == case_id)
        .where(CaseAgentMemory.memory_key == "trial_debate_brief")
    ).scalar_one_or_none()

    if mem:
        return mem.memory_value

    return {
        "case_id": case_id,
        "executive_summary": "Simulation in progress. Complete all 3 rounds to generate final brief.",
        "adversary_playbook": [],
        "citations_ledger": [],
    }


@router.get(
    "/{case_id}/debate/stream",
    summary="Real-time Server-Sent Events stream for courtroom debate"
)
async def stream_case_debate_events(case_id: str):
    """Streams live courtroom speech events, Kanoon search calls, and bench queries."""
    async def event_generator():
        async for event in DebateStreamService.subscribe_events(case_id, timeout=180):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
