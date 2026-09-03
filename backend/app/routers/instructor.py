import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.auth import get_current_user, require_instructor
from app.services.database import DatabaseService

router = APIRouter(prefix="/api/v1", tags=["Instructor Dashboard"])

@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def create_course(payload: dict, current_user: dict = Depends(require_instructor)):
    return {"status": "ok", "message": "Course created (Phase 3 Stub)"}

@router.get("/courses")
async def list_courses(current_user: dict = Depends(require_instructor)):
    return []

@router.post("/assignments/{assignment_id}/submissions/bulk")
async def bulk_upload_submissions(assignment_id: str, current_user: dict = Depends(require_instructor)):
    return {"status": "ok"}
