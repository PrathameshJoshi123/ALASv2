"""
Contract Drafting Orchestrator Entrypoint.

Wraps and exports the deterministic LangGraph-based Contract Drafting & Generation
engine (backend.agents.contract_drafting_langgraph).
"""

from __future__ import annotations

from typing import Any

from backend.agents.contract_drafting_langgraph import (
    ContractDraftingResult,
    ContractDraftingLangGraphRunner,
    build_contract_drafting_graph,
    create_contract_drafting_orchestrator,
    get_optimized_chunks_from_db,
    get_total_chunks_count,
)

__all__ = [
    "create_contract_drafting_orchestrator",
    "ContractDraftingLangGraphRunner",
    "ContractDraftingResult",
    "build_contract_drafting_graph",
    "get_optimized_chunks_from_db",
    "get_total_chunks_count",
]
