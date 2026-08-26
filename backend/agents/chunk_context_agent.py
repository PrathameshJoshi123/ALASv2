"""
Chunk Context Agent implementation.
Uses deepagents to run a structured LLM extraction for legal document chunks.
"""

import json
import os
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI
from sqlalchemy.orm import Session

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from backend.schemas.chunk_context_schema import ChunkContextResponse
from backend.models.chunk_context import ChunkContext
from dotenv import load_dotenv

load_dotenv()


def count_words(text: str) -> int:
    """Count the number of words in a text string."""
    if not text:
        return 0
    return len(text.split())


# Chunk merging configuration
MIN_CHUNK_WORDS = 200  # Minimum words threshold for chunk merging
MAX_MERGED_WORDS = 200  # Maximum words for a merged chunk


def merge_small_chunks(chunks: list[Any]) -> list[dict[str, Any]]:
    """
    Merge small chunks (< MIN_CHUNK_WORDS) with their neighbors to reduce API calls.
    
    Strategy:
    - If a chunk has < MIN_CHUNK_WORDS, try to merge it with the next chunk
    - Only merge if the combined result <= MAX_MERGED_WORDS
    - Each merged group maintains a list of original chunk_ids
    
    Args:
        chunks: List of Chunk objects ordered by sequence_number
        
    Returns:
        List of dictionaries with 'chunk_ids' (list of merged chunk IDs) and 'merged_text'
    """
    if not chunks:
        return []
    
    merged_groups = []
    current_group_ids = []
    current_group_text = ""
    current_group_original_texts = {}
    
    for chunk in chunks:
        chunk_word_count = count_words(chunk.content)
        
        # If current group is empty, start a new group
        if not current_group_ids:
            current_group_ids = [chunk.chunk_id]
            current_group_text = chunk.content
            current_group_original_texts[chunk.chunk_id] = chunk.content
        else:
            # Check if current chunk is small and can be merged
            current_group_word_count = count_words(current_group_text)
            combined_word_count = current_group_word_count + chunk_word_count
            
            if chunk_word_count < MIN_CHUNK_WORDS and combined_word_count <= MAX_MERGED_WORDS:
                # Merge with current group
                current_group_ids.append(chunk.chunk_id)
                current_group_text += "\n\n" + chunk.content
                current_group_original_texts[chunk.chunk_id] = chunk.content
            else:
                # Finalize current group and start a new one
                merged_groups.append({
                    "chunk_ids": current_group_ids,
                    "merged_text": current_group_text,
                    "original_texts": current_group_original_texts
                })
                current_group_ids = [chunk.chunk_id]
                current_group_text = chunk.content
                current_group_original_texts = {chunk.chunk_id: chunk.content}
    
    # Add the last group
    if current_group_ids:
        merged_groups.append({
            "chunk_ids": current_group_ids,
            "merged_text": current_group_text,
            "original_texts": current_group_original_texts
        })
    
    return merged_groups


def split_merged_chunk(merged_text: str, merged_chunk_ids: list[str], original_texts: dict[str, str]) -> list[dict[str, str]]:
    """
    Split a merged chunk back into its original chunks for logical separation.
    
    This function uses the original text lengths to extract the individual chunks
    from the merged text.
    
    Args:
        merged_text: The combined text from merged chunks
        merged_chunk_ids: List of chunk IDs that were merged
        original_texts: Dictionary mapping chunk_id to original text
        
    Returns:
        List of dictionaries with 'chunk_id' and 'text' for each original chunk
    """
    if not merged_chunk_ids or not merged_text:
        return []
    
    result = []
    remaining_text = merged_text
    
    for chunk_id in merged_chunk_ids:
        original_text = original_texts.get(chunk_id, "")
        
        if not remaining_text:
            # Fallback: return original text if we can't extract
            result.append({"chunk_id": chunk_id, "text": original_text})
            continue
        
        # Try to find the original text in the remaining text
        # The merged text uses "\n\n" as separator
        parts = remaining_text.split("\n\n")
        found = False
        
        for part in parts:
            if part.strip() == original_text.strip():
                result.append({"chunk_id": chunk_id, "text": part})
                # Remove this part from remaining text
                remaining_text = remaining_text.replace(part, "", 1)
                # Remove extra separators
                remaining_text = remaining_text.replace("\n\n\n\n", "\n\n")
                remaining_text = remaining_text.strip()
                found = True
                break
        
        if not found:
            # If we can't find exact match, try fuzzy matching by length
            # This handles cases where whitespace might differ
            target_length = len(original_text)
            for i, part in enumerate(parts):
                if abs(len(part) - target_length) < target_length * 0.1:  # Within 10% length
                    result.append({"chunk_id": chunk_id, "text": part})
                    remaining_text = "\n\n".join(parts[i+1:])
                    found = True
                    break
        
        if not found:
            # Last resort: use original text
            result.append({"chunk_id": chunk_id, "text": original_text})
    
    return result


