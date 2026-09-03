from typing import Optional
from pydantic import BaseModel, Field


class SentenceAIScore(BaseModel):
    """Per-sentence AI probability breakdown."""
    text: str = Field(..., description="The sentence text.")
    start_char: int = Field(..., description="Start character offset in the document.")
    end_char: int = Field(..., description="End character offset in the document.")
    perplexity: float = Field(..., description="Perplexity score for this sentence (lower = more likely AI).")
    ai_probability: float = Field(..., ge=0.0, le=1.0, description="Probability this sentence is AI-generated (0=human, 1=AI).")


class AIDetectionResult(BaseModel):
    """Complete AI-generated text detection report for a document."""
    ai_score: float = Field(..., ge=0.0, le=1.0, description="Overall AI probability (0=human, 1=AI).")
    confidence: str = Field(..., description="Classification: 'Likely Human', 'Possibly AI-Assisted', or 'Likely AI-Generated'.")
    perplexity_score: float = Field(..., description="Mean perplexity across the document (lower = more uniform/AI-like).")
    burstiness_score: float = Field(..., description="Burstiness score (lower = less variation = more AI-like).")
    fingerprint_matches: list[str] = Field(default_factory=list, description="Detected AI output pattern signatures.")
    sentence_level_scores: list[SentenceAIScore] = Field(default_factory=list, description="Per-sentence AI scores.")
    flagged_sentence_count: int = Field(0, description="Number of sentences with ai_probability >= 0.65.")
    total_sentence_count: int = Field(0, description="Total number of sentences analyzed.")
