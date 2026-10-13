"""
Jurist RAG LangGraph Agent.

Implements an autonomous, structured multi-turn retrieval-augmented generation
system for answering questions about legal contracts.

Integrates:
1. Pre-computed structured contract analysis (risk score, flagged clauses, parties, Indian Kanoon citations)
2. Deterministic and autonomous retrieval tools (hybrid vector + BM25 search, surrounding chunks, full chunks)
3. Direct Indian Kanoon lookup tools for statutory and case law inquiries
4. Multi-turn autonomous retrieval loop bounded by MAX_RETRIEVAL_TURNS to guarantee termination.
"""

from __future__ import annotations

import json
import logging
import re
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
from backend.services.contract_analysis_service import get_contract_analysis_from_db
from backend.utils.llm_utils import (
    get_resilient_llm,
    ORCHESTRATOR_MODEL_NAME,
)
from backend.tools.indian_kanoon_tools import (
    search_indian_kanoon,
    fetch_kanoon_document,
)
from backend.agents.retrieval_agent import (
    hybrid_search_chunks,
    get_surrounding_chunks,
    get_all_document_chunks,
    search_chunks_vector_db,
    search_chunks_bm25,
    get_chunk_by_sequence,
    get_total_chunks_count,
)

logger = logging.getLogger(__name__)

MAX_RETRIEVAL_TURNS = 3


# ============================================================
# Graph State & Response Schemas
# ============================================================

class CitationItem(BaseModel):
    chunk_id: Optional[str] = None
    sequence_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    content: Optional[str] = None
    source_type: str = "contract_chunk"  # 'contract_chunk' or 'indian_kanoon'


class JuristRagState(TypedDict):
    document_id: str
    question: str
    analysis_context: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    kanoon_sources: list[dict[str, Any]]
    turn_count: int
    messages: Annotated[list[BaseMessage], add_messages]
    answer: str
    citations: list[dict[str, Any]]
    unresolved_parts: list[str]


# ============================================================
# LLM & Tools setup
# ============================================================

def get_jurist_llm() -> Any:
    """Instantiate resilient Mistral LLM for Jurist RAG."""
    return get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.1)


# ============================================================
# Node 1: Intake & Context Enrichment
# ============================================================

def node_intake_and_enrich(state: JuristRagState) -> dict[str, Any]:
    """
    Load pre-computed contract analysis from database (parties, overall risk score,
    flagged clauses, legal precedents, and summary) to enrich Jurist AI context.
    """
    doc_id = state["document_id"]
    logger.info(f"[Jurist RAG] Loading document and analysis context for {doc_id}...")
    
    analysis = get_contract_analysis_from_db(doc_id) or {}
    
    # Extract compact high-signal context
    analysis_summary = {
        "contract_type": analysis.get("contract_type", "Unknown"),
        "parties": analysis.get("parties", []),
        "overall_risk_score": analysis.get("overall_risk_score", 0),
        "critical_issues": analysis.get("critical_issues", 0),
        "high_issues": analysis.get("high_issues", 0),
        "key_findings": analysis.get("key_findings", [])[:5],
        "summary": (analysis.get("summary") or analysis.get("analysis_summary") or "")[:1500],
        "flagged_clauses": [
            {
                "id": c.get("id"),
                "section_title": c.get("section_title"),
                "clause_type": c.get("clause_type"),
                "severity": c.get("severity"),
                "risk_description": c.get("risk_description"),
                "legal_reasoning": c.get("legal_reasoning"),
            }
            for c in analysis.get("clauses", [])
            if str(c.get("severity", "")).upper() in ["CRITICAL", "HIGH", "MEDIUM"]
        ][:8],
        "legal_sources": analysis.get("legal_sources", [])[:5],
    }

    # Initial prompt message
    analysis_context_str = json.dumps(analysis_summary, indent=2)
    prompt = (
        f"Target Contract Document ID: '{doc_id}'\n\n"
        f"--- PRE-COMPUTED CONTRACT ANALYSIS SUMMARY ---\n"
        f"{analysis_context_str}\n"
        f"-----------------------------------------------\n\n"
        f"User Question: {state['question']}\n\n"
        f"Instructions:\n"
        f"1. Check if the question can be fully answered using the pre-computed analysis above.\n"
        f"2. If specific verbatim clauses, missing details, surrounding text, or statutory validity are needed, invoke tools to search contract chunks (`hybrid_search_chunks`, `get_surrounding_chunks`, `get_all_document_chunks`) or Indian Kanoon (`search_indian_kanoon`).\n"
        f"3. If you have enough evidence, formulate a comprehensive and strictly grounded answer citing chunk references or statutory sections."
    )

    return {
        "analysis_context": analysis_summary,
        "retrieved_chunks": [],
        "kanoon_sources": [],
        "turn_count": 0,
        "messages": [HumanMessage(content=prompt)],
    }


