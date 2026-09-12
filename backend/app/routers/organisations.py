"""
Organisation & Research Funding Schemes Router

Provides endpoints for:
- Organisation Registration with institutional domain email validation
- Organisation Login with JWT token authentication
- Organisation Profile management
- Research Funding Schemes CRUD (Q1, Q2, Q3, Q4, Conferences, Book Chapters, Patents)
"""
from __future__ import annotations
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status, Header

from app.services.database import DatabaseService
from app.services.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    bearer_scheme
)
from app.schemas.organisation import (
    OrganisationRegister, OrganisationLogin, OrganisationProfile,
    OrganisationUpdate, OrganisationTokenResponse,
    FundingSchemeCreate, FundingSchemeUpdate, FundingSchemeResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/organisations", tags=["Organisation & Funding Schemes"])

# Disallowed public generic email domains (Must be institutional / corporate domain)
GENERIC_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "rediffmail.com", "protonmail.com", "proton.me", "icloud.com",
    "aol.com", "zoho.com", "mail.com", "gmx.com", "yandex.com"
}


def extract_and_validate_domain(email: str) -> str:
    """Extracts domain from email and verifies it is not a generic public provider."""
    email_clean = email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format."
        )
    
    parts = email_clean.split("@", 1)
    domain = parts[1].strip()
    
    if not domain or "." not in domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid domain in email address."
        )
        
    if domain in GENERIC_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generic email domains (@{domain}) are not permitted. Please use your official university or organisation domain email (e.g. admin@chitkara.edu.in)."
        )
        
    return domain


def _get_org_by_email(domain_email: str) -> Optional[dict]:
    """Fetch an organisation record by domain email."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM organisations WHERE LOWER(domain_email) = %s", (domain_email.lower().strip(),))
            return cur.fetchone()


def _get_org_by_id(org_id: str) -> Optional[dict]:
    """Fetch an organisation record by ID."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM organisations WHERE id = %s", (org_id,))
            return cur.fetchone()


def _build_org_profile(row: dict) -> OrganisationProfile:
    """Constructs OrganisationProfile from DB row."""
    return OrganisationProfile(
        id=str(row["id"]),
        name=row["name"],
        domain_email=row["domain_email"],
        domain=row["domain"],
        org_type=row.get("org_type", "University"),
        website=row.get("website"),
        contact_person=row["contact_person"],
        contact_number=row.get("contact_number"),
        description=row.get("description"),
        country=row.get("country", "India"),
        city=row.get("city"),
        region=row.get("region", "India"),
        verification_status=row.get("verification_status", "verified"),
        created_at=str(row.get("created_at", ""))
    )


def get_current_organisation(credentials=Depends(bearer_scheme)) -> dict:
    """FastAPI dependency to authenticate logged-in organisation admin."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required for organisation access."
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload.get("role") not in ("organisation_admin", "super_admin", "institution_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Organisation admin credentials required."
        )
        
    org_id = payload.get("organisation_id") or payload.get("institution_id") or payload.get("sub")
    org = _get_org_by_id(org_id)
    if not org:
        # Fallback check by email
        org = _get_org_by_email(payload.get("email", ""))
        
    if not org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organisation account not found."
        )
        
    return org


# ============================================================================
# 1. ORGANISATION AUTHENTICATION & PROFILE
# ============================================================================

@router.post("/register", response_model=OrganisationTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_organisation(payload: OrganisationRegister):
    """
    Register a new university or research organisation.
    Enforces official institutional domain email verification (e.g. @chitkara.edu.in).
    """
    domain_email = payload.domain_email.strip().lower()
    domain = extract_and_validate_domain(domain_email)
    
    if payload.confirm_password and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and Confirm Password do not match."
        )
        
    # Check duplicate email or domain
    existing = _get_org_by_email(domain_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organisation with this domain email is already registered. Please sign in."
        )

    org_id = str(uuid.uuid4())
    pw_hash = hash_password(payload.password)
    
    with DatabaseService.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO organisations (
                    id, name, domain_email, domain, password_hash,
                    org_type, website, contact_person, contact_number,
                    description, country, city, region, verification_status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, 'verified'
                )
            """, (
                org_id, payload.name.strip(), domain_email, domain, pw_hash,
                payload.org_type, payload.website, payload.contact_person.strip(), payload.contact_number,
                payload.description, payload.country, payload.city, payload.region
            ))
        conn.commit()

    row = _get_org_by_id(org_id)
    profile = _build_org_profile(row)
    
    # Generate tokens
    access_token = create_access_token(
        user_id=org_id,
        email=domain_email,
        role="organisation_admin",
        institution_id=org_id
    )
    refresh_token = create_refresh_token(org_id)
    
    return OrganisationTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        organisation=profile
    )


