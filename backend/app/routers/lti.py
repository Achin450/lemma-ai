import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse

from app.services.lti_service import LTIService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lti", tags=["LMS LTI Integration"])

@router.post("/login")
async def lti_login(request: Request):
    """
    Step 1 of LTI 1.3 OIDC flow: LMS initiates login.
    Redirects back to LMS authorization URL.
    """
    logger.info("Received LTI login request")
    # In a full implementation, use PyLTI1p3 OIDCLogin here
    return {"status": "ok", "message": "OIDC Login initiated"}

@router.post("/launch", response_class=HTMLResponse)
async def lti_launch(request: Request):
    """
    Step 2 of LTI 1.3 OIDC flow: LMS sends the JWT launch payload.
    Validates payload and returns the tool UI (e.g., assignment view).
    """
    form_data = await request.form()
    logger.info("Received LTI launch payload")
    
    launch_info = LTIService.get_launch_data(dict(form_data))
    is_instructor = any("Instructor" in role for role in launch_info.get("roles", []))
    
    if is_instructor:
        html = f"""
        <html>
            <body style="font-family: sans-serif; padding: 2rem; background: #0f172a; color: white;">
                <h2>Lemma AI — Instructor Dashboard</h2>
                <p>Welcome, Instructor! You are viewing context <b>{launch_info.get('context_title')}</b>.</p>
                <p>From here, you can configure plagiarism and AI detection settings for this assignment.</p>
                <div style="margin-top: 2rem; padding: 1rem; border: 1px solid #334155; border-radius: 8px;">
                    <h3>Assignment Sync</h3>
                    <p>Status: <span style="color: #10b981;">Connected</span></p>
                </div>
            </body>
        </html>
        """
    else:
        html = f"""
        <html>
            <body style="font-family: sans-serif; padding: 2rem; background: #0f172a; color: white;">
                <h2>Lemma AI — Student Submission</h2>
                <p>Welcome! You are submitting to <b>{launch_info.get('context_title')}</b>.</p>
                <div style="margin-top: 2rem; padding: 2rem; border: 2px dashed #334155; border-radius: 8px; text-align: center;">
                    <p>Drag and drop your document here to analyze and submit.</p>
                    <button style="padding: 10px 20px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer;">Select File</button>
                </div>
            </body>
        </html>
        """
    return HTMLResponse(content=html)

@router.get("/jwks")
async def lti_jwks():
    """
    JSON Web Key Set endpoint.
    LMS platforms fetch this to verify the JWTs we sign for grade passback.
    """
    return LTIService.generate_jwks()
