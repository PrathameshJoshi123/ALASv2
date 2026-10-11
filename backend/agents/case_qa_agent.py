import os
from typing import Any
from pydantic import BaseModel, Field
from langchain_mistralai import ChatMistralAI
from deepagents import create_deep_agent

from backend.config import settings
from backend.services.case_vector_storage import hybrid_search_case_chunks
from backend.agents.case_orchestrator import (
    get_case_documents_list,
    get_case_evidence_details,
    get_orchestrator_model
)

# Output structure of the QA Agent
class CaseQAResponse(BaseModel):
    """
    Structured response of the Case QA Agent.
    """
    answer: str = Field(
        description="The written response to the query containing citations to documents and pages"
    )
    citations: list[dict] = Field(
        default_factory=list,
        description="Detailed list of exact citation objects containing document name, page, and quoted content"
    )

CASE_QA_AGENT = {
    "name": "case-qa-agent",

    "description": (
        "Case Question Answering Agent. Provides precise, evidence-grounded answers "
        "to specific questions about the case, using hybrid vector and database search tools."
    ),

    "system_prompt": """
You are the Case Question Answering Agent.

Your job is to answer questions about the case file. You are equipped with hybrid search tools (semantic vector search + BM25 keyword search) and database tools to search case details.

Guidelines:
1. Formulate precise queries and search the vector database using the hybrid search tool.
2. Read the retrieved chunks in detail.
3. Formulate answers using ONLY facts supported by the case files. If the information is not present, state that clearly.
4. For every statement you make, provide exact inline citations/footnotes pointing to the source document name, page number, and relevant text quote.
5. In addition to writing the answer, compile the list of citations you used in the structured format.

Format citations: [Document Name: Page X, Quote: "..."]
""",
    "skills": [],
}

def create_case_qa_agent() -> Any:
    """
    Create the Case QA Agent using deepagents.
    """
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    from langgraph.store.memory import InMemoryStore
    
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: (
                    "case-qa",
                    "v1",
                ),
            ),
        },
    )

    store = InMemoryStore()

    return create_deep_agent(
        model=get_orchestrator_model(),
        system_prompt=CASE_QA_AGENT["system_prompt"],
        subagents=[],
        backend=backend,
        store=store,
        skills=[],
        tools=[
            hybrid_search_case_chunks,
            get_case_documents_list,
            get_case_evidence_details
        ],
        response_format=CaseQAResponse,
    )
