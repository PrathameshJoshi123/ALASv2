"""
Pydantic schemas for the Chunk Context Agent output.
"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field


class ContextDetail(BaseModel):
    """Context detail schema."""
    
    section_type: str = Field(
        ...,
        description="The primary section type of the chunk. Use controlled taxonomy: PREAMBLE, DEFINITIONS, PARTIES, PROPERTY_DESCRIPTION, CONSIDERATION, PAYMENT_TERMS, REPRESENTATIONS, WARRANTIES, CONDITIONS, DEFAULT, TERMINATION, DISPUTE_RESOLUTION, GOVERNING_LAW, SCHEDULE, COURT_ANALYSIS, PLAINTIFF_SUBMISSIONS, FACTS, JUDGMENT_ORDER."
    )
    speaker: str = Field(
        ...,
        description="The speaker or party whose position is being presented. Use controlled values: CONTRACTUAL_PARTIES, COURT, PLAINTIFF, DEFENDANT, PROMOTER, ALLOTTEE, etc. (do not use AGREEMENT_DRAFTERS)."
    )
    procedural_stage: Optional[str] = Field(
        None,
        description="The procedural stage of the case/document (e.g. FINAL_JUDGMENT, INTERIM_APPLICATION)."
    )
    document_role: Optional[str] = Field(
        None,
        description="The document role or type. Use controlled values: SALE_PURCHASE_AGREEMENT, JUDGMENT, AGREEMENT, PLEADINGS, etc."
    )
    section_title: Optional[str] = Field(
        None,
        description="The title of the section this chunk belongs to, if available."
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Topics discussed in this chunk (e.g. contract_termination, breach_of_contract)."
    )
    legal_domains: List[str] = Field(
        default_factory=list,
        description="Legal domains applicable to the chunk (e.g. contract_law, criminal_law)."
    )


class Dependency(BaseModel):
    """Dependency schema for unresolved reference resolution."""
    
    reference: str = Field(
        ...,
        description="The exact text of the incomplete/anaphoric reference (e.g. 'the said agreement', 'section-14 of the Act')."
    )
    reference_type: str = Field(
        ...,
        description="The type of reference (e.g. STATUTORY_PROVISION, CONTRACTUAL_PROVISION, CASE_CITATION)."
    )
    local_resolution: Optional[str] = Field(
        None,
        description="The resolved referent context if inferred directly/locally from context, otherwise null/None. No guessing."
    )
    resolution_status: str = Field(
        ...,
        description="The status of resolution (e.g. RESOLVED, UNRESOLVED)."
    )
    resolution_basis: Optional[str] = Field(
        None,
        description="The evidence or reasoning for the local resolution, or null/None if unresolved."
    )
    resolution_confidence: float = Field(
        ...,
        description="The confidence rating for this specific resolution/status (0.0 to 1.0)."
    )


class ContinuityDetail(BaseModel):
    """Continuity and flow schema."""
    
    is_continuation: bool = Field(
        ...,
        description="Whether this chunk continues a logical unit (section/clause) that started before this chunk."
    )
    continues_from_previous_chunk: bool = Field(
        ...,
        description="Whether the text continues immediately and syntactically from the previous chunk."
    )
    continues_into_next_chunk: bool = Field(
        ...,
        description="Whether the text continues immediately and syntactically into the next chunk."
    )
    dependencies: List[Dependency] = Field(
        default_factory=list,
        description="List of context dependencies or unresolved references."
    )


class PerspectiveDetail(BaseModel):
    """Perspective and stance schema."""
    
    primary_speaker: str = Field(
        ...,
        description="The primary speaker/entity whose voice is active in this chunk."
    )
    positions_present: List[str] = Field(
        default_factory=list,
        description="All entities/parties whose perspectives, arguments, or positions are mentioned."
    )
    actor_roles: List[str] = Field(
        default_factory=list,
        description="Specific actor roles active or mentioned in this chunk (e.g., PROMOTER, ALLOTTEE, BUYER, SELLER)."
    )
    contains_allegations: bool = Field(
        ...,
        description="Whether the chunk contains allegations/assertions by a party."
    )
    contains_denials: bool = Field(
        ...,
        description="Whether the chunk contains denials or defences by a party."
    )
    contains_admissions: bool = Field(
        ...,
        description="Whether the chunk contains admissions of facts by either party."
    )
    contains_court_findings: bool = Field(
        ...,
        description="Whether the chunk contains actual findings or rulings by the court."
    )


class SemanticContent(BaseModel):
    """Granular semantic content classifications."""
    
    contains_facts: bool = Field(
        ...,
        description="Whether the chunk contains factual statements or history assertions."
    )
    contains_definitions: bool = Field(
        ...,
        description="Whether the chunk contains definitions of terms."
    )
    contains_representations: bool = Field(
        ...,
        description="Whether the chunk contains representations (statements of fact made to induce entry into contract)."
    )
    contains_warranties: bool = Field(
        ...,
        description="Whether the chunk contains warranties (contractual promises)."
    )
    contains_obligations: bool = Field(
        ...,
        description="Whether the chunk contains obligations (things a party must do)."
    )
    contains_rights: bool = Field(
        ...,
        description="Whether the chunk contains rights or entitlements."
    )
    contains_conditions: bool = Field(
        ...,
        description="Whether the chunk contains conditions or conditional clauses."
    )
    contains_prohibitions: bool = Field(
        ...,
        description="Whether the chunk contains prohibitions (things a party must not do)."
    )
    contains_legal_conclusions: bool = Field(
        ...,
        description="Whether the chunk contains final legal determinations or conclusions."
    )
    contains_legal_reasoning: bool = Field(
        ...,
        description="Whether the chunk contains logical reasoning or legal justification."
    )


class SignificanceDetail(BaseModel):
    """Legal significance markers."""
    
    contains_legal_reasoning: bool = Field(
        ...,
        description="Whether the chunk contains logical reasoning or legal justification."
    )
    semantic_content: SemanticContent = Field(
        ...,
        description="Granular semantic classifications replacing simple factual assertion flags."
    )
    contains_legal_conclusions: bool = Field(
        ...,
        description="Whether the chunk contains final legal determinations or conclusions."
    )
    contains_citations: bool = Field(
        ...,
        description="Whether the chunk contains citations to other cases or legal statutes."
    )
    contains_orders: bool = Field(
        ...,
        description="Whether the chunk contains specific court orders, directions, or decrees."
    )


class ReferenceDetail(BaseModel):
    """Reference schema for key legal/contractual terms or provisions."""
    
    text: str = Field(
        ...,
        description="The exact text representing the reference (e.g. 'Clause 14', 'Section 73')."
    )
    type: str = Field(
        ...,
        description="The type of reference (e.g. CONTRACTUAL_PROVISION, STATUTORY_PROVISION, CASE_CITATION)."
    )
    status: str = Field(
        ...,
        description="Resolution status (e.g. UNRESOLVED, RESOLVED)."
    )


class ChunkContextResponse(BaseModel):
    """Canonical schema for the Chunk Context Agent's output."""
    
    chunk_id: str = Field(
        ...,
        description="The unique identifier of the chunk being analyzed."
    )
    context: ContextDetail = Field(
        ...,
        description="Contextual metadata capturing section type, speaker, role, topics, and domains."
    )
    continuity: ContinuityDetail = Field(
        ...,
        description="Syntax and semantic continuity indicators along with reference dependencies."
    )
    perspective: PerspectiveDetail = Field(
        ...,
        description="Voice, speaker perspectives, and assertion categories present in the chunk."
    )
    legal_significance: SignificanceDetail = Field(
        ...,
        description="Presence of legal reasoning, findings, conclusions, citations, and orders."
    )
    important_references: List[ReferenceDetail] = Field(
        default_factory=list,
        description="List of key statutory, contractual, or case references identified in the text."
    )
    context_warnings: List[str] = Field(
        default_factory=list,
        description="Specific warnings to downstream extractors to prevent errors like treating allegations as court findings."
    )
    confidence: float = Field(
        ...,
        description="The model's confidence rating of its classification, between 0.0 and 1.0."
    )


class ChunkContextListResponse(BaseModel):
    """List response schema for chunk contexts."""
    results: List[ChunkContextResponse] = Field(default_factory=list)
