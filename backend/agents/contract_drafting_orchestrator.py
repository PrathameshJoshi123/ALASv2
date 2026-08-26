from __future__ import annotations

import os
import re
import requests
import logging
from typing import Any, Optional, List, Dict
from html.parser import HTMLParser

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI
from ddgs import DDGS

from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

# Import subagent configs
from backend.agents.structure_understanding_agent import STRUCTURE_UNDERSTANDING_AGENT
from backend.agents.contract_research_agent import CONTRACT_RESEARCH_AGENT
from backend.agents.contract_writer_agent import CONTRACT_WRITER_AGENT
from backend.agents.contract_drafting_reviewer_agent import DRAFTING_REVIEW_AGENT

# Import chunk tools from existing orchestrator
from backend.agents.orchestrator_agent import get_optimized_chunks_from_db, get_total_chunks_count

logger = logging.getLogger(__name__)

# ============================================================
# Structured result returned by the drafting orchestrator
# ============================================================

class ContractDraftingResult(BaseModel):
    """
    Final result produced by the contract drafting orchestrator.
    """
    contract_title: str = Field(description="The title of the drafted contract")
    contract_markdown: str = Field(description="The final drafted contract in clean Markdown format")
    drafting_notes: str = Field(default="", description="Any notes, guidelines, or warnings regarding the drafted contract")
    review_comments: str = Field(default="", description="Comments from the reviewer agent")
    is_complete: bool = Field(default=False, description="Flag indicating if the drafting process is complete and verified")


# ============================================================
# Web Search & HTML Fetching Tools
# ============================================================

def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the internet for relevant contract clauses, governing laws, or legal requirements.
    This search is strictly restricted to indiankanoon.org.
    
    Args:
        query: The search query.
        max_results: Maximum search results to return (default: 5).
    """
    logger.info(f"Performing DDG search for query: '{query}'")
    
    # 1. Enforce query targeting restriction
    if "indiankanoon.org" not in query.lower():
        return [{
            "error": (
                "Search blocked: You are only allowed to search on indiankanoon.org. "
                "Please rewrite your search query to include 'site:indiankanoon.org'."
            )
        }]
        
    try:
        results = []
        with DDGS() as ddgs:
            # We catch exceptions to prevent crash if no results are found
            try:
                raw_results = ddgs.text(query, max_results=max_results, backend="brave")
            except Exception as search_err:
                logger.warning(f"DDG text search returned no results or failed: {search_err}")
                return [{"error": f"Search returned no results: {search_err}"}]
                
            for r in raw_results:
                url = r.get("href", "")
                # 2. Filter out non-indiankanoon results
                if "indiankanoon.org" in url.lower():
                    results.append({
                        "title": r.get("title"),
                        "url": url,
                        "snippet": r.get("body")
                    })
                    
        if not results:
            return [{"error": "No results found matching indiankanoon.org for this query."}]
            
        return results
    except Exception as e:
        logger.error(f"DDG search failed: {e}", exc_info=True)
        return [{"error": f"Search failed: {e}"}]


class HTMLTextStripper(HTMLParser):
    """Simple parser to strip HTML tags and extract raw text."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        self.strict = False
        self.convert_charrefs = True

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


def fetch_web_page(url: str) -> str:
    """
    Fetch the HTML content of a given URL and extract clean text content.
    
    Args:
        url: The web page URL to fetch.
    """
    logger.info(f"Fetching web page content for URL: {url}")
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        # Strip script and style tags
        html = re.sub(r'<(script|style)\b[^>]*>([\s\S]*?)<\/\1>', '', html, flags=re.I)
        
        # Use HTMLParser to strip remaining tags
        stripper = HTMLTextStripper()
        stripper.feed(html)
        text = stripper.get_data()
        
        # Clean up whitespaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Capping characters to protect context window size limits
        return text[:8000]
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}", exc_info=True)
        return f"Failed to fetch page content: {e}"


# ============================================================
# Models
# ============================================================

def get_orchestrator_model() -> ChatMistralAI:
    api_key = os.environ.get("MISTRAL_API_KEY") or os.environ.get("MISTRALAI_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY environment variable is not configured.")
    return ChatMistralAI(
        model="mistral-medium-2505",
        api_key=api_key,
        temperature=0.0,
    )


def get_specialist_model() -> ChatMistralAI:
    api_key = os.environ.get("MISTRAL_API_KEY") or os.environ.get("MISTRALAI_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY environment variable is not configured.")
    return ChatMistralAI(
        model="ministral-14b-2512",
        api_key=api_key,
        temperature=0.0,
    )


# ============================================================
# Create Orchestrator Agent
# ============================================================

