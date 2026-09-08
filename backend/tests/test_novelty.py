"""
Unit and Integration Tests for Novelty Advisor

Tests:
- 5-Dimensional Novelty Vector computation
- Heuristic claim extraction and domain detection
- Reviewer 2 attack generation and tactical rebuttals
- Venue fit categorization and acceptance probability
- API endpoints: /api/v1/novelty/analyze, /rebuttal, /polish-contributions
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.novelty_advisor import NoveltyAdvisorService
from app.schemas.novelty import NoveltyReportResponse, RebuttalResponse, PolishResponse

client = TestClient(app)

SAMPLE_RESEARCH_TEXT = """
In this paper, we propose Linear-State Attention (LSA), a novel architectural mechanism for deep representation learning.
Unlike classical softmax self-attention which suffers from quadratic complexity O(N^2), our formulation projects queries
and keys into an orthogonal reproducing kernel Hilbert space, guaranteeing strictly linear computational complexity O(N)
and reduced memory footprint. We evaluate LSA against established SOTA baselines including Transformer and FlashAttention
across four standard language modeling benchmarks. Our empirical results demonstrate a 2.8x speedup and statistically
significant improvements (p < 0.01) in perplexity while maintaining parameter efficiency. Furthermore, we provide formal
proof of the convergence bounds in Theorem 1 and conduct extensive component-wise ablations.
"""

def test_novelty_domain_detection():
    domain = NoveltyAdvisorService._detect_domain(SAMPLE_RESEARCH_TEXT)
    assert domain in ["Natural Language Processing & Speech", "Artificial Intelligence & Machine Learning"]

def test_novelty_claim_extraction():
    claims = NoveltyAdvisorService._extract_key_claims(SAMPLE_RESEARCH_TEXT)
    assert claims["has_theory"] is True  # Contains "Theorem 1", "convergence", "bounds", "O(N"
    assert len(claims["contributions"]) >= 1
    assert len(claims["baselines_mentioned"]) >= 1

def test_novelty_advisor_service_analysis():
    import asyncio
    report = asyncio.run(NoveltyAdvisorService.analyze_novelty(
        text=SAMPLE_RESEARCH_TEXT,
        title="Linear-State Attention for Scalable Deep Learning",
        domain="Artificial Intelligence & Machine Learning"
    ))
    assert isinstance(report, NoveltyReportResponse)
    assert 0 <= report.overall_novelty_score <= 100
    assert len(report.dimensions) == 5
    assert len(report.reviewer_attacks) >= 2
    assert len(report.prior_art_deltas) >= 1
    assert report.venue_fit.acceptance_probability > 0
    assert len(report.polished_contributions) == 3

def test_api_novelty_analyze_text():
    response = client.post(
        "/api/v1/novelty/analyze",
        data={
            "text": SAMPLE_RESEARCH_TEXT,
            "title": "Linear-State Attention",
            "domain": "Artificial Intelligence & Machine Learning"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "overall_novelty_score" in data
    assert "dimensions" in data
    assert len(data["dimensions"]) == 5
    assert "reviewer_attacks" in data
    assert "venue_fit" in data

def test_api_novelty_analyze_short_text_error():
    response = client.post(
        "/api/v1/novelty/analyze",
        data={"text": "Too short"}
    )
    assert response.status_code == 400

def test_api_novelty_analyze_file_upload():
    import io
    file_bytes = io.BytesIO(SAMPLE_RESEARCH_TEXT.encode("utf-8"))
    response = client.post(
        "/api/v1/novelty/analyze",
        files={"file": ("sample_paper.txt", file_bytes, "text/plain")},
        data={"domain": "Artificial Intelligence & Machine Learning"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "overall_novelty_score" in data
    assert len(data["dimensions"]) == 5

def test_api_novelty_rebuttal():
    response = client.post(
        "/api/v1/novelty/rebuttal",
        json={
            "attack_title": "Incremental Adaptation Critique",
            "critique_text": "The methodology appears to be an incremental composition of standard techniques."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "rebuttal_statement" in data
    assert "manuscript_patch_text" in data

def test_api_novelty_polish_contributions():
    response = client.post(
        "/api/v1/novelty/polish-contributions",
        json={
            "text": SAMPLE_RESEARCH_TEXT,
            "tone": "Pioneering & Authoritative"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "bullet_points" in data
    assert len(data["bullet_points"]) >= 2
