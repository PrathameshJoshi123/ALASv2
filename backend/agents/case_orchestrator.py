from __future__ import annotations

import os
import logging
from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

from backend.database import SessionLocal
from backend.models.cases import CaseDocument, CaseDocumentChunk, EvidenceDetail, CaseTimeline, CaseAnalysis, CaseAgentMemory
from backend.config import settings

# Import specialist agent configs
from backend.agents.case_document_classifier import CLASSIFIER_AGENT
from backend.agents.case_evidence_agent import EVIDENCE_AGENT
from backend.agents.case_timeline_agent import TIMELINE_AGENT
from backend.agents.case_missing_evidence_agent import MISSING_EVIDENCE_AGENT
from backend.agents.case_issue_charge_agent import ISSUE_CHARGE_AGENT
from backend.agents.case_witness_contradiction_agent import WITNESS_CONTRADICTION_AGENT
from backend.agents.case_procedural_compliance_agent import PROCEDURAL_COMPLIANCE_AGENT
from backend.agents.case_kanoon_research_agent import KANOON_RESEARCH_AGENT

logger = logging.getLogger(__name__)

# ============================================================
# Structured result returned by the orchestrator
# ============================================================

class CaseAnalysisResult(BaseModel):
    """
    Final structured response of the Case Analysis Orchestrator.
    """
    case_id: str
    document_classifications: list[dict] = Field(
        default_factory=list, 
        description="Predefined document classification types for all case files"
    )
    timeline: list[dict] = Field(
        default_factory=list, 
        description="Chronological event timeline with exact citations and document paths"
    )
    missing_evidence: list[dict] = Field(
        default_factory=list, 
        description="Missing filings, reports, or evidentiary components with legal rationale"
    )
    charges_analysis: list[dict] = Field(
        default_factory=list, 
        description="Analysis of IPC/BNS sections and evidentiary support per ingredient"
    )
    witness_contradictions: list[dict] = Field(
        default_factory=list, 
        description="Cross-witness contradictions, omissions, or improvements with citations"
    )
    procedural_compliance: list[dict] = Field(
        default_factory=list, 
        description="Upcoming deadlines and compliance checklists under BNSS/CrPC/CPC"
    )
    kanoon_precedents: list[dict] = Field(
        default_factory=list, 
        description="Landmark precedence cases fetched from Indian Kanoon"
    )
    summary_report: str = Field(
        "", 
        description="A cohesive, written legal brief summarizing the entire case analysis and findings"
    )
    analysis_completed: bool = Field(
        False, 
        description="Indicates whether the orchestrator has decided the analysis is complete"
    )


# ============================================================
# Database Tools for Case Agents with Detailed Logging
# ============================================================

def log_agent_activity(case_id: str, agent_name: str, activity_type: str, detail: str) -> str:
    """
    Log an agent's reasoning, tool call, subagent invocation, or analysis finding into the database and console.
    
    Args:
        case_id: Case UUID.
        agent_name: Name of the active agent or specialist.
        activity_type: Type of action ('thinking', 'tool_call', 'subagent_delegation', 'finding').
        detail: Human-readable description of what the agent is doing or thinking.
    """
    log_msg = f"🧠 [{agent_name}] {activity_type.upper()}: {detail}"
    logger.info(log_msg)
    print(log_msg, flush=True)

    try:
        with SessionLocal() as db:
            existing = db.execute(
                select(CaseAgentMemory)
                .where(CaseAgentMemory.case_id == case_id)
                .where(CaseAgentMemory.agent_name == agent_name)
                .where(CaseAgentMemory.memory_key == "activity_log")
            ).scalar_one_or_none()

            timestamp = datetime.now().isoformat()
            log_item = {"timestamp": timestamp, "type": activity_type, "detail": detail}

            if existing:
                current_logs = list(existing.memory_value.get("logs", []))
                current_logs.append(log_item)
                existing.memory_value = {"logs": current_logs}
            else:
                new_mem = CaseAgentMemory(
                    case_id=case_id,
                    agent_name=agent_name,
                    memory_key="activity_log",
                    memory_value={"logs": [log_item]}
                )
                db.add(new_mem)
            db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist activity log to DB: {e}")

    return f"Logged {activity_type}: {detail[:60]}..."


def count_words(text: str) -> int:
    """Count the number of words in a text string."""
    if not text:
        return 0
    return len(text.split())


