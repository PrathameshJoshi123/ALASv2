"""
Case Analysis LangGraph Orchestrator.

A deterministic, milestone-driven legal intelligence engine built on LangGraph.
Autonomously coordinates multi-document case classification, chronological event mapping,
witness testimony cross-examination, penal charge ingredient auditing, procedural compliance,
and real-time precedent research on indiankanoon.org.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.database import SessionLocal
from backend.models.cases import (
    Case,
    CaseDocument,
    CaseDocumentChunk,
    EvidenceDetail,
    CaseTimeline,
    CaseAnalysis,
    CaseAgentMemory,
)
from backend.config import settings
from backend.utils.llm_utils import (
    get_resilient_llm,
    ORCHESTRATOR_MODEL_NAME,
    SPECIALIST_MODEL_NAME,
)
from backend.tools.indian_kanoon_tools import (
    search_indian_kanoon_raw,
    fetch_kanoon_document_raw,
    extract_doc_id,
    get_cached_doc_meta,
)

logger = logging.getLogger(__name__)


# ============================================================
# Structured Output Schema (Frontend & DB Contract)
# ============================================================

class CaseAnalysisResult(BaseModel):
    """
    Final structured response of the Case Analysis Orchestrator.
    """
    case_id: str
    matter_title: str = Field(default="", description="Case or matter caption")
    executive_summary: str = Field(
        default="", 
        description="Cohesive executive legal brief summarizing the entire matter"
    )
    key_findings: list[Any] = Field(
        default_factory=list,
        description="Core evidentiary, factual, and legal findings"
    )
    recommended_actions: list[Any] = Field(
        default_factory=list,
        description="Actionable litigation steps and strategic counsel recommendations"
    )
    document_classifications: list[dict] = Field(
        default_factory=list, 
        description="Classifications for all uploaded case files"
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
        description="Precedent authorities fetched from Indian Kanoon"
    )
    summary_report: str = Field(
        default="", 
        description="Written legal brief summarizing the entire case analysis and findings"
    )
    analysis_completed: bool = Field(
        default=True, 
        description="Indicates whether the orchestrator has decided the analysis is complete"
    )


# ============================================================
# Database Tools & Helpers (Preserved for QA agent & external callers)
# ============================================================

def safe_print(msg: str) -> None:
    """Print to console safely handling Windows cp1252/terminal encoding limits."""
    try:
        print(msg, flush=True)
    except (UnicodeEncodeError, Exception):
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass

def log_agent_activity(case_id: str, agent_name: str, activity_type: str, detail: str) -> str:
    """
    Log an agent's reasoning, tool call, subagent invocation, or analysis finding into the database and console.
    """
    log_msg = f"🧠 [{agent_name}] {activity_type.upper()}: {detail}"
    logger.info(log_msg)
    safe_print(log_msg)

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


def clean_json_response(content: str) -> str:
    """Strip markdown json code fences from LLM responses."""
    cleaned = content.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    return cleaned


def safe_parse_json(content: str) -> Any:
    """
    Robustly parse JSON responses from LLMs.
    Handles unescaped inner quotes, trailing commas, unescaped control characters (raw newlines/tabs),
    unclosed brackets, and strips Markdown fences with multi-pass fallback.
    """
    cleaned = clean_json_response(content)

    def _strip_controls(s: str) -> str:
        chars = []
        for ch in s:
            code = ord(ch)
            if code < 32:
                if ch in '\n\r\t':
                    chars.append(' ')
            elif 127 <= code <= 159:
                pass
            else:
                chars.append(ch)
        return "".join(chars)

    def _clean_trailing_commas(s: str) -> str:
        return re.sub(r',\s*([\]\}])', r'\1', s)

    def _fix_inner_quotes(s: str) -> str:
        lines = s.splitlines()
        repaired = []
        for line in lines:
            m = re.match(r'^(\s*"[a-zA-Z0-9_]+"\s*:\s*")(.*)(",?\s*)$', line)
            if m:
                prefix, inner, suffix = m.group(1), m.group(2), m.group(3)
                escaped_inner = re.sub(r'(?<!\\)"', r'\"', inner)
                repaired.append(prefix + escaped_inner + suffix)
            else:
                repaired.append(line)
        return "\n".join(repaired)

    # Attempt 1: Standard load with strict=False
    try:
        return json.loads(cleaned, strict=False)
    except Exception:
        pass

    # Attempt 2: Strip trailing commas + control chars
    try:
        sanitized = _clean_trailing_commas(_strip_controls(cleaned))
        return json.loads(sanitized, strict=False)
    except Exception:
        pass

    # Attempt 3: Fix inner quotes + trailing commas + control chars
    try:
        sanitized = _fix_inner_quotes(_clean_trailing_commas(_strip_controls(cleaned)))
        return json.loads(sanitized, strict=False)
    except Exception:
        pass

    # Attempt 4: Outermost JSON object / array with trailing comma removal and inner quote fix
    try:
        m = re.search(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL)
        if m:
            sanitized = _fix_inner_quotes(_clean_trailing_commas(_strip_controls(m.group(0))))
            return json.loads(sanitized, strict=False)
    except Exception:
        pass

    # Attempt 5: If JSON was truncated at the end, attempt to close open brackets/braces
    try:
        sanitized = _fix_inner_quotes(_clean_trailing_commas(_strip_controls(cleaned)))
        open_braces = sanitized.count('{') - sanitized.count('}')
        open_brackets = sanitized.count('[') - sanitized.count(']')
        repaired = sanitized.rstrip()
        if repaired.endswith(','):
            repaired = repaired[:-1]
        repaired += (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
        return json.loads(repaired, strict=False)
    except Exception:
        pass

    return json.loads(cleaned, strict=False)


def get_case_documents_list(case_id: str) -> list[dict[str, Any]]:
    """
    Retrieve all document metadata uploaded under a case ID or document ID.
    """
    with SessionLocal() as db:
        documents = db.execute(
            select(CaseDocument)
            .where(CaseDocument.case_id == case_id)
        ).scalars().all()

        if not documents:
            target_doc = db.execute(
                select(CaseDocument).where(CaseDocument.id == case_id)
            ).scalar_one_or_none()
            if target_doc:
                documents = db.execute(
                    select(CaseDocument).where(CaseDocument.case_id == target_doc.case_id)
                ).scalars().all()

        return [
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


def get_case_total_chunks_count(document_id: str) -> int:
    """
    Retrieve the total number of chunks available in the database for a case document.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(CaseDocumentChunk.id))
            .where(CaseDocumentChunk.document_id == document_id)
        )
        count = result.scalar() or 0
        if count == 0:
            count = db.execute(
                select(func.count(CaseDocumentChunk.id))
                .join(CaseDocumentChunk.document)
                .where(CaseDocument.case_id == document_id)
            ).scalar() or 0
        return count


