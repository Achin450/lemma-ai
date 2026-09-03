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


@celery_app.task(bind=True, name="app.tasks.analysis.analyze_document_task")
def analyze_document_task(self, file_path: str, original_filename: str) -> dict:
    """
    Background Celery task to parse a document, fetch web references, and perform plagiarism analysis.
    """
    logger.info(f"Starting analysis task for file: {original_filename} (temp path: {file_path})")
    job_id = self.request.id or "dummy_job"
    
    try:
        self.update_state(state="PROGRESS", meta={"step": "Reading uploaded document...", "pct": 10})
        
        # Read the file from disk
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Temporary file not found at: {file_path}")
            
        with open(file_path, "rb") as f:
            content = f.read()
        
        self.update_state(state="PROGRESS", meta={"step": "Extracting text and structure...", "pct": 20})
        # Run extractor
        text = DocumentExtractorService.extract_text(original_filename, content)
        
        self.update_state(state="PROGRESS", meta={"step": "Segmenting sentences & coordinate mapping...", "pct": 30})
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
            self.update_state(state="PROGRESS", meta={"step": "Retrieving reference sources...", "pct": 45})
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
        self.update_state(state="PROGRESS", meta={"step": "Running lexical & semantic matching...", "pct": 65})
        matcher = DualTierMatcher()
        analysis_report = matcher.analyze_document(sentences_data, job_id=job_id)
        
        # 3. Run AI Detection
        self.update_state(state="PROGRESS", meta={"step": "Evaluating AI-generated content patterns...", "pct": 80})
        logger.info(f"Running AI detection for job: {job_id}")
        ai_detection_report = AIDetectorService.analyze_document(text, sentences)
        
        # 4. Run Citation Analysis
        self.update_state(state="PROGRESS", meta={"step": "Analyzing citation validity & final score...", "pct": 92})
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
        return result
        
    except Exception as e:
        logger.error(f"Error in analyze_document_task: {str(e)}", exc_info=True)
        raise e
        
    finally:
        # 3. Clean up the temporary uploaded file from disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Successfully deleted temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")
                
        # 4. Prune ephemeral database & Elasticsearch candidate records
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                OnlineRetrieverService.prune_cache(job_id)
            except Exception as e:
                logger.error(f"Failed to prune cache for job {job_id}: {e}")
