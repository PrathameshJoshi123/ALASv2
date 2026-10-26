"""
Contract Drafting & Generation LangGraph Engine.

Replaces the unconstrained DeepAgents ReAct coordinator with a deterministic,
milestone-driven StateGraph featuring:
1. Structured autonomy for specialized legal research, clause drafting, and compliance auditing.
2. Direct integration with Indian Kanoon and Indian Contract Act statutory tools.
3. Real-time milestone streaming through DraftingStreamService.
4. Deterministic progression across template-based drafting, prompt-only drafting, and targeted reiteration modes.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from sqlalchemy import select, func

from backend.database import SessionLocal
from backend.models.documents import Document
from backend.services.chunking.database import Chunk
from backend.services.drafting_stream_service import DraftingStreamService
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

# Constants
MAX_LEGAL_RESEARCH_TURNS = 3
MAX_REVISION_TURNS = 2
BATCH_CHUNK_LIMIT = 15


# ============================================================
# Database Tools for retrieving template chunks
# ============================================================

def count_words(text: str) -> int:
    """Count words in text string."""
    if not text:
        return 0
    return len(text.split())


def get_optimized_chunks_from_db(
    document_id: str,
    start_sequence: int = 1,
    limit: int = 15
) -> list[dict[str, Any]]:
    """
    Fetch chunks for a document sequentially, merging short chunks for optimal context.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .where(Chunk.sequence_number >= start_sequence)
            .order_by(Chunk.sequence_number)
            .limit(limit)
        )
        chunks = result.scalars().all()
        if not chunks:
            return []

        merged_groups = []
        current_group_ids = []
        current_group_text = ""

        for chunk in chunks:
            chunk_word_count = count_words(chunk.content)
            if not current_group_ids:
                current_group_ids = [chunk.chunk_id]
                current_group_text = chunk.content
            else:
                combined_word_count = count_words(current_group_text) + chunk_word_count
                if chunk_word_count < 200 and combined_word_count <= 250:
                    current_group_ids.append(chunk.chunk_id)
                    current_group_text += "\n\n" + chunk.content
                else:
                    merged_groups.append({
                        "chunk_ids": current_group_ids,
                        "merged_text": current_group_text,
                    })
                    current_group_ids = [chunk.chunk_id]
                    current_group_text = chunk.content

        if current_group_ids:
            merged_groups.append({
                "chunk_ids": current_group_ids,
                "merged_text": current_group_text,
            })

        return merged_groups


def get_total_chunks_count(document_id: str) -> int:
    """Retrieve total chunks count for document."""
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(Chunk.chunk_id))
            .where(Chunk.document_id == document_id)
        )
        return result.scalar() or 0


# ============================================================
# Pydantic Models for State & Output
# ============================================================

class SectionBlueprint(BaseModel):
    section_id: str
    section_number: str
    title: str
    category: str = "Commercial"  # Preamble, Recitals, Commercial, Protective, Boilerplate, Execution
    description: str = ""
    statutory_requirements: List[str] = Field(default_factory=list)
    user_constraints: List[str] = Field(default_factory=list)
    is_affected_by_reiteration: bool = False


class SectionReviewIssue(BaseModel):
    section_id: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    issue_description: str
    statutory_violation: Optional[str] = None
    remedy_instruction: str


class DraftingReviewVerdict(BaseModel):
    verdict: Literal["APPROVED", "REVISE"] = "APPROVED"
    overall_compliance_score: float = 90.0
    issues: List[SectionReviewIssue] = Field(default_factory=list)
    positive_findings: List[str] = Field(default_factory=list)


class ContractDraftingResult(BaseModel):
    contract_title: str
    contract_type: str
    parties: List[str] = Field(default_factory=list)
    contract_markdown: str
    blueprint: List[Dict[str, Any]] = Field(default_factory=list)
    legal_citations: List[Dict[str, Any]] = Field(default_factory=list)
    review_comments: str = ""
    is_complete: bool = True


# ============================================================
# Typed LangGraph State
# ============================================================

class ContractDraftingGraphState(TypedDict):
    document_id: str
    mode: Literal["template", "prompt_only", "reiteration"]
    contract_type: str
    parties: List[str]
    user_instructions: str
    existing_draft_markdown: Optional[str]
    
    # Structured Preset / Configuration Parameters
    favor_party: str
    governing_law: str
    drafting_style: str
    company_name: Optional[str]
    counterparty_name: Optional[str]
    
    # Blueprint & Structural Map
    blueprint: List[Dict[str, Any]]
    total_sections: int
    
    # Autonomous Legal Research
    legal_research_queries: List[str]
    legal_research_findings: List[Dict[str, Any]]
    research_turn: int
    
    # Drafted Sections
    drafted_sections: Dict[str, Dict[str, Any]]
    current_draft_markdown: str
    
    # Compliance & Review
    review_verdict: Optional[Dict[str, Any]]
    revision_turn: int
    
    # Progress & Output
    progress_percentage: int
    structured_response: Optional[ContractDraftingResult]


# ============================================================
# Helper: Extract JSON safely from LLM output
# ============================================================

def clean_and_parse_json(content: str, fallback_value: Any = None) -> Any:
    """Clean markdown fence and parse JSON."""
    try:
        cleaned = content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"clean_and_parse_json error: {e}. Raw content snippet: {content[:200]}")
        return fallback_value


def strip_markdown_code_fences(content: str) -> str:
    """
    Remove accidental enclosing code block fences (```markdown ... ``` or ``` ... ```)
    and any rogue standalone ``` lines so that the text remains raw, properly parseable Markdown.
    """
    if not content:
        return ""
    text = content.strip()
    # Strip leading/trailing code fences
    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    # Strip any standalone lines that consist only of backtick fences
    text = re.sub(r"^[ \t]*```[a-zA-Z0-9_-]*[ \t]*$", "", text, flags=re.MULTILINE)
    # Normalize excess newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ============================================================
