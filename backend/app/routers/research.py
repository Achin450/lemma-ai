"""
Research Paper API Router — handles paper generation, restructuring, status polling,
paper retrieval, and export endpoints.

Routes:
    POST /api/v1/research/generate           — Queue paper generation
    POST /api/v1/research/restructure        — Queue restructuring
    GET  /api/v1/research/status/{job_id}    — Get job status
    GET  /api/v1/research/{paper_id}         — Get completed paper
    GET  /api/v1/research/export/{paper_id}  — Export paper (PDF/DOCX)
    POST /api/v1/research/{paper_id}/improve — Improve section similarity
    GET  /api/v1/research/list               — List user's papers
"""
from __future__ import annotations

import uuid
import logging
from typing import Optional, Literal

from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File,
    Query, Form, BackgroundTasks
)
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.services.auth import get_current_user, require_any_user
from app.services.paper_store import PaperStore
from app.schemas.research import (
    GenerateRequest, PaperStatusResponse, PaperStatus, PaperLength,
    PaperSummaryResponse, ImproveRequest, ResearchPaper,
    PaperUpdateRequest, PaperSection
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research", tags=["Research Paper"])


# ---------------------------------------------------------------------------
# Helper to get Celery result
# ---------------------------------------------------------------------------
def _get_celery_result(job_id: str):
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app
    return AsyncResult(job_id, app=celery_app)


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------
@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a new IEEE-structured research paper",
    description=(
        "Queues a background task to generate a full IEEE-structured research paper "
        "with real citations from arXiv and Semantic Scholar. "
        "Returns a job_id to poll with GET /api/v1/research/status/{job_id}."
    ),
)
async def generate_research_paper(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    paper_id = str(uuid.uuid4())

    from app.schemas.research import ResearchPaper, PaperStatus, PaperType
    init_paper = ResearchPaper(
        paper_id=paper_id,
        title=f"Research Paper on {payload.topic}",
        status=PaperStatus.processing,
        paper_type=PaperType.generated
    )
    PaperStore.save(init_paper)

    dispatched = False
    try:
        from app.tasks.research_tasks import generate_paper_task
        generate_paper_task.apply_async(
            args=[paper_id],
            kwargs={
                "topic": payload.topic,
                "domain": payload.domain,
                "length": payload.length.value,
                "num_references": payload.num_references,
                "ieee_format": payload.ieee_format,
            },
            task_id=paper_id,
        )
        dispatched = True
        logger.info(f"Queued paper generation to Celery for topic='{payload.topic}', paper_id={paper_id}")
    except Exception as e:
        logger.warning(f"Could not dispatch to Celery: {e}. Falling back to FastAPI BackgroundTasks.")

    if not dispatched:
        def _bg_generate():
            from app.tasks.research_tasks import generate_paper_task
            try:
                generate_paper_task.run(
                    paper_id=paper_id,
                    topic=payload.topic,
                    domain=payload.domain,
                    length=payload.length.value,
                    num_references=payload.num_references,
                    ieee_format=payload.ieee_format
                )
            except Exception as e:
                logger.error(f"Background generation task error: {e}", exc_info=True)

        background_tasks.add_task(_bg_generate)

    return {
        "job_id": paper_id,
        "paper_id": paper_id,
        "status": "pending",
        "message": f"Research paper generation started for topic: '{payload.topic}'",
        "poll_url": f"/api/v1/research/status/{paper_id}",
    }


# ---------------------------------------------------------------------------
# POST /restructure
# ---------------------------------------------------------------------------
@router.post(
    "/restructure",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restructure an uploaded paper to IEEE format",
    description=(
        "Uploads a PDF, DOCX, or TXT file and restructures its content into IEEE format. "
        "Returns a job_id to poll for completion."
    ),
)
async def restructure_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    preserve_citations: bool = Form(True),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    paper_id = str(uuid.uuid4())
    temp_filename = f"{paper_id}_{file.filename}"
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
                        detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB."
                    )
                f_out.write(chunk)
    except HTTPException:
        if temp_filepath.exists():
            temp_filepath.unlink()
        raise
    except Exception as e:
        if temp_filepath.exists():
            temp_filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    dispatched = False
    try:
        from app.tasks.research_tasks import restructure_paper_task
        restructure_paper_task.apply_async(
            args=[paper_id, str(temp_filepath), file.filename],
            kwargs={"preserve_citations": preserve_citations},
            task_id=paper_id,
        )
        dispatched = True
        logger.info(f"Queued restructuring to Celery for file='{file.filename}', paper_id={paper_id}")
    except Exception as e:
        logger.warning(f"Could not dispatch restructure to Celery: {e}. Falling back to BackgroundTasks.")

    if not dispatched:
        def _bg_restructure():
            from app.tasks.research_tasks import restructure_paper_task
            try:
                restructure_paper_task.run(
                    paper_id=paper_id,
                    file_path=str(temp_filepath),
                    original_filename=file.filename,
                    preserve_citations=preserve_citations
                )
            except Exception as e:
                logger.error(f"Background restructure task error: {e}", exc_info=True)

        background_tasks.add_task(_bg_restructure)

    return {
        "job_id": paper_id,
        "paper_id": paper_id,
        "status": "pending",
        "message": f"Restructuring started for '{file.filename}'",
        "poll_url": f"/api/v1/research/status/{paper_id}",
    }


