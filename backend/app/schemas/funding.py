"""
University Research Publishing Incentives & Grants Schemas

Defines data models for university cash bounties, APC grants,
tier breakdowns, query filtering, and summary statistics.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class RewardTierBreakdown(BaseModel):
    """Specific payout breakdown by journal / conference tier."""
    tier_name: str = Field(..., description="e.g. 'Nature / Science Index', 'Scopus Q1 / SCI', 'IEEE / ACM Conference'")
    amount_inr: int = Field(..., ge=10000, description="Incentive in INR (minimum ₹10,000)")
    amount_usd: int = Field(..., description="Equivalent or direct incentive in USD")
    criteria: str = Field(..., description="Journal indexing or Impact Factor requirement")
    payout_type: str = Field(..., description="'Direct Cash Award', 'APC Reimbursement', 'Research Seed Grant'")


class UniversityBounty(BaseModel):
    """Profile of a university offering publication incentives."""
    id: str = Field(..., description="Unique university slug")
    name: str = Field(..., description="Full university name")
    short_name: str = Field(..., description="Abbreviation, e.g. 'CU', 'VIT', 'KAUST'")
    country: str = Field(..., description="Country name")
    country_code: str = Field(..., description="ISO 2-letter country code for flag rendering")
    flag_emoji: str = Field(..., description="Country flag emoji")
    region: str = Field(..., description="'India' or 'International'")
    city: str = Field(..., description="City / campus location")
    min_amount_inr: int = Field(..., ge=10000, description="Minimum payout (>= ₹10,000)")
    max_amount_inr: int = Field(..., ge=10000, description="Maximum potential bounty in INR")
    min_amount_usd: int = Field(..., description="Minimum payout in USD")
    max_amount_usd: int = Field(..., description="Maximum payout in USD")
    accepted_indexing: List[str] = Field(..., description="List of accepted indexing, e.g. ['SCI', 'Scopus', 'IEEE']")
    funding_types: List[str] = Field(..., description="['Direct Cash Bounty', 'APC Sponsorship', 'Co-Authorship Grant']")
    eligibility_type: str = Field(..., description="e.g. 'Open to External Co-Authors', 'Faculty & Students', 'Open Access'")
    key_perks: List[str] = Field(..., description="Top perks, e.g. ['Direct Bank Transfer', 'Fast-track Verification']")
    reward_tiers: List[RewardTierBreakdown] = Field(..., description="Tier-by-tier pay scale breakdown")
    official_policy_url: Optional[str] = Field(None, description="Link to official university research policy / portal")
    contact_email: Optional[str] = Field(None, description="Contact email for research dean or R&D cell")
    verified: bool = Field(True, description="Whether incentive policy is verified")
    notes: Optional[str] = Field(None, description="Special guidelines or co-author conditions")


class FundingFilterParams(BaseModel):
    """Filters for searching and querying universities."""
    region: Optional[str] = Field(None, description="'All', 'India', or 'International'")
    min_amount_inr: Optional[int] = Field(10000, description="Minimum bounty in INR (default: 10000)")
    journal_tier: Optional[str] = Field(None, description="Filter by tier e.g. 'Q1', 'Nature', 'IEEE'")
    funding_type: Optional[str] = Field(None, description="Filter by funding type")
    search_query: Optional[str] = Field(None, description="Search by name, country, or keyword")


class FundingSummaryStats(BaseModel):
    """Summary metrics for the directory."""
    total_institutions: int
    indian_institutions: int
    foreign_institutions: int
    max_bounty_inr: int
    max_bounty_usd: int
    min_threshold_inr: int = 10000
    average_bounty_inr: int