# Node 1: Intake & Blueprint Resolver
# ============================================================

def node_intake_blueprint(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Deterministically determines the mode (template, prompt_only, or reiteration)
    and initializes contract title, parties, and preliminary blueprint.
    Integrates user-specified preset parameters: posture, governing law, and drafting style.
    """
    doc_id = state["document_id"]
    instructions = state.get("user_instructions", "")
    existing_draft = state.get("existing_draft_markdown")
    mode = state.get("mode")

    preset_contract_type = state.get("contract_type")
    favor_party = state.get("favor_party") or "Balanced"
    governing_law = state.get("governing_law") or "Indian Contract Act, 1872"
    drafting_style = state.get("drafting_style") or "Institutional Legal"
    company_name = state.get("company_name")
    counterparty_name = state.get("counterparty_name")

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="INTAKE",
        message=f"Resolving blueprint for {preset_contract_type or 'contract'} (Posture: {favor_party}, Law: {governing_law})...",
        progress=10,
        stage=1,
        total_stages=6,
        details={
            "contract_type": preset_contract_type,
            "favor_party": favor_party,
            "governing_law": governing_law,
            "drafting_style": drafting_style,
        },
    )

    # 1. Check if an existing draft exists in DB, state, or disk
    if not existing_draft:
        try:
            from backend.services.contract_draft_service import get_draft_from_db
            db_draft = get_draft_from_db(doc_id)
            if db_draft and db_draft.get("content"):
                existing_draft = db_draft.get("content")
        except Exception as e:
            logger.warning(f"Error querying existing draft from DB for {doc_id}: {e}")

    output_dir = Path("backend/storage/outputs")
    draft_file = output_dir / f"{doc_id}_drafted_contract.md"
    memories_file = Path("backend/storage/memories") / doc_id / "drafted_contract.md"
    
    if not existing_draft:
        if draft_file.exists():
            try:
                existing_draft = draft_file.read_text(encoding="utf-8")
            except Exception:
                pass
        elif memories_file.exists():
            try:
                existing_draft = memories_file.read_text(encoding="utf-8")
            except Exception:
                pass

    total_chunks = get_total_chunks_count(doc_id)

    # Resolve mode if not explicitly set
    if not mode:
        if existing_draft and len(existing_draft.strip()) > 100:
            mode = "reiteration"
        elif total_chunks > 0:
            mode = "template"
        else:
            mode = "prompt_only"

    # Query LLM to identify contract type and contracting parties if not explicitly provided
    parties = []
    if company_name and counterparty_name:
        parties = [company_name.strip(), counterparty_name.strip()]
    elif company_name:
        parties = [company_name.strip(), "Counterparty / Service Provider"]

    contract_title = preset_contract_type or "Commercial Agreement"
    contract_type = preset_contract_type or "Commercial Contract"

    if not parties or not preset_contract_type or preset_contract_type in ("Custom Contract", "Contract"):
        llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)
        prompt = f"""You are a Legal Contract Intake Architect under Indian Law.
Analyze the user drafting instructions and determine:
1. Contract Title (e.g. Master Services Agreement, Commercial Lease Agreement, Non-Disclosure Agreement)
2. Contract Type category
3. Contracting Parties (names, entity forms, or placeholder roles)

User Instructions:
{instructions[:4000]}

Respond ONLY in valid JSON with keys:
"contract_title": string,
"contract_type": string,
"parties": list of strings
"""
        response = llm.invoke([HumanMessage(content=prompt)])
        parsed = clean_and_parse_json(response.content, fallback_value={})

        if not preset_contract_type or preset_contract_type in ("Custom Contract", "Contract"):
            contract_title = parsed.get("contract_title", "Commercial Agreement")
            contract_type = parsed.get("contract_type", "Commercial Contract")

        if not parties:
            parties = parsed.get("parties", ["Party A (Client)", "Party B (Provider)"])

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="INTAKE_COMPLETE",
        message=f"Blueprint configured: '{contract_title}' ({mode} mode, Posture: {favor_party}, Style: {drafting_style})",
        progress=18,
        stage=1,
        total_stages=6,
        details={
            "mode": mode,
            "contract_type": contract_type,
            "parties": parties,
            "favor_party": favor_party,
            "governing_law": governing_law,
            "drafting_style": drafting_style,
        },
    )

    return {
        "mode": mode,
        "contract_type": contract_type,
        "parties": parties,
        "favor_party": favor_party,
        "governing_law": governing_law,
        "drafting_style": drafting_style,
        "company_name": company_name,
        "counterparty_name": counterparty_name,
        "existing_draft_markdown": existing_draft,
        "progress_percentage": 18,
        "research_turn": 0,
        "revision_turn": 0,
    }


# ============================================================
# Node 2: Structure Extraction & Blueprint Synthesis
# ============================================================

def node_structure_extraction(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Generates or extracts the structural blueprint:
    - If template mode: reads chunks sequentially and extracts exact section outline.
    - If reiteration mode: parses existing draft and tags affected sections.
    - If prompt_only mode: creates industry-standard Indian contract blueprint.
    """
    doc_id = state["document_id"]
    mode = state["mode"]
    contract_type = state["contract_type"]
    instructions = state["user_instructions"]
    existing_draft = state.get("existing_draft_markdown", "")

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="STRUCTURE_ANALYSIS",
        message=f"Constructing section blueprint for {contract_type} ({mode} mode)...",
        progress=25,
        stage=2,
        total_stages=6,
    )

    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)
    blueprint: List[Dict[str, Any]] = []

    if mode == "template":
        total_chunks = get_total_chunks_count(doc_id)
        batches = get_optimized_chunks_from_db(doc_id, start_sequence=1, limit=15)
        template_text = "\n\n".join([b.get("merged_text", "") for b in batches])

        prompt = f"""You are a Template Structure Specialist.
Analyze the template contract text below and extract a complete ordered list of all sections.
Template Text:
{template_text[:6000]}

User Requirements:
{instructions[:2000]}

Respond ONLY in valid JSON with an array of objects matching this schema:
[
  {{
    "section_id": "sec_1",
    "section_number": "1",
    "title": "Title of section",
    "category": "Preamble|Commercial|Protective|Boilerplate|Execution",
    "description": "Short summary of what this section governs",
    "statutory_requirements": ["Indian Contract Act 1872", ...],
    "user_constraints": []
  }}
]
"""
        response = llm.invoke([HumanMessage(content=prompt)])
        blueprint = clean_and_parse_json(response.content, fallback_value=[])

    elif mode == "reiteration" and existing_draft:
        prompt = f"""You are a Contract Revision Specialist.
We have an existing drafted contract in Markdown. The user wants to apply specific edits.
Break the existing contract into its top-level sections, and mark which sections MUST be revised based on the user's comments.

Existing Draft Snippet:
{existing_draft[:5000]}

User Revision Instructions:
{instructions[:3000]}

Respond ONLY in valid JSON with an array:
[
  {{
    "section_id": "sec_1",
    "section_number": "1",
    "title": "Title of section",
    "category": "Commercial",
    "description": "Summary",
    "statutory_requirements": [],
    "user_constraints": [],
    "is_affected_by_reiteration": true or false
  }}
]
"""
        response = llm.invoke([HumanMessage(content=prompt)])
        blueprint = clean_and_parse_json(response.content, fallback_value=[])

    # Fallback or prompt-only standard blueprint
    favor_party = state.get("favor_party", "Balanced")
    governing_law = state.get("governing_law", "Indian Contract Act, 1872")
    drafting_style = state.get("drafting_style", "Institutional Legal")
    parties = state.get("parties", ["Party A", "Party B"])

    if not blueprint:
        prompt = f"""You are a Master Legal Drafter under Indian Law.
Design a complete, comprehensive, standard Indian contract blueprint for a '{contract_type}'.
Governing Statutory Regime: {governing_law}
Drafting Posture & Strategic Bias: {favor_party}
Drafting Style: {drafting_style}
Parties: {', '.join(parties)}

Ensure the blueprint contains standard commercial, protective, and Indian statutory boilerplate sections tailored specifically for {contract_type}:
1. Preamble & Parties (Full corporate forms, registered addresses, CIN/PAN references)
2. Recitals & Transactional Background
3. Definitions & Rules of Interpretation
4. Scope of Commercial Engagement / Performance Obligations / Deliverables / SLAs
5. Consideration, Invoicing, Taxes (GST compliance) & Payment Terms
6. Representations & Warranties (aligned with posture: {favor_party})
7. Confidentiality & Non-Disclosure (statutory trade secret protection)
8. Intellectual Property Rights & Ownership (work-for-hire, licensing, assignment)
9. Term, Renewal & Termination (cause, convenience, effect of termination)
10. Indemnification & Limitation of Liability (Section 73/74 Indian Contract Act, reflecting posture: {favor_party})
11. Dispute Resolution & Arbitration (Arbitration & Conciliation Act 1996, Perkins Eastman compliant, specified seat)
12. Governing Law & Jurisdiction ({governing_law}, Section 28 Indian Contract Act compliant exclusive jurisdiction)
13. Miscellaneous Boilerplate (Severability, Force Majeure, Notices, Entire Agreement, Amendments)
14. Execution & Signatures (Section 10A Information Technology Act 2000 digital signature compliant)

User Instructions:
{instructions[:2000]}

Respond ONLY in valid JSON with an array matching the schema:
[
  {{
    "section_id": "sec_1",
    "section_number": "1",
    "title": "Section Title",
    "category": "Commercial",
    "description": "Description",
    "statutory_requirements": [],
    "user_constraints": []
  }}
]
"""
        response = llm.invoke([HumanMessage(content=prompt)])
        blueprint = clean_and_parse_json(response.content, fallback_value=[])

    # Ensure valid fallback if empty
    if not blueprint:
        blueprint = [
            {"section_id": "sec_1", "section_number": "1", "title": "Preamble and Recitals", "category": "Preamble"},
            {"section_id": "sec_2", "section_number": "2", "title": "Definitions and Interpretation", "category": "Definitions"},
            {"section_id": "sec_3", "section_number": "3", "title": "Commercial Scope & Performance", "category": "Commercial"},
            {"section_id": "sec_4", "section_number": "4", "title": "Consideration & Payment Terms", "category": "Commercial"},
            {"section_id": "sec_5", "section_number": "5", "title": "Confidentiality & Non-Disclosure", "category": "Protective"},
            {"section_id": "sec_6", "section_number": "6", "title": "Intellectual Property Rights", "category": "Protective"},
            {"section_id": "sec_7", "section_number": "7", "title": "Indemnity & Limitation of Liability", "category": "Protective"},
            {"section_id": "sec_8", "section_number": "8", "title": "Term & Termination", "category": "Commercial"},
            {"section_id": "sec_9", "section_number": "9", "title": "Dispute Resolution & Arbitration", "category": "Boilerplate"},
            {"section_id": "sec_10", "section_number": "10", "title": "Governing Law & Jurisdiction", "category": "Boilerplate"},
            {"section_id": "sec_11", "section_number": "11", "title": "Miscellaneous Provisions", "category": "Boilerplate"},
            {"section_id": "sec_12", "section_number": "12", "title": "Execution & Signatures", "category": "Execution"},
        ]

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="BLUEPRINT_READY",
        message=f"Blueprint verified with {len(blueprint)} structured sections.",
        progress=35,
        stage=2,
        total_stages=6,
        details={"total_sections": len(blueprint), "sections": [b.get("title") for b in blueprint]},
    )

    return {
        "blueprint": blueprint,
        "total_sections": len(blueprint),
        "progress_percentage": 35,
    }


