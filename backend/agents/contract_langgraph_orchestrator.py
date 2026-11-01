"""
Contract Analysis LangGraph Orchestrator.

Replaces the unconstrained DeepAgents ReAct coordinator with a deterministic,
milestone-driven StateGraph that provides structured autonomy for Indian legal
research and Indian Kanoon validation.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from backend.database import SessionLocal
from backend.services.chunking.database import Chunk
from backend.utils.llm_utils import (
    get_resilient_llm,
    ORCHESTRATOR_MODEL_NAME,
    SPECIALIST_MODEL_NAME,
    safe_parse_json,
    execute_with_exponential_backoff,
)
from backend.tools.indian_kanoon_tools import (
    search_indian_kanoon,
    fetch_kanoon_document,
    extract_doc_id,
    get_cached_doc_meta,
)
from sqlalchemy import select, func
from backend.schemas.contract_analysis_models import (
    ClauseAnalysisItem,
    ObligationItem,
    RiskItem,
    LegalSourceItem,
    ContractAnalysisResult,
    normalize_string_list,
)

logger = logging.getLogger(__name__)

# ============================================================
# Database Tools for retrieving document chunks
# ============================================================

def count_words(text: str) -> int:
    """Count the number of words in a text string."""
    if not text:
        return 0
    return len(text.split())


def get_optimized_chunks_from_db(
    document_id: str,
    start_sequence: int = 1,
    limit: int = 10
) -> list[dict[str, Any]]:
    """
    Fetch chunks for a document sequentially starting from a sequence_number up to a limit,
    optimizing/merging small sequential chunks (< 200 words) to create proper context.
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
            
        MIN_CHUNK_WORDS = 200
        MAX_MERGED_WORDS = 200
        
        merged_groups = []
        current_group_ids = []
        current_group_text = ""
        current_group_original_texts = {}
        
        for chunk in chunks:
            chunk_word_count = count_words(chunk.content)
            
            if not current_group_ids:
                current_group_ids = [chunk.chunk_id]
                current_group_text = chunk.content
                current_group_original_texts[chunk.chunk_id] = chunk.content
            else:
                current_group_word_count = count_words(current_group_text)
                combined_word_count = current_group_word_count + chunk_word_count
                
                if chunk_word_count < MIN_CHUNK_WORDS and combined_word_count <= MAX_MERGED_WORDS:
                    current_group_ids.append(chunk.chunk_id)
                    current_group_text += "\n\n" + chunk.content
                    current_group_original_texts[chunk.chunk_id] = chunk.content
                else:
                    merged_groups.append({
                        "chunk_ids": current_group_ids,
                        "merged_text": current_group_text,
                        "original_texts": current_group_original_texts
                    })
                    current_group_ids = [chunk.chunk_id]
                    current_group_text = chunk.content
                    current_group_original_texts = {chunk.chunk_id: chunk.content}
        
        if current_group_ids:
            merged_groups.append({
                "chunk_ids": current_group_ids,
                "merged_text": current_group_text,
                "original_texts": current_group_original_texts
            })
            
        return merged_groups


