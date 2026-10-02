import uuid
import logging
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status, Security, UploadFile, File
from fastapi.security.api_key import APIKeyHeader

from app.services.database import DatabaseService
from app.tasks.analysis import analyze_document_task
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/public", tags=["Public API"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Security(api_key_header)) -> dict:
    """Verify the provided API key against the database."""
    import hashlib
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT a.id, a.user_id, u.institution_id 
                   FROM api_keys a
                   JOIN users u ON a.user_id = u.id
                   WHERE a.key_hash = %s AND (a.expires_at IS NULL OR a.expires_at > NOW())""",
                (key_hash,)
            )
            key_record = cur.fetchone()
            
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API Key"
        )
        
    # Log usage asynchronously in production
    return key_record

@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def public_analyze(
    file: UploadFile = File(...),
    api_key_record: dict = Depends(verify_api_key)
):
    """
    Submit a document for analysis via the public API.
    Returns a job_id for polling.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    import re, os
    safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(file.filename))
    file_ext = safe_filename.rsplit(".", 1)[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    job_id = str(uuid.uuid4())
    temp_filepath = settings.UPLOAD_DIR / f"api_{job_id}_{safe_filename}"
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    content_size = 0

    try:
        with open(temp_filepath, "wb") as f:
            while chunk := await file.read(8192):
                content_size += len(chunk)
                if content_size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB.")
                f.write(chunk)
    except HTTPException:
        if temp_filepath.exists():
            temp_filepath.unlink(missing_ok=True)
        raise
    except Exception as e:
        if temp_filepath.exists():
            temp_filepath.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Queue task
    analyze_document_task.apply_async(
        args=[str(temp_filepath), safe_filename],
        task_id=job_id
    )

    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Analysis started. Poll /api/v1/public/status/{job_id} for results."
    }

@router.get("/status/{job_id}")
async def public_status(job_id: str, api_key_record: dict = Depends(verify_api_key)):
    """Check the status of a submitted API job."""
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app
    
    res = AsyncResult(job_id, app=celery_app)
    if res.state == "SUCCESS":
        return {"job_id": job_id, "status": "completed"}
    elif res.state == "FAILURE":
        return {"job_id": job_id, "status": "failed", "error": str(res.result)}
    else:
        return {"job_id": job_id, "status": "processing"}
        
@router.get("/report/{job_id}")
async def public_report(job_id: str, api_key_record: dict = Depends(verify_api_key)):
    """Get the full JSON report of a completed API job."""
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app
    
    res = AsyncResult(job_id, app=celery_app)
    if res.state != "SUCCESS":
        raise HTTPException(status_code=400, detail="Report not ready or failed.")
        
    return res.result
