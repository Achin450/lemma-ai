import os
import logging
import asyncio
import threading
from app.config import settings
from app.tasks.celery_app import celery_app
from app.services.extractor import DocumentExtractorService
from app.services.segmenter import SentenceSegmenterService
from app.services.matcher import DualTierMatcher
from app.services.ai_detector import AIDetectorService
from app.services.citation_analyzer import CitationAnalyzerService

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


class JobRegistry:
    """Thread-safe in-memory job registry for instant real-time progress and results."""
    _jobs = {}
    _lock = threading.Lock()

    @classmethod
    def set_progress(cls, job_id: str, step: str, pct: int):
        with cls._lock:
            cls._jobs[job_id] = {
                "job_id": job_id,
                "status": "processing",
                "progress_step": step,
                "progress_pct": pct
            }

    @classmethod
    def set_completed(cls, job_id: str, result: dict):
        with cls._lock:
            cls._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "result": result,
                "progress_step": "Analysis complete!",
                "progress_pct": 100
            }

    @classmethod
    def set_failed(cls, job_id: str, error: str):
        with cls._lock:
            cls._jobs[job_id] = {
                "job_id": job_id,
                "status": "failed",
                "error": error
            }

    @classmethod
    def get(cls, job_id: str):
        with cls._lock:
            return cls._jobs.get(job_id)


def execute_analysis_pipeline(job_id: str, file_path: str, original_filename: str) -> dict:
    """Core analysis pipeline execution that safely runs in worker or daemon thread."""
    logger.info(f"Starting analysis pipeline for file: {original_filename} (job: {job_id})")
    JobRegistry.set_progress(job_id, "Reading uploaded document...", 10)

    try:
        # Read the file from disk
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Temporary file not found at: {file_path}")
            
        with open(file_path, "rb") as f:
            content = f.read()
        
        JobRegistry.set_progress(job_id, "Extracting text and structure...", 20)
        # Run extractor
        text = DocumentExtractorService.extract_text(original_filename, content)
        
        JobRegistry.set_progress(job_id, "Segmenting sentences & coordinate mapping...", 30)
        # Segment sentences
        sentences_data = SentenceSegmenterService.segment(text)
        
        # Format sentences
        sentences = [
            {
                "text": s["text"],
                "start_char": s["start_char"],
                "end_char": s["end_char"]
            }
            for s in sentences_data
        ]
        
        # 1. Ephemeral online candidate retrieval & caching
        if settings.ENABLE_ONLINE_RETRIEVAL:
            JobRegistry.set_progress(job_id, "Retrieving reference sources...", 45)
            try:
                from app.services.online_retriever import OnlineRetrieverService
                logger.info(f"Triggering online retrieval query generation for job: {job_id}")
                queries = OnlineRetrieverService.extract_search_queries(text)
                
                logger.info(f"Generated search queries: {queries}")
                candidates = _run_async(OnlineRetrieverService.get_online_candidates(queries))
                
                _run_async(OnlineRetrieverService.seed_ephemeral_candidates(job_id, candidates))
            except Exception as e:
                logger.error(f"Failed to fetch/cache online candidate papers: {e}")

        # 2. Run dual-tier plagiarism matcher
        JobRegistry.set_progress(job_id, "Running lexical & semantic matching...", 65)
        matcher = DualTierMatcher()
        analysis_report = matcher.analyze_document(sentences_data, job_id=job_id)
        
        # 3. Run AI Detection
        JobRegistry.set_progress(job_id, "Evaluating AI-generated content patterns...", 80)
        logger.info(f"Running AI detection for job: {job_id}")
        ai_detection_report = AIDetectorService.analyze_document(text, sentences)
        
        # 4. Run Citation Analysis
        JobRegistry.set_progress(job_id, "Analyzing citation validity & final score...", 92)
        logger.info(f"Running citation analysis for job: {job_id}")
        citation_analysis_report = CitationAnalyzerService.analyze(
            text, sentences, analysis_report.get("matches", [])
        )
        
        # Return complete results in the same structure as DocumentUploadResponse
        result = {
            "filename": original_filename,
            "text": text,
            "char_count": len(text),
            "sentence_count": len(sentences),
            "sentences": sentences,
            "analysis": analysis_report,
            "ai_detection": ai_detection_report,
            "citation_analysis": citation_analysis_report
        }
        JobRegistry.set_completed(job_id, result)
        return result
        
    except Exception as e:
        logger.error(f"Error in execute_analysis_pipeline for job {job_id}: {str(e)}", exc_info=True)
        JobRegistry.set_failed(job_id, str(e))
        raise e
        
    finally:
        # Clean up the temporary uploaded file from disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Successfully deleted temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")
                
        # Prune ephemeral database & Elasticsearch candidate records
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                OnlineRetrieverService.prune_cache(job_id)
            except Exception as e:
                logger.error(f"Failed to prune cache for job {job_id}: {e}")


def start_analysis_job(job_id: str, file_path: str, original_filename: str):
    """Spawns an async analysis execution in a thread or Celery worker."""
    JobRegistry.set_progress(job_id, "Queued for analysis...", 10)
    worker_thread = threading.Thread(
        target=execute_analysis_pipeline,
        args=(job_id, file_path, original_filename),
        daemon=True
    )
    worker_thread.start()


@celery_app.task(bind=True, name="app.tasks.analysis.analyze_document_task")
def analyze_document_task(self, file_path: str, original_filename: str) -> dict:
    """Background Celery task to parse a document, fetch web references, and perform plagiarism analysis."""
    job_id = self.request.id or "dummy_job"
    return execute_analysis_pipeline(job_id, file_path, original_filename)
