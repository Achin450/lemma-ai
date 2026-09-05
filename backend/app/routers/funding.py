"""
University Publishing Incentives & Grants API Router

Provides endpoints to query, filter, and inspect research publication
bounties and APC grants offered by verified universities (>= ₹10,000 INR).
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.funding import (
    UniversityBounty, FundingFilterParams, FundingSummaryStats
)
from app.services.funding_service import FundingService

router = APIRouter(prefix="/api/v1/funding", tags=["Publishing Bounties & Grants"])


@router.get(
    "/universities",
    response_model=List[UniversityBounty],
    summary="List and filter university publication bounties"
)
async def list_universities(
    region: Optional[str] = Query(None, description="'All', 'India', or 'International'"),
    min_amount_inr: Optional[int] = Query(10000, ge=10000, description="Minimum payout in INR (>= 10000)"),
    journal_tier: Optional[str] = Query(None, description="Tier keyword e.g. 'Nature', 'Q1', 'Scopus', 'IEEE'"),
    funding_type: Optional[str] = Query(None, description="Type e.g. 'Cash Bounty', 'APC'"),
    search_query: Optional[str] = Query(None, description="Keyword search in name, country, or perks")
):
    """
    Returns verified institutions offering publication rewards matching the criteria.
    Guarantees that all results meet the minimum threshold of >= ₹10,000 INR.
    """
    filters = FundingFilterParams(
        region=region,
        min_amount_inr=min_amount_inr,
        journal_tier=journal_tier,
        funding_type=funding_type,
        search_query=search_query
    )
    return FundingService.get_all_universities(filters)


@router.get(
    "/stats",
    response_model=FundingSummaryStats,
    summary="Get summary metrics across the funding directory"
)
async def get_funding_stats():
    """Returns directory statistics: total universities, max bounties, regional count, and averages."""
    return FundingService.get_summary_stats()


@router.get(
    "/{university_id}",
    response_model=UniversityBounty,
    summary="Get detailed reward tiers and guidelines for a specific university"
)
async def get_university_detail(university_id: str):
    """Fetches comprehensive payout slabs and application guidelines for the specified university."""
    bounty = FundingService.get_university_by_id(university_id)
    if not bounty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"University with ID '{university_id}' not found in verified registry."
        )
    return bounty
