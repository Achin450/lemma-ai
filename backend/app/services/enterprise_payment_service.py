"""
Enterprise Payment, Purchase Orders, Institutional Invoices & Seat Allocation Service
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import psycopg2.extras
from app.config import settings
from app.services.database import DatabaseService
from app.schemas.enterprise_payment import (
    EnterprisePlanDetail,
    QuoteRequestCreate,
    QuoteRequestResponse,
    PurchaseOrderCreate,
    EnterpriseContractResponse,
    EnterpriseInvoiceResponse,
    SeatAllocationCreate,
    SeatAllocationItem,
    SeatListResponse,
    EnterpriseSummaryResponse,
)

logger = logging.getLogger(__name__)

ENTERPRISE_PLANS: Dict[str, Dict[str, Any]] = {
    "enterprise_department": {
        "id": "enterprise_department",
        "name": "Department Edition (250 Seats)",
        "headline": "Full-stack academic integrity & research suite for academic departments and specialized research labs.",
        "target_audience": "Academic Departments, PG Programs & Research Labs",
        "seats_included": 250,
        "price_inr": 49999.0,
        "price_usd": 699.0,
        "billing_cycle": "annual",
        "badge": "Departmental License",
        "sla": "99.5% Uptime SLA • Next Business Day Support",
        "limits": {
            "plagiarism_scans": 5000,
            "paper_generations": 1500,
            "restructures": 2500,
            "novelty_checks": 2500,
            "humanizer_words": 1000000,
            "seats": 250,
            "api_keys": 3,
            "lti_lms_integration": True,
        },
        "features": [
            "👥 250 Enterprise Scholar & Faculty Seats",
            "🔍 5,000 High-Throughput Plagiarism & Similarity Scans / yr",
            "📄 2,500 IEEE/Springer Research Restructures / yr",
            "🎓 Canvas, Moodle & Blackboard LTI 1.3 LMS Integration",
            "📑 Net-30 Institutional Purchase Order (PO) & GST Invoicing",
            "🏛️ Multi-Department Quota Management Console",
            "⚡ Priority Multi-GPU Processing Queue",
            "🔒 100% On-Campus Data Privacy & Zero-Retention Option"
        ]
    },
    "enterprise_campus": {
        "id": "enterprise_campus",
        "name": "Campus-Wide Edition (5,000 Seats)",
        "headline": "Unrestricted university-wide deployment with dedicated neural models and centralized administrative control.",
        "target_audience": "Universities, Institutes of National Importance & Large Colleges",
        "seats_included": 5000,
        "price_inr": 199999.0,
        "price_usd": 2499.0,
        "billing_cycle": "annual",
        "badge": "Most Popular for Universities",
        "sla": "99.9% Uptime SLA • 24/7 Dedicated Support Engineer",
        "limits": {
            "plagiarism_scans": -1,
            "paper_generations": -1,
            "restructures": -1,
            "novelty_checks": -1,
            "humanizer_words": -1,
            "seats": 5000,
            "api_keys": 10,
            "lti_lms_integration": True,
            "on_premise_ollama": True,
        },
        "features": [
            "🏫 5,000 Campus-Wide Student & Faculty Seats",
            "♾️ Unlimited Plagiarism, Novelty & Research Generation",
            "🤖 Dedicated On-Premise GPU or Private VPC Neural Engine",
            "🎓 Full Single Sign-On (SSO / SAML 2.0 / Google Workspace)",
            "📊 Executive Dean Analytics & Accreditation Audit Reports",
            "💰 Institutional Publishing Grants & Bounty Pool Manager",
            "📜 Official GST Tax Invoice, Net-60 PO & Wire Remittance",
            "🛡️ Custom Institutional Repository Federation & Private Archive",
            "📞 Dedicated Account Manager & Live Campus Training Workshops"
        ]
    },
    "enterprise_custom": {
        "id": "enterprise_custom",
        "name": "Consortium & State Scale (Unlimited Seats)",
        "headline": "Tailored multi-campus infrastructure for state university networks and large research conglomerates.",
        "target_audience": "University Systems, State Higher Education Boards & Research Consortia",
        "seats_included": -1,
        "price_inr": 499999.0,
        "price_usd": 5999.0,
        "billing_cycle": "annual",
        "badge": "State / Consortium",
        "sla": "99.99% Financial Uptime SLA • Dedicated Engineering Team",
        "limits": {
            "plagiarism_scans": -1,
            "paper_generations": -1,
            "restructures": -1,
            "novelty_checks": -1,
            "humanizer_words": -1,
            "seats": -1,
            "api_keys": 50,
            "lti_lms_integration": True,
            "on_premise_ollama": True,
        },
        "features": [
            "🌐 Unlimited Multi-Campus & Affiliate College Seats",
            "🚀 High-Density Clustering & Bare-Metal GPU Orchestration",
            "🏛️ Centralized State Procurement Billing & Custom Net-90 Terms",
            "📚 Custom Domain LLM Fine-Tuning on University Archives",
            "🔐 Air-Gapped / Sovereign Cloud Compliance (HIPAA, FERPA, GDPR)",
            "💼 Custom Legal Master Services Agreement (MSA) & Custom DPA"
        ]
    }
}

BANK_WIRE_DETAILS = {
    "beneficiary_name": "Lemma AI Technologies Private Limited",
    "bank_name": "HDFC Bank Ltd.",
    "account_number": "50200084920194",
    "account_type": "Institutional Current Account",
    "ifsc_code": "HDFC0001234",
    "swift_code": "HDFCINBB",
    "branch_address": "Technology & Science Park Branch, Outer Ring Road, Bangalore - 560103, India",
    "pan_number": "AAACL8492K",
    "gstin": "29AAACL8492K1ZX"
}


class EnterprisePaymentService:
    """Manages Enterprise Contracts, Purchase Orders, Invoices, Bank Transfers, and Seat Allocations."""

    @classmethod
    def get_plans(cls) -> List[EnterprisePlanDetail]:
        return [
            EnterprisePlanDetail(
                id=p["id"],
                name=p["name"],
                headline=p["headline"],
                target_audience=p["target_audience"],
                seats_included=p["seats_included"],
                price_inr=p["price_inr"],
                price_usd=p["price_usd"],
                billing_cycle=p["billing_cycle"],
                badge=p.get("badge"),
                features=p["features"],
                sla=p["sla"],
                limits=p["limits"],
            )
            for p in ENTERPRISE_PLANS.values()
        ]

    @classmethod
    def submit_quote_request(cls, req: QuoteRequestCreate) -> QuoteRequestResponse:
        quote_id = str(uuid.uuid4())
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO enterprise_quote_requests (
                        id, organisation_name, domain_email, contact_person,
                        contact_phone, estimated_seats, requested_tier, requirements, status
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, 'pending'
                    ) RETURNING *
                """, (
                    quote_id, req.organisation_name.strip(), req.domain_email.strip().lower(),
                    req.contact_person.strip(), req.contact_phone, req.estimated_seats,
                    req.requested_tier, req.requirements
                ))
                row = cur.fetchone()
            conn.commit()

        return QuoteRequestResponse(
            id=str(row["id"]),
            organisation_name=row["organisation_name"],
            domain_email=row["domain_email"],
            contact_person=row["contact_person"],
            estimated_seats=row["estimated_seats"],
            requested_tier=row["requested_tier"],
            status=row["status"],
            created_at=str(row["created_at"]),
        )

    @classmethod
    def create_purchase_order(cls, org_id: str, po_data: PurchaseOrderCreate) -> Dict[str, Any]:
        plan = ENTERPRISE_PLANS.get(po_data.plan_id, ENTERPRISE_PLANS["enterprise_department"])
        
        contract_id = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        
        year = datetime.now().year
        rand_suffix = str(uuid.uuid4().hex[:6]).upper()
        contract_number = f"LEMMA-CTR-{year}-{rand_suffix}"
        invoice_number = f"LEMMA-INV-{year}-{rand_suffix}"

        seats = po_data.custom_seats if (po_data.custom_seats and po_data.custom_seats > 0) else plan["seats_included"]
        val_inr = plan["price_inr"]
        val_usd = plan["price_usd"]
        tax_inr = round(val_inr * 0.18, 2)
        total_inr = round(val_inr + tax_inr, 2)
        total_usd = val_usd

        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. Create Enterprise Contract
                cur.execute("""
                    INSERT INTO enterprise_contracts (
                        id, organisation_id, contract_number, plan_id, plan_name,
                        total_seats, allocated_seats, status, billing_cycle,
                        contract_value_inr, contract_value_usd, payment_terms,
                        payment_status, po_number, gstin_tax_id, billing_contact_name,
                        billing_contact_email, billing_address, start_date, end_date
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, 0, 'active', 'annual',
                        %s, %s, %s,
                        'unpaid', %s, %s, %s,
                        %s, %s, NOW(), NOW() + INTERVAL '365 days'
                    ) RETURNING *
                """, (
                    contract_id, org_id, contract_number, plan["id"], plan["name"],
                    seats, val_inr, val_usd, po_data.payment_terms,
                    po_data.po_number, po_data.gstin_tax_id, po_data.billing_contact_name,
                    po_data.billing_contact_email, po_data.billing_address
                ))
                contract_row = cur.fetchone()

                # 2. Create Proforma Tax Invoice
                import json
                cur.execute("""
                    INSERT INTO enterprise_invoices (
                        id, contract_id, organisation_id, invoice_number, invoice_type,
                        subtotal_inr, tax_inr, total_inr, subtotal_usd, total_usd,
                        currency, status, due_date, po_reference, bank_details
                    ) VALUES (
                        %s, %s, %s, %s, 'proforma',
                        %s, %s, %s, %s, %s,
                        %s, 'issued', NOW() + INTERVAL '30 days', %s, %s::jsonb
                    ) RETURNING *
                """, (
                    inv_id, contract_id, org_id, invoice_number,
                    val_inr, tax_inr, total_inr, val_usd, total_usd,
                    po_data.currency, po_data.po_number, json.dumps(BANK_WIRE_DETAILS)
                ))
                inv_row = cur.fetchone()
            conn.commit()

        return {
            "contract": cls._build_contract_response(contract_row),
            "invoice": cls._build_invoice_response(inv_row),
            "bank_details": BANK_WIRE_DETAILS
        }

    @classmethod
    def get_organisation_contracts(cls, org_id: str) -> List[EnterpriseContractResponse]:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM enterprise_contracts
                    WHERE organisation_id = %s
                    ORDER BY created_at DESC
                """, (org_id,))
                rows = cur.fetchall()
                return [cls._build_contract_response(r) for r in rows]

    @classmethod
    def get_contract_by_id(cls, contract_id: str, org_id: Optional[str] = None) -> Optional[EnterpriseContractResponse]:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if org_id:
                    cur.execute("SELECT * FROM enterprise_contracts WHERE id = %s AND organisation_id = %s", (contract_id, org_id))
                else:
                    cur.execute("SELECT * FROM enterprise_contracts WHERE id = %s", (contract_id,))
                row = cur.fetchone()
                if row:
                    return cls._build_contract_response(row)
        return None

    @classmethod
    def list_organisation_invoices(cls, org_id: str) -> List[EnterpriseInvoiceResponse]:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM enterprise_invoices
                    WHERE organisation_id = %s
                    ORDER BY created_at DESC
                """, (org_id,))
                rows = cur.fetchall()
                return [cls._build_invoice_response(r) for r in rows]

    @classmethod
    def get_invoice_by_id(cls, invoice_id: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if org_id:
                    cur.execute("""
                        SELECT i.*, o.name AS org_name, o.domain_email, o.domain, o.website,
                               c.contract_number, c.plan_name, c.total_seats, c.po_number,
                               c.gstin_tax_id, c.billing_address, c.billing_contact_name, c.billing_contact_email
                        FROM enterprise_invoices i
                        JOIN organisations o ON i.organisation_id = o.id
                        JOIN enterprise_contracts c ON i.contract_id = c.id
                        WHERE i.id = %s AND i.organisation_id = %s
                    """, (invoice_id, org_id))
                else:
                    cur.execute("""
                        SELECT i.*, o.name AS org_name, o.domain_email, o.domain, o.website,
                               c.contract_number, c.plan_name, c.total_seats, c.po_number,
                               c.gstin_tax_id, c.billing_address, c.billing_contact_name, c.billing_contact_email
                        FROM enterprise_invoices i
                        JOIN organisations o ON i.organisation_id = o.id
                        JOIN enterprise_contracts c ON i.contract_id = c.id
                        WHERE i.id = %s
                    """, (invoice_id,))
                return cur.fetchone()

    @classmethod
    def submit_offline_payment_ref(cls, invoice_id: str, org_id: str, payment_ref: str, notes: Optional[str] = None) -> EnterpriseInvoiceResponse:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    UPDATE enterprise_invoices
                    SET payment_reference = %s,
                        payment_notes = %s,
                        status = 'pending_verification'
                    WHERE id = %s AND organisation_id = %s
                    RETURNING *
                """, (payment_ref.strip(), notes, invoice_id, org_id))
                inv_row = cur.fetchone()
            conn.commit()

        if not inv_row:
            raise ValueError("Invoice not found or access denied.")

        return cls._build_invoice_response(inv_row)

    @classmethod
    def mark_invoice_paid(cls, invoice_id: str, org_id: Optional[str] = None) -> EnterpriseInvoiceResponse:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "UPDATE enterprise_invoices SET status = 'paid', paid_at = NOW() WHERE id = %s"
                params = [invoice_id]
                if org_id:
                    query += " AND organisation_id = %s"
                    params.append(org_id)
                query += " RETURNING *"
                cur.execute(query, tuple(params))
                inv_row = cur.fetchone()

                if inv_row:
                    cur.execute("""
                        UPDATE enterprise_contracts
                        SET payment_status = 'paid'
                        WHERE id = %s
                    """, (inv_row["contract_id"],))
            conn.commit()

        if not inv_row:
            raise ValueError("Invoice not found.")

        return cls._build_invoice_response(inv_row)

    @classmethod
    def allocate_campus_seat(cls, org_id: str, payload: SeatAllocationCreate) -> SeatAllocationItem:
        email = payload.user_email.strip().lower()
        
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 0. Check org domain
                cur.execute("SELECT domain FROM organisations WHERE id = %s", (org_id,))
                org_row = cur.fetchone()
                if not org_row:
                    raise ValueError("Organisation not found.")
                org_domain = org_row["domain"].lower()

                email_domain = email.split("@")[-1].lower()
                if email_domain != org_domain and not email_domain.endswith("." + org_domain):
                    raise ValueError(f"Email domain (@{email_domain}) does not match organisation institutional domain (@{org_domain}).")

                # 1. Fetch active contract
                cur.execute("""
                    SELECT * FROM enterprise_contracts
                    WHERE organisation_id = %s AND status = 'active'
                    ORDER BY created_at DESC LIMIT 1
                """, (org_id,))
                contract = cur.fetchone()
                if not contract:
                    raise ValueError("No active enterprise contract found. Please submit a Purchase Order first.")

                # Check seat quota
                if contract["total_seats"] != -1 and contract["allocated_seats"] >= contract["total_seats"]:
                    raise ValueError(f"Seat limit reached ({contract['allocated_seats']}/{contract['total_seats']}).")

                # Check if seat already allocated
                cur.execute("""
                    SELECT * FROM enterprise_seat_allocations
                    WHERE organisation_id = %s AND user_email = %s AND status = 'active'
                """, (org_id, email))
                existing_seat = cur.fetchone()
                if existing_seat:
                    raise ValueError(f"Seat is already allocated to {email}.")

                cur.execute("SELECT id, full_name FROM users WHERE LOWER(email) = %s", (email,))
                user_row = cur.fetchone()
                user_id = str(user_row["id"]) if user_row else None
                user_name = payload.user_name or (user_row["full_name"] if user_row else email.split("@")[0].capitalize())

                seat_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO enterprise_seat_allocations (
                        id, contract_id, organisation_id, user_id, user_email,
                        user_name, department, seat_role, status
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, 'active'
                    ) RETURNING *
                """, (
                    seat_id, contract["id"], org_id, user_id, email,
                    user_name, payload.department, payload.seat_role
                ))
                seat_row = cur.fetchone()

                cur.execute("""
                    UPDATE enterprise_contracts
                    SET allocated_seats = allocated_seats + 1
                    WHERE id = %s
                """, (contract["id"],))

                if user_id:
                    cur.execute("""
                        UPDATE users
                        SET is_pro = TRUE, subscription_tier = 'enterprise_pro'
                        WHERE id = %s
                    """, (user_id,))
            conn.commit()

        return SeatAllocationItem(
            id=str(seat_row["id"]),
            contract_id=str(seat_row["contract_id"]),
            organisation_id=str(seat_row["organisation_id"]),
            user_id=str(seat_row["user_id"]) if seat_row["user_id"] else None,
            user_email=seat_row["user_email"],
            user_name=seat_row["user_name"],
            department=seat_row["department"],
            seat_role=seat_row["seat_role"],
            status=seat_row["status"],
            assigned_at=str(seat_row["assigned_at"]),
        )

    @classmethod
    def list_campus_seats(cls, org_id: str) -> SeatListResponse:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM enterprise_contracts
                    WHERE organisation_id = %s AND status = 'active'
                    ORDER BY created_at DESC LIMIT 1
                """, (org_id,))
                contract = cur.fetchone()
                
                total = contract["total_seats"] if contract else 0
                
                cur.execute("""
                    SELECT * FROM enterprise_seat_allocations
                    WHERE organisation_id = %s AND status = 'active'
                    ORDER BY assigned_at DESC
                """, (org_id,))
                rows = cur.fetchall()

        allocated = len(rows)
        available = -1 if total == -1 else max(0, total - allocated)

        seats = [
            SeatAllocationItem(
                id=str(r["id"]),
                contract_id=str(r["contract_id"]),
                organisation_id=str(r["organisation_id"]),
                user_id=str(r["user_id"]) if r["user_id"] else None,
                user_email=r["user_email"],
                user_name=r["user_name"],
                department=r["department"],
                seat_role=r["seat_role"],
                status=r["status"],
                assigned_at=str(r["assigned_at"]),
            )
            for r in rows
        ]

        return SeatListResponse(
            total_seats=total,
            allocated_seats=allocated,
            available_seats=available,
            seats=seats
        )

    @classmethod
    def revoke_campus_seat(cls, org_id: str, seat_id: str) -> bool:
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM enterprise_seat_allocations
                    WHERE id = %s AND organisation_id = %s AND status = 'active'
                """, (seat_id, org_id))
                seat = cur.fetchone()
                if not seat:
                    return False

                cur.execute("""
                    UPDATE enterprise_seat_allocations
                    SET status = 'revoked'
                    WHERE id = %s
                """, (seat_id,))

                cur.execute("""
                    UPDATE enterprise_contracts
                    SET allocated_seats = GREATEST(0, allocated_seats - 1)
                    WHERE id = %s
                """, (seat["contract_id"],))

                if seat.get("user_id"):
                    cur.execute("""
                        UPDATE users
                        SET is_pro = FALSE, subscription_tier = 'free'
                        WHERE id = %s
                    """, (seat["user_id"],))
            conn.commit()
        return True

    @classmethod
    def get_enterprise_summary(cls, org_id: str) -> EnterpriseSummaryResponse:
        contracts = cls.get_organisation_contracts(org_id)
        active_contract = contracts[0] if contracts else None
        
        invoices = cls.list_organisation_invoices(org_id)
        pending_invoices = [i for i in invoices if i.status != "paid"]
        
        seats_data = cls.list_campus_seats(org_id)

        return EnterpriseSummaryResponse(
            contract=active_contract,
            total_seats=seats_data.total_seats,
            allocated_seats=seats_data.allocated_seats,
            available_seats=seats_data.available_seats,
            invoices_count=len(invoices),
            pending_invoices_count=len(pending_invoices),
            active_plan=active_contract.plan_name if active_contract else None,
            status=active_contract.status if active_contract else "no_contract"
        )

    @classmethod
    def generate_invoice_html(cls, inv: Dict[str, Any]) -> str:
        date_issued = str(inv["created_at"]).split()[0]
        due_date = str(inv["due_date"]).split()[0]
        status_color = "#10b981" if inv["status"] == "paid" else "#f59e0b"
        status_label = "PAID / SETTLED" if inv["status"] == "paid" else "PROFORMA / UNPAID (NET 30)"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Tax Invoice - {inv['invoice_number']}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; padding: 40px; margin: 0; }}
    .invoice-card {{ max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
    .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #6366f1; padding-bottom: 24px; margin-bottom: 28px; }}
    .logo {{ font-size: 24px; font-weight: 800; color: #4338ca; }}
    .badge {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; color: #fff; background: {status_color}; text-transform: uppercase; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 30px; }}
    .table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
    .table th {{ background: #f1f5f9; padding: 12px; text-align: left; font-size: 13px; font-weight: 700; color: #475569; border-bottom: 1px solid #cbd5e1; }}
    .table td {{ padding: 14px 12px; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
    .total-box {{ float: right; width: 280px; margin-bottom: 30px; }}
    .total-row {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; }}
    .total-grand {{ font-size: 18px; font-weight: 800; color: #1e293b; border-top: 2px solid #e2e8f0; padding-top: 8px; }}
    .bank-box {{ clear: both; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin-top: 30px; font-size: 13px; }}
    .footer {{ margin-top: 40px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
</style>
</head>
<body>
<div class="invoice-card">
    <div class="header">
        <div>
            <div class="logo">LEMMA AI TECHNOLOGIES</div>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 13px;">Academic Integrity & Neural Research Platform</p>
            <p style="margin: 2px 0 0 0; color: #64748b; font-size: 12px;">GSTIN: {BANK_WIRE_DETAILS['gstin']} | PAN: {BANK_WIRE_DETAILS['pan_number']}</p>
        </div>
        <div style="text-align: right;">
            <h2 style="margin: 0 0 8px 0; font-size: 20px;">TAX INVOICE / PROFORMA</h2>
            <div class="badge">{status_label}</div>
            <p style="margin: 8px 0 0 0; font-size: 13px; font-weight: 600;">Invoice #: {inv['invoice_number']}</p>
        </div>
    </div>

    <div class="grid-2">
        <div>
            <h4 style="margin: 0 0 6px 0; color: #475569; font-size: 12px; text-transform: uppercase;">Billed To (Organisation):</h4>
            <strong style="font-size: 15px;">{inv.get('org_name', 'University')}</strong>
            <p style="margin: 4px 0; font-size: 13px; color: #334155;">{inv.get('billing_address', 'University Campus')}</p>
            <p style="margin: 2px 0; font-size: 13px; color: #334155;">Contact: {inv.get('billing_contact_name', 'Dean of Research')} ({inv.get('billing_contact_email', inv.get('domain_email'))})</p>
            {f'<p style="margin: 2px 0; font-size: 13px; color: #334155;">GSTIN / Tax ID: {inv["gstin_tax_id"]}</p>' if inv.get('gstin_tax_id') else ''}
        </div>
        <div style="text-align: right;">
            <p style="margin: 4px 0; font-size: 13px;"><strong>Issue Date:</strong> {date_issued}</p>
            <p style="margin: 4px 0; font-size: 13px;"><strong>Payment Due Date:</strong> {due_date}</p>
            <p style="margin: 4px 0; font-size: 13px;"><strong>Contract Ref:</strong> {inv.get('contract_number', 'N/A')}</p>
            <p style="margin: 4px 0; font-size: 13px;"><strong>Purchase Order (PO):</strong> {inv.get('po_reference') or inv.get('po_number') or 'N/A'}</p>
        </div>
    </div>

    <table class="table">
        <thead>
            <tr>
                <th>Description</th>
                <th style="text-align: center;">Campus Seats</th>
                <th style="text-align: center;">Billing Term</th>
                <th style="text-align: right;">Amount (INR)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>
                    <strong>Lemma AI {inv.get('plan_name', 'Enterprise Edition')}</strong><br>
                    <span style="font-size: 12px; color: #64748b;">Campus-wide plagiarism scans, IEEE paper generator, LMS LTI 1.3 & priority GPU queue</span>
                </td>
                <td style="text-align: center;">{inv.get('total_seats', 250)}</td>
                <td style="text-align: center;">Annual</td>
                <td style="text-align: right; font-weight: 600;">₹{inv['subtotal_inr']:,.2f}</td>
            </tr>
        </tbody>
    </table>

    <div class="total-box">
        <div class="total-row">
            <span>Subtotal:</span>
            <span>₹{inv['subtotal_inr']:,.2f}</span>
        </div>
        <div class="total-row">
            <span>GST (18%):</span>
            <span>₹{inv['tax_inr']:,.2f}</span>
        </div>
        <div class="total-row total-grand">
            <span>Total Payable:</span>
            <span style="color: #4338ca;">₹{inv['total_inr']:,.2f}</span>
        </div>
    </div>

    <div class="bank-box">
        <h4 style="margin: 0 0 8px 0; color: #4338ca;">🏛️ Official Bank Wire (NEFT / RTGS / IMPS / SWIFT) Remittance Instructions:</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div><strong>Beneficiary:</strong> {BANK_WIRE_DETAILS['beneficiary_name']}</div>
            <div><strong>Bank Name:</strong> {BANK_WIRE_DETAILS['bank_name']}</div>
            <div><strong>Account Number:</strong> {BANK_WIRE_DETAILS['account_number']}</div>
            <div><strong>Account Type:</strong> {BANK_WIRE_DETAILS['account_type']}</div>
            <div><strong>IFSC Code:</strong> {BANK_WIRE_DETAILS['ifsc_code']}</div>
            <div><strong>SWIFT Code:</strong> {BANK_WIRE_DETAILS['swift_code']}</div>
        </div>
        <p style="margin: 8px 0 0 0; font-size: 12px; color: #64748b;">Please mention Invoice Number <strong>{inv['invoice_number']}</strong> in the payment narration / remarks and submit UTR reference in your Org Portal.</p>
    </div>

    <div class="footer">
        <p>This is a computer-generated institutional tax document authorized by Lemma AI Technologies Pvt. Ltd.</p>
        <p>For billing queries, contact <strong>finance@lemma.ai</strong> or <strong>support@lemma.ai</strong>.</p>
    </div>
</div>
</body>
</html>"""

    @classmethod
    def _build_contract_response(cls, row: dict) -> EnterpriseContractResponse:
        return EnterpriseContractResponse(
            id=str(row["id"]),
            organisation_id=str(row["organisation_id"]),
            contract_number=row["contract_number"],
            plan_id=row["plan_id"],
            plan_name=row["plan_name"],
            total_seats=row["total_seats"],
            allocated_seats=row.get("allocated_seats", 0),
            status=row["status"],
            billing_cycle=row["billing_cycle"],
            contract_value_inr=row["contract_value_inr"],
            contract_value_usd=row["contract_value_usd"],
            payment_terms=row["payment_terms"],
            payment_status=row["payment_status"],
            po_number=row.get("po_number"),
            gstin_tax_id=row.get("gstin_tax_id"),
            billing_contact_name=row.get("billing_contact_name"),
            billing_contact_email=row.get("billing_contact_email"),
            billing_address=row.get("billing_address"),
            start_date=str(row.get("start_date", "")),
            end_date=str(row.get("end_date", "")),
            created_at=str(row.get("created_at", "")),
        )

    @classmethod
    def _build_invoice_response(cls, row: dict) -> EnterpriseInvoiceResponse:
        bank_details = row.get("bank_details")
        if isinstance(bank_details, str):
            import json
            try: bank_details = json.loads(bank_details)
            except Exception: bank_details = BANK_WIRE_DETAILS
        elif not isinstance(bank_details, dict) or not bank_details:
            bank_details = BANK_WIRE_DETAILS

        return EnterpriseInvoiceResponse(
            id=str(row["id"]),
            contract_id=str(row["contract_id"]),
            organisation_id=str(row["organisation_id"]),
            invoice_number=row["invoice_number"],
            invoice_type=row["invoice_type"],
            subtotal_inr=row["subtotal_inr"],
            tax_inr=row.get("tax_inr", 0.0),
            total_inr=row["total_inr"],
            subtotal_usd=row.get("subtotal_usd", 0.0),
            total_usd=row.get("total_usd", 0.0),
            currency=row.get("currency", "INR"),
            status=row["status"],
            due_date=str(row.get("due_date", "")),
            po_reference=row.get("po_reference"),
            bank_details=bank_details,
            payment_reference=row.get("payment_reference"),
            payment_notes=row.get("payment_notes"),
            paid_at=str(row.get("paid_at", "")) if row.get("paid_at") else None,
            created_at=str(row.get("created_at", "")),
        )