@router.post("/login", response_model=OrganisationTokenResponse)
async def login_organisation(payload: OrganisationLogin):
    """Authenticate an organisation with domain email and password."""
    domain_email = payload.domain_email.strip().lower()
    row = _get_org_by_email(domain_email)
    
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid domain email or password."
        )
        
    org_id = str(row["id"])
    profile = _build_org_profile(row)
    
    access_token = create_access_token(
        user_id=org_id,
        email=domain_email,
        role="organisation_admin",
        institution_id=org_id
    )
    refresh_token = create_refresh_token(org_id)
    
    return OrganisationTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        organisation=profile
    )


@router.get("/me", response_model=OrganisationProfile)
async def get_my_organisation_profile(current_org: dict = Depends(get_current_organisation)):
    """Fetches profile details of the authenticated organisation."""
    return _build_org_profile(current_org)


@router.put("/me", response_model=OrganisationProfile)
async def update_organisation_profile(
    payload: OrganisationUpdate,
    current_org: dict = Depends(get_current_organisation)
):
    """Updates organisation profile information."""
    org_id = str(current_org["id"])
    
    updates = {}
    if payload.name is not None: updates["name"] = payload.name.strip()
    if payload.org_type is not None: updates["org_type"] = payload.org_type
    if payload.website is not None: updates["website"] = payload.website
    if payload.contact_person is not None: updates["contact_person"] = payload.contact_person.strip()
    if payload.contact_number is not None: updates["contact_number"] = payload.contact_number
    if payload.description is not None: updates["description"] = payload.description
    if payload.city is not None: updates["city"] = payload.city
    if payload.country is not None: updates["country"] = payload.country
    if payload.region is not None: updates["region"] = payload.region
    
    if updates:
        set_clauses = [f"{k} = %s" for k in updates.keys()]
        set_clauses.append("updated_at = NOW()")
        values = list(updates.values()) + [org_id]
        
        query = f"UPDATE organisations SET {', '.join(set_clauses)} WHERE id = %s"
        with DatabaseService.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(values))
            conn.commit()
            
    row = _get_org_by_id(org_id)
    return _build_org_profile(row)


# ============================================================================
# 2. RESEARCH FUNDING SCHEMES CRUD
# ============================================================================

def _build_scheme_response(row: dict) -> FundingSchemeResponse:
    """Converts a database row into a structured FundingSchemeResponse."""
    pub_crit = row.get("publication_criteria")
    if isinstance(pub_crit, str):
        try: pub_crit = json.loads(pub_crit)
        except Exception: pub_crit = []
    elif not isinstance(pub_crit, list):
        pub_crit = []

    indexing = row.get("accepted_indexing")
    if isinstance(indexing, str):
        try: indexing = json.loads(indexing)
        except Exception: indexing = []
    elif not isinstance(indexing, list):
        indexing = []

    reward_tiers = row.get("reward_tiers")
    if isinstance(reward_tiers, str):
        try: reward_tiers = json.loads(reward_tiers)
        except Exception: reward_tiers = []
    elif not isinstance(reward_tiers, list):
        reward_tiers = []

    return FundingSchemeResponse(
        id=str(row["id"]),
        organisation_id=str(row["organisation_id"]),
        organisation_name=row.get("org_name") or row.get("name") or "Organisation",
        organisation_domain=row.get("domain"),
        organisation_type=row.get("org_type"),
        organisation_website=row.get("website"),
        organisation_contact_email=row.get("domain_email"),
        scheme_name=row["scheme_name"],
        description=row.get("description"),
        min_amount_inr=row.get("min_amount_inr", 10000),
        max_amount_inr=row.get("max_amount_inr", 50000),
        min_amount_usd=row.get("min_amount_usd", 120),
        max_amount_usd=row.get("max_amount_usd", 600),
        eligibility_criteria=row.get("eligibility_criteria"),
        application_deadline=row.get("application_deadline"),
        application_link=row.get("application_link"),
        research_area=row.get("research_area"),
        publication_criteria=pub_crit,
        accepted_indexing=indexing,
        reward_tiers=reward_tiers,
        additional_requirements=row.get("additional_requirements"),
        is_active=row.get("is_active", True),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", ""))
    )