def get_case_documents_list(case_id: str) -> list[dict[str, Any]]:
    """
    Retrieve all document metadata uploaded under a case ID or document ID.
    Always call this tool first to understand what files are available.
    """
    logger.info(f"🛠️ [Tool: get_case_documents_list] Querying case documents for query_id={case_id}")
    with SessionLocal() as db:
        # Try direct lookup by case_id
        documents = db.execute(
            select(CaseDocument)
            .where(CaseDocument.case_id == case_id)
        ).scalars().all()

        # Smart fallback: If 0 results, check if query_id was actually a document_id
        if not documents:
            target_doc = db.execute(
                select(CaseDocument).where(CaseDocument.id == case_id)
            ).scalar_one_or_none()
            if target_doc:
                documents = db.execute(
                    select(CaseDocument).where(CaseDocument.case_id == target_doc.case_id)
                ).scalars().all()

        doc_list = [
            {
                "id": doc.id,
                "name": doc.name,
                "storage_link": doc.storage_link,
                "file_type": doc.file_type,
                "document_type": doc.document_type,
                "status": doc.status
            }
            for doc in documents
        ]
        logger.info(f"🛠️ [Tool: get_case_documents_list] Found {len(doc_list)} document(s) for query {case_id}")
        return doc_list


def get_case_total_chunks_count(document_id: str) -> int:
    """
    Retrieve the total number of chunks available in the database for a case document.
    """
    logger.info(f"🛠️ [Tool: get_case_total_chunks_count] Counting chunks for document_id={document_id}")
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(CaseDocumentChunk.id))
            .where(CaseDocumentChunk.document_id == document_id)
        )
        count = result.scalar() or 0
        if count == 0:
            # Fallback: check if document_id was passed as case_id
            count = db.execute(
                select(func.count(CaseDocumentChunk.id))
                .join(CaseDocumentChunk.document)
                .where(CaseDocument.case_id == document_id)
            ).scalar() or 0
        logger.info(f"🛠️ [Tool: get_case_total_chunks_count] Total chunks for {document_id}: {count}")
        return count


def get_case_chunks_from_db(
    document_id: str,
    start_sequence: int = 1,
    limit: int = 10
) -> list[dict[str, Any]]:
    """
    Fetch chunks for a case document sequentially starting from a sequence_number up to a limit,
    optimizing/merging small sequential chunks (< 200 words) to create proper context blocks.
    """
    logger.info(f"🛠️ [Tool: get_case_chunks_from_db] Fetching chunks seq {start_sequence}..{start_sequence+limit-1} for target={document_id}")
    with SessionLocal() as db:
        result = db.execute(
            select(CaseDocumentChunk)
            .where(CaseDocumentChunk.document_id == document_id)
            .where(CaseDocumentChunk.sequence_number >= start_sequence)
            .order_by(CaseDocumentChunk.sequence_number)
            .limit(limit)
        )
        chunks = result.scalars().all()

        # Fallback: If 0 results, check if target was actually a case_id
        if not chunks:
            result = db.execute(
                select(CaseDocumentChunk)
                .join(CaseDocumentChunk.document)
                .where(CaseDocument.case_id == document_id)
                .where(CaseDocumentChunk.sequence_number >= start_sequence)
                .order_by(CaseDocumentChunk.sequence_number)
                .limit(limit)
            )
            chunks = result.scalars().all()

        if not chunks:
            logger.info(f"🛠️ [Tool: get_case_chunks_from_db] Retrieved 0 chunk(s) - END OF DOCUMENT")
            return []

        MIN_CHUNK_WORDS = 200
        MAX_MERGED_WORDS = 400

        merged_groups = []
        current_group_ids = []
        current_group_text = ""
        current_group_page_start = None
        current_group_page_end = None

        for chunk in chunks:
            chunk_word_count = count_words(chunk.content)

            if not current_group_ids:
                current_group_ids = [chunk.id]
                current_group_text = chunk.content
                current_group_page_start = chunk.page_start
                current_group_page_end = chunk.page_end
            else:
                current_group_word_count = count_words(current_group_text)
                combined_word_count = current_group_word_count + chunk_word_count

                if chunk_word_count < MIN_CHUNK_WORDS and combined_word_count <= MAX_MERGED_WORDS:
                    current_group_ids.append(chunk.id)
                    current_group_text += "\n\n" + chunk.content
                    if chunk.page_end:
                        current_group_page_end = chunk.page_end
                else:
                    merged_groups.append({
                        "chunk_ids": current_group_ids,
                        "document_id": chunk.document_id,
                        "content": current_group_text,
                        "page_start": current_group_page_start,
                        "page_end": current_group_page_end,
                        "sequence_number": chunk.sequence_number
                    })
                    current_group_ids = [chunk.id]
                    current_group_text = chunk.content
                    current_group_page_start = chunk.page_start
                    current_group_page_end = chunk.page_end

        if current_group_ids:
            merged_groups.append({
                "chunk_ids": current_group_ids,
                "document_id": chunks[0].document_id,
                "content": current_group_text,
                "page_start": current_group_page_start,
                "page_end": current_group_page_end,
                "sequence_number": chunks[-1].sequence_number
            })

        logger.info(f"🛠️ [Tool: get_case_chunks_from_db] Retrieved {len(merged_groups)} merged chunk group(s)")
        return merged_groups