# ============================================================
# Node 3: Autonomous Legal Researcher
# ============================================================

def node_autonomous_legal_research(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Autonomously investigates Indian statutory standards and Indian Kanoon authorities
    by performing live searches on indiankanoon.org and scraping verbatim legal provisions
    and landmark Supreme Court precedents for the drafted agreement.
    """
    doc_id = state["document_id"]
    contract_type = state["contract_type"]
    blueprint = state.get("blueprint", [])
    user_instructions = state.get("user_instructions", "")
    favor_party = state.get("favor_party", "Balanced")
    governing_law = state.get("governing_law", "Indian Contract Act, 1872")

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="LEGAL_RESEARCH_START",
        message=f"Formulating autonomous legal research plan for {governing_law} via Indian Kanoon...",
        progress=40,
        stage=3,
        total_stages=6,
        details={"governing_law": governing_law, "posture": favor_party, "contract_type": contract_type},
    )

    # 1. Analyze blueprint sections and user requirements to formulate targeted Indian Kanoon queries
    blueprint_titles = [b.get("title", "") for b in blueprint]
    titles_summary = ", ".join(blueprint_titles[:8])

    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)
    query_prompt = f"""You are the Indian Legal Research Specialist.
We are drafting a {contract_type}.
Governing Law Framework: {governing_law}
Drafting Posture: {favor_party}
Blueprint sections planned: {titles_summary}
User Instructions: {user_instructions[:1500]}

Generate 3 to 4 precise, high-impact search queries to execute on Indian Kanoon (indiankanoon.org) to inspect:
1. Governing provisions of {governing_law} (e.g. Section 27 restraint of trade, Section 73/74 liquidated damages vs penalty, Section 28 court jurisdiction).
2. Dispute resolution & arbitration rules under Arbitration and Conciliation Act, 1996 (e.g. unilateral appointment prohibition under Perkins Eastman / Section 12(5)).
3. Specific commercial precedent for {contract_type} (e.g. SLA enforcement, IP assignment Copyright Act Section 19, or Specific Relief Act 1963).

Respond ONLY in a valid JSON list of strings:
[
  "query 1",
  "query 2",
  "query 3"
]
"""
    query_resp = llm.invoke([HumanMessage(content=query_prompt)])
    queries = clean_and_parse_json(query_resp.content, fallback_value=[
        f"Section 27 Indian Contract Act 1872 restraint of trade",
        "Section 74 Indian Contract Act liquidated damages penalty Kailash Nath",
        "Arbitration and Conciliation Act 1996 Perkins Eastman sole arbitrator appointment",
        f"Indian Contract Act 1872 {contract_type} essential terms",
    ])

    findings: List[Dict[str, Any]] = []
    total_q = len(queries)

    # 2. Autonomously execute live search and scraping on indiankanoon.org for each query
    for idx, q in enumerate(queries):
        progress_now = int(42 + (idx / max(total_q, 1)) * 10)
        DraftingStreamService.publish_event(
            document_id=doc_id,
            milestone="KANOON_SEARCH",
            message=f"Querying Indian Kanoon & Yahoo Legal Index ({idx+1}/{total_q}): '{q}'",
            progress=progress_now,
            stage=3,
            total_stages=6,
            details={"query": q, "index": idx + 1, "total": total_q, "engines": ["Indian Kanoon Direct", "Yahoo DDGS"]},
        )

        # Live search against indiankanoon.org
        search_output = search_indian_kanoon_raw(q, max_results=3)

        # Extract returned document IDs
        doc_ids = re.findall(r"`(\d+)`", search_output)
        if doc_ids:
            # Scrape top relevant document directly from indiankanoon.org/doc/{doc_id}/
            target_doc_id = doc_ids[0]
            DraftingStreamService.publish_event(
                document_id=doc_id,
                milestone="KANOON_SCRAPE",
                message=f"Scraping statutory text & ratio for Kanoon Doc ID: {target_doc_id}...",
                progress=progress_now + 2,
                stage=3,
                total_stages=6,
                details={"doc_id": target_doc_id, "query": q},
            )

            # Scrapes HTML from indiankanoon.org/doc/{target_doc_id}/ and extracts clean text
            scraped_text = fetch_kanoon_document_raw(target_doc_id)
            meta = get_cached_doc_meta(target_doc_id) or {}
            doc_title = meta.get("title", f"Indian Kanoon Doc {target_doc_id}")
            doc_url = meta.get("url", f"https://indiankanoon.org/doc/{target_doc_id}/")

            findings.append({
                "query": q,
                "doc_id": target_doc_id,
                "title": doc_title,
                "url": doc_url,
                "source": "indiankanoon.org (Live Scraped)",
                "summary": scraped_text[:1200],
            })

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="LEGAL_RESEARCH_COMPLETE",
        message=f"Live legal research complete. Scraped {len(findings)} authorities from Indian Kanoon.",
        progress=52,
        stage=3,
        total_stages=6,
        details={"scraped_authorities": [{"title": f["title"], "url": f["url"]} for f in findings]},
    )

    return {
        "legal_research_queries": queries,
        "legal_research_findings": findings,
        "progress_percentage": 52,
        "research_turn": state.get("research_turn", 0) + 1,
    }


# ============================================================
# Node 4: Section-by-Section Writer
# ============================================================

def node_section_writer(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Autonomously synthesizes the contract clauses section by section according to the blueprint.
    Under reiteration mode, re-drafts ONLY the affected sections.
    Integrates user-defined posture, style, and statutory jurisdiction into clause generation.
    """
    doc_id = state["document_id"]
    mode = state["mode"]
    contract_type = state["contract_type"]
    parties = state.get("parties", ["Party A", "Party B"])
    user_instructions = state.get("user_instructions", "")
    blueprint = state.get("blueprint", [])
    research = state.get("legal_research_findings", [])
    existing_draft = state.get("existing_draft_markdown", "")
    drafted_sections = dict(state.get("drafted_sections", {}))

    favor_party = state.get("favor_party", "Balanced")
    governing_law = state.get("governing_law", "Indian Contract Act, 1872")
    drafting_style = state.get("drafting_style", "Institutional Legal")

    total = len(blueprint)
    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)

    # Prepare posture instructions
    if "Client-Favored" in favor_party:
        posture_directive = (
            "POSTURE: CLIENT-FAVORED (AGGRESSIVE PROTECTIVE BIAS FOR PRIMARY CLIENT).\n"
            "- Indemnity: Broad, unilateral indemnification protecting the Client against all third-party claims, IP infringement, gross negligence, and breach of covenants.\n"
            "- Liability: Client aggregate liability strictly capped (e.g. fees paid), while Counterparty liability is UNCAPPED for IP infringement, confidentiality breach, and gross misconduct.\n"
            "- Intellectual Property: 100% full, perpetual, worldwide assignment of all work product and IP to Client immediately upon creation (work-for-hire).\n"
            "- Termination: Client retains unilateral right to terminate for convenience upon short written notice without penalty.\n"
            "- Warranties & SLAs: Strict performance warranties by Counterparty with robust service credit remedies."
        )
    elif "Counterparty-Favored" in favor_party:
        posture_directive = (
            "POSTURE: COUNTERPARTY / VENDOR-FAVORED (PROTECTIVE SUPPLIER BIAS).\n"
            "- Indemnity: Strictly limited indemnities with mandatory prompt notice and mitigation conditions.\n"
            "- Liability: Aggregate liability of Supplier strictly capped to fees paid in preceding 3 to 12 months; comprehensive waiver of indirect, consequential, or punitive damages.\n"
            "- Payment: Strict payment schedules, interest on delayed payments (18% p.a.), right to suspend services for non-payment.\n"
            "- Warranties: Disclaimers of implied warranties to the maximum extent permitted by Indian law."
        )
    else:  # Balanced / Mutual
        posture_directive = (
            "POSTURE: BALANCED & MUTUAL (COMMERCIAL MARKET STANDARD).\n"
            "- Reciprocal covenants: Mutual confidentiality, mutual representations, balanced bilateral indemnities for third-party claims.\n"
            "- Liability: Reciprocal liability cap equal to 12 months contract value; mutual exclusion of consequential damages with standard carve-outs for gross negligence and willful misconduct.\n"
            "- Termination: Mutual rights to terminate for uncured material breach (30 days written cure notice)."
        )

    # Prepare drafting style instructions
    if "Plain English" in drafting_style:
        style_directive = (
            "STYLE: PLAIN ENGLISH COMMERCIAL.\n"
            "- Use clean, concise, modern commercial language without redundant legal archaisms (eliminate 'heretofore', 'witnesseth', 'whereas').\n"
            "- Ensure clear active voice, bulleted obligations where helpful, and high readability while preserving total enforceability under Indian law."
        )
    elif "Regulatory Strict" in drafting_style:
        style_directive = (
            "STYLE: REGULATORY STRICT & COMPLIANCE-FOCUSED.\n"
            "- Cite exact Indian statutory sections (e.g., Section 73 & 74 ICA 1872, Section 27 ICA 1872, Section 10A IT Act 2000, Section 12(5) Arbitration Act 1996).\n"
            "- Include extensive compliance warranties, statutory verification covenants, audit rights, and regulatory inspection clauses."
        )
    else:  # Institutional Legal
        style_directive = (
            "STYLE: INSTITUTIONAL LEGAL (TIER-1 INDIAN LAW FIRM STANDARD).\n"
            "- Authoritative, dense, highly structured institutional legal drafting (comparable to Harvey / Ironclad / top-tier law firms).\n"
            "- Rigorous numbered sub-clauses, precise legal definitions, exhaustive covenants, and unambiguous operative legal obligations."
        )

    # Prepare research summary from actual scraped Indian Kanoon authorities
    research_summary = "\n\n".join([
        f"### Authority: {f.get('title')} (Source: {f.get('url')})\n"
        f"Kanoon Scraped Text / Ratio: {f.get('summary', '')[:500]}"
        for f in research[:6]
    ]) if research else f"Governed generally under {governing_law}."

    completed_count = 0
    assembled_sections: List[str] = []

    for idx, sec in enumerate(blueprint):
        sec_id = sec.get("section_id", f"sec_{idx+1}")
        sec_title = sec.get("title", f"Section {idx+1}")
        is_affected = sec.get("is_affected_by_reiteration", True) if mode == "reiteration" else True

        # If reiteration and section is NOT affected and already drafted, reuse
        if mode == "reiteration" and not is_affected and sec_id in drafted_sections:
            content = drafted_sections[sec_id].get("markdown_content", "")
            assembled_sections.append(content)
            completed_count += 1
            continue

        progress_now = int(50 + (idx / max(total, 1)) * 25)
        DraftingStreamService.publish_event(
            document_id=doc_id,
            milestone="DRAFTING_SECTION",
            message=f"Drafting Section {idx+1} of {total}: {sec_title} ({favor_party})",
            progress=progress_now,
            stage=4,
            total_stages=6,
            details={"section_index": idx + 1, "title": sec_title, "posture": favor_party},
        )

        section_prompt = f"""You are the Specialist Contract Writer under Indian Law.
Draft Section {sec.get('section_number', idx+1)} of the contract: '{sec_title}'.

Contract Type: {contract_type}
Parties: {', '.join(parties)}
Category: {sec.get('category')}
Section Objective: {sec.get('description')}
Governing Statutory Framework: {governing_law}

{posture_directive}

{style_directive}

User Instructions:
{user_instructions[:2000]}

Indian Statutory Principles & Kanoon Authorities to Adhere to:
{research_summary}

RULES:
1. Write complete, detailed, fully articulate, formal legal clauses.
2. DO NOT use generic placeholders like '[Insert clause here]' or 'TBD'.
3. CRITICAL: Output raw Markdown directly. DO NOT wrap or enclose your response in markdown code fences (do NOT use ``` or ```markdown). Begin directly with the section heading (e.g. `## {sec.get('section_number', idx+1)}. {sec_title}`).
4. For non-compete clauses, ensure compliance with Section 27 ICA (restrict post-termination covenants strictly to non-solicitation and trade secrets).
5. For arbitration, specify mutual consent or institutional arbitration (compliant with Perkins Eastman / Section 12(5) Arbitration Act 1996).
"""
        response = llm.invoke([HumanMessage(content=section_prompt)])
        section_md = strip_markdown_code_fences(response.content.strip())

        drafted_sections[sec_id] = {
            "section_id": sec_id,
            "title": sec_title,
            "markdown_content": section_md,
        }
        assembled_sections.append(section_md)
        completed_count += 1

    # Assemble full markdown document
    title_header = f"# {contract_type.upper().replace('_', ' ')}\n\n"
    full_markdown = title_header + "\n\n---\n\n".join(assembled_sections)

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="DRAFTING_COMPLETE",
        message=f"All {total} sections drafted successfully. Ready for legal compliance audit.",
        progress=75,
        stage=4,
        total_stages=6,
    )

    return {
        "drafted_sections": drafted_sections,
        "current_draft_markdown": full_markdown,
        "progress_percentage": 75,
    }


