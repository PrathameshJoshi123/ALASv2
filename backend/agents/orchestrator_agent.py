from __future__ import annotations

import os
from typing import Any, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

from backend.database import SessionLocal
from backend.services.chunking.database import Chunk
from backend.config import settings

# Import specialist agent configs
from backend.agents.document_structure_agent import STRUCTURE_AGENT
from backend.agents.chunk_context_specialist import CONTEXT_AGENT
from backend.agents.entity_resolution_agent import ENTITY_AGENT
from backend.agents.clause_analysis_agent import CLAUSE_AGENT
from backend.agents.obligation_rights_agent import OBLIGATION_AGENT
from backend.agents.contract_risk_agent import RISK_AGENT
from backend.agents.cross_reference_agent import CROSS_REFERENCE_AGENT
from backend.agents.contract_review_agent import REVIEW_AGENT

from dotenv import load_dotenv
load_dotenv()

# ============================================================
# Structured result returned by the orchestrator
# ============================================================

class ContractAnalysisResult(BaseModel):
    """
    Final result produced by the contract analysis orchestrator.
    """

    contract_type: Optional[str] = None

    parties: list[str] = Field(default_factory=list)

    key_findings: list[str] = Field(default_factory=list)

    obligations: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)

    unresolved_questions: list[str] = Field(default_factory=list)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
    )

    analysis_complete: bool = False

    summary: str = ""


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
    Always call this tool first to determine how many chunks exist for the contract before fetching context.
    """
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(Chunk.chunk_id))
            .where(Chunk.document_id == document_id)
        )
        return result.scalar() or 0


# ============================================================
# Orchestrator Prompt
# ============================================================

ORCHESTRATOR_PROMPT = """
You are the Contract Analysis Orchestrator.

Your job is to coordinate a team of specialist agents to produce
a complete, evidence-grounded analysis of a contract.

You are NOT simply executing a predefined pipeline.

You must decide dynamically:

- what needs to be analyzed
- which specialist should analyze it
- what information should be given to that specialist
- whether the result is sufficient
- whether another specialist is required
- whether a finding requires verification
- whether two findings conflict
- whether additional analysis should be performed
- when the contract analysis is complete

AVAILABLE SPECIALISTS:

1. document-structure-agent
   Understands overall contract organization.

2. chunk-context-agent
   Understands local chunk context, continuity, references,
   and section boundaries.

3. entity-resolution-agent
   Resolves parties, entities, defined terms, and references.

4. clause-analysis-agent
   Identifies and classifies contractual provisions.

5. obligation-rights-agent
   Extracts obligations, rights, permissions, conditions,
   prohibitions, triggers, deadlines, and consequences.

6. contract-risk-agent
   Identifies potentially significant contractual risks.

7. cross-reference-agent
   Detects relationships, inconsistencies, and conflicts
    across the contract.

8. contract-review-agent
   Reviews completeness, consistency, and unresolved issues.

COORDINATION AND DELEGATION GUIDELINES:
- When invoking any specialist subagent using the `task` tool, you MUST explicitly include the correct `document_id` UUID (e.g. '7750cfec-...') in the instruction description you send to the subagent. If you do not pass the document ID, the subagent will be unable to access the database.