def get_total_chunks_count(document_id: str) -> int:
    """
    Retrieve the total number of chunks (maximum sequence number) available in the database for a document.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(Chunk.chunk_id))
            .where(Chunk.document_id == document_id)
        )
        return result.scalar() or 0


def normalize_parties_list(parties: Any) -> list[str]:
    """Normalize contracting parties into a list of clean strings, safely handling dicts, lists, or strings."""
    if not parties:
        return []
    if isinstance(parties, str):
        return [parties.strip()]
    if not isinstance(parties, (list, tuple)):
        return [str(parties)]
    
    normalized = []
    for p in parties:
        if isinstance(p, dict):
            name = p.get("name") or p.get("entity") or p.get("party") or ""
            role = p.get("role") or p.get("designation") or ""
            if name and role:
                normalized.append(f"{name} ({role})")
            elif name:
                normalized.append(str(name))
            elif role:
                normalized.append(str(role))
            else:
                normalized.append(json.dumps(p))
        elif isinstance(p, (list, tuple)):
            normalized.append(", ".join([str(item) for item in p]))
        elif p is not None:
            normalized.append(str(p).strip())
    return [item for item in normalized if item]


# Maximum turns for autonomous legal research loop
MAX_LEGAL_RESEARCH_TURNS = 3
BATCH_CHUNK_LIMIT = 15


# ============================================================
# LangGraph State Definition
# ============================================================

class ContractAnalysisGraphState(TypedDict):
    """Full typed state for the Contract Analysis LangGraph."""
    document_id: str
    total_chunks: int
    contract_type: Optional[str]
    parties: List[str]
    preamble_summary: str
    
    # Cumulative extractions
    clauses: List[ClauseAnalysisItem]
    obligations: List[ObligationItem]
    risks: List[RiskItem]
    
    # Chunk tracking
    current_sequence: int
    
    # Autonomous Legal Research loop
    flagged_legal_topics: List[str]
    legal_research_notes: List[str]
    legal_sources: List[LegalSourceItem]
    messages: Annotated[List[BaseMessage], add_messages]
    research_turn: int
    
    # Final consolidated findings
    overall_risk_score: float
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    key_findings: List[str]
    recommended_actions: List[str]
    unresolved_questions: List[str]
    summary: str
    
    # Final validated result
    final_result: Optional[ContractAnalysisResult]
    structured_response: Optional[ContractAnalysisResult]


# ============================================================
# Node 1: Document Intake & Structural Outline
# ============================================================

def node_document_intake(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Deterministically retrieves total chunks count, reads introductory chunks
    (preamble, recitals, defined terms), and identifies the contract type and parties.
    """
    doc_id = state["document_id"]
    total = get_total_chunks_count(doc_id)
    logger.info(f"[LangGraph: node_document_intake] Document {doc_id} has {total} total chunks.")
    
    # Read initial chunk batch for preamble, parties, and contract type
    intro_batches = get_optimized_chunks_from_db(doc_id, start_sequence=1, limit=12)
    intro_text = "\n\n".join([b.get("merged_text", "") for b in intro_batches])
    
    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)
    
    prompt = f"""You are a Senior Legal Intake Specialist and Contract Review Advocate.
Examine the introductory portion, recitals, and initial clauses of the agreement below with legal precision.
Determine:
1. Exact Contract Classification (e.g., 'Commercial Lease Agreement', 'Agreement of Lease', 'Master Services Agreement', 'Non-Disclosure Agreement', 'Employment Agreement', 'EPC Contract', 'Share Purchase Agreement').
2. Contracting Parties: List each entity name, formal corporate/statutory designation (e.g. 'National Highways Authority of India', 'Proprietor', 'Private Limited Company'), and designated role ('Lessor', 'Lessee', 'Disclosing Party', 'Employer', etc.).
3. Preamble & Recitals Synthesis: Concise legal analysis of the underlying consideration, demised premises/scope, execution date, and legal intent.

Contract Intake Excerpt:
{intro_text[:5000]}

Respond STRICTLY in valid JSON matching this schema:
{{
  "contract_type": "Specific Legal Classification",
  "parties": ["Party 1 (Role)", "Party 2 (Role)"],
  "preamble_summary": "Detailed legal summary of recitals and consideration"
}}
"""

    response = execute_with_exponential_backoff(llm.invoke, [HumanMessage(content=prompt)])
    content = response.content.strip()
    
    if "```json" in content:
        cleaned = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        cleaned = content.split("```")[1].split("```")[0].strip()
    else:
        cleaned = content

    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1).strip()

    try:
        data = safe_parse_json(cleaned)
    except Exception as e:
        logger.error(f"[node_document_intake] Failed to parse document intake JSON: {e}\nRaw content:\n{content}")
        raise ValueError(f"Document intake classification failed to produce valid JSON: {e}")

    contract_type = data.get("contract_type")
    if not contract_type:
        raise ValueError("Document intake failed: 'contract_type' was not extracted by the legal intake specialist.")

    parties = normalize_parties_list(data.get("parties"))
    preamble_summary = data.get("preamble_summary") or ""

    logger.info(f"[LangGraph: node_document_intake] Successfully Classified: {contract_type}, Parties: {parties}")
    
    return {
        "total_chunks": total,
        "contract_type": contract_type,
        "parties": parties,
        "preamble_summary": preamble_summary,
        "current_sequence": 1,
        "clauses": [],
        "obligations": [],
        "risks": [],
        "flagged_legal_topics": [],
        "legal_research_notes": [],
        "research_turn": 0,
    }


# ============================================================
# Node 2: Deterministic Clause & Obligation Extraction
# ============================================================