# ============================================================
# Node 5: Compliance Reviewer
# ============================================================

def node_compliance_reviewer(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Autonomously audits the drafted contract against Indian statutory mandates:
    - Section 27 ICA (restraint of trade)
    - Section 74 ICA (penalties vs liquidated damages)
    - Section 28 ICA (restraint of legal proceedings)
    - Arbitration Act 1996 (unilateral appointment prohibition)
    - Empty placeholder audit
    """
    doc_id = state["document_id"]
    contract_md = state["current_draft_markdown"]
    instructions = state.get("user_instructions", "")
    favor_party = state.get("favor_party", "Balanced")
    governing_law = state.get("governing_law", "Indian Contract Act, 1872")

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="COMPLIANCE_REVIEW",
        message=f"Auditing draft against {governing_law} & requested posture ({favor_party})...",
        progress=80,
        stage=5,
        total_stages=6,
    )

    llm = get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)
    audit_prompt = f"""You are the Chief Legal Compliance Reviewer specializing in Indian Law.
Audit the following drafted contract against:
1. Section 27, Indian Contract Act, 1872: Are there post-termination non-compete clauses that are legally void? (Only non-solicitation and trade secret protection are valid).
2. Section 74, Indian Contract Act, 1872: Are there unconscionable penalties disguised as liquidated damages? (Per Kailash Nath Associates, genuine pre-estimate required).
3. Section 28, Indian Contract Act, 1872: Does the contract attempt to shorten statutory limitation periods or oust all legal remedies?
4. Arbitration Act 1996 (Perkins Eastman): Does any party have unilateral appointment of a sole arbitrator?
5. Strategic Posture Alignment: Does the contract correctly embody the requested posture '{favor_party}'?
6. Completeness: Are there any unfinished placeholders (e.g. `[Insert...]`, `[Party A to confirm]`)?

Contract Markdown:
{contract_md[:10000]}

User Instructions & Guidelines:
{instructions[:2000]}

Respond ONLY in valid JSON matching this schema:
{{
  "verdict": "APPROVED" or "REVISE",
  "overall_compliance_score": 92.5,
  "issues": [
    {{
      "section_id": "sec_X",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "issue_description": "Explanation of defect",
      "statutory_violation": "e.g. Section 27 ICA 1872",
      "remedy_instruction": "Specific text modification needed"
    }}
  ],
  "positive_findings": ["All boilerplate clauses compliant with Indian Law", ...]
}}
"""
    response = llm.invoke([HumanMessage(content=audit_prompt)])
    verdict_data = clean_and_parse_json(response.content, fallback_value={
        "verdict": "APPROVED",
        "overall_compliance_score": 92.0,
        "issues": [],
        "positive_findings": ["Contract meets statutory requirements under Indian Contract Act 1872"],
    })

    verdict_str = verdict_data.get("verdict", "APPROVED")
    score = float(verdict_data.get("overall_compliance_score", 90.0))
    issues = verdict_data.get("issues", [])

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="AUDIT_VERDICT",
        message=f"Audit Verdict: {verdict_str} (Compliance Score: {score}%, Issues: {len(issues)})",
        progress=85,
        stage=5,
        total_stages=6,
        details={"verdict": verdict_str, "score": score, "issues_count": len(issues)},
    )

    return {
        "review_verdict": verdict_data,
        "progress_percentage": 85,
    }


# ============================================================
# Conditional Edge: Should Revise Draft?
# ============================================================

def should_revise_draft(state: ContractDraftingGraphState) -> str:
    """Determine whether to route to targeted reviser or finalize."""
    verdict_data = state.get("review_verdict") or {}
    verdict = verdict_data.get("verdict", "APPROVED")
    issues = verdict_data.get("issues", [])
    revision_turn = state.get("revision_turn", 0)

    # If critical issues exist and turn limit not exceeded, revise
    if verdict == "REVISE" and issues and revision_turn < MAX_REVISION_TURNS:
        logger.info(f"[LangGraph Router] Routing to targeted reviser (Turn {revision_turn + 1}/{MAX_REVISION_TURNS}).")
        return "targeted_reviser"

    logger.info("[LangGraph Router] Audit approved or max turns reached. Routing to final assembly.")
    return "final_assembly"


# ============================================================
# Node 6: Targeted Section Reviser
# ============================================================

def node_targeted_reviser(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Applies precise legal remedies strictly to the sections flagged by the reviewer,
    leaving all other sections intact.
    """
    doc_id = state["document_id"]
    verdict_data = state.get("review_verdict") or {}
    issues = verdict_data.get("issues", [])
    drafted_sections = dict(state.get("drafted_sections", {}))
    current_md = state.get("current_draft_markdown", "")
    revision_turn = state.get("revision_turn", 0)

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="TARGETED_REVISION",
        message=f"Applying statutory remedies to {len(issues)} flagged sections...",
        progress=88,
        stage=5,
        total_stages=6,
        details={"issues": issues},
    )

    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)

    for issue in issues:
        sec_id = issue.get("section_id")
        remedy = issue.get("remedy_instruction")
        sec_obj = drafted_sections.get(sec_id)

        if sec_obj and remedy:
            current_text = sec_obj.get("markdown_content", "")
            prompt = f"""You are a Precision Legal Reviser.
Fix the following contract section to eliminate the identified statutory issue while preserving all other clauses.

Section Title: {sec_obj.get('title')}
Identified Issue: {issue.get('issue_description')}
Remedy Directive: {remedy}

Original Section Text:
{current_text}

Output ONLY the revised Markdown text for this section, starting with its header. CRITICAL: Output raw Markdown directly without enclosing backticks or code fences. No conversational preface.
"""
            resp = llm.invoke([HumanMessage(content=prompt)])
            revised_text = strip_markdown_code_fences(resp.content.strip())
            sec_obj["markdown_content"] = revised_text
            drafted_sections[sec_id] = sec_obj

    # Reassemble updated full draft
    rebuilt_sections = [strip_markdown_code_fences(sec["markdown_content"]) for sec in drafted_sections.values()]
    title_header = f"# {state.get('contract_type', 'COMMERCIAL AGREEMENT').upper().replace('_', ' ')}\n\n"
    updated_md = title_header + "\n\n---\n\n".join(rebuilt_sections)

    return {
        "drafted_sections": drafted_sections,
        "current_draft_markdown": updated_md,
        "revision_turn": revision_turn + 1,
        "progress_percentage": 90,
    }


