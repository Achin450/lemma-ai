"""
Unit Tests for Enterprise Edition Payment, Purchase Orders, GST Invoicing & Campus Seat Allocations
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_test_org():
    """Helper to register a test university organisation and return headers and org data."""
    unique_suffix = str(uuid.uuid4())[:8]
    domain_email = f"finance.dean_{unique_suffix}@thapar.edu"
    org_name = f"Thapar Institute {unique_suffix}"

    reg_payload = {
        "name": org_name,
        "short_name": "TIET",
        "official_email": domain_email,
        "password": "StrongPassword2026!",
        "organisation_type": "University",
        "website": "https://www.thapar.edu",
        "contact_person": "Dean Academic Affairs",
        "contact_phone": "+91 9988776655",
        "description": "Institute of Engineering & Technology",
        "country": "India",
        "city": "Patiala"
    }

    reg_res = client.post("/api/v1/organisations/register", json=reg_payload)
    assert reg_res.status_code in (200, 201), f"Org registration failed: {reg_res.text}"
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, reg_res.json()["organisation"]


def test_get_enterprise_plans():
    """Verify that standard institutional tiers are returned with seat counts, pricing and features."""
    res = client.get("/api/v1/enterprise/plans")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) >= 3
    plan_ids = [p["id"] for p in plans]
    assert "enterprise_department" in plan_ids
    assert "enterprise_campus" in plan_ids
    assert "enterprise_custom" in plan_ids

    campus_plan = next(p for p in plans if p["id"] == "enterprise_campus")
    assert campus_plan["seats_included"] == 5000
    assert "👥" in campus_plan["features"][0] or "🏫" in campus_plan["features"][0]


def test_quote_request_submission():
    """Verify RFQ / Custom quotation request submission."""
    payload = {
        "organisation_name": "Indian Institute of Science",
        "contact_person": "Prof. Rao",
        "domain_email": "dean.rd@iisc.ac.in",
        "contact_phone": "+91 8022932000",
        "estimated_seats": 2500,
        "requested_tier": "enterprise_custom",
        "requirements": "Campus-wide deployment for 2,500 postgrads and faculty."
    }
    res = client.post("/api/v1/enterprise/quote-request", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["organisation_name"] == "Indian Institute of Science"
    assert data["estimated_seats"] == 2500
    assert data["status"] == "pending"


def test_enterprise_po_contract_and_invoice_lifecycle():
    """
    Full Enterprise lifecycle:
    1. Submit Purchase Order (PO-2026-TIET-001) for Campus Plan (5000 seats)
    2. Contract generated with Net-30 terms
    3. Proforma GST Tax Invoice generated with HDFC Bank Wire details
    4. Download and verify HTML Invoice document
    5. Submit Bank Wire UTR transaction reference
    6. Verify / mark invoice settled
    """
    headers, org = _register_test_org()

    # 1. Create Contract from PO
    po_payload = {
        "plan_id": "enterprise_campus",
        "po_number": f"PO-2026-TIET-{uuid.uuid4().hex[:6].upper()}",
        "billing_contact_name": "Dr. Accounts Officer",
        "billing_contact_email": org["official_email"],
        "billing_address": "Thapar University Campus, Bhadson Road, Patiala, Punjab 147004",
        "gstin_tax_id": "03AAACT1234F1Z9",
        "payment_terms": "Net-30",
        "currency": "INR"
    }

    contract_res = client.post("/api/v1/enterprise/contracts/create-po", json=po_payload, headers=headers)
    assert contract_res.status_code == 201, f"Contract creation failed: {contract_res.text}"
    contract = contract_res.json()
    assert contract["total_seats"] == 5000
    assert contract["payment_terms"] == "Net-30"
    assert contract["status"] == "active"
    assert contract["contract_number"].startswith("LEMMA-CTR-")
    contract_id = contract["id"]

    # 2. Verify Contract in List
    contracts_res = client.get("/api/v1/enterprise/contracts/me", headers=headers)
    assert contracts_res.status_code == 200
    assert len(contracts_res.json()) >= 1

    # 3. Verify Invoice generated
    invoices_res = client.get("/api/v1/enterprise/invoices", headers=headers)
    assert invoices_res.status_code == 200
    invoices = invoices_res.json()
    assert len(invoices) >= 1
    invoice = invoices[0]
    invoice_id = invoice["id"]
    assert invoice["invoice_number"].startswith("LEMMA-INV-")
    assert invoice["total_inr"] > 0
    assert invoice["status"] == "issued"

    # 4. Download and inspect printable HTML Invoice
    html_res = client.get(f"/api/v1/enterprise/invoices/{invoice_id}/download", headers=headers)
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers.get("content-type", "")
    html_content = html_res.text
    assert "TAX INVOICE / PROFORMA" in html_content
    assert "HDFC Bank Ltd." in html_content
    assert "HDFC0001234" in html_content
    assert invoice["invoice_number"] in html_content

    # 5. Submit Offline Bank Wire UTR Reference
    utr_number = f"UTR{uuid.uuid4().hex[:12].upper()}"
    wire_payload = {
        "payment_reference": utr_number,
        "payment_notes": "NEFT transfer executed against PO reference via State Bank of India."
    }
    submit_wire_res = client.post(f"/api/v1/enterprise/invoices/{invoice_id}/submit-offline-payment", json=wire_payload, headers=headers)
    assert submit_wire_res.status_code == 200
    updated_inv = submit_wire_res.json()
    assert updated_inv["status"] == "pending_verification"
    assert updated_inv["payment_reference"] == utr_number

    # 6. Admin Payment Settlement / Verification
    verify_res = client.post(f"/api/v1/enterprise/invoices/{invoice_id}/verify-payment", headers=headers)
    assert verify_res.status_code == 200
    settled_inv = verify_res.json()
    assert settled_inv["status"] == "paid"


def test_campus_seat_allocation_lifecycle():
    """
    Test seat allocation to faculty members and students:
    1. Allocate seat with matching institutional domain (@thapar.edu)
    2. Attempt seat allocation with foreign mismatch domain (should be rejected)
    3. List allocated seats & overview
    4. Revoke allocated seat
    """
    headers, org = _register_test_org()

    # 1. First create a PO contract to have active seats
    po_payload = {
        "plan_id": "enterprise_department",
        "po_number": f"PO-CSE-{uuid.uuid4().hex[:4].upper()}",
        "billing_contact_name": "Prof. Registrar",
        "billing_contact_email": org["official_email"],
        "billing_address": "Computer Science Block, TIET, Patiala",
        "payment_terms": "Net-30"
    }
    client.post("/api/v1/enterprise/contracts/create-po", json=po_payload, headers=headers)

    # 2. Allocate seat to Faculty member
    faculty_email = f"prof.sharma@{org['domain']}"
    alloc_payload = {
        "user_email": faculty_email,
        "user_name": "Prof. R. K. Sharma",
        "department": "Computer Science & Engineering",
        "seat_role": "faculty"
    }
    alloc_res = client.post("/api/v1/enterprise/seats/allocate", json=alloc_payload, headers=headers)
    assert alloc_res.status_code == 201, f"Allocation failed: {alloc_res.text}"
    seat = alloc_res.json()
    assert seat["user_email"] == faculty_email
    assert seat["status"] == "active"
    seat_id = seat["id"]

    # 3. Test Domain mismatch rejection
    foreign_payload = {
        "user_email": "intruder@otheruniversity.ac.in",
        "user_name": "Foreign Researcher",
        "department": "Biotech",
        "seat_role": "faculty"
    }
    foreign_res = client.post("/api/v1/enterprise/seats/allocate", json=foreign_payload, headers=headers)
    assert foreign_res.status_code == 400
    assert "domain" in foreign_res.json().get("detail", "").lower()

    # 4. List seats
    seats_res = client.get("/api/v1/enterprise/seats", headers=headers)
    assert seats_res.status_code == 200
    seats_data = seats_res.json()
    assert seats_data["total_seats"] == 250
    assert seats_data["allocated_seats"] >= 1
    assert len(seats_data["seats"]) >= 1

    # 5. Summary
    summary_res = client.get("/api/v1/enterprise/summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_seats"] == 250
    assert summary["allocated_seats"] >= 1

    # 6. Revoke Seat
    del_res = client.delete(f"/api/v1/enterprise/seats/{seat_id}", headers=headers)
    assert del_res.status_code == 200