def get_case_chunks_from_db(
    document_id: str,
    start_sequence: int = 1,
    limit: int = 20
) -> list[dict[str, Any]]:
    """
    Fetch chunks for a case document sequentially starting from a sequence_number up to a limit.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(CaseDocumentChunk)
            .where(CaseDocumentChunk.document_id == document_id)
            .where(CaseDocumentChunk.sequence_number >= start_sequence)
            .order_by(CaseDocumentChunk.sequence_number)
            .limit(limit)
        )
        chunks = result.scalars().all()

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

        return [chunk.to_dict() for chunk in chunks]


def get_case_evidence_details(case_id: str) -> list[dict[str, Any]]:
    """
    Retrieve all processed visual evidence descriptions cached for a case or document.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(EvidenceDetail)
            .join(EvidenceDetail.document)
            .where(
                (CaseDocument.case_id == case_id) | (EvidenceDetail.case_document_id == case_id)
            )
        )
        evidences = result.scalars().all()
        return [
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


def save_case_timeline_entry(
    case_id: str,
    event_date: str,
    event_description: str,
    source_document_id: Optional[str] = None,
    source_page: Optional[int] = None,
    citation_quote: Optional[str] = None
) -> str:
    """
    Save an extracted event timeline entry into the database with foreign key validation.
    """
    try:
        dt = datetime.fromisoformat(event_date)
    except ValueError:
        try:
            dt = datetime.strptime(event_date, "%Y-%m-%d")
        except ValueError:
            dt = datetime.now()

    with SessionLocal() as db:
        safe_doc_id = None
        if source_document_id:
            val_str = str(source_document_id).strip()
            doc = db.execute(
                select(CaseDocument.id)
                .where(CaseDocument.case_id == case_id)
                .where(CaseDocument.id == val_str)
            ).scalar_one_or_none()
            if doc:
                safe_doc_id = doc
            else:
                named_doc = db.execute(
                    select(CaseDocument.id)
                    .where(CaseDocument.case_id == case_id)
                    .where(CaseDocument.name.ilike(f"%{val_str}%"))
                ).scalars().first()
                if named_doc:
                    safe_doc_id = named_doc

        try:
            entry = CaseTimeline(
                case_id=case_id,
                event_date=dt,
                event_description=event_description,
                source_document_id=safe_doc_id,
                source_page=source_page,
                citation_quote=citation_quote
            )
            db.add(entry)
            db.commit()
            return f"Success: Saved timeline event for {dt.date()}"
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to persist timeline entry: {e}")
            return f"Warning: could not persist timeline event: {e}"


def save_case_analysis_report(
    case_id: str,
    analysis_type: str,
    content: dict
) -> str:
    """
    Save or update a structured legal findings report in the database.
    """
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


def get_orchestrator_model() -> Any:
    """Orchestrator model: ministral-14b-2512 with exponential backoff retries."""
    return get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)


def get_specialist_model() -> Any:
    """Specialist subagent model: ministral-3b-2512 with exponential backoff retries."""
    return get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)


# ============================================================
# LangGraph TypedDict State Definition
# ============================================================

class CaseAnalysisGraphState(TypedDict):
    """
    State dictionary passed sequentially between LangGraph analysis nodes.
    """
    case_id: str
    case_title: str
    case_description: str
    documents_metadata: List[Dict[str, Any]]
    document_texts: Dict[str, str]
    evidence_items: List[Dict[str, Any]]

    # Extractions from specialist milestone nodes
    document_classifications: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    witness_contradictions: List[Dict[str, Any]]
    charges_analysis: List[Dict[str, Any]]
    missing_evidence: List[Dict[str, Any]]
    procedural_compliance: List[Dict[str, Any]]
    kanoon_queries: List[str]
    kanoon_precedents: List[Dict[str, Any]]

    # Final Dossier Synthesis
    executive_summary: str
    key_findings: List[str]
    recommended_actions: List[str]
    summary_report: str
    analysis_completed: bool

    # Running execution logs for streaming / persistence
    log_messages: List[str]
    structured_response: Optional[Dict[str, Any]]