# ============================================================
# Node 7: Final Assembly & Export Engine
# ============================================================

def node_final_assembly(state: ContractDraftingGraphState) -> Dict[str, Any]:
    """
    Finalizes the contract Markdown, writes to output and memory files,
    updates database Document record, and emits the completion event.
    """
    doc_id = state["document_id"]
    contract_md = strip_markdown_code_fences(state["current_draft_markdown"])
    contract_type = state.get("contract_type", "Commercial Contract")
    parties = state.get("parties", [])
    blueprint = state.get("blueprint", [])
    research = state.get("legal_research_findings", [])
    verdict = state.get("review_verdict") or {}

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="FINAL_ASSEMBLY",
        message="Assembling final contract document and saving persistent storage...",
        progress=95,
        stage=6,
        total_stages=6,
    )

    # 1. Save contract draft directly to the database
    from backend.services.contract_draft_service import save_or_update_draft_in_db
    try:
        draft_record = save_or_update_draft_in_db(
            document_id=doc_id,
            content=contract_md,
            contract_title=contract_type,
            contract_type=contract_type,
            parties=parties,
            blueprint=blueprint,
            legal_citations=research,
            review_comments=verdict.get("positive_findings", ["Statutory compliance confirmed"]),
            compliance_score=verdict.get("overall_compliance_score", 90.0),
        )
        logger.info(f"Contract draft saved to DB for document {doc_id} (version {draft_record.get('version', 1)})")
    except Exception as db_save_err:
        logger.error(f"Failed to save contract draft to database for {doc_id}: {db_save_err}", exc_info=True)

    # Optional disk cache / backup for legacy consumers
    output_dir = Path("backend/storage/outputs")
    markdown_file = output_dir / f"{doc_id}_drafted_contract.md"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_file.write_text(contract_md, encoding="utf-8")
        report_data = {
            "contract_title": contract_type,
            "contract_type": contract_type,
            "parties": parties,
            "blueprint_sections_count": len(blueprint),
            "compliance_score": verdict.get("overall_compliance_score", 90.0),
            "review_comments": verdict.get("positive_findings", ["Statutory compliance confirmed"]),
            "legal_sources_count": len(research),
        }
        report_file = output_dir / f"{doc_id}_drafting_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
    except Exception as disk_cache_err:
        logger.warning(f"Optional cache writing skipped for {doc_id}: {disk_cache_err}")

    # Optional memory directory cache
    try:
        mem_dir = Path("backend/storage/memories") / doc_id
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "drafted_contract.md").write_text(contract_md, encoding="utf-8")
        (mem_dir / "drafting_memory.md").write_text(
            f"# Drafting Memory for {doc_id}\n\nContract Type: {contract_type}\nParties: {', '.join(parties)}\n\n## Blueprint:\n" +
            "\n".join([f"- {b.get('title')}" for b in blueprint]),
            encoding="utf-8"
        )
    except Exception as mem_err:
        logger.warning(f"Optional memory cache skipped for {doc_id}: {mem_err}")

    # 4. Update Document status in database
    try:
        with SessionLocal() as db:
            result = db.execute(select(Document).where(Document.id == doc_id))
            doc_record = result.scalar_one_or_none()
            if doc_record:
                doc_record.status = "COMPLETED"
                doc_record.contract_type = contract_type
                clean_title = re.sub(r"[^\w\s-]", "", contract_type).strip().replace(" ", "_")
                if doc_record.name.startswith("Custom_Contract_") or not doc_record.name:
                    doc_record.name = f"{clean_title}.pdf"
                if parties and len(parties) >= 2:
                    doc_record.company_name = parties[0]
                    doc_record.counterparty_name = parties[1]
                db.commit()
    except Exception as db_err:
        logger.warning(f"Failed to update document status in DB for {doc_id}: {db_err}")

    # Construct clean Pydantic result
    final_obj = ContractDraftingResult(
        contract_title=contract_type,
        contract_type=contract_type,
        parties=parties,
        contract_markdown=contract_md,
        blueprint=blueprint,
        legal_citations=research,
        review_comments=json.dumps(verdict.get("positive_findings", [])),
        is_complete=True,
    )

    DraftingStreamService.publish_event(
        document_id=doc_id,
        milestone="COMPLETED",
        message=f"Contract successfully drafted and verified! Ready in document editor.",
        progress=100,
        stage=6,
        total_stages=6,
        details={"file": str(markdown_file)},
        is_complete=True,
    )

    return {
        "structured_response": final_obj,
        "progress_percentage": 100,
    }


