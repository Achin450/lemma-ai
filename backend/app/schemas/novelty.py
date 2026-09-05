"""
Novelty Advisor Schemas

Defines Pydantic models for:
- 5-Dimensional Novelty Vector (Methodology, Problem, Theoretical, Empirical, Cross-Domain)
- Reviewer 2 Attack Simulation & Preemptive Rebuttal Shield
- Prior Art Delta Matrix (Direct comparison with arXiv / Semantic Scholar papers)
- Conference Venue Fit & Acceptance Probability
- IEEE / ACM Contribution Statement Polisher
- Analysis Requests & Complete Report Responses
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NoveltyDimensionScore(BaseModel):
    """Score and assessment for a single novelty dimension."""
    dimension_id: str
    name: str
    score: int = Field(..., ge=0, le=100, description="Score between 0 and 100")
    grade: str = Field(..., description="Letter or tier grade, e.g., 'A+', 'B', 'Borderline'")
    summary: str
    strengths: List[str] = Field(default_factory=list)
    vulnerabilities: List[str] = Field(default_factory=list)


class ReviewerAttack(BaseModel):
    """Simulated adversarial peer-reviewer critique and defense rebuttal."""
    id: str
    vector_title: str
    severity: str = Field(..., description="'High', 'Medium', or 'Low' risk of rejection")
    reviewer_critique: str = Field(..., description="Exact phrasing Reviewer 2 will use")
    attack_category: str = Field(..., description="'Incremental Scope', 'Missing Baseline', 'Weak Ablation', 'Overclaimed Generalization', etc.")
    defense_rebuttal: str = Field(..., description="Recommended rebuttal and preemptive manuscript edit")
    paper_section_to_patch: str = Field(default="Related Work / Discussion", description="Where to insert the defense")


class PriorArtDelta(BaseModel):
    """Direct comparison between author's work and a specific published paper."""
    paper_title: str
    authors: str
    year: str
    url: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    prior_art_core: str = Field(..., description="What the prior art already established")
    author_unique_delta: str = Field(..., description="What the user's paper uniquely contributes beyond this work")
    risk_level: str = Field(..., description="'Low Overlap', 'Moderate Overlap', 'Critical Differentiation Needed'")


class VenueFit(BaseModel):
    """Conference and journal fit analysis with estimated acceptance probability."""
    target_tier: str = Field(..., description="'Tier 1 (Flagship)', 'Tier 2 (Q1 Transactions)', 'Tier 3 (Workshops)'")
    tier_label: str
    acceptance_probability: int = Field(..., ge=0, le=100, description="Estimated acceptance %")
    recommended_venues: List[str] = Field(default_factory=list, description="e.g. ['IEEE TPAMI', 'NeurIPS', 'ICML']")
    current_readiness: str
    level_up_gates: List[str] = Field(default_factory=list, description="Action items to jump to the next publication tier")


class PolishedContribution(BaseModel):
    """IEEE/ACM-ready contribution bullet points with varying tones."""
    tone: str = Field(..., description="'Pioneering & Authoritative', 'Empirical & Methodical', 'Rigorous & Theoretical'")
    headline: str
    bullet_points: List[str] = Field(default_factory=list)


class NoveltyAnalyzeRequest(BaseModel):
    """Request payload for novelty analysis."""
    text: Optional[str] = Field(None, description="Raw text of abstract, introduction, or full paper")
    title: Optional[str] = Field(None, description="Optional paper title")
    domain: Optional[str] = Field(None, description="Optional research domain, e.g. 'Computer Vision', 'Bioinformatics'")
    target_venue_tier: Optional[str] = Field("Tier 1 & Tier 2", description="Desired venue tier")


class NoveltyReportResponse(BaseModel):
    """Complete Novelty Advisor audit report."""
    analysis_id: str
    document_title: str
    domain: str
    word_count: int
    overall_novelty_score: int = Field(..., ge=0, le=100)
    novelty_tier: str = Field(..., description="e.g. 'Substantial Contribution', 'Breakthrough', 'Incremental Adaptation'")
    tier_badge_color: str
    executive_verdict: str

    # 5-Dimensional Novelty Vector
    dimensions: List[NoveltyDimensionScore]

    # Reviewer 2 Attack Simulation
    reviewer_attacks: List[ReviewerAttack]

    # Prior Art Delta Matrix
    prior_art_deltas: List[PriorArtDelta]

    # Venue Fit & Acceptance Odds
    venue_fit: VenueFit

    # Polished Contributions
    polished_contributions: List[PolishedContribution]

    # Actionable Elevation Roadmap
    elevation_roadmap: List[Dict[str, str]]


class RebuttalRequest(BaseModel):
    """Request for deeper interactive rebuttal generation."""
    attack_title: str
    critique_text: str
    user_context: Optional[str] = None


class RebuttalResponse(BaseModel):
    """Detailed defense and manuscript patch."""
    attack_title: str
    rebuttal_statement: str
    manuscript_patch_text: str
    target_section: str


class PolishRequest(BaseModel):
    """Request for regenerating contribution points."""
    text: str
    tone: str = "Pioneering & Authoritative"
    domain: Optional[str] = None


class PolishResponse(BaseModel):
    """Polished contribution statement response."""
    tone: str
    bullet_points: List[str]
