"""
Unit Tests for Organisation Registration & Research Funding Scheme Management
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_organisation_registration_public_email_rejected():
    """Verify that generic public domains (gmail, yahoo, etc.) are rejected."""
    payload = {
        "name": "Invalid Test University",
        "official_email": "dean.research@gmail.com",
        "password": "SecurePassword123!",
        "organisation_type": "University",
        "contact_person": "Dr. Dean"
    }
    res = client.post("/api/v1/organisations/register", json=payload)
    assert res.status_code == 400
    assert "Generic email domains" in res.json().get("detail", "")


def test_organisation_registration_and_scheme_lifecycle():
    """Full lifecycle: Register -> Login -> Add Q1/Q2/Q3/Q4 Scheme -> Verify in Public Grants Directory."""
    unique_suffix = str(uuid.uuid4())[:8]
    domain_email = f"dean.research_{unique_suffix}@chitkara.edu.in"
    org_name = f"Chitkara University {unique_suffix}"

    reg_payload = {
        "name": org_name,
        "short_name": "CU-TEST",
        "official_email": domain_email,
        "password": "StrongPassword2026!",
        "organisation_type": "University",
        "website": "https://www.chitkara.edu.in",
        "contact_person": "Dr. Research Director",
        "contact_phone": "+91 9876543210",
        "description": "Premier Research University",
        "country": "India",
        "city": "Punjab"
    }

    # 1. Register Organisation
    reg_res = client.post("/api/v1/organisations/register", json=reg_payload)
    assert reg_res.status_code in (200, 201), f"Registration failed: {reg_res.text}"
    data = reg_res.json()
    assert "access_token" in data
    assert data["organisation"]["official_email"] == domain_email
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get /me Profile
    me_res = client.get("/api/v1/organisations/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["domain"] == "chitkara.edu.in"

    # 3. Create Funding Scheme with Q1, Q2, Q3, Q4, Conference, Book Chapter
    scheme_payload = {
        "scheme_name": "Faculty High-Impact Incentive Scheme 2026",
        "description": "Incentives for Q1, Q2, Q3, Q4 Scopus journals and IEEE conferences.",
        "min_amount_inr": 15000,
        "max_amount_inr": 100000,
        "eligibility_criteria": "All permanent faculty & PhD scholars",
        "application_deadline": "Rolling (Quarterly Review)",
        "application_link": "https://chitkara.edu.in/grants",
        "research_area": "All Engineering & Applied Sciences",
        "publication_criteria": [
            {"key": "q1_sci", "label": "Scopus / WoS Q1 Journal", "amount_inr": 100000, "amount_usd": 1200},
            {"key": "q2", "label": "Scopus / WoS Q2 Journal", "amount_inr": 50000, "amount_usd": 600},
            {"key": "q3", "label": "Scopus / WoS Q3 Journal", "amount_inr": 25000, "amount_usd": 300},
            {"key": "q4", "label": "Scopus / WoS Q4 Journal", "amount_inr": 15000, "amount_usd": 180},
            {"key": "conference_ieee", "label": "Flagship IEEE Conference Paper", "amount_inr": 20000, "amount_usd": 240},
            {"key": "book_chapter", "label": "Scopus Book Chapter", "amount_inr": 12000, "amount_usd": 145}
        ],
        "accepted_indexing": ["Scopus Q1", "Scopus Q2", "Scopus Q3", "Scopus Q4", "IEEE Conference", "Book Chapter"],
        "reward_tiers": [
            {"tier_name": "Q1 Journal Top 25%", "amount_inr": 100000, "amount_usd": 1200, "criteria": "Published in Q1", "payout_type": "Direct Cash Bounty"}
        ]
    }

    create_scheme_res = client.post("/api/v1/organisations/schemes", headers=headers, json=scheme_payload)
    assert create_scheme_res.status_code in (200, 201), f"Create scheme failed: {create_scheme_res.text}"
    scheme_data = create_scheme_res.json()
    assert scheme_data["scheme_name"] == scheme_payload["scheme_name"]
    scheme_id = scheme_data["id"]

    # 4. List My Schemes
    list_schemes_res = client.get("/api/v1/organisations/schemes", headers=headers)
    assert list_schemes_res.status_code == 200
    assert len(list_schemes_res.json()) >= 1
    assert any(s["id"] == scheme_id for s in list_schemes_res.json())

    # 5. Verify Scheme is now dynamically listed in Public Directory
    public_grants_res = client.get("/api/v1/funding/universities")
    assert public_grants_res.status_code == 200
    public_list = public_grants_res.json()
    assert any(f"org-scheme-{scheme_id}" == u["id"] or org_name in u["name"] for u in public_list)

    # 6. Delete Scheme
    del_res = client.delete(f"/api/v1/organisations/schemes/{scheme_id}", headers=headers)
    assert del_res.status_code == 200
