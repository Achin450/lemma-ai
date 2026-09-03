from typing import Optional
from pydantic import BaseModel, Field


class InTextCitation(BaseModel):
    """A single parsed in-text citation."""
    text: str = Field(..., description="Raw citation text, e.g. '(Smith, 2023)'")
    style: str = Field(..., description="Detected citation style: 'apa', 'mla', 'ieee', 'chicago', 'unknown'")
    author: Optional[str] = None
    year: Optional[str] = None
    reference_number: Optional[int] = None   # For IEEE [1] style
    sentence_context: str = Field("", description="The sentence containing this citation.")
    start_char: int = Field(0)
    end_char: int = Field(0)


class BibliographyEntry(BaseModel):
    """A parsed bibliography/references entry."""
    raw_text: str = Field(..., description="Raw bibliography entry text.")
    author: Optional[str] = None
    title: Optional[str] = None
    year: Optional[str] = None
    cited_in_text: bool = Field(False, description="Whether this entry appears in any in-text citation.")


class CitationIssue(BaseModel):
    """A specific citation integrity problem detected."""
    issue_type: str = Field(
        ...,
        description="Type of issue: 'unsupported_citation', 'padded_citation', 'uncited_paraphrase'"
    )
    severity: str = Field(..., description="Severity level: 'high', 'medium', 'low'")
    sentence_text: str = Field("", description="The problematic sentence text.")
    citation_text: Optional[str] = Field(None, description="The citation involved (if applicable).")
    explanation: str = Field(..., description="Plain-language explanation of the issue.")
    start_char: int = Field(0, description="Character offset in the document.")
    end_char: int = Field(0)
    suggested_fix: str = Field("", description="Suggested remediation action.")


class CitationAnalysisResult(BaseModel):
    """Complete citation graph analysis report."""
    total_in_text_citations: int = Field(0)
    total_bibliography_entries: int = Field(0)
    citation_integrity_score: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Overall citation quality (1.0 = fully cited and supported)."
    )
    unsupported_citations: list[CitationIssue] = Field(default_factory=list)
    padded_citations: list[CitationIssue] = Field(default_factory=list)
    uncited_paraphrases: list[CitationIssue] = Field(default_factory=list)
    in_text_citations: list[InTextCitation] = Field(default_factory=list)
    bibliography_entries: list[BibliographyEntry] = Field(default_factory=list)
    summary: str = Field("", description="One-paragraph summary of citation health.")

from pydantic import BaseModel

class CitationGenerateRequest(BaseModel):
    query: str
    
class CitationGenerateResponse(BaseModel):
    apa: str
    mla: str
    chicago: str
    ieee: str