# Versioning and Prompt configuration
PROMPT_VERSION = "1.0.0"
MODEL_NAME = "ministral-3b-2512"

# Chunk merging configuration
MIN_CHUNK_WORDS = 200  # Minimum words threshold for chunk merging
MAX_MERGED_WORDS = 200  # Maximum words for a merged chunk

def get_agent_model() -> ChatMistralAI:
    """
    Initialize the MistralAI Chat model with structured output support.
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    
    # Get the JSON schema from ChunkContextResponse for structured output
    schema = ChunkContextResponse.model_json_schema()
    
    return ChatMistralAI(
        model=MODEL_NAME,
        api_key=api_key,
        temperature=0.0,
    )


# System prompt defining the Chunk Context Agent's behaviors and constraints
SYSTEM_PROMPT = """You are the Chunk Context Agent in a legal-document extraction pipeline.

Your task is to analyze one chunk of a legal document and produce structured contextual memory for downstream extraction agents.

You are NOT the final legal analyst.

You must NOT:
- determine whether an allegation is legally true
- provide legal advice
- infer facts that are not reasonably supported by the supplied text
- resolve entities across the document
- merge references to different entities
- decide the ultimate legal issue
- invent missing information

Your responsibility is to determine:
1. What type of legal section this chunk belongs to.
2. Who is speaking or whose position is being presented.
3. What procedural context applies.
4. What legal/documentary context applies.
5. What topics are discussed.
6. Which entities or concepts are referenced anaphorically or incompletely.
7. Whether the chunk depends on information from preceding or following chunks.
8. What contextual warnings downstream extraction agents should know.
9. Which parts of the chunk contain potentially important legal reasoning, findings, allegations, admissions, denials, or factual assertions.

The current chunk is the primary source of truth.
Use previous and next chunks only to resolve local context such as:
- pronouns
- incomplete sentences
- continuation of a paragraph
- speaker identity
- section boundaries
- references such as "the agreement", "the said property", "the appellant", "the aforesaid order"

Do not copy facts from neighboring chunks unless they are necessary to correctly interpret the current chunk.
Every conclusion must be grounded in the supplied text or metadata.
When uncertain, return UNKNOWN or mark the field as uncertain instead of guessing.

Distinguish carefully between:
- allegation and finding
- submission and fact
- argument and factual assertion
- court observation and final finding
- cited law and applied law
- party position and court position
- evidence description and established fact

Your output must conform exactly to the supplied JSON schema.
Do not output markdown.
Do not output explanations outside the JSON.