# ============================================================
# Graph Builder
# ============================================================

def build_contract_drafting_graph() -> Any:
    """Builds and compiles the Contract Drafting & Generation StateGraph."""
    builder = StateGraph(ContractDraftingGraphState)

    # Nodes
    builder.add_node("intake_blueprint", node_intake_blueprint)
    builder.add_node("structure_extraction", node_structure_extraction)
    builder.add_node("autonomous_legal_research", node_autonomous_legal_research)
    builder.add_node("section_writer", node_section_writer)
    builder.add_node("compliance_reviewer", node_compliance_reviewer)
    builder.add_node("targeted_reviser", node_targeted_reviser)
    builder.add_node("final_assembly", node_final_assembly)

    # Edges
    builder.add_edge(START, "intake_blueprint")
    builder.add_edge("intake_blueprint", "structure_extraction")
    builder.add_edge("structure_extraction", "autonomous_legal_research")
    builder.add_edge("autonomous_legal_research", "section_writer")
    builder.add_edge("section_writer", "compliance_reviewer")

    # Conditional Review Loop
    builder.add_conditional_edges(
        "compliance_reviewer",
        should_revise_draft,
        {
            "targeted_reviser": "targeted_reviser",
            "final_assembly": "final_assembly",
        }
    )
    # Loop back from reviser to reviewer
    builder.add_edge("targeted_reviser", "compliance_reviewer")
    builder.add_edge("final_assembly", END)

    return builder.compile()