def node_clause_extraction(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Deterministically processes document chunks in structured batches,
    extracting clauses, obligations, and preliminary risks without looping.
    """
    doc_id = state["document_id"]
    total = state["total_chunks"]
    llm = get_resilient_llm(model_name=SPECIALIST_MODEL_NAME, temperature=0.0)
    
    all_clauses: List[ClauseAnalysisItem] = list(state.get("clauses", []))
    all_obligations: List[ObligationItem] = list(state.get("obligations", []))
    all_risks: List[RiskItem] = list(state.get("risks", []))
    flagged_topics: List[str] = list(state.get("flagged_legal_topics", []))
    
    current_seq = 1
    batch_size = BATCH_CHUNK_LIMIT
    
    # Process batches systematically until total chunks are covered
    while current_seq <= max(total, 1):
        logger.info(f"[LangGraph: node_clause_extraction] Extracting chunks {current_seq} to {current_seq + batch_size - 1} of {total}...")
        batches = get_optimized_chunks_from_db(doc_id, start_sequence=current_seq, limit=batch_size)
        if not batches:
            break
            
        merged_text = "\n\n".join([b.get("merged_text", "") for b in batches])
        
        prompt = f"""You are a Contract Extraction Specialist analyzing chunks {current_seq} to {current_seq + batch_size - 1}.
Extract all contractual clauses, obligations, and preliminary risks from the text below.

For each clause provide:
- section_title
- clause_type (e.g. payment, termination, indemnity, confidentiality, non-compete, governing_law, arbitration, liability, force_majeure, intellectual_property)
- raw_text (short excerpt)
- severity: "LOW", "MEDIUM", "HIGH", "CRITICAL", or "INFO"
- risk_description (any unfair terms, ambiguities, or compliance risks)
- legal_reasoning

For each obligation provide:
- description
- category (e.g. 'Payment & Financial', 'Performance & Delivery', 'Maintenance & Services', 'Compliance & Legal', 'General')
- actor
- action
- beneficiary
- deadline (or None)
- trigger (or None)

For each risk provide:
- description
- category ('Financial & Payment', 'Compliance & Legal', 'Operational & Facility', 'General')
- severity ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
- affected_party
- mitigation

Also flag any clauses that may conflict with Indian Law (such as non-compete, penalty vs liquidated damages, unilateral termination, sole arbitrator appointment, unlimited indemnity, ouster of court jurisdiction).

Text:
{merged_text[:6000]}

Respond ONLY in valid JSON matching this schema:
{{
  "clauses": [
    {{
      "section_title": "...",
      "clause_type": "...",
      "raw_text": "...",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL|INFO",
      "risk_description": "...",
      "legal_reasoning": "..."
    }}
  ],
  "obligations": [
    {{
      "description": "...",
      "category": "...",
      "actor": "...",
      "action": "...",
      "beneficiary": "...",
      "deadline": null,
      "trigger": null
    }}
  ],
  "risks": [
    {{
      "description": "...",
      "category": "...",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "affected_party": "...",
      "mitigation": "..."
    }}
  ],
  "flagged_legal_topics": ["..."]
}}
"""

        try:
            resp = execute_with_exponential_backoff(llm.invoke, [HumanMessage(content=prompt)])
            cleaned = resp.content.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            data = safe_parse_json(cleaned)
            
            # Append extracted clauses
            for idx, c in enumerate(data.get("clauses", [])):
                item = ClauseAnalysisItem(
                    id=str(uuid.uuid4()),
                    clause_number=len(all_clauses) + 1,
                    clause_type=c.get("clause_type", "general"),
                    section_title=c.get("section_title", "Clause"),
                    raw_text=c.get("raw_text", "")[:500],
                    severity=c.get("severity", "LOW").upper(),
                    risk_description=c.get("risk_description", ""),
                    legal_reasoning=c.get("legal_reasoning", ""),
                    confidence_score=0.85
                )
                all_clauses.append(item)
                
            # Append obligations
            for o in data.get("obligations", []):
                all_obligations.append(ObligationItem(
                    description=o.get("description", ""),
                    category=o.get("category", "General"),
                    actor=o.get("actor"),
                    action=o.get("action"),
                    beneficiary=o.get("beneficiary"),
                    deadline=o.get("deadline"),
                    trigger=o.get("trigger"),
                    citation=f"Chunk {current_seq}"
                ))
                
            # Append risks
            for r in data.get("risks", []):
                all_risks.append(RiskItem(
                    description=r.get("description", ""),
                    category=r.get("category", "General"),
                    severity=r.get("severity", "MEDIUM").upper(),
                    affected_party=r.get("affected_party"),
                    mitigation=r.get("mitigation"),
                    citation=f"Chunk {current_seq}"
                ))
                
            for ft in data.get("flagged_legal_topics", []):
                if ft and ft not in flagged_topics:
                    flagged_topics.append(ft)
                    
        except Exception as err:
            logger.warning(f"[node_clause_extraction] Error processing chunk sequence {current_seq}: {err}")
            
        current_seq += batch_size

    logger.info(f"[LangGraph: node_clause_extraction] Completed. Total Clauses: {len(all_clauses)}, Obligations: {len(all_obligations)}, Risks: {len(all_risks)}")
    
    return {
        "clauses": all_clauses,
        "obligations": all_obligations,
        "risks": all_risks,
        "flagged_legal_topics": flagged_topics,
        "current_sequence": current_seq,
    }


# ============================================================
# Node 3: Entity Resolution & Cross-Reference Mapping
# ============================================================

def node_entity_resolution(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Consolidates parties, normalizes entity references, and identifies clauses
    that require legal compliance checks under Indian law.
    """
    clauses = state.get("clauses", [])
    flagged = list(state.get("flagged_legal_topics", []))
    
    # Identify legal keywords in extracted clauses that trigger statutory scrutiny
    scrutiny_keywords = [
        ("restraint of trade", "Section 27 Indian Contract Act 1872 non-compete restraint of trade void"),
        ("non-compete", "Section 27 Indian Contract Act 1872 restraint of trade void"),
        ("liquidated damages", "Section 74 Indian Contract Act liquidated damages penalty reasonable compensation"),
        ("penalty", "Section 74 Indian Contract Act penalty stipulation Kailash Nath"),
        ("jurisdiction", "Section 28 Indian Contract Act restraint of legal proceedings jurisdiction"),
        ("ouster", "Section 28 Indian Contract Act ouster of court jurisdiction"),
        ("arbitrator", "Arbitration and Conciliation Act 1996 Section 12 unilateral appointment sole arbitrator Perkins"),
        ("sole arbitrator", "Arbitration Act unilateral appointment of arbitrator Perkins Eastman Supreme Court"),
        ("unilateral termination", "Section 14 Specific Relief Act determinable contracts unilateral termination"),
        ("unlimited indemnity", "Section 124 125 Indian Contract Act contract of indemnity"),
        ("force majeure", "Section 56 Indian Contract Act frustration of contract Energy Watchdog"),
        ("frustration", "Section 56 Indian Contract Act doctrine of frustration"),
    ]
    
    for clause in clauses:
        clause_text = (clause.section_title + " " + clause.raw_text + " " + clause.risk_description).lower()
        for kw, search_topic in scrutiny_keywords:
            if kw in clause_text and search_topic not in flagged:
                flagged.append(search_topic)
                
    logger.info(f"[LangGraph: node_entity_resolution] Identified {len(flagged)} legal verification topics: {flagged[:4]}")
    
    # Initialize message history for the autonomous legal advisor node
    system_msg = SystemMessage(content="""You are the Autonomous Indian Legal Research Specialist.
Your mission is to evaluate the contractual clauses against Indian statutory laws (The Indian Contract Act 1872, Specific Relief Act 1963, Arbitration & Conciliation Act 1996) and Supreme Court precedents via Indian Kanoon.

You have access to two tools:
1. `search_indian_kanoon`: Search Indian Kanoon for relevant statutory sections or court precedents.
2. `fetch_kanoon_document`: Scrape and read the exact text and ratio decidendi of any document using its Kanoon Doc ID or URL.

RESEARCH METHODOLOGY & MULTI-TURN CAPABILITIES:
- You are equipped with multiple research turns. Use them actively to ensure comprehensive legal verification:
  * Turn 1: Search for the key suspect statutory provisions (e.g. 'Section 27 Indian Contract Act restraint of trade', 'Section 74 Indian Contract Act liquidated damages', 'Section 28 Indian Contract Act', 'Perkins Eastman arbitrator appointment').
  * Turn 2: Inspect returned Doc IDs and call `fetch_kanoon_document` on the most critical documents to read the verbatim statutory section or judgment ratio decidendi.
  * Turn 3: Conduct follow-up searches for any unresolved nuances or state-specific/industry-specific rules, then finalize your legal reasoning.

CRITICAL INDIAN LAW CHECKS:
1. Section 27, Indian Contract Act 1872: Any agreement by which anyone is restrained from exercising a lawful profession, trade or business is VOID ab initio. Post-employment non-competes or post-termination business restrictions are completely void in India (see Niranjan Shankar Golikari, Percept D'Mark).
2. Section 74, Indian Contract Act 1872: Liquidated damages vs penalty. Sums specified in contracts serve only as an upper ceiling. The aggrieved party is entitled only to 'reasonable compensation' not exceeding the named amount, and must prove actual loss unless proof is impossible (see Kailash Nath Associates v. DDA, ONGC v. Saw Pipes). Forfeiture clauses without genuine pre-estimate of loss are void penalties.
3. Section 28, Indian Contract Act 1872: Agreements restricting legal proceedings or shortening the statutory limitation period (3 years under Limitation Act) are void. Complete ouster of civil court jurisdiction where no jurisdiction exists by law is invalid.
4. Unilateral Arbitrator Appointment: Under Arbitration and Conciliation Act (Section 12(5) read with Seventh Schedule and TRF Ltd / Perkins Eastman), an interested party cannot unilaterally appoint a sole arbitrator.
5. Section 56, Indian Contract Act 1872: Frustration of contract and force majeure (Energy Watchdog v. CERC). Commercial hardship or mere unprofitability does NOT constitute frustration.
6. Section 14 & 41, Specific Relief Act 1963: Injunctions cannot be granted to prevent breach of determinable contracts or contracts not specifically enforceable.

Synthesize your legal conclusions with explicit statutory citations, ratio decidendi, and exact Indian Kanoon URLs.""")

    topics_summary = "\n".join([f"- {t}" for t in flagged[:6]]) if flagged else "- Check Indian Contract Act 1872 general enforceability and Section 73/74 damages."
    parties_str = ', '.join(normalize_parties_list(state.get('parties', []))) or "Parties unspecified"
    initial_user_msg = HumanMessage(content=f"""Here are the legal issues and suspect clauses identified in the contract:
{topics_summary}

Parties: {parties_str}
Contract Type: {state.get('contract_type', 'Commercial Contract')}

Please investigate these provisions on Indian Kanoon using your tools. Search for the relevant statutory sections or landmark judgments, inspect the document text, and verify if any contractual terms are void, unenforceable, or legally risky under Indian Law.""")

    return {
        "flagged_legal_topics": flagged,
        "messages": [system_msg, initial_user_msg],
        "research_turn": 0,
        "legal_sources": list(state.get("legal_sources", [])),
    }


# ============================================================
# Node 4: Autonomous Legal Advisor (Agentic Reasoning)
# ============================================================

def node_autonomous_legal_advisor(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Autonomous legal reasoning node. The agent decides whether to search
    Indian Kanoon, read document texts, or synthesize findings.
    """
    llm = get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)
    tools = [search_indian_kanoon, fetch_kanoon_document]
    llm_with_tools = llm.bind_tools(tools)
    
    messages = state["messages"]
    logger.info(f"[LangGraph: node_autonomous_legal_advisor] Invoking legal model (Turn {state['research_turn']}/{MAX_LEGAL_RESEARCH_TURNS})...")
    
    response = execute_with_exponential_backoff(llm_with_tools.invoke, messages)
    
    return {
        "messages": [response],
    }


# ============================================================
# Conditional Edge: Check if Autonomous Loop Continues
# ============================================================

def should_continue_legal_research(state: ContractAnalysisGraphState) -> str:
    """
    Determines whether the agent continues autonomous tool calls or transitions
    deterministically to risk synthesis.
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    current_turn = state.get("research_turn", 0)
    
    # If the model requested tool calls and we haven't exceeded MAX_LEGAL_RESEARCH_TURNS
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if current_turn < MAX_LEGAL_RESEARCH_TURNS:
            logger.info(f"[LangGraph: should_continue_legal_research] Tool calls requested: {[tc['name'] for tc in last_message.tool_calls]}. Routing to legal_tools.")
            return "legal_tools"
        else:
            logger.info(f"[LangGraph: should_continue_legal_research] Reached max research turns ({MAX_LEGAL_RESEARCH_TURNS}). Capping autonomous loop and routing to risk synthesis.")
            return "synthesize_risks"
            
    logger.info("[LangGraph: should_continue_legal_research] No more tool calls. Routing to risk synthesis.")
    return "synthesize_risks"


# ============================================================
# Node 5: Legal Tool Execution Node
# ============================================================

def node_legal_tools(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Executes the tool calls made by the legal advisor (search_indian_kanoon or fetch_kanoon_document)
    and captures responses cleanly as ToolMessages.
    """
    messages = state["messages"]
    last_message = messages[-1]
    notes = list(state.get("legal_research_notes", []))
    sources = list(state.get("legal_sources", []))
    seen_urls = {s.url for s in sources}
    tool_messages: List[BaseMessage] = []
    
    tools_map = {
        "search_indian_kanoon": search_indian_kanoon,
        "fetch_kanoon_document": fetch_kanoon_document,
    }
    
    for tool_call in getattr(last_message, "tool_calls", []):
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id") or str(uuid.uuid4())
        
        logger.info(f"[LangGraph: node_legal_tools] Executing Tool: {tool_name} with args: {tool_args}")
        
        tool_fn = tools_map.get(tool_name)
        if tool_fn:
            try:
                result = tool_fn.invoke(tool_args)
                tool_output = str(result)

                # Collect structured LegalSourceItem
                if tool_name == "fetch_kanoon_document":
                    doc_arg = str(tool_args.get("doc_id_or_url", ""))
                    doc_id = extract_doc_id(doc_arg)
                    if doc_id:
                        meta = get_cached_doc_meta(doc_id)
                        url = f"https://indiankanoon.org/doc/{doc_id}/"
                        if url not in seen_urls:
                            seen_urls.add(url)
                            title = meta.get("title", f"Kanoon Doc {doc_id}") if meta else f"Kanoon Doc {doc_id}"
                            statute_or_court = meta.get("statute_or_court", "Indian Statutory / Judicial Precedent") if meta else "Indian Statutory / Judicial Precedent"
                            summary = meta.get("summary", tool_output[:250]) if meta else tool_output[:250]
                            sources.append(LegalSourceItem(
                                doc_id=doc_id,
                                title=title,
                                url=url,
                                statute_or_court=statute_or_court,
                                relevance_summary=summary,
                                key_provision_or_ratio=tool_output[:400].strip(),
                            ))
                elif tool_name == "search_indian_kanoon":
                    # Parse found results from tool output or cache
                    for line in tool_output.splitlines():
                        if "**" in line and ("Section" in line or "Act" in line or "vs" in line or "v." in line):
                            t_title = line.replace("**", "").strip()
                            if t_title.startswith(("1.", "2.", "3.", "4.", "5.")):
                                t_title = t_title.split(".", 1)[1].strip()
                            t_match = re.search(r"Doc ID:\s*`(\d+)`", tool_output)
                            if t_match:
                                t_id = t_match.group(1)
                                t_url = f"https://indiankanoon.org/doc/{t_id}/"
                                if t_url not in seen_urls and len(sources) < 6:
                                    seen_urls.add(t_url)
                                    sources.append(LegalSourceItem(
                                        doc_id=t_id,
                                        title=t_title,
                                        url=t_url,
                                        statute_or_court="Indian Kanoon Legal Authority",
                                        relevance_summary=f"Discovered via Kanoon query: {tool_args.get('query', '')}",
                                        key_provision_or_ratio="Referenced in contract clause risk assessment.",
                                    ))

            except Exception as e:
                tool_output = f"Tool execution error: {e}"
        else:
            tool_output = f"Unknown tool: {tool_name}"
            
        notes.append(f"Tool {tool_name}({json.dumps(tool_args)}):\n{tool_output[:400]}")
        
        tool_messages.append(ToolMessage(
            tool_call_id=tool_id,
            name=tool_name,
            content=tool_output
        ))
        
    return {
        "messages": tool_messages,
        "research_turn": state.get("research_turn", 0) + 1,
        "legal_research_notes": notes,
        "legal_sources": sources,
    }


# ============================================================
# Node 6: Risk Synthesis & Legal Cross-Examination Node
# ============================================================

def node_risk_synthesis(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Synthesizes the extracted clauses, obligations, and Indian Kanoon research findings.
    Elevates risk levels for clauses that violate Indian statutes (e.g. Section 27, 74, 28),
    computes risk scores, and generates actionable recommendations.
    """
    clauses = state.get("clauses", [])
    obligations = state.get("obligations", [])
    risks = state.get("risks", [])
    notes = state.get("legal_research_notes", [])
    
    # Extract legal advisor's final thoughts from message history
    legal_advisor_text = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            legal_advisor_text = str(msg.content)
            break
            
    # Build structured substantive summaries of extracted clauses and preliminary risks
    clauses_digest = []
    for idx, c in enumerate(clauses[:35]):
        clauses_digest.append(
            f"Clause {idx + 1}: [{c.section_title}] (Type: {c.clause_type}, Severity: {c.severity})\n"
            f"  Text Excerpt: \"{c.raw_text[:220]}\"\n"
            f"  Identified Risk: {c.risk_description}\n"
            f"  Legal Reasoning: {c.legal_reasoning}"
        )
    clauses_text = "\n\n".join(clauses_digest) if clauses_digest else "No individual clauses extracted."

    risks_digest = []
    for r in risks[:25]:
        risks_digest.append(
            f"- [{r.severity} | {r.category}] {r.description}\n"
            f"  Affected Party: {r.affected_party or 'Unspecified'} | Mitigation: {r.mitigation or 'Legal Review Required'}"
        )
    risks_text = "\n".join(risks_digest) if risks_digest else "No preliminary risks categorized."

    llm = get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)
    
    prompt = f"""You are the Chief Legal Risk Assessor and Senior Advocate.
Conduct a rigorous, lawyer-grade synthesis of this agreement under Indian Law (Indian Contract Act 1872, Specific Relief Act 1963, Arbitration & Conciliation Act 1996, and Indian Kanoon judicial precedents).

CONTRACT METADATA:
- Classification: {state.get('contract_type')}
- Contracting Parties: {', '.join(normalize_parties_list(state.get('parties', []))) or 'Parties defined in agreement'}
- Preamble/Recitals: {state.get('preamble_summary', 'Not specified')}

EXTRACTED SUBSTANTIVE CLAUSES ({len(clauses)} Total):
{clauses_text}

PRELIMINARY RISK FINDINGS ({len(risks)} Total):
{risks_text}

INDIAN KANOON PRECEDENTS & STATUTORY RESEARCH:
{legal_advisor_text[:3500] if legal_advisor_text else 'Direct statutory review under Indian Contract Act 1872'}

RESEARCH NOTES & RATIO DECIDENDI:
{chr(10).join(notes[:6]) if notes else 'Standard Indian statutory review'}

YOUR MANDATE:
1. Conduct deep statutory scrutiny under Indian Law:
   - Section 27, Indian Contract Act 1872: Restraint of trade / post-termination covenants (VOID ab initio).
   - Section 74, Indian Contract Act 1872: Liquidated damages vs unenforceable penalty stipulations (Kailash Nath Associates v. DDA; reasonable compensation ceiling).
   - Section 28, Indian Contract Act 1872: Restraint on legal proceedings, truncated limitation periods, or improper jurisdiction ouster.
   - Section 12(5), Arbitration & Conciliation Act 1996: Unilateral appointment of sole arbitrator (Perkins Eastman, TRF Ltd).
   - Indefinite/Unlimited Indemnities and unilateral termination without notice.
2. Calculate a realistic, calibrated OVERALL RISK SCORE (0.0 to 100.0 as a float):
   - 0.0 to 25.0 (LOW RISK): Well-balanced commercial contract, standard mutual obligations, standard boilerplate.
   - 25.1 to 50.0 (MODERATE RISK): Standard commercial agreement with normal negotiation points, minor blanks/placeholders, missing notice grace periods.
   - 50.1 to 75.0 (HIGH RISK): Disproportionate covenants, uncapped liability, one-sided termination for convenience.
   - 75.1 to 95.0 (CRITICAL RISK): Explicit statutory violations (e.g. void non-compete, void penalty forfeiture, unilateral arbitrator).
   - 95.1 to 100.0 (UNLAWFUL / VOID AB INITIO): Completely void contract under Section 23 ICA.
   Do NOT arbitrarily assign 100% to standard agreements. A typical lease or commercial agreement with standard blanks or missing terms should score between 28.0 and 48.0.
3. Count issues by severity based on the clauses and risks above.
4. Formulate 4-6 specific, high-impact key legal findings referencing actual clauses from the agreement.
5. Formulate 4-6 concrete, actionable redlining and negotiation recommendations for legal counsel.
6. Formulate 3-5 critical unresolved questions/ambiguities to clarify with counterparty before execution.
7. Write an authoritative, multi-paragraph Legal Executive Summary analyzing enforceability, commercial balance, and statutory grounding.

Respond STRICTLY in valid JSON matching this schema:
{{
  "overall_risk_score": 38.5,
  "critical_issues": 1,
  "high_issues": 4,
  "medium_issues": 8,
  "low_issues": 10,
  "key_findings": [
    "Specific finding analyzing clause X and legal risk under Indian Law...",
    "..."
  ],
  "recommended_actions": [
    "Concrete negotiation or drafting revision recommendation...",
    "..."
  ],
  "unresolved_questions": [
    "Specific ambiguous commercial or legal point that must be clarified...",
    "..."
  ],
  "summary": "Authoritative executive summary...",
  "additional_statutory_risks": [
    {{
      "description": "Risk description...",
      "category": "Compliance & Legal",
      "severity": "HIGH",
      "affected_party": "Lessee / Party Name",
      "mitigation": "Recommended legal amendment..."
    }}
  ]
}}
IMPORTANT: "key_findings", "recommended_actions", and "unresolved_questions" must each be a list of plain strings (NOT objects or dictionaries).
"""

    resp = execute_with_exponential_backoff(llm.invoke, [HumanMessage(content=prompt)])
    content = resp.content.strip()
    
    cleaned = content
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    
    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1).strip()

    try:
        data = safe_parse_json(cleaned)
    except Exception as e:
        logger.error(f"[node_risk_synthesis] Failed to parse Chief Legal Risk Assessor JSON: {e}\nRaw content:\n{content}")
        raise ValueError(f"Chief Legal Risk Assessor failed to produce valid JSON: {e}")

    # Parse overall risk score safely, handling any accidental percent string e.g. "45%"
    raw_score = data.get("overall_risk_score", 35.0)
    if isinstance(raw_score, str):
        raw_score = float(raw_score.replace("%", "").strip())
    overall_score = round(max(0.0, min(100.0, float(raw_score))), 1)

    critical_c = int(data.get("critical_issues", 0))
    high_c = int(data.get("high_issues", 0))
    medium_c = int(data.get("medium_issues", 0))
    low_c = int(data.get("low_issues", 0))
    key_findings = normalize_string_list(data.get("key_findings") or [], "finding")
    recommended_actions = normalize_string_list(data.get("recommended_actions") or [], "action")
    unresolved_questions = normalize_string_list(data.get("unresolved_questions") or [], "question")
    summary_text = data.get("summary") or ""

    if not summary_text:
        raise ValueError("Chief Legal Risk Assessor output missing required 'summary' field.")

    # Add any additional statutory risks found from Kanoon
    for ar in data.get("additional_statutory_risks", []):
        risks.append(RiskItem(
            description=ar.get("description", ""),
            category=ar.get("category", "Compliance & Legal"),
            severity=ar.get("severity", "HIGH"),
            affected_party=ar.get("affected_party"),
            mitigation=ar.get("mitigation"),
            citation="Indian Kanoon Precedent / Statute"
        ))

    return {
        "risks": risks,
        "overall_risk_score": overall_score,
        "critical_issues": critical_c,
        "high_issues": high_c,
        "medium_issues": medium_c,
        "low_issues": low_c,
        "key_findings": key_findings,
        "recommended_actions": recommended_actions,
        "unresolved_questions": unresolved_questions,
        "summary": summary_text,
    }


# ============================================================
# Node 7: Final Validation & Output Assembly
# ============================================================

def node_final_validation(state: ContractAnalysisGraphState) -> Dict[str, Any]:
    """
    Assembles the final ContractAnalysisResult Pydantic model and guarantees
    type safety, schema validity, and confidence scoring.
    """
    final_obj = ContractAnalysisResult(
        contract_type=state.get("contract_type", "Commercial Contract"),
        parties=normalize_string_list(state.get("parties", []), "party"),
        overall_risk_score=state.get("overall_risk_score", 0.0),
        critical_issues=state.get("critical_issues", 0),
        high_issues=state.get("high_issues", 0),
        medium_issues=state.get("medium_issues", 0),
        low_issues=state.get("low_issues", 0),
        key_findings=normalize_string_list(state.get("key_findings", []), "finding"),
        recommended_actions=normalize_string_list(state.get("recommended_actions", []), "action"),
        clauses=state.get("clauses", []),
        obligations=state.get("obligations", []),
        risks=state.get("risks", []),
        legal_sources=state.get("legal_sources", []),
        unresolved_questions=normalize_string_list(state.get("unresolved_questions", []), "question"),
        confidence=0.92,
        analysis_complete=True,
        summary=state.get("summary", ""),
    )
    
    logger.info(f"[LangGraph: node_final_validation] Successfully generated ContractAnalysisResult with {len(final_obj.clauses)} clauses, {len(final_obj.legal_sources)} Kanoon sources, and {len(final_obj.risks)} risks.")
    
    return {
        "final_result": final_obj,
        "structured_response": final_obj,
    }


# ============================================================
# Graph Construction & Compilation
# ============================================================

def build_contract_analysis_graph() -> Any:
    """Builds and compiles the Contract Analysis LangGraph."""
    builder = StateGraph(ContractAnalysisGraphState)
    
    # Add Nodes
    builder.add_node("document_intake", node_document_intake)
    builder.add_node("clause_extraction", node_clause_extraction)
    builder.add_node("entity_resolution", node_entity_resolution)
    builder.add_node("autonomous_legal_advisor", node_autonomous_legal_advisor)
    builder.add_node("legal_tools", node_legal_tools)
    builder.add_node("synthesize_risks", node_risk_synthesis)
    builder.add_node("final_validation", node_final_validation)
    
    # Deterministic Edges
    builder.add_edge(START, "document_intake")
    builder.add_edge("document_intake", "clause_extraction")
    builder.add_edge("clause_extraction", "entity_resolution")
    builder.add_edge("entity_resolution", "autonomous_legal_advisor")
    
    # Autonomous Tool Loop with Conditional Edge
    builder.add_conditional_edges(
        "autonomous_legal_advisor",
        should_continue_legal_research,
        {
            "legal_tools": "legal_tools",
            "synthesize_risks": "synthesize_risks",
        }
    )
    # Loop back from tool execution to autonomous advisor
    builder.add_edge("legal_tools", "autonomous_legal_advisor")
    
    # Deterministic Final Assembly
    builder.add_edge("synthesize_risks", "final_validation")
    builder.add_edge("final_validation", END)
    
    return builder.compile()


# ============================================================
# Streaming Compatibility Adapter
# ============================================================

class ContractAnalysisGraphRunner:
    """
    Adapter wrapper that exposes a `.stream()` method compatible with
    DeepAgents / Celery streaming handlers in pdf_tasks.py.
    """
    def __init__(self):
        self.graph = build_contract_analysis_graph()

    def stream(
        self,
        input_data: Dict[str, Any],
        stream_mode: str = "updates",
        subgraphs: bool = True,
        version: str = "v2",
    ):
        """
        Stream LangGraph execution events wrapped in the standard format
        expected by pdf_tasks.py logger and event handlers.
        """
        # Extract document_id from messages or dict
        doc_id = input_data.get("document_id")
        if not doc_id and "messages" in input_data:
            for msg in input_data["messages"]:
                content = getattr(msg, "content", "")
                if "document ID:" in content:
                    doc_id = content.split("document ID:")[1].strip()
                    break
                    
        if not doc_id:
            raise ValueError("document_id could not be determined from input_data.")

        initial_state: ContractAnalysisGraphState = {
            "document_id": doc_id,
            "total_chunks": 0,
            "contract_type": None,
            "parties": [],
            "preamble_summary": "",
            "clauses": [],
            "obligations": [],
            "risks": [],
            "current_sequence": 1,
            "flagged_legal_topics": [],
            "legal_research_notes": [],
            "legal_sources": [],
            "messages": [],
            "research_turn": 0,
            "overall_risk_score": 0.0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "key_findings": [],
            "recommended_actions": [],
            "unresolved_questions": [],
            "summary": "",
            "final_result": None,
            "structured_response": None,
        }

        # Stream directly from the compiled LangGraph
        for chunk in self.graph.stream(initial_state, stream_mode="updates"):
            # chunk is a dict: {node_name: {updated_state_keys...}}
            for node_name, node_output in chunk.items():
                ns = ["indian_kanoon_legal_advisor"] if node_name in {"legal_tools"} else []
                # Format event matching pdf_tasks.py consumer
                yield {
                    "type": "updates",
                    "ns": ns,
                    "data": {
                        node_name: node_output
                    }
                }
                # When final_validation is reached, explicitly yield top-level structured_response
                if node_name == "final_validation" and "structured_response" in node_output:
                    yield {
                        "type": "updates",
                        "ns": [],
                        "data": {
                            "coordinator": {
                                "structured_response": node_output["structured_response"],
                                "final_result": node_output.get("final_result"),
                            }
                        }
                    }

    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct invoke method."""
        doc_id = input_data.get("document_id")
        if not doc_id and "messages" in input_data:
            for msg in input_data["messages"]:
                content = getattr(msg, "content", "")
                if "document ID:" in content:
                    doc_id = content.split("document ID:")[1].strip()
                    break
        initial_state = {
            "document_id": doc_id,
            "total_chunks": 0,
            "contract_type": None,
            "parties": [],
            "preamble_summary": "",
            "clauses": [],
            "obligations": [],
            "risks": [],
            "current_sequence": 1,
            "flagged_legal_topics": [],
            "legal_research_notes": [],
            "messages": [],
            "research_turn": 0,
            "overall_risk_score": 0.0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "key_findings": [],
            "recommended_actions": [],
            "unresolved_questions": [],
            "summary": "",
            "final_result": None,
            "structured_response": None,
        }
        return self.graph.invoke(initial_state)