def get_case_evidence_details(case_id: str) -> list[dict[str, Any]]:
    """
    Retrieve all processed image and visual evidence descriptions cached for a case or document.
    """
    logger.info(f"🛠️ [Tool: get_case_evidence_details] Retrieving evidence OCR & vision cache for query_id={case_id}")
    with SessionLocal() as db:
        # Search by case_id OR document_id
        result = db.execute(
            select(EvidenceDetail)
            .join(EvidenceDetail.document)
            .where(
                (CaseDocument.case_id == case_id) | (EvidenceDetail.case_document_id == case_id)
            )
        )
        evidences = result.scalars().all()
        ev_list = [
            {
                "id": ev.id,
                "document_id": ev.case_document_id,
                "document_name": ev.document.name,
                "page_number": ev.page_number,
                "image_path": ev.image_path,
                "extracted_text": ev.extracted_text,
                "visual_description": ev.visual_description,
                "key_objects": ev.key_objects,
                "timeline_timestamp": ev.timeline_timestamp.isoformat() if ev.timeline_timestamp else None,
                "detected_timeline_event": ev.detected_timeline_event
            }
            for ev in evidences
        ]
        if not ev_list:
            logger.info(f"🛠️ [Tool: get_case_evidence_details] No visual evidence/OCR entries found for query '{case_id}'. Case contains standard PDF text documents.")
        else:
            logger.info(f"🛠️ [Tool: get_case_evidence_details] Found {len(ev_list)} visual evidence entry/entries")
        return ev_list


def save_case_timeline_entry(
    case_id: str,
    event_date: str,
    event_description: str,
    source_document_id: Optional[str] = None,
    source_page: Optional[int] = None,
    citation_quote: Optional[str] = None
) -> str:
    """
    Save an extracted event timeline entry into the database.
    """
    logger.info(f"🛠️ [Tool: save_case_timeline_entry] Date={event_date} | Desc={event_description[:50]}...")
    print(f"🛠️ [Tool: save_case_timeline_entry] Date={event_date} | Desc={event_description[:50]}...", flush=True)
    try:
        dt = datetime.fromisoformat(event_date)
    except ValueError:
        try:
            dt = datetime.strptime(event_date, "%Y-%m-%d")
        except ValueError:
            return f"Error: Invalid date format '{event_date}'. Use ISO YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            
    with SessionLocal() as db:
        entry = CaseTimeline(
            case_id=case_id,
            event_date=dt,
            event_description=event_description,
            source_document_id=source_document_id,
            source_page=source_page,
            citation_quote=citation_quote
        )
        db.add(entry)
        db.commit()
        return f"Success: Saved timeline event for {dt.date()}"


def save_case_analysis_report(
    case_id: str,
    analysis_type: str,
    content: dict
) -> str:
    """
    Save or update a structured legal findings report in the database.
    """
    logger.info(f"🛠️ [Tool: save_case_analysis_report] Saving report type '{analysis_type}' for case_id={case_id}")
    print(f"🛠️ [Tool: save_case_analysis_report] Saving report type '{analysis_type}' for case_id={case_id}", flush=True)
    with SessionLocal() as db:
        existing = db.execute(
            select(CaseAnalysis)
            .where(CaseAnalysis.case_id == case_id)
            .where(CaseAnalysis.analysis_type == analysis_type)
        ).scalar_one_or_none()
        
        if existing:
            existing.content = content
        else:
            new_report = CaseAnalysis(
                case_id=case_id,
                analysis_type=analysis_type,
                content=content
            )
            db.add(new_report)
            
        db.commit()
        return f"Success: Saved analysis report for '{analysis_type}'"


# ============================================================
# Model Initializers
# ============================================================

def get_orchestrator_model() -> Any:
    """Orchestrator main agent model: ministral-14b-2512 with exponential backoff retries."""
    from backend.utils.llm_utils import get_resilient_llm, ORCHESTRATOR_MODEL_NAME
    return get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)


def get_specialist_model() -> Any:
    """Specialist subagent model: ministral-3b-2512 with exponential backoff retries."""
    from backend.utils.llm_utils import get_resilient_llm, SPECIALIST_MODEL_NAME
    return get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)


# ============================================================
# Create Case Orchestrator Agent
# ============================================================

