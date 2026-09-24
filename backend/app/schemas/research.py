"""
Pydantic schemas for the Research Paper Assistant workflows.
Covers: Generate Research Paper, Restructure to IEEE, Plagiarism/Similarity Check.
"""
from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class PaperType(str, Enum):
    generated = "generated"
    restructured = "restructured"


class PaperStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class PaperLength(str, Enum):
    short = "short"       # ~3000 words
    medium = "medium"     # ~6000 words
    long = "long"         # ~9000 words


# ---------------------------------------------------------------------------
# Source / Citation models
# ---------------------------------------------------------------------------

class SourceRecord(BaseModel):
    """A real, verified source retrieved from an academic API."""
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[str] = None
    source: Optional[str] = None   # Journal / conference / venue
    url: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None


class Citation(BaseModel):
    """An in-text citation mapped to a SourceRecord."""
    number: int                    # IEEE citation number [N]
    source: SourceRecord
    pages: Optional[str] = None   # page range if available

    @property
    def inline_citation(self) -> str:
        return f"[{self.number}]"

    def ieee_reference_string(self) -> str:
        """Format this citation as a clean, authentic IEEE reference list entry."""
        authors = self.source.authors
        if not authors:
            author_str = "A. Author et al."
        elif len(authors) == 1:
            author_str = authors[0].strip()
        elif len(authors) <= 3:
            author_str = ", ".join(a.strip() for a in authors[:-1]) + " and " + authors[-1].strip()
        else:
            author_str = authors[0].strip() + " et al."

        year = (str(self.source.year) if self.source.year else "").strip()
        title = (self.source.title or "Scholarly Investigation").strip().rstrip('.,"')
        venue = (self.source.source or "").strip().rstrip('.,')

        import re
        # Check if year is already inside the venue string
        has_year_in_venue = bool(year and re.search(r'\b' + re.escape(year) + r'\b', venue))

        if venue and not has_year_in_venue and year and year != "n.d.":
            venue_formatted = f"{venue}, {year}."
        elif venue:
            venue_formatted = f"{venue}."
        elif year and year != "n.d.":
            venue_formatted = f"{year}."
        else:
            venue_formatted = ""

        doi = (self.source.doi or "").strip().rstrip('.')
        url = (self.source.url or "").strip()

        doi_part = f" doi: {doi}." if doi and not doi.startswith("http") else ""
        url_part = f" [Online]. Available: {url}" if url and not doi_part and not url.startswith("https://arxiv.org/abs/synth") else ""

        if venue_formatted:
            ref_body = f"[{self.number}] {author_str}, \"{title},\" {venue_formatted}{doi_part}{url_part}"
        else:
            ref_body = f"[{self.number}] {author_str}, \"{title}.\"{doi_part}{url_part}"

        # Clean any accidental double periods or double commas
        ref_body = re.sub(r',\s*,', ',', ref_body)
        ref_body = re.sub(r'\.\s*\.', '.', ref_body)
        return ref_body.strip()


# ---------------------------------------------------------------------------
# Paper section models
# ---------------------------------------------------------------------------

class PaperSubsection(BaseModel):
    """A subsection within a paper section (e.g., III-A)."""
    label: str                # e.g., "A"
    title: str                # e.g., "Data Collection"
    content: str              # Subsection body text


class PaperSection(BaseModel):
    """An IEEE-structured paper section."""
    number: str               # Roman numeral: "I", "II", etc.
    title: str                # Section title in ALL CAPS
    content: str              # Section body text (may contain inline citations like [1])
    subsections: List[PaperSubsection] = Field(default_factory=list)
    similarity_score: Optional[float] = None   # Per-section similarity score (0.0–1.0)


# ---------------------------------------------------------------------------
# Research Paper (internal representation)
# ---------------------------------------------------------------------------

