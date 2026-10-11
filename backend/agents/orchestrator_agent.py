"""
Contract Analysis Orchestrator.

Provides the entrypoint for the deterministic LangGraph-based Contract Analysis
engine equipped with structured autonomy and Indian Kanoon research tools.
"""

from __future__ import annotations

from typing import Any

# Re-export clean models for backwards compatibility
from backend.schemas.contract_analysis_models import (
    ClauseAnalysisItem,
    ObligationItem,
    RiskItem,
    ContractAnalysisResult,
)

# Re-export database chunk tools and LangGraph runner
from backend.agents.contract_langgraph_orchestrator import (
    ContractAnalysisGraphRunner,
    get_optimized_chunks_from_db,
    get_total_chunks_count,
    build_contract_analysis_graph,
)


def create_contract_orchestrator() -> Any:
    """
    Create the top-level contract-analysis orchestrator.

    Returns the deterministic LangGraph-based ContractAnalysisGraphRunner
    equipped with structured autonomy and Indian Kanoon research tools.
    """
    return ContractAnalysisGraphRunner()


__all__ = [
    "create_contract_orchestrator",
    "ContractAnalysisGraphRunner",
    "ClauseAnalysisItem",
    "ObligationItem",
    "RiskItem",
    "ContractAnalysisResult",
    "get_optimized_chunks_from_db",
    "get_total_chunks_count",
    "build_contract_analysis_graph",
]
