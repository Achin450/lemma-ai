import logging
from fastapi import APIRouter, Depends, HTTPException
from app.services.auth import get_current_user
from app.services.llm import LLMService
from app.schemas.citation import CitationGenerateRequest, CitationGenerateResponse

router = APIRouter(prefix="/api/v1/citations", tags=["Citation Generator"])
logger = logging.getLogger(__name__)

@router.post("/generate", response_model=CitationGenerateResponse)
async def generate_citation(req: CitationGenerateRequest, current_user: dict = Depends(get_current_user)):
    return await LLMService.generate_citations(req.query)
