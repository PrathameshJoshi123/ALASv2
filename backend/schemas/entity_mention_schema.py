"""
Pydantic schemas for the Entity & Mention Extraction Agent output.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class ProvenanceDetail(BaseModel):
    """Provenance detail schema representing exact position of mention in chunk."""
    
    chunk_id: str = Field(
        ...,
        description="The unique identifier of the chunk where the mention was found."
    )
    start_char: int = Field(
        ...,
        description="The start character offset of the mention in the chunk (0-indexed)."
    )
    end_char: int = Field(
        ...,
        description="The end character offset of the mention in the chunk (exclusive)."
    )
    quote: str = Field(
        ...,
        description="The exact text quote representing the mention."
    )


class MentionDetail(BaseModel):
    """Detail schema for a single extracted entity mention."""
    
    mention_id: str = Field(
        ...,
        description="Local chunk-specific mention identifier (e.g. m_001, m_002)."
    )
    surface_text: str = Field(
        ...,
        description="The exact string as it appears in the text."
    )
    entity_type: str = Field(
        ...,
        description="Broad family category. Allowed: PERSON, COMPANY, ORGANIZATION, GOVERNMENT_BODY, COURT, TRIBUNAL, AUTHORITY, JUDGE, LAWYER, WITNESS, EXPERT, CASE, STATUTE, REGULATION, RULE_SET, LEGAL_PROVISION, CONTRACT, AGREEMENT, CONTRACT_CLAUSE, SCHEDULE, ORDER, JUDGMENT, APPLICATION, NOTICE, PARTY, PARTY_ROLE, PROMOTER, ALLOTTEE, PLAINTIFF, DEFENDANT, PETITIONER, RESPONDENT, APPELLANT, APPLICANT, PROPERTY, PLOT, LAND, BUILDING, ASSET, ACCOUNT, SHARE, SECURITY, GOODS, SERVICE, ADDRESS, LOCATION, CITY, STATE, COUNTRY, CURRENCY"
    )
    subtype: Optional[str] = Field(
        None,
        description="Specific subtype or role value (e.g., PROMOTER, ALLOTTEE, etc.) if applicable, otherwise null."
    )
    mention_form: str = Field(
        ...,
        description="Grammatical mention form. Allowed: PROPER_NAME, DEFINED_TERM, ROLE_REFERENCE, PRONOUN, NOMINAL_REFERENCE, LEGAL_CITATION, DOCUMENT_REFERENCE, DESCRIPTION"
    )
    resolution_status: str = Field(
        "UNRESOLVED",
        description="Default is UNRESOLVED. Allowed: UNRESOLVED, LOCALLY_RESOLVED, RESOLVED, AMBIGUOUS, NOT_APPLICABLE"
    )
    canonical_name_hint: Optional[str] = Field(
        None,
        description="Optional hint for canonical name if explicit (e.g. standard name of a company or full statute title), otherwise null."
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional key-value pairs representing extracted properties or attributes of the mention (e.g. role: PROMOTER)."
    )
    provenance: ProvenanceDetail = Field(
        ...,
        description="Provenance coordinates in the current chunk."
    )
    confidence: float = Field(
        ...,
        description="Confidence score between 0.0 and 1.0."
    )


class EntityMentionResponse(BaseModel):
    """Canonical output schema for the Entity & Mention Extraction Agent."""
    
    chunk_id: str = Field(
        ...,
        description="The unique identifier of the chunk being analyzed."
    )
    mentions: List[MentionDetail] = Field(
        default_factory=list,
        description="List of all legally meaningful mentions extracted from the chunk."
    )


class EntityMentionListResponse(BaseModel):
    """List response schema for entity mentions."""
    results: List[EntityMentionResponse] = Field(default_factory=list)