IMPORTANT NOTES ABOUT CHUNK MERGING:
- Small chunks (less than 200 words) may have been merged with adjacent chunks to optimize processing
- If 'is_merged' is true, the current chunk text contains content from multiple original chunks
- The 'merged_chunk_ids' field contains the list of original chunk IDs that were merged
- You should analyze the combined text as a single logical unit
- Logical separation of the merged content for downstream processing will be handled separately
- The analysis should treat the merged text as cohesive, but be aware it represents multiple original chunks
"""


def create_context_agent() -> Any:
    """
    Instantiate the deep agent with filesystem backend to load the chunk_context_skill.
    Uses structured output with ProviderStrategy for ChunkContextResponse (native Mistral support).
    """
    from langchain.agents.structured_output import ProviderStrategy
    
    # Locate project root directory to load skills properly
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    backend = FilesystemBackend(root_dir=project_root)
    
    return create_deep_agent(
        model=get_agent_model(),
        system_prompt=SYSTEM_PROMPT,
        skills=["backend/skills/chunk-context-skill"],  # Direct path to the skill
        backend=backend,
        name="chunk-context-agent",
        response_format=ChunkContextResponse,  # Auto-selects ProviderStrategy for Mistral
    )


def save_context_to_db(
    response: ChunkContextResponse,
    document_id: str,
    db_session: Session,
    merged_chunk_ids: Optional[list[str]] = None,
    is_merged: bool = False,
) -> list[ChunkContext]:
    """
    Persist the ChunkContextResponse output into the database.
    If the chunk was merged, save the same context for all merged chunk IDs.
    
    Args:
        response: The ChunkContextResponse to save
        document_id: The document ID
        db_session: SQLAlchemy session
        merged_chunk_ids: List of chunk IDs that were merged (if any)
        is_merged: Whether this analysis represents merged chunks
        
    Returns:
        List of saved ChunkContext records
    """
    # Determine which chunk IDs to save
    chunk_ids_to_save = merged_chunk_ids if merged_chunk_ids else [response.chunk_id]
    
    # Derive boundary chunk logic: if it doesn't continue from previous or doesn't continue into next, it's a boundary.
    is_boundary = (not response.continuity.continues_from_previous_chunk) or (not response.continuity.continues_into_next_chunk)
    
    db_records = []
    
    for chunk_id in chunk_ids_to_save:
        # Check if a record already exists for this chunk/document to update in-place
        existing = db_session.query(ChunkContext).filter(
            ChunkContext.document_id == document_id,
            ChunkContext.chunk_id == chunk_id
        ).first()
        
        data = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "section_type": response.context.section_type,
            "speaker": response.context.speaker,
            "procedural_stage": response.context.procedural_stage,
            "document_role": response.context.document_role,
            "section_title": response.context.section_title,
            "topics": response.context.topics,
            "legal_domains": response.context.legal_domains,
            "context_dependencies": [d.model_dump() for d in response.continuity.dependencies],
            "important_references": [r.model_dump() for r in response.important_references],
            "context_warnings": response.context_warnings,
            "is_continuation": response.continuity.is_continuation,
            "is_boundary_chunk": is_boundary,
            "confidence": response.confidence,
            "model_name": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "raw_output": response.model_dump(),
            "is_merged": is_merged,
            "merged_chunk_ids": merged_chunk_ids or [],
        }
        
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            db_record = existing
        else:
            db_record = ChunkContext(**data)
            db_session.add(db_record)
            
        db_records.append(db_record)
    
    db_session.commit()
    
    # Refresh all records
    for db_record in db_records:
        db_session.refresh(db_record)
    
    return db_records


def strip_markdown_code_fences(content: str) -> str:
    """
    Remove markdown code fences (```json ... ```) from the content.
    """
    import re
    # Remove leading/trailing whitespace
    content = content.strip()
    # Remove ```json and ``` markers
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```\s*$', '', content)
    return content.strip()


def analyze_chunk(
    current_chunk_id: str,
    current_chunk_text: str,
    document_id: str,
    previous_chunk_text: Optional[str] = None,
    next_chunk_text: Optional[str] = None,
    document_metadata: Optional[dict[str, Any]] = None,
    db_session: Optional[Session] = None,
    merged_chunk_ids: Optional[list[str]] = None,
    is_merged: bool = False,
) -> ChunkContextResponse:
    """
    Run the Chunk Context Agent to analyze a chunk and optionally save the results to the database.
    
    Args:
        current_chunk_id: The chunk_id string of the chunk to analyze (or first chunk_id if merged).
        current_chunk_text: The main text content of the chunk (may be merged from multiple chunks).
        document_id: The UUID of the document.
        previous_chunk_text: Text content of the preceding chunk (if any).
        next_chunk_text: Text content of the succeeding chunk (if any).
        document_metadata: Any metadata dictionary for the document.
        db_session: SQLAlchemy session to save results.
        merged_chunk_ids: List of chunk IDs that were merged into this analysis (if any).
        is_merged: Whether this analysis represents merged chunks.
        
    Returns:
        ChunkContextResponse object containing the parsed context analysis.
    """
    # Prepare input query
    input_data = {
        "document_metadata": document_metadata or {},
        "current_chunk": {
            "chunk_id": current_chunk_id,
            "text": current_chunk_text,
            "is_merged": is_merged,
            "merged_chunk_ids": merged_chunk_ids or [],
        },
        "previous_chunk": previous_chunk_text,
        "next_chunk": next_chunk_text,
    }
    
    user_message = f"""Please analyze the following legal document chunk context:

DOCUMENT METADATA:
{json.dumps(input_data["document_metadata"], indent=2)}

PREVIOUS CHUNK:
{input_data["previous_chunk"] or "[None]"}

CURRENT CHUNK (Analyze this, ID: {current_chunk_id}):
{input_data["current_chunk"]["text"]}

{'NOTE: This chunk has been merged from multiple smaller chunks. Original chunk IDs: ' + ', '.join(input_data["current_chunk"]["merged_chunk_ids"]) if is_merged and input_data["current_chunk"]["merged_chunk_ids"] else ''}

NEXT CHUNK:
{input_data["next_chunk"] or "[None]"}
"""

    # Create and run agent with structured output using ProviderStrategy (native Mistral)
    agent = create_context_agent()
    
    # Invoke the agent - structured output is already configured in create_context_agent
    result = agent.invoke({"messages": [HumanMessage(content=user_message)]})
    
    # Extract the structured response from the result
    response = None
    if result.get("structured_response") is not None:
        raw_resp = result["structured_response"]
        if isinstance(raw_resp, ChunkContextResponse):
            response = raw_resp
        elif isinstance(raw_resp, dict):
            response = ChunkContextResponse.model_validate(raw_resp)
        else:
            response = ChunkContextResponse.model_validate(raw_resp)
            
    if response is None and "messages" in result and len(result["messages"]) > 0:
        # Fallback: parse from messages (for older versions or non-structured output)
        last_message = result["messages"][-1]
        if hasattr(last_message, "content") and last_message.content:
            content = last_message.content
            # Try to parse as JSON if it's a string
            if isinstance(content, str):
                # Strip markdown code fences if present
                content = strip_markdown_code_fences(content)
                try:
                    import json as json_lib
                    response_data = json_lib.loads(content)
                    response = ChunkContextResponse.model_validate(response_data)
                except (json_lib.JSONDecodeError, Exception) as e:
                    raise RuntimeError(f"Failed to parse response as JSON: {e}\nContent: {content[:500]}")
            elif isinstance(content, dict):
                response = ChunkContextResponse.model_validate(content)
            else:
                raise RuntimeError("Unexpected response content type")
        else:
            raise RuntimeError("No content in last message")
            
    if response is None and "response" in result:
        # Fallback: try to get from 'response' key
        response_data = result["response"]
        if isinstance(response_data, dict):
            response = ChunkContextResponse.model_validate(response_data)
        elif isinstance(response_data, str):
            response_data = strip_markdown_code_fences(response_data)
            import json as json_lib
            response_data = json_lib.loads(response_data)
            response = ChunkContextResponse.model_validate(response_data)
        else:
            raise RuntimeError(f"Unexpected response format: {type(response_data)}")
            
    if response is None:
        raise RuntimeError(f"No structured response was returned by the Chunk Context Agent. Result: {result}")
    
    # Save to database if session is provided
    if db_session is not None:
        save_context_to_db(
            response, 
            document_id, 
            db_session,
            merged_chunk_ids=merged_chunk_ids,
            is_merged=is_merged
        )
        
    return response