@router.post("/me/schemes", response_model=FundingSchemeResponse, status_code=status.HTTP_201_CREATED)
@router.post("/schemes", response_model=FundingSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_funding_scheme(
    payload: FundingSchemeCreate,
    current_org: dict = Depends(get_current_organisation)
):
    """
    Creates a new research funding scheme for the logged-in organisation.
    Accepts criteria for Q1, Q2, Q3, Q4 journals, Conference papers, Book chapters, Patents, etc.
    """
    org_id = str(current_org["id"])
    scheme_id = str(uuid.uuid4())
    
    # Build reward tiers from publication criteria list
    reward_tiers = []
    min_inr = payload.min_amount_inr
    max_inr = payload.max_amount_inr
    
    for crit in payload.publication_criteria:
        reward_tiers.append({
            "tier_name": crit.label,
            "amount_inr": crit.amount_inr,
            "amount_usd": crit.amount_usd,
            "criteria": crit.description or f"Eligible for {crit.label}",
            "payout_type": "Direct Research Incentive"
        })
        if crit.amount_inr > max_inr:
            max_inr = crit.amount_inr
        if crit.amount_inr < min_inr and crit.amount_inr > 0:
            min_inr = crit.amount_inr

    pub_criteria_json = json.dumps([c.dict() for c in payload.publication_criteria])
    accepted_indexing_json = json.dumps(payload.accepted_indexing)
    reward_tiers_json = json.dumps(reward_tiers)
    
    min_usd = int(min_inr / 83) if min_inr else 120
    max_usd = int(max_inr / 83) if max_inr else 600
    
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO funding_schemes (
                    id, organisation_id, scheme_name, description,
                    min_amount_inr, max_amount_inr, min_amount_usd, max_amount_usd,
                    eligibility_criteria, application_deadline, application_link,
                    research_area, publication_criteria, accepted_indexing,
                    reward_tiers, additional_requirements, is_active
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s, TRUE
                ) RETURNING *
            """, (
                scheme_id, org_id, payload.scheme_name.strip(), payload.description,
                min_inr, max_inr, min_usd, max_usd,
                payload.eligibility_criteria, payload.application_deadline, payload.application_link,
                payload.research_area, pub_criteria_json, accepted_indexing_json,
                reward_tiers_json, payload.additional_requirements
            ))
            row = cur.fetchone()
        conn.commit()

    row["org_name"] = current_org["name"]
    row["domain"] = current_org["domain"]
    row["org_type"] = current_org.get("org_type")
    row["website"] = current_org.get("website")
    row["domain_email"] = current_org.get("domain_email")
    return _build_scheme_response(row)


@router.get("/me/schemes", response_model=List[FundingSchemeResponse])
@router.get("/schemes", response_model=List[FundingSchemeResponse])
async def list_my_funding_schemes(current_org: dict = Depends(get_current_organisation)):
    """Lists all funding schemes configured by the authenticated organisation."""
    org_id = str(current_org["id"])
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT f.*, o.name AS org_name, o.domain, o.org_type, o.website, o.domain_email
                FROM funding_schemes f
                JOIN organisations o ON f.organisation_id = o.id
                WHERE f.organisation_id = %s
                ORDER BY f.created_at DESC
            """, (org_id,))
            rows = cur.fetchall()
            
    return [_build_scheme_response(r) for r in rows]