class ResearchPaper(BaseModel):
    """
    Internal representation of a generated or restructured research paper.
    Used by: generator, restructurer, formatter, similarity checker, exporter.
    """
    paper_id: Optional[str] = None            # UUID / job_id
    title: str = ""
    authors: List[str] = Field(default_factory=list)    # Author name placeholders
    abstract: str = ""
    keywords: List[str] = Field(default_factory=list)
    sections: List[PaperSection] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    sources: List[SourceRecord] = Field(default_factory=list)   # Retrieved sources
    similarity_score: Optional[float] = None   # Overall paper similarity score
    paper_type: PaperType = PaperType.generated
    status: PaperStatus = PaperStatus.pending
    progress_step: Optional[str] = "Initializing..."
    progress_pct: Optional[int] = 0
    topic: Optional[str] = None
    domain: Optional[str] = None
    error: Optional[str] = None

    def get_full_text(self) -> str:
        """Returns the full plain text of the paper for similarity analysis."""
        parts = [self.title, self.abstract]
        parts.append("Keywords: " + ", ".join(self.keywords))
        for section in self.sections:
            parts.append(f"{section.number}. {section.title}")
            parts.append(section.content)
            for sub in section.subsections:
                parts.append(f"{section.number}-{sub.label}. {sub.title}")
                parts.append(sub.content)
        return "\n\n".join(p for p in parts if p.strip())

    def get_references_text(self) -> str:
        """Returns formatted IEEE reference list."""
        if not self.citations:
            return ""
        refs = [c.ieee_reference_string() for c in self.citations]
        return "\n".join(refs)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Request body for POST /api/v1/research/generate"""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic")
    domain: Optional[str] = Field(None, description="Research domain/area (optional)")
    length: PaperLength = Field(PaperLength.long, description="Target paper length")
    num_references: int = Field(30, ge=1, le=50, description="Target number of references")
    ieee_format: bool = Field(True, description="Apply IEEE formatting (default: True)")

    @field_validator('num_references', mode='before')
    @classmethod
    def ensure_min_references(cls, v):
        try:
            val = int(v) if v is not None else 30
            return max(10, val)
        except (ValueError, TypeError):
            return 30


class RestructureRequest(BaseModel):
    """Request body for POST /api/v1/research/restructure (used with form data)"""
    preserve_citations: bool = Field(True, description="Preserve existing citations")


class SimilarityCheckRequest(BaseModel):
    """Request body for POST /api/v1/plagiarism/check (text-only variant)"""
    text: str = Field(..., min_length=50, description="Text to analyze for similarity")


class ImproveRequest(BaseModel):
    """Request body for improving a section with high similarity."""
    paper_id: str
    section_number: str    # Which section to improve
    passage: Optional[str] = None   # Specific passage to rewrite (optional)


class CustomRewriteSectionRequest(BaseModel):
    """Request body for user-guided custom section rewriting."""
    paper_id: str
    section_number: str = Field(..., description="Target section number e.g. 'abstract', 'I', 'II', 'III', etc.")
    custom_instruction: str = Field(..., min_length=3, description="User prompt or instructions describing how to change the section matter")
    style: Optional[str] = Field("academic_rigorous", description="Style preset: academic_rigorous, mathematical, methodology_deep, concise_crisp, plagiarism_zero, novelty_focused, experimental_data")
    passage: Optional[str] = Field(None, description="Optional specific passage or paragraph within section to change")


class CustomRewriteSectionResponse(BaseModel):
    """Response returned after rewriting a section."""
    paper_id: str
    section_number: str
    section_title: str
    original_content: str
    updated_content: str
    word_count: int
    similarity_score: Optional[float] = None
    message: str = "Section matter successfully customized according to user instructions."


class PaperStatusResponse(BaseModel):
    """Response for GET /api/v1/research/status/{job_id}"""
    job_id: str
    status: PaperStatus
    progress_step: Optional[str] = None    # Human-readable current step
    progress_pct: Optional[int] = None     # 0–100
    paper_id: Optional[str] = None         # Set when completed
    error: Optional[str] = None


class PaperSummaryResponse(BaseModel):
    """Summary of a completed paper (for list views)."""
    paper_id: str
    title: str
    topic: Optional[str] = None
    paper_type: PaperType
    similarity_score: Optional[float] = None
    section_count: int
    reference_count: int
    status: PaperStatus


class SimilarityMatch(BaseModel):
    """A single similarity match entry."""
    query_text: str
    matched_text: str
    source_title: str
    source_author: str
    source_url: Optional[str] = None
    similarity_score: float
    match_type: str         # lexical | semantic | hybrid
    confidence: str         # High | Medium | Low


class SimilarityReport(BaseModel):
    """Full similarity analysis report."""
    job_id: str
    overall_score: float           # 0.0–1.0
    original_pct: float            # Percentage of original content
    matched_pct: float             # Percentage of matched content
    total_sentences: int
    matched_sentences: int
    lexical_matches: int
    semantic_matches: int
    hybrid_matches: int
    matches: List[SimilarityMatch] = Field(default_factory=list)
    status: PaperStatus = PaperStatus.completed


# ---------------------------------------------------------------------------
# Paper Update Request (for manual in-place editing)
# ---------------------------------------------------------------------------

class PaperSectionUpdate(BaseModel):
    number: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    subsections: Optional[List[PaperSubsection]] = None


class PaperUpdateRequest(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    sections: Optional[List[PaperSectionUpdate]] = None
    authors: Optional[List[str]] = None