# ---------------------------------------------------------------------------
# GET /status/{job_id}
# ---------------------------------------------------------------------------
@router.get(
    "/status/{job_id}",
    summary="Get research job status and progress",
)
async def get_research_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    res = _get_celery_result(job_id)
    paper = PaperStore.load(job_id)
    paper_data = paper.model_dump() if paper else None

    if res.state == "SUCCESS":
        result = res.result or {}
        return {
            "job_id": job_id,
            "status": "completed",
            "paper_id": result.get("paper_id", job_id),
            "title": result.get("title") or (paper.title if paper else None),
            "sections": result.get("sections", len(paper.sections) if paper else 0),
            "citations": result.get("citations", len(paper.citations) if paper else 0),
            "similarity_score": result.get("similarity_score") or (paper.similarity_score if paper else None),
            "progress_step": "Paper ready!",
            "progress_pct": 100,
            "paper": paper_data,
            "error": result.get("error"),
        }
    elif res.state == "FAILURE":
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(res.result) if res.result else "Unknown error occurred.",
            "paper": paper_data,
        }
    elif res.state == "PROGRESS":
        meta = res.info or {}
        return {
            "job_id": job_id,
            "status": "processing",
            "progress_step": meta.get("step", "Processing..."),
            "progress_pct": meta.get("pct", 0),
            "paper": paper_data,
        }
    elif res.state in ("PENDING", "RECEIVED"):
        # Also check if paper file exists (in case task completed outside Celery or is updating)
        if paper and paper.status == PaperStatus.completed:
            return {
                "job_id": job_id,
                "status": "completed",
                "paper_id": job_id,
                "title": paper.title,
                "sections": len(paper.sections),
                "citations": len(paper.citations),
                "similarity_score": paper.similarity_score,
                "progress_step": "Paper ready!",
                "progress_pct": 100,
                "paper": paper_data,
            }
        elif paper and (paper.sections or paper.title):
            return {
                "job_id": job_id,
                "status": "processing",
                "progress_step": "Generating paper structure...",
                "progress_pct": 35,
                "paper": paper_data,
            }
        return {
            "job_id": job_id,
            "status": "pending",
            "progress_step": "Waiting to start...",
            "progress_pct": 0,
            "paper": paper_data,
        }
    else:
        return {
            "job_id": job_id,
            "status": "processing",
            "progress_step": "Working...",
            "paper": paper_data,
        }


# ---------------------------------------------------------------------------
# GET /papers and GET /list — List user's research papers and checks
# ---------------------------------------------------------------------------
@router.get(
    "/papers",
    summary="List all research papers, restructured papers, and similarity checks",
)
@router.get(
    "/list",
    summary="List user's research papers",
)
async def list_papers(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    papers = PaperStore.list_papers(user_id=user_id, limit=limit)
    return papers


# ---------------------------------------------------------------------------
# GET /similarity-report/{job_id}
# ---------------------------------------------------------------------------
@router.get(
    "/similarity-report/{job_id}",
    summary="Get a saved similarity check report",
)
async def get_similarity_report(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    report = PaperStore.load_similarity_report(job_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Similarity report for '{job_id}' not found."
        )
    return {"job_id": job_id, "report": report}


# ---------------------------------------------------------------------------
# DELETE /papers/{paper_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/papers/{paper_id}",
    summary="Delete a paper or similarity check from DB and disk",
)
async def delete_paper(
    paper_id: str,
    current_user: dict = Depends(get_current_user),
):
    deleted = PaperStore.delete(paper_id)
    return {"success": True, "paper_id": paper_id, "deleted": deleted}


# ---------------------------------------------------------------------------
# GET /{paper_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{paper_id}",
    summary="Get a completed research paper",
    description="Returns the full ResearchPaper object including all sections, citations, and metadata.",
)
async def get_paper(
    paper_id: str,
    current_user: dict = Depends(get_current_user),
):
    paper = PaperStore.load(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper '{paper_id}' not found."
        )

    if paper.status == PaperStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Paper generation failed: {paper.error or 'Unknown error'}"
        )

    return paper.model_dump()


