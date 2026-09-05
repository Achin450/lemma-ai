"""
Novelty Advisor API Router

Endpoints:
- POST /api/v1/novelty/analyze              — Analyze paper novelty, 5-D radar vector, Reviewer 2 attacks, and venue fit
- POST /api/v1/novelty/rebuttal             — Generate interactive rebuttal and manuscript patch for a critique
- POST /api/v1/novelty/polish-contributions — Re-polish contribution bullet points for different target tones
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse

from app.schemas.novelty import (
    NoveltyAnalyzeRequest, NoveltyReportResponse,
    RebuttalRequest, RebuttalResponse,
    PolishRequest, PolishResponse
)
from app.services.novelty_advisor import NoveltyAdvisorService
from app.services.extractor import DocumentExtractorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/novelty", tags=["Research Novelty Advisor"])


@router.post(
    "/analyze",
    response_model=NoveltyReportResponse,
    summary="Assess paper novelty and simulate peer-review defensibility",
    description=(
        "Performs full 5-dimensional novelty evaluation (Methodology, Problem, Theory, Empirical, Cross-Domain), "
        "detects closest prior art from arXiv/Semantic Scholar, simulates Reviewer 2 adversarial attacks, "
        "predicts conference acceptance probability, and generates publication-grade IEEE/ACM contribution statements."
    )
)
async def analyze_novelty(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    target_venue_tier: Optional[str] = Form("Tier 1 & Tier 2"),
):
    """
    Accepts either raw text or uploaded document (PDF, DOCX, TXT) and returns complete novelty audit.
    """
    extracted_text = ""
    extracted_title = title or ""

    if file and file.filename:
        # Validate extension
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ["pdf", "docx", "txt"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: .{ext}. Allowed: .pdf, .docx, .txt"
            )
        try:
            content = await file.read()
            extracted_text = DocumentExtractorService.extract_text(filename=file.filename, content=content)
            if not extracted_title:
                extracted_title = file.filename.rsplit(".", 1)[0].replace("_", " ").title()
        except Exception as e:
            logger.error(f"Error extracting document in novelty analyze: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract text from {file.filename}: {str(e)}"
            )

    # If text was provided directly or alongside
    if text and text.strip():
        extracted_text = (extracted_text + "\n\n" + text.strip()).strip()

    if not extracted_text or len(extracted_text.strip()) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide an abstract, research proposal, or upload a document with at least 30 characters."
        )

    # Cloud memory protection: Focus on Abstract, Intro & Methodology (first 20,000 characters)
    # This prevents spaCy parser memory explosion on large 20-50 page uploaded PDFs
    if len(extracted_text) > 20000:
        extracted_text = extracted_text[:20000]

    try:
        report = await NoveltyAdvisorService.analyze_novelty(
            text=extracted_text,
            title=extracted_title,
            domain=domain,
            target_venue_tier=target_venue_tier
        )
        import gc
        gc.collect()
        return report
    except Exception as e:
        logger.exception(f"Novelty analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Novelty analysis pipeline encountered an error: {str(e)}"
        )


@router.post(
    "/analyze-json",
    response_model=NoveltyReportResponse,
    summary="Analyze novelty via direct JSON payload"
)
async def analyze_novelty_json(payload: NoveltyAnalyzeRequest):
    """Direct JSON endpoint for programmatic client applications."""
    if not payload.text or len(payload.text.strip()) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide text with at least 30 characters for analysis."
        )
    return await NoveltyAdvisorService.analyze_novelty(
        text=payload.text,
        title=payload.title,
        domain=payload.domain,
        target_venue_tier=payload.target_venue_tier
    )


@router.post(
    "/rebuttal",
    response_model=RebuttalResponse,
    summary="Generate tactical reviewer rebuttal and manuscript patch"
)
async def generate_rebuttal(payload: RebuttalRequest):
    """Generates an immediate formal rebuttal statement and manuscript patch text."""
    return await NoveltyAdvisorService.generate_deep_rebuttal(
        attack_title=payload.attack_title,
        critique_text=payload.critique_text,
        user_context=payload.user_context
    )


@router.post(
    "/polish-contributions",
    response_model=PolishResponse,
    summary="Polish contribution bullet points"
)
async def polish_contributions(payload: PolishRequest):
    """Generates contribution bullet points for Section I of paper."""
    domain = payload.domain or "Artificial Intelligence & Machine Learning"
    contributions = NoveltyAdvisorService._generate_polished_contributions(payload.text, domain)
    
    # Match tone or default to first
    matched = next((c for c in contributions if c.tone.lower().startswith(payload.tone.lower()[:5])), contributions[0])
    return PolishResponse(
        tone=matched.tone,
        bullet_points=matched.bullet_points
    )