@router.get("/me/schemes/{scheme_id}", response_model=FundingSchemeResponse)
async def get_my_funding_scheme_detail(
    scheme_id: str,
    current_org: dict = Depends(get_current_organisation)
):
    """Retrieves details of a specific funding scheme owned by the organisation."""
    org_id = str(current_org["id"])
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT f.*, o.name AS org_name, o.domain, o.org_type, o.website, o.domain_email
                FROM funding_schemes f
                JOIN organisations o ON f.organisation_id = o.id
                WHERE f.id = %s AND f.organisation_id = %s
            """, (scheme_id, org_id))
            row = cur.fetchone()
            
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding scheme not found or access denied."
        )
    return _build_scheme_response(row)


@router.put("/me/schemes/{scheme_id}", response_model=FundingSchemeResponse)
async def update_funding_scheme(
    scheme_id: str,
    payload: FundingSchemeUpdate,
    current_org: dict = Depends(get_current_organisation)
):
    """Updates an existing funding scheme with ownership validation."""
    org_id = str(current_org["id"])
    
    # Check ownership
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM funding_schemes WHERE id = %s AND organisation_id = %s", (scheme_id, org_id))
            existing = cur.fetchone()
            
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding scheme not found or access denied."
        )

    updates = {}
    if payload.scheme_name is not None: updates["scheme_name"] = payload.scheme_name.strip()
    if payload.description is not None: updates["description"] = payload.description
    if payload.min_amount_inr is not None: updates["min_amount_inr"] = payload.min_amount_inr
    if payload.max_amount_inr is not None: updates["max_amount_inr"] = payload.max_amount_inr
    if payload.min_amount_usd is not None: updates["min_amount_usd"] = payload.min_amount_usd
    if payload.max_amount_usd is not None: updates["max_amount_usd"] = payload.max_amount_usd
    if payload.eligibility_criteria is not None: updates["eligibility_criteria"] = payload.eligibility_criteria
    if payload.application_deadline is not None: updates["application_deadline"] = payload.application_deadline
    if payload.application_link is not None: updates["application_link"] = payload.application_link
    if payload.research_area is not None: updates["research_area"] = payload.research_area
    if payload.is_active is not None: updates["is_active"] = payload.is_active
    if payload.additional_requirements is not None: updates["additional_requirements"] = payload.additional_requirements

    if payload.publication_criteria is not None:
        updates["publication_criteria"] = json.dumps([c.dict() for c in payload.publication_criteria])
        reward_tiers = [
            {
                "tier_name": crit.label,
                "amount_inr": crit.amount_inr,
                "amount_usd": crit.amount_usd,
                "criteria": crit.description or f"Eligible for {crit.label}",
                "payout_type": "Direct Research Incentive"
            }
            for crit in payload.publication_criteria
        ]
        updates["reward_tiers"] = json.dumps(reward_tiers)

    if payload.accepted_indexing is not None:
        updates["accepted_indexing"] = json.dumps(payload.accepted_indexing)

    if updates:
        set_clauses = []
        values = []
        for k, v in updates.items():
            if k in ("publication_criteria", "accepted_indexing", "reward_tiers"):
                set_clauses.append(f"{k} = %s::jsonb")
            else:
                set_clauses.append(f"{k} = %s")
            values.append(v)
            
        set_clauses.append("updated_at = NOW()")
        values.extend([scheme_id, org_id])
        
        query = f"UPDATE funding_schemes SET {', '.join(set_clauses)} WHERE id = %s AND organisation_id = %s"
        with DatabaseService.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(values))
            conn.commit()

    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT f.*, o.name AS org_name, o.domain, o.org_type, o.website, o.domain_email
                FROM funding_schemes f
                JOIN organisations o ON f.organisation_id = o.id
                WHERE f.id = %s
            """, (scheme_id,))
            updated_row = cur.fetchone()
            
    return _build_scheme_response(updated_row)


@router.delete("/me/schemes/{scheme_id}")
@router.delete("/schemes/{scheme_id}")
async def delete_funding_scheme(
    scheme_id: str,
    current_org: dict = Depends(get_current_organisation)
):
    """Deletes a funding scheme owned by the organisation."""
    org_id = str(current_org["id"])
    with DatabaseService.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM funding_schemes WHERE id = %s AND organisation_id = %s RETURNING id;", (scheme_id, org_id))
            deleted = cur.fetchone()
        conn.commit()
        
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding scheme not found or access denied."
        )
    return {"message": "Funding scheme deleted successfully.", "id": scheme_id}


@router.get("/all")
async def list_all_public_organisations():
    """Public directory of verified organisations and their active schemes count."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT o.id, o.name, o.domain, o.org_type, o.website, o.country, o.city, o.region,
                       COUNT(f.id) AS active_schemes_count
                FROM organisations o
                LEFT JOIN funding_schemes f ON o.id = f.organisation_id AND f.is_active = TRUE
                GROUP BY o.id
                ORDER BY o.name ASC
            """)
            rows = cur.fetchall()
    return [dict(r) for r in rows]