from typing import Optional
from pydantic import BaseModel, Field


class IntegrityCoachRequest(BaseModel):
    """Request body for the Integrity Coach endpoint."""
    text: str = Field(..., min_length=5, description="The flagged sentence or paragraph to get guidance on.")
    matched_source_title: Optional[str] = Field(None, description="Title of the matched reference source.")
    matched_source_author: Optional[str] = Field(None, description="Author of the matched reference source.")
    matched_source_url: Optional[str] = Field(None, description="URL or DOI of the matched source, if available.")
    match_type: str = Field("semantic", description="Type of plagiarism match: lexical, semantic, or hybrid.")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity score (0.0 - 1.0).")


class CitationFormats(BaseModel):
    """Auto-generated citation in standard academic formats."""
    apa: Optional[str] = None
    mla: Optional[str] = None
    chicago: Optional[str] = None


class IntegrityCoachResponse(BaseModel):
    """Response from the Integrity Coach — guidance instead of direct rewriting."""
    guidance_prompt: str = Field(..., description="Pedagogical guidance prompt shown to the student.")
    issue_explanation: str = Field(..., description="Plain-language explanation of why this was flagged.")
    suggested_citation: Optional[str] = Field(None, description="Suggested in-text citation string.")
    citation_formats: CitationFormats = Field(default_factory=CitationFormats)
    example_rewrite: Optional[str] = Field(None, description="Optional example of how to properly express the idea.")
    action_steps: list[str] = Field(default_factory=list, description="Concrete steps the student should take.")
