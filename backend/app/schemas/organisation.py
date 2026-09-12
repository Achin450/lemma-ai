"""
Organisation & Funding Schemes Pydantic Schemas

Defines data models for organisation registration, domain email validation,
authentication, profile management, and research funding schemes (Q1/Q2/Q3/Q4, etc.).
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class PublicationCriteriaItem(BaseModel):
    """Specific publication or research output criterion."""
    criteria_key: str = Field(..., description="e.g. 'q1_sci', 'q2', 'conference_ieee', 'book_chapter', 'patent'")
    label: str = Field(..., description="Display label e.g. 'Scopus Q1 / SCI Journal'")
    amount_inr: int = Field(10000, ge=0, description="Funding/incentive payout in INR")
    amount_usd: int = Field(120, ge=0, description="Funding/incentive payout in USD")
    description: Optional[str] = Field(None, description="Specific criteria rules or indexing requirement")
    payout_form: Optional[str] = Field("Direct Cash Bounty & APC Reimbursement", description="Payout format")

    @model_validator(mode="before")
    @classmethod
    def normalize_criteria_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "key" in data and "criteria_key" not in data:
                data["criteria_key"] = data["key"]
            if "criteria_type" in data and "criteria_key" not in data:
                data["criteria_key"] = data["criteria_type"]
            if "criteria_name" in data and "label" not in data:
                data["label"] = data["criteria_name"]
            if "min_indexing" in data and "description" not in data:
                data["description"] = data["min_indexing"]
        return data


class OrganisationRegister(BaseModel):
    """Organisation registration request schema with domain email."""
    name: str = Field(..., min_length=2, description="Organisation or University name")
    short_name: Optional[str] = Field(None, description="Short abbreviation e.g. 'CU'")
    domain_email: str = Field(..., description="Official domain email (e.g. research@chitkara.edu.in)")
    password: str = Field(..., min_length=8, description="Account password (min 8 characters)")
    confirm_password: Optional[str] = Field(None, description="Password confirmation")
    org_type: str = Field("University", description="'University', 'Research Institute', 'Corporate R&D', 'Government Body', 'Non-Profit', 'Other'")
    website: Optional[str] = Field(None, description="Official website URL")
    contact_person: str = Field(..., min_length=2, description="Name of contact officer / Dean of Research")
    contact_number: Optional[str] = Field(None, description="Contact phone or office number")
    description: Optional[str] = Field(None, description="Brief description of the organisation and research vision")
    country: str = Field("India", description="Country")
    city: Optional[str] = Field(None, description="City / Campus location")
    region: str = Field("India", description="'India' or 'International'")

    @model_validator(mode="before")
    @classmethod
    def normalize_register_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "official_email" in data and "domain_email" not in data:
                data["domain_email"] = data["official_email"]
            if "organisation_type" in data and "org_type" not in data:
                data["org_type"] = data["organisation_type"]
            if "contact_phone" in data and "contact_number" not in data:
                data["contact_number"] = data["contact_phone"]
            if "contact_name" in data and "contact_person" not in data:
                data["contact_person"] = data["contact_name"]
        return data


class OrganisationLogin(BaseModel):
    """Organisation login request schema."""
    domain_email: str = Field(..., description="Registered domain email")
    password: str = Field(..., description="Password")

    @model_validator(mode="before")
    @classmethod
    def normalize_login_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "official_email" in data and "domain_email" not in data:
                data["domain_email"] = data["official_email"]
        return data


class OrganisationProfile(BaseModel):
    """Organisation profile response schema."""
    id: str
    name: str
    short_name: Optional[str] = None
    domain_email: str
    official_email: Optional[str] = None
    domain: str
    org_type: str
    organisation_type: Optional[str] = None
    website: Optional[str] = None
    contact_person: str
    contact_number: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None
    country: str
    city: Optional[str] = None
    region: str
    verification_status: str
    created_at: str

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "domain_email" in data and "official_email" not in data:
                data["official_email"] = data["domain_email"]
            if "org_type" in data and "organisation_type" not in data:
                data["organisation_type"] = data["org_type"]
            if "contact_number" in data and "contact_phone" not in data:
                data["contact_phone"] = data["contact_number"]
        return data


class OrganisationUpdate(BaseModel):
    """Payload to update organisation profile."""
    name: Optional[str] = None
    short_name: Optional[str] = None
    org_type: Optional[str] = None
    website: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_update_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "organisation_type" in data and "org_type" not in data:
                data["org_type"] = data["organisation_type"]
            if "contact_phone" in data and "contact_number" not in data:
                data["contact_number"] = data["contact_phone"]
        return data


class OrganisationTokenResponse(BaseModel):
    """JWT Token response for logged-in organisation."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organisation: OrganisationProfile