ORCHESTRATOR_DRAFT_PROMPT = """
You are the Contract Drafting Orchestrator.

Your goal is to coordinate a team of specialized agents to draft a high-quality, customized contract based on a user-provided PDF template (loaded via database chunks) and drafting instructions.

You must decide dynamically:
1. What sections/clauses the template possesses by delegating to the `structure-understanding-agent`.
2. What jurisdictional regulations, governing laws, or clauses require external research. You MUST list all distinct legal domains from the template and instructions, and ask the `contract-research-agent` to run comprehensive, multi-query searches and page fetches focusing strictly on **Indian Law** and portals like **Indian Kanoon** and **India Code**.
3. How to write and format the contract by delegating to the `contract-writer-agent`.
4. Whether the drafted contract is accurate, complete, and free of placeholder fields by delegating to the `contract-reviewer-agent`.
5. When the contract drafting process is complete and approved.

STRICT DELEGATION REQUIREMENTS:
1. For `structure-understanding-agent`: You MUST explicitly pass the `document_id` UUID (36-character string) in the task description. Order the agent to fetch and read ALL database chunks sequentially from sequence 1 to the total count without skipping any. Example: "Analyze the structure of the document with ID: 2f11c7cb-22d4-475d-b8c1-9cd933c6e9ba, fetching all chunks sequentially from 1 to total."
2. For `contract-research-agent`: You MUST request a deep-dive investigation strictly targeting **Indian Law** (and local state laws if applicable). Order the agent to formulate queries for portals like **Indian Kanoon** (`indiankanoon.org`) and **India Code** (`indiacode.nic.in`) and fetch page content. Do not search for non-Indian laws.
3. For `contract-writer-agent`: You MUST copy and paste:
   - The structural map of the template provided by the `structure-understanding-agent`.
   - The detailed research findings provided by the `contract-research-agent`.
   - The user's original drafting instructions.
   Instruct the writer to match the template structure and section order exactly.
   Example: "Draft the contract using this template structure: [Paste structure] and these research notes: [Paste research notes] and these user instructions: [Paste user instructions]".
4. For `contract-reviewer-agent`: You MUST copy and paste:
   - The complete drafted contract Markdown text produced by the `contract-writer-agent`.
   - The user's original drafting instructions.
   Instruct the reviewer to perform a section-by-section comparison against the template and verify that all provisions align strictly with Indian Law.
   Example: "Review this draft contract: [Paste drafted contract Markdown] against these user instructions: [Paste user instructions]".

COORDINATION AND DELEGATION GUIDELINES:
- Review findings carefully. If the reviewer flags gaps, simplified clauses, or empty placeholders, ask the writer to revise the contract. Do not declare complete until the reviewer gives an "APPROVED" verdict.
"""

def create_contract_drafting_orchestrator() -> Any:
    """
    Create the top-level contract-drafting orchestrator.
    """
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: (
                    "contract-drafting",
                    "v1",
                ),
            ),
            "/skills/": StoreBackend(
                namespace=lambda rt: (
                    "contract-drafting",
                    "v1",
                ),
            ),
        },
    )

    DB_GUIDELINES = """
STRICT DATABASE CHUNK RETRIEVAL GUIDELINES:
If you need to query contract chunks from the database:
1. Identify the actual `document_id` UUID (a 36-character string like '7750cfec-...') from your task description instructions. Never use placeholder strings.
2. First, call `get_total_chunks_count` with that correct document ID to get the total number of chunks.
3. ALWAYS retrieve chunks in batches by calling `get_optimized_chunks_from_db`. Set the `limit` parameter to a maximum of 15 to 20 chunks per call.
4. You MUST read ALL chunks in the document sequentially (incrementing `start_sequence` by your batch limit each time, e.g. 1, 16, 31, etc.) until you have retrieved all chunks up to the total count.
5. Stop immediately when `start_sequence` exceeds the total chunk count.
"""

    specialist_agents = [
        {
            **STRUCTURE_UNDERSTANDING_AGENT,
            "model": get_specialist_model(),
            "inherit_tools": True,
            "system_prompt": STRUCTURE_UNDERSTANDING_AGENT.get("system_prompt", "") + DB_GUIDELINES
        },
        {
            **CONTRACT_RESEARCH_AGENT,
            "model": get_specialist_model(),
            "inherit_tools": True,
            "system_prompt": CONTRACT_RESEARCH_AGENT.get("system_prompt", "")
        },
        {
            **CONTRACT_WRITER_AGENT,
            "model": get_specialist_model(),
            "inherit_tools": True,
            "system_prompt": CONTRACT_WRITER_AGENT.get("system_prompt", "")
        },
        {
            **DRAFTING_REVIEW_AGENT,
            "model": get_orchestrator_model(),
            "inherit_tools": True,
            "system_prompt": DRAFTING_REVIEW_AGENT.get("system_prompt", "")
        },
    ]

    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()

    return create_deep_agent(
        model=get_orchestrator_model(),
        system_prompt=ORCHESTRATOR_DRAFT_PROMPT,
        subagents=specialist_agents,
        backend=backend,
        store=store,
        skills=[
            "backend/skills/contract-drafting-orchestration",
            "backend/skills/structure-understanding",
            "backend/skills/contract-research",
            "backend/skills/contract-writing",
            "backend/skills/contract-drafting-review"
        ],
        tools=[
            get_optimized_chunks_from_db,
            get_total_chunks_count,
            web_search,
            fetch_web_page
        ],
        middleware=[
            CodeInterpreterMiddleware()
        ],
        response_format=ContractDraftingResult,
    )