DATABASE ACCESS:
The contract chunks are stored sequentially in the database table `chunks` with `sequence_number`.
1. First, call `get_total_chunks_count` to get the total number of chunks for the document. This tells you the maximum count so you know the limit and don't query beyond the available chunks.
2. ALWAYS retrieve chunks in batches by calling `get_optimized_chunks_from_db`. Set the `limit` parameter to a maximum of 15 to 20 chunks per call. NEVER request all chunks at once (e.g. limit=100+).
3. Decide dynamically which sequential parts of the document you need to pull context from.
4. IMPORTANT: You MUST continue fetching and analyzing chunks sequentially from `start_sequence = 1` in batches up to the total count of chunks. Do not query beyond the total chunk count. Do not stop midway.
"""


# ============================================================
# Models
# ============================================================

def get_orchestrator_model() -> ChatMistralAI:
    api_key = os.environ.get("MISTRAL_API_KEY") or settings.MISTRAL_API_KEY

    if not api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY environment variable is not configured."
        )

    # Orchestrator, Review and Cross-Reference agents use mistral-medium-2505
    return ChatMistralAI(
        model="mistral-medium-2505",
        api_key=api_key,
        temperature=0.0,
        timeout=settings.MISTRAL_API_TIMEOUT,
        max_retries=settings.MISTRAL_MAX_RETRIES,
    )


def get_specialist_model() -> ChatMistralAI:
    api_key = os.environ.get("MISTRAL_API_KEY") or settings.MISTRAL_API_KEY

    if not api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY environment variable is not configured."
        )

    # Other specialists use ministral-14b-2512
    return ChatMistralAI(
        model="ministral-14b-2512",
        api_key=api_key,
        temperature=0.0,
        timeout=settings.MISTRAL_API_TIMEOUT,
        max_retries=settings.MISTRAL_MAX_RETRIES,
    )


# ============================================================
# Create Orchestrator
# ============================================================

def create_contract_orchestrator() -> Any:
    """
    Create the top-level contract-analysis orchestrator.

    This agent owns the workflow and dynamically delegates
    specialist work through Deep Agents' task mechanism.
    """

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )

    # Configure CompositeBackend as recommended for short-term and persistent memory separation
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: (
                    "contract-analysis",
                    "v1",
                ),
            ),
            "/skills/": StoreBackend(
                namespace=lambda rt: (
                    "contract-analysis",
                    "v1",
                ),
            ),
        },
    )

    DB_GUIDELINES = """

STRICT DATABASE CHUNK RETRIEVAL GUIDELINES:
If you need to query contract chunks from the database:
1. Identify the actual `document_id` UUID (a 36-character string like '7750cfec-...') from your task description instructions. Never use placeholder strings like 'contract_id' or 'contract'. If no UUID is present in the task instruction, look at the chat history to find the 36-character document ID.
2. First, call `get_total_chunks_count` with that correct document ID to get the total number of chunks.
3. ALWAYS retrieve chunks in batches by calling `get_optimized_chunks_from_db`. Set the `limit` parameter to a maximum of 15 to 20 chunks per call. NEVER request all chunks at once (e.g. limit=100+) as it will return a file path or fail.
4. You MUST read ALL chunks in the document sequentially (incrementing `start_sequence` by your batch limit each time, e.g. 1, 16, 31, etc.) until you have retrieved all chunks up to the total count.
5. Stop immediately when `start_sequence` exceeds the total chunk count. Do not loop infinitely. Do not stop early under any circumstance.
"""

    # Update specialist subagent models and configure tool inheritance
    specialist_agents = [
        {**STRUCTURE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": STRUCTURE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**CONTEXT_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": CONTEXT_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**ENTITY_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": ENTITY_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**CLAUSE_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": CLAUSE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**OBLIGATION_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": OBLIGATION_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**RISK_AGENT, "model": get_specialist_model(), "inherit_tools": True, "system_prompt": RISK_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**CROSS_REFERENCE_AGENT, "model": get_orchestrator_model(), "inherit_tools": True, "system_prompt": CROSS_REFERENCE_AGENT.get("system_prompt", "") + DB_GUIDELINES},
        {**REVIEW_AGENT, "model": get_orchestrator_model(), "inherit_tools": True, "system_prompt": REVIEW_AGENT.get("system_prompt", "") + DB_GUIDELINES},
    ]

    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()

    return create_deep_agent(
        model=get_orchestrator_model(),

        system_prompt=ORCHESTRATOR_PROMPT,

        subagents=specialist_agents,

        backend=backend,
        store=store,

        skills=[
            "backend/skills/contract-orchestration",
            "backend/skills/document-structure",
            "backend/skills/chunk-context",
            "backend/skills/entity-resolution",
            "backend/skills/clause-analysis",
            "backend/skills/obligation-rights",
            "backend/skills/contract-risk",
            "backend/skills/cross-reference",
            "backend/skills/contract-review"
        ],

        tools=[get_optimized_chunks_from_db, get_total_chunks_count],

        middleware=[
            CodeInterpreterMiddleware()
        ],

        response_format=ContractAnalysisResult,
    )
