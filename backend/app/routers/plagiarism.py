"""
Plagiarism/Similarity Check API Router — dedicated endpoints for standalone similarity checking.
These routes are additive and do NOT replace the existing /api/v1/analyze endpoint.

Routes:
    POST /api/v1/plagiarism/check         — Upload or paste text for similarity check
    GET  /api/v1/plagiarism/status/{id}   — Poll check status
    POST /api/v1/plagiarism/improve       — Improve a passage with high similarity
    GET  /api/v1/plagiarism/report/{id}   — Download PDF similarity report
"""
from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response

from app.config import settings
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/plagiarism", tags=["Plagiarism / Similarity"])


# ---------------------------------------------------------------------------
# POST /check — file upload
# ---------------------------------------------------------------------------
@router.post(
    "/check",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Check a document or text for similarity",
    description=(
        "Upload a PDF/DOCX/TXT file OR provide plain text to analyze for textual "
        "and semantic similarity. Uses lexical (BM25), semantic (pgvector), and "
        "hybrid matching. Returns a job_id to poll for results."
    ),
)
async def check_similarity(
    file: UploadFile = File(None),
    text: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    if not file and not text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or paste text for similarity analysis."
        )

    if text and not text.strip():
        raise HTTPException(status_code=400, detail="Provided text is empty.")

    job_id = str(uuid.uuid4())
    file_path = None
    original_filename = None

    # Handle file upload
    if file and file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        temp_filename = f"{job_id}_{file.filename}"
        temp_filepath = settings.UPLOAD_DIR / temp_filename
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        content_size = 0

        try:
            with open(temp_filepath, "wb") as f_out:
                while chunk := await file.read(8192):
                    content_size += len(chunk)
                    if content_size > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit."
                        )
                    f_out.write(chunk)
        except HTTPException:
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise
        except Exception as e:
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

        file_path = str(temp_filepath)
        original_filename = file.filename

    # Queue similarity check
    from app.tasks.research_tasks import similarity_check_task
    similarity_check_task.apply_async(
        args=[job_id],
        kwargs={
            "text": text if not file_path else None,
            "file_path": file_path,
            "original_filename": original_filename,
        },
        task_id=job_id,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Similarity analysis started. Poll /api/v1/plagiarism/status/{job_id} for results.",
        "poll_url": f"/api/v1/plagiarism/status/{job_id}",
    }


# ---------------------------------------------------------------------------
# GET /status/{job_id}
# ---------------------------------------------------------------------------
@router.get(
    "/status/{job_id}",
    summary="Get similarity check status and results",
)
async def get_similarity_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app

    res = AsyncResult(job_id, app=celery_app)

    if res.state == "SUCCESS":
        result = res.result or {}
        # Return the structured similarity report
        return {
            "job_id": job_id,
            "status": "completed",
            "report": result.get("report"),
            "progress_step": "Analysis complete!",
            "progress_pct": 100,
        }
    elif res.state == "FAILURE":
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(res.result) if res.result else "Analysis failed.",
        }
    elif res.state == "PROGRESS":
        meta = res.info or {}
        return {
            "job_id": job_id,
            "status": "processing",
            "progress_step": meta.get("step", "Analyzing..."),
            "progress_pct": meta.get("pct", 0),
        }
    else:
        return {
            "job_id": job_id,
            "status": "pending",
            "progress_step": "Waiting to start...",
            "progress_pct": 0,
        }


# ---------------------------------------------------------------------------
# POST /improve — rewrite a passage to reduce similarity
# ---------------------------------------------------------------------------
@router.post(
    "/improve",
    summary="Rewrite a passage to reduce similarity",
    description=(
        "Rewrites a flagged passage using the LLM to reduce textual similarity "
        "while preserving meaning, facts, and citation references. "
        "Prefer using the Integrity Coach (/api/v1/coach) for student-facing feedback."
    ),
)
async def improve_similarity(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    text = (payload.get("text") or payload.get("passage") or "").strip()
    topic = payload.get("topic", "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="No text provided to improve.")


    from app.services.llm import LLMService
    improved = await LLMService.improve_section_similarity(
        section_content=text,
        section_title=payload.get("section_title", "Section"),
        topic=topic or "research",
    )

    # Quick similarity check on improved text
    improved_score = None
    try:
        from app.services.segmenter import SentenceSegmenterService
        from app.services.matcher import DualTierMatcher

        sentences = SentenceSegmenterService.segment(improved)
        if sentences:
            matcher = DualTierMatcher()
            analysis = matcher.analyze_document(sentences)
            improved_score = analysis.get("plagiarism_score", 0.0)
    except Exception as e:
        logger.warning(f"Post-improve similarity check failed: {e}")

    return {
        "original_text": text,
        "improved_text": improved,
        "improved_similarity_score": improved_score,
    }


# ---------------------------------------------------------------------------
# GET /report/{job_id} — download PDF similarity report
# ---------------------------------------------------------------------------
@router.get(
    "/report/{job_id}",
    summary="Download PDF similarity report for a completed check",
)
async def get_similarity_report_pdf(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app
    from app.services.pdf_generator import PDFGeneratorService

    res = AsyncResult(job_id, app=celery_app)

    if res.state != "SUCCESS":
        if res.state in ("PENDING", "RECEIVED", "STARTED", "RETRY", "PROGRESS"):
            raise HTTPException(
                status_code=400,
                detail="Analysis is still in progress. Wait for completion before downloading."
            )
        raise HTTPException(status_code=404, detail="Report not found or analysis failed.")

    result = res.result or {}
    if not result:
        raise HTTPException(status_code=404, detail="Report details are empty.")

    try:
        # Use the existing PDFGeneratorService (already handles this format)
        pdf_bytes = PDFGeneratorService.generate_report(result)
        filename = (result.get("filename") or "similarity_report.txt").rsplit(".", 1)[0] + "_report.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"PDF report generation failed for job_id={job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
