"""
Research Celery Tasks — background tasks for research paper generation and restructuring.
Reuses the existing Celery/Redis infrastructure from tasks/celery_app.py.
"""
from __future__ import annotations

import asyncio
import logging
import os
from app.tasks.celery_app import celery_app
from app.services.paper_store import PaperStore
from app.schemas.research import PaperStatus, PaperType, ResearchPaper, GenerateRequest, PaperLength

logger = logging.getLogger(__name__)


import concurrent.futures

def _run_async(coro):
    """Run an async coroutine from a synchronous context safely."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


@celery_app.task(bind=True, name="app.tasks.research_tasks.generate_paper_task")
def generate_paper_task(self, paper_id: str, topic: str, domain: str = None,
                         length: str = "medium", num_references: int = 10,
                         ieee_format: bool = True) -> dict:

    """
    Background Celery task for full research paper generation.
    Updates paper status via PaperStore at each stage.
    Returns the paper_id on completion.
    """
    logger.info(f"Starting paper generation task for paper_id={paper_id}, topic='{topic}'")

    # Progress reporter that updates the task state AND paper store
    def report_progress(step: str, pct: int):
        try:
            self.update_state(state="PROGRESS", meta={"step": step, "pct": pct, "paper_id": paper_id}, task_id=paper_id)
        except Exception:
            try:
                self.update_state(state="PROGRESS", meta={"step": step, "pct": pct, "paper_id": paper_id})
            except Exception:
                pass
        # Update the paper in store with processing status
        try:
            paper = PaperStore.load(paper_id)
            if paper:
                paper.status = PaperStatus.processing
                PaperStore.save(paper)
        except Exception:
            pass

    try:
        # Ensure paper store DB table exists
        PaperStore.ensure_db_table()

        # Create initial paper record
        initial_paper = ResearchPaper(
            paper_id=paper_id,
            topic=topic,
            domain=domain,
            status=PaperStatus.processing,
            paper_type=PaperType.generated,
            title=f"Generating: {topic}",
        )
        PaperStore.save(initial_paper)

        # Build request object
        from app.schemas.research import PaperLength
        try:
            paper_length = PaperLength(length)
        except ValueError:
            paper_length = PaperLength.medium

        request = GenerateRequest(
            topic=topic,
            domain=domain,
            length=paper_length,
            num_references=num_references,
            ieee_format=ieee_format,
        )

        # Run the async generator in this sync Celery task
        from app.services.research_generator import ResearchGeneratorService
        generator = ResearchGeneratorService(progress_callback=report_progress)

        paper = _run_async(generator.generate(request, paper_id=paper_id))

        # Apply IEEE formatting if requested
        if ieee_format and paper.status == PaperStatus.completed:
            from app.services.ieee_formatter import IEEEFormatterService
            IEEEFormatterService.format_paper(paper)

        # Save final paper
        PaperStore.save(paper)

        logger.info(f"Paper generation completed for paper_id={paper_id}, "
                    f"status={paper.status}, sections={len(paper.sections)}, "
                    f"citations={len(paper.citations)}")

        return {
            "paper_id": paper_id,
            "status": paper.status.value,
            "title": paper.title,
            "sections": len(paper.sections),
            "citations": len(paper.citations),
            "similarity_score": paper.similarity_score,
            "error": paper.error,
        }

    except Exception as e:
        logger.error(f"generate_paper_task failed for paper_id={paper_id}: {e}", exc_info=True)
        # Mark paper as failed
        try:
            paper = PaperStore.load(paper_id)
            if paper:
                paper.status = PaperStatus.failed
                paper.error = str(e)
                PaperStore.save(paper)
            else:
                failed_paper = ResearchPaper(
                    paper_id=paper_id,
                    topic=topic,
                    status=PaperStatus.failed,
                    paper_type=PaperType.generated,
                    error=str(e),
                )
                PaperStore.save(failed_paper)
        except Exception as save_err:
            logger.error(f"Failed to save failure state: {save_err}")
        raise


@celery_app.task(bind=True, name="app.tasks.research_tasks.restructure_paper_task")
def restructure_paper_task(self, paper_id: str, file_path: str, original_filename: str,
                            preserve_citations: bool = True) -> dict:
    """
    Background Celery task for paper restructuring.
    Reads the uploaded file, extracts text, and restructures to IEEE format.
    """
    logger.info(f"Starting restructure task for paper_id={paper_id}, file={original_filename}")

    def report_progress(step: str, pct: int):
        try:
            self.update_state(state="PROGRESS", meta={"step": step, "pct": pct, "paper_id": paper_id}, task_id=paper_id)
        except Exception:
            try:
                self.update_state(state="PROGRESS", meta={"step": step, "pct": pct, "paper_id": paper_id})
            except Exception:
                pass

    try:
        PaperStore.ensure_db_table()

        # Read the uploaded file
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Uploaded file not found: {file_path}")

        with open(file_path, "rb") as f:
            content = f.read()

        # Extract text
        from app.services.extractor import DocumentExtractorService
        text = DocumentExtractorService.extract_text(original_filename, content)

        # Create initial record
        initial_paper = ResearchPaper(
            paper_id=paper_id,
            status=PaperStatus.processing,
            paper_type=PaperType.restructured,
            title=f"Restructuring: {original_filename}",
        )
        PaperStore.save(initial_paper)

        # Run restructurer
        from app.services.paper_restructurer import PaperRestructurerService
        restructurer = PaperRestructurerService(progress_callback=report_progress)

        paper = _run_async(restructurer.restructure(
            text=text,
            filename=original_filename,
            paper_id=paper_id,
            preserve_citations=preserve_citations,
        ))

        # Apply IEEE formatting
        from app.services.ieee_formatter import IEEEFormatterService
        IEEEFormatterService.format_paper(paper)

        # Save final paper
        PaperStore.save(paper)

        logger.info(f"Restructuring completed for paper_id={paper_id}, "
                    f"status={paper.status}, sections={len(paper.sections)}")

        return {
            "paper_id": paper_id,
            "status": paper.status.value,
            "title": paper.title,
            "sections": len(paper.sections),
            "citations": len(paper.citations),
            "similarity_score": paper.similarity_score,
            "error": paper.error,
        }

    except Exception as e:
        logger.error(f"restructure_paper_task failed for paper_id={paper_id}: {e}", exc_info=True)
        try:
            failed_paper = ResearchPaper(
                paper_id=paper_id,
                status=PaperStatus.failed,
                paper_type=PaperType.restructured,
                error=str(e),
            )
            PaperStore.save(failed_paper)
        except Exception:
            pass
        raise
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")


@celery_app.task(bind=True, name="app.tasks.research_tasks.similarity_check_task")
def similarity_check_task(self, job_id: str, text: str = None,
                           file_path: str = None, original_filename: str = None) -> dict:
    """
    Background Celery task for standalone similarity checking.
    Can accept either plain text or a file path.
    Returns full similarity analysis report.
    """
    logger.info(f"Starting similarity check task for job_id={job_id}")

    def report_progress(step: str, pct: int):
        try:
            self.update_state(state="PROGRESS", meta={"step": step, "pct": pct, "job_id": job_id}, task_id=job_id)
        except Exception:
            try:
                self.update_state(state="PROGRESS", meta={"step": step, "pct": pct})
            except Exception:
                pass

    try:
        report_progress("Extracting document text...", 10)

        # Get text
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            from app.services.extractor import DocumentExtractorService
            text = DocumentExtractorService.extract_text(original_filename or "document.txt", content)
        elif not text:
            raise ValueError("No text or file provided for similarity check.")

        report_progress("Segmenting document...", 20)
        from app.services.segmenter import SentenceSegmenterService
        sentences = SentenceSegmenterService.segment(text)

        report_progress("Fetching online candidates...", 30)
        from app.config import settings
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                queries = OnlineRetrieverService.extract_search_queries(text)
                candidates = _run_async(OnlineRetrieverService.get_online_candidates(queries))
                _run_async(OnlineRetrieverService.seed_ephemeral_candidates(job_id, candidates))
            except Exception as e:
                logger.warning(f"Online retrieval failed for similarity check: {e}")

        report_progress("Running similarity analysis...", 50)
        from app.services.matcher import DualTierMatcher
        matcher = DualTierMatcher()
        analysis = matcher.analyze_document(sentences, job_id=job_id)

        report_progress("Building similarity report...", 90)

        # Convert matches to SimilarityMatch format
        from app.schemas.research import SimilarityReport, SimilarityMatch, PaperStatus
        similarity_matches = []
        for m in analysis.get("matches", []):
            similarity_matches.append(SimilarityMatch(
                query_text=m["query_sentence"]["text"],
                matched_text=m["matched_sentence"]["text"],
                source_title=m["matched_sentence"].get("doc_title", "Unknown"),
                source_author=m["matched_sentence"].get("doc_author", "N/A"),
                source_url=m["matched_sentence"].get("doc_source"),
                similarity_score=m.get("score", 0.0),
                match_type=m.get("match_type", "lexical"),
                confidence=m.get("confidence_tier", "Low"),
            ))

        plag_score = analysis.get("plagiarism_score", 0.0)
        total_sents = analysis.get("total_sentences", 0)
        matched_sents = analysis.get("plagiarized_sentences_count", 0)

        report = SimilarityReport(
            job_id=job_id,
            overall_score=plag_score,
            original_pct=max(0.0, 1.0 - plag_score),
            matched_pct=plag_score,
            total_sentences=total_sents,
            matched_sentences=matched_sents,
            lexical_matches=analysis.get("lexical_matches_count", 0),
            semantic_matches=analysis.get("semantic_matches_count", 0),
            hybrid_matches=analysis.get("hybrid_matches_count", 0),
            matches=similarity_matches,
            status=PaperStatus.completed,
        )

        # Persist similarity report to PaperStore & PostgreSQL database
        try:
            from app.services.paper_store import PaperStore
            PaperStore.save_similarity_report(
                job_id=job_id,
                report_dict=report.model_dump(),
                filename=original_filename,
                text_preview=text[:100] if text else "",
                score=plag_score,
            )
            logger.info(f"Persisted similarity check {job_id} to database and disk.")
        except Exception as e:
            logger.warning(f"Failed to persist similarity check report: {e}")

        report_progress("Similarity check complete!", 100)

        return {
            "job_id": job_id,
            "status": "completed",
            "report": report.model_dump(),
            # Also include original analysis for PDF report generation
            "filename": original_filename or "pasted_text.txt",
            "text": text,
            "char_count": len(text),
            "sentence_count": len(sentences),
            "sentences": sentences,
            "analysis": analysis,
        }

    except Exception as e:
        logger.error(f"similarity_check_task failed for job_id={job_id}: {e}", exc_info=True)
        raise
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        # Prune ephemeral cache
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                OnlineRetrieverService.prune_cache(job_id)
            except Exception:
                pass