class FundingSchemeCreate(BaseModel):
    """Schema for creating a new research funding scheme."""
    scheme_name: str = Field(..., min_length=3, description="Scheme title e.g. 'Research Publication Incentive Policy 2026'")
    scheme_title: Optional[str] = None
    description: Optional[str] = Field(None, description="Detailed policy description and objectives")
    min_amount_inr: int = Field(10000, ge=0, description="Minimum payout per publication in INR")
    max_amount_inr: int = Field(50000, ge=0, description="Maximum potential payout in INR")
    min_amount_usd: Optional[int] = Field(120, description="Minimum payout in USD")
    max_amount_usd: Optional[int] = Field(600, description="Maximum payout in USD")
    eligibility_criteria: Optional[str] = Field("Open to Faculty, PhD Scholars & External Co-Authors", description="Eligible applicant types")
    eligibility_scope: Optional[str] = None
    application_deadline: Optional[str] = Field("Rolling / Year-Round", description="Application deadline or schedule")
    academic_year: Optional[str] = Field("2026-2027", description="Academic year")
    application_link: Optional[str] = Field(None, description="Official portal link or policy document URL")
    guidelines_url: Optional[str] = None
    contact_email: Optional[str] = None
    research_area: Optional[str] = Field("All Disciplines", description="Target research domain")
    publication_criteria: List[PublicationCriteriaItem] = Field(
        default_factory=list,
        description="Eligible research outputs (Q1, Q2, Q3, Q4, Conference, Book Chapter, Patent, etc.)"
    )
    accepted_indexing: List[str] = Field(
        default_factory=lambda: ["Scopus", "SCI / SCIE", "IEEE"],
        description="Accepted indexings"
    )
    additional_requirements: Optional[str] = Field(None, description="Affiliation requirements or co-authorship policies")
    status: Optional[str] = Field("active", description="'active' or 'draft'")

    @model_validator(mode="before")
    @classmethod
    def normalize_scheme_create(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "scheme_title" in data and "scheme_name" not in data:
                data["scheme_name"] = data["scheme_title"]
            if "scheme_name" in data and "scheme_title" not in data:
                data["scheme_title"] = data["scheme_name"]
            if "criteria" in data and "publication_criteria" not in data:
                data["publication_criteria"] = data["criteria"]
            if "guidelines_url" in data and "application_link" not in data:
                data["application_link"] = data["guidelines_url"]
            if "eligibility_scope" in data and "eligibility_criteria" not in data:
                data["eligibility_criteria"] = data["eligibility_scope"]

            # Calculate min and max from publication criteria if present
            crit_list = data.get("publication_criteria") or data.get("criteria") or []
            if crit_list and isinstance(crit_list, list):
                amounts_inr = [c.get("amount_inr", 0) for c in crit_list if isinstance(c, dict) and c.get("amount_inr")]
                if amounts_inr:
                    data["min_amount_inr"] = min(amounts_inr)
                    data["max_amount_inr"] = max(amounts_inr)
                    data["min_amount_usd"] = round(min(amounts_inr) / 85)
                    data["max_amount_usd"] = round(max(amounts_inr) / 85)
        return data


class FundingSchemeUpdate(BaseModel):
    """Schema for updating an existing research funding scheme."""
    scheme_name: Optional[str] = None
    scheme_title: Optional[str] = None
    description: Optional[str] = None
    min_amount_inr: Optional[int] = None
    max_amount_inr: Optional[int] = None
    min_amount_usd: Optional[int] = None
    max_amount_usd: Optional[int] = None
    eligibility_criteria: Optional[str] = None
    eligibility_scope: Optional[str] = None
    application_deadline: Optional[str] = None
    academic_year: Optional[str] = None
    application_link: Optional[str] = None
    guidelines_url: Optional[str] = None
    contact_email: Optional[str] = None
    research_area: Optional[str] = None
    publication_criteria: Optional[List[PublicationCriteriaItem]] = None
    criteria: Optional[List[PublicationCriteriaItem]] = None
    accepted_indexing: Optional[List[str]] = None
    additional_requirements: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_scheme_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "scheme_title" in data and "scheme_name" not in data:
                data["scheme_name"] = data["scheme_title"]
            if "criteria" in data and "publication_criteria" not in data:
                data["publication_criteria"] = data["criteria"]
            if "guidelines_url" in data and "application_link" not in data:
                data["application_link"] = data["guidelines_url"]
            if "eligibility_scope" in data and "eligibility_criteria" not in data:
                data["eligibility_criteria"] = data["eligibility_scope"]
            if "status" in data:
                data["is_active"] = (data["status"] == "active")
        return data


class FundingSchemeResponse(BaseModel):
    """Detailed response for a funding scheme with organisation details."""
    id: str
    organisation_id: str
    organisation_name: str
    organisation_domain: Optional[str] = None
    organisation_type: Optional[str] = None
    organisation_website: Optional[str] = None
    organisation_contact_email: Optional[str] = None
    scheme_name: str
    scheme_title: Optional[str] = None
    description: Optional[str] = None
    min_amount_inr: int
    max_amount_inr: int
    min_amount_usd: int
    max_amount_usd: int
    eligibility_criteria: Optional[str] = None
    eligibility_scope: Optional[str] = None
    application_deadline: Optional[str] = None
    academic_year: Optional[str] = None
    application_link: Optional[str] = None
    guidelines_url: Optional[str] = None
    contact_email: Optional[str] = None
    research_area: Optional[str] = None
    publication_criteria: List[Dict[str, Any]] = []
    criteria: List[Dict[str, Any]] = []
    accepted_indexing: List[str] = []
    reward_tiers: List[Dict[str, Any]] = []
    additional_requirements: Optional[str] = None
    is_active: bool = True
    status: str = "active"
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def populate_response_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "scheme_name" in data and "scheme_title" not in data:
                data["scheme_title"] = data["scheme_name"]
            if "publication_criteria" in data and "criteria" not in data:
                data["criteria"] = data["publication_criteria"]
            if "application_link" in data and "guidelines_url" not in data:
                data["guidelines_url"] = data["application_link"]
            if "eligibility_criteria" in data and "eligibility_scope" not in data:
                data["eligibility_scope"] = data["eligibility_criteria"]
            if "is_active" in data:
                data["status"] = "active" if data["is_active"] else "draft"
        return data