# ---------------------------------------------------------------------------
# PUT /{paper_id} — Update paper content (Manual in-place edits)
# ---------------------------------------------------------------------------
@router.put(
    "/{paper_id}",
    summary="Update an existing research paper",
    description="Allows updating title, abstract, keywords, and sections for manual editing and customized export.",
)
async def update_paper(
    paper_id: str,
    payload: PaperUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    paper = PaperStore.load(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper '{paper_id}' not found."
        )

    if payload.title is not None:
        paper.title = payload.title.strip()
    if payload.abstract is not None:
        paper.abstract = payload.abstract.strip()
    if payload.keywords is not None:
        paper.keywords = payload.keywords
    if payload.authors is not None:
        paper.authors = payload.authors

    if payload.sections is not None:
        new_sections = []
        for i, s_update in enumerate(payload.sections):
            if i < len(paper.sections):
                sec = paper.sections[i]
                if s_update.title is not None:
                    sec.title = s_update.title.strip()
                if s_update.content is not None:
                    sec.content = s_update.content.strip()
                if s_update.number is not None:
                    sec.number = s_update.number.strip()
                new_sections.append(sec)
            else:
                new_sec = PaperSection(
                    number=s_update.number or f"SECTION_{i+1}",
                    title=s_update.title or f"SECTION {i+1}",
                    content=s_update.content or ""
                )
                new_sections.append(new_sec)
        paper.sections = new_sections

    PaperStore.save(paper)
    logger.info(f"Successfully updated paper '{paper_id}'")
    return paper.model_dump()


# ---------------------------------------------------------------------------
# GET /export/{paper_id}
# ---------------------------------------------------------------------------
@router.get(
    "/export/{paper_id}",
    summary="Export a research paper as PDF or DOCX",
    description="Returns the paper as a downloadable PDF or DOCX file. Use ?format=pdf or ?format=docx",
)
async def export_paper(
    paper_id: str,
    format: Literal["pdf", "docx"] = Query("pdf", description="Export format: pdf or docx"),
    current_user: dict = Depends(get_current_user),
):
    paper = PaperStore.load(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found.")

    if paper.status != PaperStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Paper is not yet ready for export. Wait for generation to complete."
        )

    from app.services.export_service import ExportService

    try:
        if format == "pdf":
            file_bytes = ExportService.export_pdf(paper)
            media_type = "application/pdf"
        else:
            file_bytes = ExportService.export_docx(paper)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        filename = ExportService.get_safe_filename(paper, format)

        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Export failed for paper_id={paper_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ---------------------------------------------------------------------------
# POST /{paper_id}/improve
# ---------------------------------------------------------------------------
@router.post(
    "/{paper_id}/improve",
    summary="Improve a section's similarity score",
    description=(
        "Rewrites a specific section or passage to reduce textual similarity "
        "while preserving technical meaning, facts, citations, and research claims."
    ),
)
async def improve_paper_section(
    paper_id: str,
    payload: ImproveRequest,
    current_user: dict = Depends(get_current_user),
):
    paper = PaperStore.load(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found.")

    # Find the target section
    target_section = None
    for section in paper.sections:
        if section.number == payload.section_number:
            target_section = section
            break

    if not target_section:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{payload.section_number}' not found in paper."
        )

    # Improve the section
    content_to_improve = payload.passage or target_section.content
    if not content_to_improve:
        raise HTTPException(status_code=400, detail="Section has no content to improve.")

    from app.services.llm import LLMService
    improved = await LLMService.improve_section_similarity(
        section_content=content_to_improve,
        section_title=target_section.title,
        topic=paper.topic or paper.title or "",
    )

    if payload.passage:
        # Replace only the specific passage
        target_section.content = target_section.content.replace(payload.passage, improved, 1)
    else:
        target_section.content = improved

    # Re-run similarity check for this section
    try:
        from app.services.segmenter import SentenceSegmenterService
        from app.services.matcher import DualTierMatcher
        sec_sentences = SentenceSegmenterService.segment(target_section.content)
        if sec_sentences:
            matcher = DualTierMatcher()
            sec_analysis = matcher.analyze_document(sec_sentences)
            target_section.similarity_score = sec_analysis.get("plagiarism_score", 0.0)
    except Exception as e:
        logger.warning(f"Section similarity re-check failed: {e}")

    PaperStore.save(paper)

    return {
        "paper_id": paper_id,
        "section_number": payload.section_number,
        "improved_content": improved,
        "section_similarity_score": target_section.similarity_score,
    }