ORCHESTRATOR_PROMPT = """
You are the Case Analysis Orchestrator.

Your goal is to coordinate a team of specialized legal subagents to analyze case files, classify documents under strict predefined schemas, identify timeline events and cross-examine them for inconsistencies, inspect witness statement contradictions, trace charges/sections to statutory elements, evaluate procedural compliance stages, and run precedent searches on Indian Kanoon.

STRICT ID & CHUNK RETRIEVAL DIRECTIVE:
1. ALWAYS start by calling `get_case_documents_list(case_id)` ONCE using the exact case_id provided in the user prompt.
2. From the returned document list, note down the exact 36-character `id` (document_id) and `name` for each file.
3. When querying text chunks using `get_case_chunks_from_db` or `get_case_total_chunks_count`, ALWAYS pass the specific target `document_id`.
4. When delegating tasks to subagents or passing instructions between agents, ALWAYS pass the exact `case_id` AND the explicit 36-character `document_id`s for each file. NEVER use placeholder strings like "default_case_id", "placeholder", or "your_case_id_here".
5. DO NOT call `read_file`, `write_file`, or local filesystem file tools. Document content is stored ONLY in database chunks via `get_case_chunks_from_db`.

MANDATORY TERMINATION WORKFLOW:
- Step 1: Call `get_case_documents_list(case_id)` ONCE to get the file list.
- Step 2: For each file, call `get_case_total_chunks_count(document_id)` ONCE.
- Step 3: Call `get_case_chunks_from_db(document_id, start_sequence=1)` to read the chunks.
- Step 4: Once `get_case_chunks_from_db` returns chunk content or an empty list `[]`, STOP calling all retrieval tools immediately. Do NOT repeat queries for documents you have already fetched.
- Step 5: Construct and output your final structured JSON response matching `CaseAnalysisResult`.

STRICT CITATION DIRECTIVE:
You and all specialists MUST include exact citations for every single point, timeline event, compliance tracker, or contradiction report. Citations must point to the specific document_id, document name, page, and exact quotes.

AVAILABLE LEGAL SPECIALISTS:
1. case-document-classifier
2. case-evidence-agent
3. case-timeline-agent
4. case-missing-evidence-agent
5. case-issue-charge-agent
6. case-witness-contradiction-agent
7. case-procedural-compliance-agent
8. case-kanoon-research-agent
"""

def create_case_orchestrator() -> Any:
    """
    Create the top-level case orchestrator agent.
    """
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    from langgraph.store.memory import InMemoryStore
    
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: (
                    "case-analysis",
                    "v1",
                ),
            ),
            "/skills/": StoreBackend(
                namespace=lambda rt: (
                    "case-analysis",
                    "v1",
                ),
            ),
        },
    )

    DB_GUIDELINES = """

STRICT CHUNK RETRIEVAL & MANDATORY STOPPING DIRECTIVE:
1. DO NOT call `read_file`, `write_file`, or local filesystem file tools. Files do NOT exist on local disk paths.
2. All document content MUST be retrieved ONLY from database chunks using `get_case_chunks_from_db(document_id, start_sequence, limit)`.
3. First, call `get_case_documents_list(case_id)` to list all uploaded files and read their exact 36-character `id` (document_id).
4. Next, call `get_case_total_chunks_count(document_id)` to check the total count of chunks.
5. Call `get_case_chunks_from_db(document_id, start_sequence=1, limit=10)` to read the chunks for the document.
6. MANDATORY STOPPING CONDITION: Once you have called `get_case_chunks_from_db` for a document and received its chunks (or an empty list `[]`), you have 100% of the information. STOP calling retrieval tools for that document immediately. Do NOT loop or re-query chunk counts or document lists!
"""

    specialist_agents = [
        {**CLASSIFIER_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": CLASSIFIER_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**EVIDENCE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": EVIDENCE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**TIMELINE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": TIMELINE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**MISSING_EVIDENCE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": MISSING_EVIDENCE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**ISSUE_CHARGE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": ISSUE_CHARGE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**WITNESS_CONTRADICTION_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": WITNESS_CONTRADICTION_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**PROCEDURAL_COMPLIANCE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": PROCEDURAL_COMPLIANCE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**KANOON_RESEARCH_AGENT, "model": get_orchestrator_model(), "inherit_tools": True, "system_prompt": KANOON_RESEARCH_AGENT.get("system_prompt", "") + DB_GUIDELINES},
    ]

    store = InMemoryStore()

    return create_deep_agent(
        model=get_orchestrator_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=specialist_agents,
        backend=backend,
        store=store,
        skills=[
            "backend/skills/case-orchestration",
            "backend/skills/case-document-classification",
            "backend/skills/case-evidence-analysis",
            "backend/skills/case-timeline-analysis",
            "backend/skills/case-missing-evidence",
            "backend/skills/case-kanoon-research"
        ],
        tools=[
            get_case_documents_list,
            get_case_total_chunks_count,
            get_case_chunks_from_db,
            get_case_evidence_details
        ],
        middleware=[
            CodeInterpreterMiddleware()
        ],
        response_format=CaseAnalysisResult,
    )