# ============================================================
# Node 2: Autonomous Jurist Agent (Tool-Calling)
# ============================================================

def node_autonomous_retriever(state: JuristRagState) -> dict[str, Any]:
    """
    Agent node equipped with chunk retrieval and Indian Kanoon research tools.
    Decides whether to query chunks, retrieve surrounding context, or synthesize.
    """
    doc_id = state["document_id"]
    turn = state.get("turn_count", 0) + 1
    logger.info(f"[Jurist RAG] Running autonomous retriever turn {turn}/{MAX_RETRIEVAL_TURNS} for {doc_id}")

    tools = [
        hybrid_search_chunks,
        get_surrounding_chunks,
        get_all_document_chunks,
        search_chunks_vector_db,
        search_chunks_bm25,
        get_chunk_by_sequence,
        search_indian_kanoon,
        fetch_kanoon_document,
    ]

    llm = get_jurist_llm().bind_tools(tools)
    response = llm.invoke(state["messages"])
    
    return {
        "messages": [response],
        "turn_count": turn,
    }


# ============================================================
# Node 3: Execute Retrieval Tools
# ============================================================

def node_execute_rag_tools(state: JuristRagState) -> dict[str, Any]:
    """
    Executes the tool calls made by the autonomous retriever, collects chunks and Kanoon sources.
    """
    last_msg = state["messages"][-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {}

    tool_map = {
        "hybrid_search_chunks": hybrid_search_chunks,
        "get_surrounding_chunks": get_surrounding_chunks,
        "get_all_document_chunks": get_all_document_chunks,
        "search_chunks_vector_db": search_chunks_vector_db,
        "search_chunks_bm25": search_chunks_bm25,
        "get_chunk_by_sequence": get_chunk_by_sequence,
        "search_indian_kanoon": search_indian_kanoon,
        "fetch_kanoon_document": fetch_kanoon_document,
    }

    new_tool_messages: list[ToolMessage] = []
    retrieved_chunks = list(state.get("retrieved_chunks", []))
    kanoon_sources = list(state.get("kanoon_sources", []))
    doc_id = state["document_id"]

    for tc in last_msg.tool_calls:
        tool_name = tc.get("name", "")
        args = dict(tc.get("args", {}))
        tool_call_id = tc.get("id", "")

        # Always inject the valid document_id if missing or mismatched
        if "document_id" in args:
            args["document_id"] = doc_id
        elif tool_name in ["hybrid_search_chunks", "get_surrounding_chunks", "get_all_document_chunks", "search_chunks_vector_db", "search_chunks_bm25", "get_chunk_by_sequence"]:
            args["document_id"] = doc_id

        logger.info(f"[Jurist RAG Tool] Executing {tool_name} with args: {args}")
        fn = tool_map.get(tool_name)

        if fn:
            try:
                res = fn(**args)
                # Track retrieved chunks
                if isinstance(res, list):
                    for item in res:
                        if isinstance(item, dict) and ("chunk_id" in item or "sequence_number" in item):
                            if not any(c.get("chunk_id") == item.get("chunk_id") for c in retrieved_chunks if c.get("chunk_id")):
                                retrieved_chunks.append(item)
                        elif isinstance(item, dict) and "doc_id" in item:
                            kanoon_sources.append(item)
                elif isinstance(res, dict) and ("chunk_id" in res or "sequence_number" in res):
                    retrieved_chunks.append(res)
                elif isinstance(res, dict) and "doc_id" in res:
                    kanoon_sources.append(res)

                # Format tool output for LLM message
                str_res = json.dumps(res, default=str)
                if len(str_res) > 4000:
                    str_res = str_res[:4000] + "... [truncated]"
                new_tool_messages.append(ToolMessage(content=str_res, tool_call_id=tool_call_id))
            except Exception as ex:
                logger.error(f"[Jurist RAG Tool] Tool execution error for {tool_name}: {ex}")
                new_tool_messages.append(ToolMessage(content=f"Error: {ex}", tool_call_id=tool_call_id))
        else:
            new_tool_messages.append(ToolMessage(content=f"Tool {tool_name} not found", tool_call_id=tool_call_id))

    return {
        "messages": new_tool_messages,
        "retrieved_chunks": retrieved_chunks,
        "kanoon_sources": kanoon_sources,
    }


# ============================================================
# Conditional Edge: Check if more retrieval is needed
# ============================================================

def should_continue_retrieval(state: JuristRagState) -> str:
    """
    Decides whether to execute tools and loop back, or proceed to final synthesis.
    """
    last_msg = state["messages"][-1]
    turn = state.get("turn_count", 0)

    # If the LLM requested tool calls and we haven't reached the cap
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        if turn < MAX_RETRIEVAL_TURNS:
            return "execute_tools"
        else:
            logger.info(f"[Jurist RAG] Reached maximum turns ({MAX_RETRIEVAL_TURNS}), proceeding to synthesis.")
            return "synthesize"

    return "synthesize"


# ============================================================
# Node 4: Final Synthesis & Citation Assembly
# ============================================================

def node_synthesize_answer(state: JuristRagState) -> dict[str, Any]:
    """
    Synthesizes the grounded final answer combining retrieved chunks, pre-computed analysis,
    and Indian legal statutory research.
    """
    question = state["question"]
    analysis = state.get("analysis_context", {})
    retrieved_chunks = state.get("retrieved_chunks", [])
    kanoon_sources = state.get("kanoon_sources", [])

    # Prepare compact chunks snippet
    chunks_context = ""
    for idx, c in enumerate(retrieved_chunks[:12]):
        seq = c.get("sequence_number", idx + 1)
        p_start = c.get("page_start", "")
        p_end = c.get("page_end", "")
        pages = f" (Pages {p_start}-{p_end})" if p_start else ""
        content = c.get("content", "").strip()[:600]
        chunks_context += f"\n--- Chunk {seq}{pages} ---\n{content}\n"

    synthesis_prompt = (
        f"You are the Senior Legal Jurist AI Assistant.\n\n"
        f"Synthesize a clear, authoritative, and groundedly referenced answer to the user's question:\n"
        f"\"{question}\"\n\n"
        f"AVAILABLE CONTRACT EVIDENCE:\n"
        f"1. Pre-computed Contract Analysis:\n"
        f"- Contract Type: {analysis.get('contract_type')}\n"
        f"- Contracting Parties: {', '.join(analysis.get('parties', []))}\n"
        f"- Overall Risk Score: {analysis.get('overall_risk_score')}%\n"
        f"- Critical/High Issues: {analysis.get('critical_issues')} Critical, {analysis.get('high_issues')} High\n"
        f"- Relevant Flagged Clauses: {json.dumps(analysis.get('flagged_clauses', []), indent=1)}\n\n"
        f"2. Retrieved Contract Chunks:\n{chunks_context or 'No specific chunks retrieved beyond analysis.'}\n\n"
        f"3. Researched Indian Kanoon Precedents / Statutes:\n{json.dumps(kanoon_sources, indent=1) if kanoon_sources else 'None.'}\n\n"
        f"RESPONSE RULES:\n"
        f"- Answer directly and thoroughly, synthesizing BOTH the contract provisions and the pre-computed risk findings.\n"
        f"- When referencing sections, specify chunk sequence or clause titles.\n"
        f"- When Indian statutes apply (e.g., Section 27, Section 74 Indian Contract Act 1872), explain enforceability clearly.\n"
        f"- If any detail requested by the user is truly NOT mentioned anywhere in the contract, explicitly state so.\n"
        f"- Format with professional Markdown headings, bullet points, and citations."
    )

    llm = get_jurist_llm()
    resp = llm.invoke([SystemMessage(content=synthesis_prompt)])
    final_text = resp.content if isinstance(resp.content, str) else str(resp.content)

    # Format structured citations for frontend rendering
    citations: list[dict[str, Any]] = []
    for c in retrieved_chunks[:10]:
        citations.append({
            "chunk_id": c.get("chunk_id") or str(c.get("sequence_number")),
            "sequence_number": c.get("sequence_number"),
            "page_start": c.get("page_start"),
            "page_end": c.get("page_end"),
            "content": (c.get("content") or "")[:250],
            "source_type": "contract_chunk",
        })

    for k in kanoon_sources[:5]:
        citations.append({
            "chunk_id": str(k.get("doc_id", "")),
            "section_title": k.get("title", "Indian Kanoon Citation"),
            "content": (k.get("snippet") or k.get("text") or "")[:250],
            "source_type": "indian_kanoon",
            "url": k.get("url") or (f"https://indiankanoon.org/doc/{k.get('doc_id')}/" if k.get("doc_id") else None),
        })

    return {
        "answer": final_text,
        "citations": citations,
        "unresolved_parts": [],
    }


# ============================================================
# Graph Builder & Runner
# ============================================================

def build_jurist_rag_graph():
    """Build and compile the LangGraph StateGraph for Jurist RAG."""
    builder = StateGraph(JuristRagState)

    builder.add_node("intake_and_enrich", node_intake_and_enrich)
    builder.add_node("autonomous_retriever", node_autonomous_retriever)
    builder.add_node("execute_tools", node_execute_rag_tools)
    builder.add_node("synthesize", node_synthesize_answer)

    builder.add_edge(START, "intake_and_enrich")
    builder.add_edge("intake_and_enrich", "autonomous_retriever")

    builder.add_conditional_edges(
        "autonomous_retriever",
        should_continue_retrieval,
        {
            "execute_tools": "execute_tools",
            "synthesize": "synthesize",
        }
    )

    # After executing tools, return to autonomous retriever for follow-up or completion
    builder.add_edge("execute_tools", "autonomous_retriever")
    builder.add_edge("synthesize", END)

    return builder.compile()


# Singleton compiled graph
_JURIST_RAG_APP = None

def get_jurist_rag_app():
    global _JURIST_RAG_APP
    if _JURIST_RAG_APP is None:
        _JURIST_RAG_APP = build_jurist_rag_graph()
    return _JURIST_RAG_APP


def run_jurist_rag(document_id: str, question: str) -> dict[str, Any]:
    """
    Execute the compiled LangGraph Jurist RAG agent for a contract and question.
    """
    app = get_jurist_rag_app()
    initial_state: JuristRagState = {
        "document_id": document_id,
        "question": question,
        "analysis_context": {},
        "retrieved_chunks": [],
        "kanoon_sources": [],
        "turn_count": 0,
        "messages": [],
        "answer": "",
        "citations": [],
        "unresolved_parts": [],
    }
    
    result = app.invoke(initial_state)
    return {
        "status": "success",
        "document_id": document_id,
        "question": question,
        "answer": result.get("answer", "No answer could be determined from the contract."),
        "citations": result.get("citations", []),
        "unresolved_parts": result.get("unresolved_parts", []),
    }