# ============================================================
# Node 1: Case Intake & Autonomous Multi-Doc Classification
# ============================================================

def node_intake_and_classification(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Intake all uploaded exhibits for the case, verify document text existence,
    and autonomously classify each exhibit into standard legal categories.
    """
    case_id = state["case_id"]
    logger.info(f"🏛️ [LangGraph: node_intake_and_classification] Initializing case {case_id}")

    with SessionLocal() as db:
        case = db.execute(
            select(Case).where(Case.id == case_id)
        ).scalar_one_or_none()

        if not case:
            raise ValueError(f"Case with ID '{case_id}' was not found in the database.")

        case_title = case.title or "Untitled Legal Matter"
        case_description = case.description or "Litigation matter records under examination."

        docs = db.execute(
            select(CaseDocument).where(CaseDocument.case_id == case_id)
        ).scalars().all()

        if not docs:
            raise ValueError(f"Case '{case_id}' has no uploaded exhibit documents. Please upload at least one document.")

        docs_meta = []
        doc_texts = {}

        for doc in docs:
            chunks = db.execute(
                select(CaseDocumentChunk)
                .where(CaseDocumentChunk.document_id == doc.id)
                .order_by(CaseDocumentChunk.sequence_number)
                .limit(25)
            ).scalars().all()

            text_content = "\n\n".join([c.content for c in chunks if c.content])
            doc_texts[doc.id] = text_content

            docs_meta.append({
                "id": doc.id,
                "name": doc.name,
                "storage_link": doc.storage_link,
                "file_type": doc.file_type,
                "document_type": doc.document_type,
                "total_chunks": len(chunks),
                "word_count": count_words(text_content),
            })

        evidence_items = get_case_evidence_details(case_id)

    total_words = sum(count_words(t) for t in doc_texts.values())
    if total_words == 0 and not evidence_items:
        raise ValueError(
            f"Case '{case_id}' documents contain 0 words and no visual evidence. "
            "Please ensure exhibit OCR or parsing has completed before triggering analysis."
        )

    log_entry = (
        f"🏛️ [CaseOrchestrator] Intake completed: {len(docs_meta)} exhibits loaded, "
        f"{total_words} total words, {len(evidence_items)} visual evidence items."
    )
    log_agent_activity(case_id, "CaseOrchestrator", "intake", log_entry)

    # Classify each document using Specialist LLM
    specialist_llm = get_specialist_model()
    classifications = []

    for doc in docs_meta:
        doc_id = doc["id"]
        doc_name = doc["name"]
        snippet = doc_texts.get(doc_id, "")[:3500]

        prompt = f"""You are the Document Classification Specialist.
Examine this document header and opening text, and classify it into exactly one of these predefined legal categories:
- FIR (First Information Report)
- CHARGE_SHEET (Police Final Report under Section 173 CrPC / 193 BNSS)
- WITNESS_STATEMENT (Section 161 / 164 CrPC statement or deposition)
- FORENSIC_REPORT (Post-mortem, FSL, chemical examiner, ballistic or DNA report)
- EVIDENCE_PHOTO (Seizure photo, spot map, physical evidence log)
- COURT_ORDER (Bail order, framing of charges, summons, interlocutory ruling)
- LEGAL_NOTICE (Statutory notice, reply to notice)
- PETITION_AFFIDAVIT (Bail application, writ petition, plaint, written statement)
- OTHER

Document Name: {doc_name}
Document Text Sample:
{snippet}

Respond ONLY in valid JSON matching this schema:
{{
  "document_id": "{doc_id}",
  "document_name": "{doc_name}",
  "classification": "FIR | CHARGE_SHEET | WITNESS_STATEMENT | FORENSIC_REPORT | EVIDENCE_PHOTO | COURT_ORDER | LEGAL_NOTICE | PETITION_AFFIDAVIT | OTHER",
  "confidence": 0.95,
  "rationale": "Brief reason based on document heading and contents",
  "execution_or_filing_date": "YYYY-MM-DD or null",
  "citation_quote": "Exact header quote confirming category",
  "summary": "1-2 sentence legal summary of what this document covers",
  "key_parties": ["Party name 1", "Party name 2"]
}}
"""
        try:
            resp = specialist_llm.invoke([HumanMessage(content=prompt)])
            data = safe_parse_json(resp.content)
            cat = data.get("classification", "OTHER")
            classifications.append(data)

            # Persist classification type on CaseDocument
            with SessionLocal() as db:
                db_doc = db.execute(select(CaseDocument).where(CaseDocument.id == doc_id)).scalar_one_or_none()
                if db_doc:
                    db_doc.document_type = cat
                    db.commit()

            log_agent_activity(case_id, "DocumentClassifier", "classification", f"Exhibit '{doc_name}' classified as '{cat}'")
        except Exception as e:
            logger.warning(f"Error classifying document {doc_name}: {e}")
            classifications.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "classification": "OTHER",
                "confidence": 0.5,
                "rationale": f"Rule-based classification fallback: {doc_name}",
                "execution_or_filing_date": None,
                "citation_quote": ""
            })

    return {
        "case_title": case_title,
        "case_description": case_description,
        "documents_metadata": docs_meta,
        "document_texts": doc_texts,
        "evidence_items": evidence_items,
        "document_classifications": classifications,
        "log_messages": [log_entry]
    }


# ============================================================
# Node 2: Chronological Timeline & Delay Mapping
# ============================================================

def node_chronological_timeline(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Reconstruct the chronological timeline of events across all exhibits with exact dates,
    page citations, and flag unexplained delays (e.g. delayed FIR, delayed medical examination).
    """
    case_id = state["case_id"]
    logger.info(f"⏳ [LangGraph: node_chronological_timeline] Building timeline for {case_id}")

    combined_context = []
    for doc in state["documents_metadata"]:
        doc_id = doc["id"]
        text = state["document_texts"].get(doc_id, "")
        combined_context.append(f"--- Exhibit: {doc['name']} (ID: {doc_id}) ---\n{text[:4500]}")

    for ev in state["evidence_items"][:5]:
        combined_context.append(
            f"--- Visual Evidence: {ev.get('document_name')} Page {ev.get('page_number')} ---\n"
            f"Description: {ev.get('visual_description')}\n"
            f"OCR: {ev.get('extracted_text')}\n"
            f"Detected Event: {ev.get('detected_timeline_event')}"
        )

    context_str = "\n\n".join(combined_context)

    specialist_llm = get_specialist_model()
    prompt = f"""You are the Timeline & Chronology Specialist for Indian litigation.
Reconstruct the master chronological timeline from these case exhibits.

Strict Requirements:
1. Identify all events: date of incident/offence, FIR registration, arrest, seizure panchanama, statements recorded, hospital admission, post-mortem, charge sheet filing, bail hearings.
2. Every single entry MUST have an exact citation quote from the text, specifying the document name and page number.
3. If there is a delay (e.g., incident at 10:00 PM, FIR lodged 36 hours later without explanation), explicitly flag it in the description.
4. Output strictly sorted in ascending chronological order.

Case Context:
{context_str[:12000]}

Respond ONLY in valid JSON matching this schema:
{{
  "timeline": [
    {{
      "event_date": "YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD",
      "event_description": "Factual description of the event including any delay",
      "source_document_id": "Document ID string",
      "source_document_name": "Exhibit filename",
      "source_page": 1,
      "citation_quote": "Exact verbatim sentence from the document",
      "event_type": "incident | fir_lodged | arrest | seizure | statement | medical_exam | charge_sheet | court_hearing | other",
      "is_delay_or_gap": false,
      "delay_details": "Explanation if this represents an unexplained chronological gap or delay"
    }}
  ]
}}
"""
    timeline_events = []
    try:
        resp = specialist_llm.invoke([HumanMessage(content=prompt)])
        data = safe_parse_json(resp.content)
        timeline_events = data.get("timeline", [])
    except Exception as e:
        logger.error(f"Error parsing chronological timeline: {e}")
        timeline_events = []

    log_entry = f"⏳ [TimelineSpecialist] Extracted {len(timeline_events)} chronological events with citations."
    log_agent_activity(case_id, "TimelineSpecialist", "finding", log_entry)

    # Save timeline events directly to DB table CaseTimeline
    for event in timeline_events:
        save_case_timeline_entry(
            case_id=case_id,
            event_date=event.get("event_date", datetime.now().isoformat()),
            event_description=event.get("event_description", ""),
            source_document_id=event.get("source_document_id"),
            source_page=event.get("source_page"),
            citation_quote=event.get("citation_quote")
        )

    return {
        "timeline": timeline_events,
        "log_messages": [log_entry]
    }


# ============================================================
# Node 3: Witness Contradictions & Statement Impeachment
# ============================================================

def node_witness_contradictions(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Cross-examine witness testimonies (161/164 CrPC/BNSS) against the FIR and physical evidence,
    pinpointing contradictions, material omissions, and post-facto improvements.
    """
    case_id = state["case_id"]
    logger.info(f"👥 [LangGraph: node_witness_contradictions] Cross-examining witness statements for {case_id}")

    combined_context = []
    for doc in state["documents_metadata"]:
        doc_id = doc["id"]
        text = state["document_texts"].get(doc_id, "")
        combined_context.append(f"--- Exhibit: {doc['name']} (Type: {doc.get('document_type')}) ---\n{text[:4000]}")

    context_str = "\n\n".join(combined_context)

    specialist_llm = get_specialist_model()
    prompt = f"""You are the Witness Testimony & Evidence Impeachment Specialist.
Examine the statements of witnesses, informants, and victims across the case documents.

Identify:
1. Direct Contradictions: Conflicts between different witnesses or between a witness statement and physical/medical evidence.
2. Material Omissions: Important facts missing from an initial statement or FIR that surfaced later.
3. Post-Facto Improvements: New embellished claims added in subsequent statements.

Case Exhibits:
{context_str[:12000]}

Respond ONLY in valid JSON matching this schema:
{{
  "witness_contradictions": [
    {{
      "witness_name": "Name of witness (e.g. PW-1 / Informant)",
      "conflicting_party_or_record": "Contradicting witness or document (e.g. PW-2 statement / Post-Mortem Report)",
      "defect_type": "Contradiction | Material Omission | Improvement",
      "description": "Clear explanation of the discrepancy and its legal significance",
      "source_document_name": "Exhibit filename",
      "source_page": 1,
      "citation_quote": "Exact verbatim quote evidencing the contradiction",
      "impeachment_severity": "High | Medium | Low",
      "cross_examination_angle": "Cross-examination tactical line under Section 145/146 Indian Evidence Act / BSA"
    }}
  ]
}}
"""
    contradictions = []
    try:
        resp = specialist_llm.invoke([HumanMessage(content=prompt)])
        data = safe_parse_json(resp.content)
        contradictions = data.get("witness_contradictions", [])
    except Exception as e:
        logger.error(f"Error extracting witness contradictions: {e}")
        contradictions = []

    log_entry = f"👥 [WitnessSpecialist] Identified {len(contradictions)} testimony contradictions / omissions."
    log_agent_activity(case_id, "WitnessSpecialist", "finding", log_entry)

    return {
        "witness_contradictions": contradictions,
        "log_messages": [log_entry]
    }


# ============================================================
# Node 4: Legal Issues, Charges, and Research Query Generation
# ============================================================

def node_charges_and_issues(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Formulate legal issues, break down penal offences (IPC/BNS) into statutory ingredients,
    assess evidentiary backing, and formulate targeted queries for Indian Kanoon research.
    """
    case_id = state["case_id"]
    logger.info(f"⚖️ [LangGraph: node_charges_and_issues] Auditing statutory charges for {case_id}")

    combined_context = []
    for doc in state["documents_metadata"]:
        doc_id = doc["id"]
        text = state["document_texts"].get(doc_id, "")
        combined_context.append(f"--- Exhibit: {doc['name']} ---\n{text[:3500]}")

    context_str = "\n\n".join(combined_context)

    orchestrator_llm = get_orchestrator_model()
    prompt = f"""You are the Legal Issue & Penal Charge Auditor under Indian Law.
Examine the charges, allegations, and facts in these exhibits.

Tasks:
1. List the specific penal sections invoked or applicable under IPC (Indian Penal Code) or BNS (Bharatiya Nyaya Sanhita) or Special Acts (e.g. POCSO, NDPS, NI Act 138).
2. For each offence, list its core statutory ingredients.
3. Map the evidence to each ingredient: determine whether it is prima facie established or unsupported.
4. Formulate 2 to 3 targeted, concise Indian Kanoon research queries targeting the core legal ambiguities, defenses, or evidentiary standards (e.g. 'Section 302 IPC eyewitness contradiction appreciation of evidence', 'Section 420 IPC dishonest intention at inception').

Case Context:
{context_str[:12000]}

Respond ONLY in valid JSON matching this schema:
{{
  "charges_analysis": [
    {{
      "section": "e.g. Section 302 IPC / Section 103 BNS",
      "offence_name": "Punishment for Murder",
      "statutory_act": "IPC / BNS",
      "ingredients": [
        {{
          "ingredient": "Description of legal element",
          "evidentiary_support": "Backed by evidence | Unsupported assertion",
          "citations": "Exhibit reference or quote"
        }}
      ],
      "prosecution_strength": "Strong | Moderate | Weak",
      "defense_vulnerabilities": "Core weakness or missing link in the charge",
      "defense_strategy": "Actionable defense legal counter-theory"
    }}
  ],
  "kanoon_queries": [
    "concise query 1",
    "concise query 2"
  ]
}}
"""
    charges = []
    kanoon_queries = []
    try:
        resp = orchestrator_llm.invoke([HumanMessage(content=prompt)])
        data = safe_parse_json(resp.content)
        charges = data.get("charges_analysis", [])
        kanoon_queries = data.get("kanoon_queries", [])
    except Exception as e:
        logger.error(f"Error auditing charges and legal issues: {e}")
        charges = []
        kanoon_queries = ["Section 302 IPC appreciation of evidence Supreme Court"]

    log_entry = (
        f"⚖️ [ChargesAuditor] Evaluated {len(charges)} penal charges. "
        f"Generated {len(kanoon_queries)} Indian Kanoon research queries."
    )
    log_agent_activity(case_id, "ChargesAuditor", "finding", log_entry)

    return {
        "charges_analysis": charges,
        "kanoon_queries": kanoon_queries,
        "log_messages": [log_entry]
    }


# ============================================================
# Node 5: Procedural Compliance & Missing Evidentiary Audit
# ============================================================

def node_procedural_compliance(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Audit procedural stages under CrPC/BNSS or CPC, determine mandatory filings/deadlines,
    and detect missing evidence (e.g., Section 65B/63 BSA certificate, autopsy, seizure memo).
    """
    case_id = state["case_id"]
    logger.info(f"📋 [LangGraph: node_procedural_compliance] Running procedural compliance audit for {case_id}")

    combined_context = []
    for doc in state["documents_metadata"]:
        doc_id = doc["id"]
        text = state["document_texts"].get(doc_id, "")
        combined_context.append(f"--- Exhibit: {doc['name']} (Type: {doc.get('document_type')}) ---\n{text[:3000]}")

    context_str = "\n\n".join(combined_context)

    specialist_llm = get_specialist_model()
    prompt = f"""You are the Procedural Compliance & Evidentiary Gap Specialist.
Analyze the procedural status and evidentiary completeness of this matter under Indian procedural codes (CrPC/BNSS, CPC, Indian Evidence Act / Bharatiya Sakshya Adhiniyam).

Tasks:
1. Missing Evidence: Check for absent trial-critical records:
   - Certificate under Section 65B Indian Evidence Act / Section 63 BSA for electronic records (CCTV, call logs, phone extractions).
   - Spot Panchanama, Seizure Memo, or chain of custody logs.
   - Forensic Science Laboratory (FSL) or Post-Mortem reports if injuries/deaths/substances are alleged.
   - Statutory Sanctions (Section 197 CrPC / Section 218 BNSS).
2. Procedural Compliance: Identify the current procedural stage, statutory limitation periods, and mandatory procedural requirements (default bail under 167(2) CrPC / 187 BNSS, filing of charge sheet, framing of charges).

Case Context:
{context_str[:12000]}

Respond ONLY in valid JSON matching this schema:
{{
  "missing_evidence": [
    {{
      "item_name": "Name of missing filing or evidence",
      "legal_relevance": "Why this item is legally mandatory under Indian Law",
      "statutory_provision": "e.g. Section 65B Indian Evidence Act / Section 63 BSA",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "recommendation": "Specific tactical action required by counsel"
    }}
  ],
  "procedural_compliance": [
    {{
      "procedural_stage": "e.g. Investigation / Framing of Charges / Trial",
      "requirement": "Description of mandatory procedural rule",
      "statutory_deadline": "Applicable deadline or limitation period",
      "status": "COMPLIANT | OVERDUE | PENDING | VIOLATED",
      "remedy": "Legal application or remedy under CrPC/BNSS/CPC"
    }}
  ]
}}
"""
    missing_ev = []
    compliance = []
    try:
        resp = specialist_llm.invoke([HumanMessage(content=prompt)])
        data = safe_parse_json(resp.content)
        missing_ev = data.get("missing_evidence", [])
        compliance = data.get("procedural_compliance", [])
    except Exception as e:
        logger.error(f"Error auditing procedural compliance: {e}")
        missing_ev = []
        compliance = []

    log_entry = (
        f"📋 [ProceduralSpecialist] Flagged {len(missing_ev)} missing evidence gaps, "
        f"{len(compliance)} procedural compliance checkpoints."
    )
    log_agent_activity(case_id, "ProceduralSpecialist", "finding", log_entry)

    return {
        "missing_evidence": missing_ev,
        "procedural_compliance": compliance,
        "log_messages": [log_entry]
    }


# ============================================================
# Node 6: Autonomous Indian Kanoon Precedent Research
# ============================================================

def node_kanoon_precedent_research(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Autonomously executes live research queries on indiankanoon.org using the existing
    Indian Kanoon search tools, extracts ratios and authoritative citations, and integrates
    landmark Supreme Court and High Court precedents.
    """
    case_id = state["case_id"]
    queries = state.get("kanoon_queries", [])
    if not queries:
        queries = ["Section 302 IPC eyewitness contradiction Supreme Court"]

    # Bound research queries to top 3 for guaranteed speed and deterministic completion
    active_queries = queries[:3]
    logger.info(f"🔍 [LangGraph: node_kanoon_precedent_research] Executing Kanoon research for {len(active_queries)} query/queries")

    orchestrator_llm = get_orchestrator_model()
    precedents: List[Dict[str, Any]] = []
    log_messages: List[str] = []

    for q in active_queries:
        search_log = f"🔍 [KanoonResearch] Searching Indian Kanoon for: '{q}'"
        logger.info(search_log)
        log_messages.append(search_log)
        log_agent_activity(case_id, "KanoonResearch", "tool_call", search_log)

        # Call existing Indian Kanoon tools directly
        search_output = search_indian_kanoon_raw(query=q, max_results=2)
        
        # Parse document IDs found
        found_ids = re.findall(r"`(\d+)`", search_output)
        if not found_ids:
            found_ids = re.findall(r"/doc/(\d+)/", search_output)

        if not found_ids:
            log_messages.append(f"🔍 [KanoonResearch] No direct Kanoon document IDs returned for query: '{q}'")
            continue

        for doc_id in found_ids[:1]:  # Read top authority per query
            read_log = f"🛠️ [KanoonResearch] Reading Indian Kanoon document ID: {doc_id}"
            logger.info(read_log)
            log_messages.append(read_log)
            log_agent_activity(case_id, "KanoonResearch", "tool_call", read_log)

            doc_text = fetch_kanoon_document_raw(doc_id)
            cached_meta = get_cached_doc_meta(doc_id) or {}

            # Analyze precedent ratio with LLM
            analysis_prompt = f"""You are the Indian Kanoon Legal Precedent Specialist.
Analyze this court judgment from indiankanoon.org and extract the core legal precedent.

Document ID: {doc_id}
Title: {cached_meta.get('title', 'Indian Kanoon Legal Precedent')}
URL: https://indiankanoon.org/doc/{doc_id}/
Document Text Sample:
{doc_text[:4000]}

Respond ONLY in valid JSON matching this schema:
{{
  "doc_id": "{doc_id}",
  "title": "{cached_meta.get('title', 'Judgment Title')}",
  "court": "Supreme Court of India / High Court of ...",
  "year": "YYYY",
  "citation_standard": "e.g. (2021) 5 SCC 123 or AIR 2019 SC 456",
  "url": "https://indiankanoon.org/doc/{doc_id}/",
  "ratio_decidendi": "Concise holding / rule of law established by the bench",
  "statutory_sections": ["Section 302 IPC", "Section 161 CrPC"],
  "relevance": "Direct application to the charges and evidence in the present case",
  "application_strategy": "How to deploy or distinguish this authority in court arguments"
}}
"""
            try:
                resp = orchestrator_llm.invoke([HumanMessage(content=analysis_prompt)])
                parsed = safe_parse_json(resp.content)
                precedents.append(parsed)
                log_messages.append(f"📋 [KanoonResearch] Integrated authority: '{parsed.get('title')}' ({parsed.get('court')})")
            except Exception as e:
                logger.warning(f"Error parsing Kanoon precedent {doc_id}: {e}")

    summary_log = f"🔍 [KanoonResearch] Completed precedent research with {len(precedents)} landmark authorities."
    log_messages.append(summary_log)
    log_agent_activity(case_id, "KanoonResearch", "finding", summary_log)

    return {
        "kanoon_precedents": precedents,
        "log_messages": log_messages
    }


# ============================================================
# Node 7: Cohesive Legal Dossier Synthesis
# ============================================================

def node_synthesize_dossier(state: CaseAnalysisGraphState) -> Dict[str, Any]:
    """
    Consolidate all specialist findings into a cohesive, institutional legal brief.
    Builds executive summary, key findings, and recommended litigation actions.
    """
    case_id = state["case_id"]
    logger.info(f"📝 [LangGraph: node_synthesize_dossier] Compiling master legal dossier for {case_id}")

    matter_title = state.get("case_title", "Litigation Matter Dossier")
    docs_count = len(state.get("documents_metadata", []))
    events_count = len(state.get("timeline", []))
    contradictions_count = len(state.get("witness_contradictions", []))
    charges_count = len(state.get("charges_analysis", []))
    missing_count = len(state.get("missing_evidence", []))
    precedents_count = len(state.get("kanoon_precedents", []))

    orchestrator_llm = get_orchestrator_model()
    prompt = f"""You are the Executive Legal Counsel and Jurist synthesizing the final Case Analysis Dossier.
Synthesize the structured findings from our specialist team into an authoritative, institutional litigation brief.

Case Caption: {matter_title}
Case Description: {state.get('case_description')}
Exhibits Analyzed: {docs_count}
Timeline Events: {events_count}
Witness Contradictions: {contradictions_count}
Charges Under Review: {charges_count}
Missing Evidence Gaps: {missing_count}
Precedents Retrieved: {precedents_count}

Specialist Findings Summary:
- Classifications: {json.dumps(state.get('document_classifications', [])[:5], default=str)}
- Top Timeline Events: {json.dumps(state.get('timeline', [])[:5], default=str)}
- Top Witness Contradictions: {json.dumps(state.get('witness_contradictions', [])[:5], default=str)}
- Charges: {json.dumps(state.get('charges_analysis', [])[:3], default=str)}
- Missing Evidence: {json.dumps(state.get('missing_evidence', [])[:4], default=str)}
- Kanoon Authorities: {json.dumps(state.get('kanoon_precedents', [])[:3], default=str)}

Respond ONLY in valid JSON matching this schema:
{{
  "executive_summary": "A dense, high-contrast, institutional legal summary (3-4 paragraphs) covering the nature of the matter, core evidentiary vulnerabilities, key timeline contradictions, and prosecutorial weaknesses.",
  "key_findings": [
    "Key evidentiary point 1 with citation",
    "Key timeline gap or delay with citation",
    "Key witness contradiction with citation",
    "Key procedural failure or missing certificate under Section 65B/63 BSA"
  ],
  "recommended_actions": [
    "Specific strategic litigation action 1 (e.g. File Section 91 CrPC application for CDR records)",
    "Specific strategic litigation action 2 (e.g. Cross-examine PW-1 on statement improvement under 145 Evidence Act)",
    "Specific strategic litigation action 3 (e.g. File discharge application or move for regular bail citing precedents)"
  ],
  "summary_report": "Comprehensive written legal brief uniting all findings."
}}
"""
    try:
        resp = orchestrator_llm.invoke([HumanMessage(content=prompt)])
        data = safe_parse_json(resp.content)
        exec_summary = data.get("executive_summary", "")
        key_findings = data.get("key_findings", [])
        recommended_actions = data.get("recommended_actions", [])
        summary_report = data.get("summary_report", exec_summary)
    except Exception as e:
        logger.error(f"Error synthesizing final dossier: {e}")
        exec_summary = f"Case analysis completed for {matter_title}. Analyzed {docs_count} exhibit(s) and {events_count} chronological event(s)."
        key_findings = [f"Processed {docs_count} document(s) with {contradictions_count} contradiction(s) noted."]
        recommended_actions = ["Review extracted witness contradictions and procedural checkpoints."]
        summary_report = exec_summary

    # Normalize key_findings and recommended_actions so strings and dicts are both supported cleanly
    norm_findings = []
    for item in key_findings:
        if isinstance(item, str):
            norm_findings.append(item)
        elif isinstance(item, dict):
            val = item.get("description") or item.get("finding") or item.get("text") or str(item)
            norm_findings.append(str(val))
        else:
            norm_findings.append(str(item))

    norm_actions = []
    for item in recommended_actions:
        if isinstance(item, str):
            norm_actions.append(item)
        elif isinstance(item, dict):
            val = item.get("action") or item.get("recommendation") or item.get("text") or str(item)
            norm_actions.append(str(val))
        else:
            norm_actions.append(str(item))

    final_result_data = {
        "case_id": case_id,
        "matter_title": matter_title,
        "executive_summary": exec_summary,
        "key_findings": norm_findings,
        "recommended_actions": norm_actions,
        "document_classifications": state.get("document_classifications", []),
        "timeline": state.get("timeline", []),
        "missing_evidence": state.get("missing_evidence", []),
        "charges_analysis": state.get("charges_analysis", []),
        "witness_contradictions": state.get("witness_contradictions", []),
        "procedural_compliance": state.get("procedural_compliance", []),
        "kanoon_precedents": state.get("kanoon_precedents", []),
        "summary_report": summary_report,
        "analysis_completed": True
    }

    # Validate against Pydantic schema
    validated = CaseAnalysisResult(**final_result_data).model_dump()

    log_entry = f"📝 [CaseOrchestrator] Legal intelligence dossier compilation complete for case '{case_id}'."
    log_agent_activity(case_id, "CaseOrchestrator", "complete", log_entry)

    return {
        "executive_summary": exec_summary,
        "key_findings": key_findings,
        "recommended_actions": recommended_actions,
        "summary_report": summary_report,
        "analysis_completed": True,
        "structured_response": validated,
        "log_messages": [log_entry]
    }


# ============================================================
# StateGraph Assembly
# ============================================================

def build_case_analysis_graph() -> Any:
    """
    Constructs the deterministic LangGraph for Case File Analysis.
    Intake -> Timeline -> Witness Contradictions -> Charges & Issues ->
    Procedural Compliance -> Kanoon Precedent Research -> Dossier Synthesis -> END
    """
    builder = StateGraph(CaseAnalysisGraphState)

    builder.add_node("intake_and_classification", node_intake_and_classification)
    builder.add_node("chronological_timeline", node_chronological_timeline)
    builder.add_node("witness_contradictions", node_witness_contradictions)
    builder.add_node("charges_and_issues", node_charges_and_issues)
    builder.add_node("procedural_compliance", node_procedural_compliance)
    builder.add_node("kanoon_precedent_research", node_kanoon_precedent_research)
    builder.add_node("synthesize_dossier", node_synthesize_dossier)

    builder.add_edge(START, "intake_and_classification")
    builder.add_edge("intake_and_classification", "chronological_timeline")
    builder.add_edge("chronological_timeline", "witness_contradictions")
    builder.add_edge("witness_contradictions", "charges_and_issues")
    builder.add_edge("charges_and_issues", "procedural_compliance")
    builder.add_edge("procedural_compliance", "kanoon_precedent_research")
    builder.add_edge("kanoon_precedent_research", "synthesize_dossier")
    builder.add_edge("synthesize_dossier", END)

    return builder.compile()


# ============================================================
# Streaming Compatibility Adapter Runner
# ============================================================

class CaseAnalysisGraphRunner:
    """
    Adapter wrapper that exposes `.stream()` and `.invoke()` methods
    compatible with Celery background task streaming in case_tasks.py.
    """
    def __init__(self):
        self.graph = build_case_analysis_graph()

    def _extract_case_id(self, input_data: Dict[str, Any]) -> str:
        case_id = input_data.get("case_id")
        if not case_id and "messages" in input_data:
            for msg in input_data["messages"]:
                content = getattr(msg, "content", "")
                if "case ID:" in content:
                    case_id = content.split("case ID:")[1].strip()
                    break
                elif "case with ID:" in content:
                    case_id = content.split("case with ID:")[1].strip()
                    break
        if not case_id:
            raise ValueError("case_id could not be determined from input_data.")
        return case_id.strip()

    def stream(
        self,
        input_data: Dict[str, Any],
        stream_mode: str = "updates",
        subgraphs: bool = True,
        version: str = "v2",
    ):
        """
        Stream deterministic LangGraph node execution events formatted
        consistently with Celery stream consumers.
        """
        case_id = self._extract_case_id(input_data)

        initial_state: CaseAnalysisGraphState = {
            "case_id": case_id,
            "case_title": "",
            "case_description": "",
            "documents_metadata": [],
            "document_texts": {},
            "evidence_items": [],
            "document_classifications": [],
            "timeline": [],
            "witness_contradictions": [],
            "charges_analysis": [],
            "missing_evidence": [],
            "procedural_compliance": [],
            "kanoon_queries": [],
            "kanoon_precedents": [],
            "executive_summary": "",
            "key_findings": [],
            "recommended_actions": [],
            "summary_report": "",
            "analysis_completed": False,
            "log_messages": [],
            "structured_response": None,
        }

        for chunk in self.graph.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                ns = ["case_orchestrator", node_name]
                yield {
                    "type": "updates",
                    "ns": ns,
                    "data": {
                        node_name: node_output
                    }
                }
                if node_name == "synthesize_dossier" and "structured_response" in node_output:
                    yield {
                        "type": "updates",
                        "ns": ["case_orchestrator"],
                        "data": {
                            "orchestrator": {
                                "structured_response": node_output["structured_response"]
                            }
                        }
                    }

    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct invoke method returning compiled CaseAnalysisResult."""
        case_id = self._extract_case_id(input_data)
        initial_state: CaseAnalysisGraphState = {
            "case_id": case_id,
            "case_title": "",
            "case_description": "",
            "documents_metadata": [],
            "document_texts": {},
            "evidence_items": [],
            "document_classifications": [],
            "timeline": [],
            "witness_contradictions": [],
            "charges_analysis": [],
            "missing_evidence": [],
            "procedural_compliance": [],
            "kanoon_queries": [],
            "kanoon_precedents": [],
            "executive_summary": "",
            "key_findings": [],
            "recommended_actions": [],
            "summary_report": "",
            "analysis_completed": False,
            "log_messages": [],
            "structured_response": None,
        }
        res = self.graph.invoke(initial_state)
        return res.get("structured_response") or res


def create_case_orchestrator() -> CaseAnalysisGraphRunner:
    """
    Factory function instantiating the LangGraph Case Analysis Runner.
    """
    return CaseAnalysisGraphRunner()