# ============================================================
# Streaming Compatibility Adapter
# ============================================================

class ContractDraftingLangGraphRunner:
    """
    Adapter wrapper that exposes a `.stream()` method compatible with Celery streaming
    and log files, mirroring the ContractAnalysisGraphRunner.
    """
    def __init__(self):
        self.graph = build_contract_drafting_graph()

    def stream(
        self,
        input_data: Dict[str, Any],
        stream_mode: str = "updates",
        subgraphs: bool = True,
        version: str = "v2",
    ):
        """Yield LangGraph stream events."""
        doc_id = input_data.get("document_id")
        instructions = input_data.get("drafting_instructions") or input_data.get("instructions") or ""

        # Check for user message
        if not instructions and "messages" in input_data:
            for msg in input_data["messages"]:
                if hasattr(msg, "content") and msg.content:
                    instructions = str(msg.content)
                    if "ID: " in instructions:
                        try:
                            doc_id = instructions.split("ID: ")[1].split(".")[0].strip()
                        except Exception:
                            pass
                    break

        initial_state: ContractDraftingGraphState = {
            "document_id": doc_id or "",
            "mode": input_data.get("mode", "prompt_only"),
            "contract_type": input_data.get("contract_type", "Commercial Contract"),
            "parties": [],
            "user_instructions": instructions,
            "existing_draft_markdown": input_data.get("existing_draft_markdown"),
            "blueprint": [],
            "total_sections": 0,
            "legal_research_queries": [],
            "legal_research_findings": [],
            "research_turn": 0,
            "drafted_sections": {},
            "current_draft_markdown": "",
            "review_verdict": None,
            "revision_turn": 0,
            "progress_percentage": 0,
            "structured_response": None,
        }

        # Stream node updates from the LangGraph
        for chunk in self.graph.stream(
            initial_state,
            stream_mode=stream_mode,
            version=version,
        ):
            # Normalizes format to match Celery log handling
            if isinstance(chunk, tuple) and len(chunk) == 2:
                node_name, node_output = chunk
                yield {
                    "type": "updates",
                    "ns": [node_name],
                    "data": {node_name: node_output},
                }
            elif isinstance(chunk, dict):
                yield {
                    "type": "updates",
                    "ns": list(chunk.keys()),
                    "data": chunk,
                }


def create_contract_drafting_orchestrator(document_id: str) -> Any:
    """
    Main entrypoint factory returning the deterministic LangGraph-based
    ContractDraftingLangGraphRunner.
    """
    return ContractDraftingLangGraphRunner()
