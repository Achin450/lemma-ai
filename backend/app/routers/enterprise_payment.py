"""
Enterprise Payment, Purchase Orders & Institutional Billing Router
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse

from app.routers.organisations import get_current_organisation
from app.services.enterprise_payment_service import EnterprisePaymentService
from app.schemas.enterprise_payment import (
    EnterprisePlanDetail, EnterprisePlanListResponse,
    QuoteRequestCreate, QuoteRequestResponse,
    PurchaseOrderCreate, EnterpriseContractResponse,
    EnterpriseInvoiceResponse, EnterpriseInvoiceListResponse,
    OfflinePaymentSubmit, SeatAllocationCreate,
    SeatAllocationItem, SeatListResponse,
    EnterpriseSummaryResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enterprise", tags=["Enterprise Payment & Billing"])


@router.get("/plans", response_model=List[EnterprisePlanDetail])
async def get_enterprise_plans():
    """Retrieve standard institutional tiers (Department, Campus Wide, Custom Institution)."""
    return EnterprisePaymentService.get_plans()


@router.post("/quote-request", response_model=QuoteRequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_quote_request(payload: QuoteRequestCreate):
    """Submit an institutional RFQ / Custom Quote request."""
    return EnterprisePaymentService.submit_quote_request(payload)


@router.post("/contracts/create-po", response_model=EnterpriseContractResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order_contract(
    payload: PurchaseOrderCreate,
    current_org: dict = Depends(get_current_organisation)
):
    """Generate an official Enterprise Contract & Proforma GST Invoice using a Purchase Order."""
    try:
        res = EnterprisePaymentService.create_purchase_order(str(current_org["id"]), payload)
        return res["contract"]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating contract: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process Purchase Order.")


@router.get("/contracts/me", response_model=List[EnterpriseContractResponse])
async def list_my_contracts(current_org: dict = Depends(get_current_organisation)):
    """List all enterprise contracts for the authenticated institution."""
    return EnterprisePaymentService.get_organisation_contracts(str(current_org["id"]))


@router.get("/contracts/{contract_id}", response_model=EnterpriseContractResponse)
async def get_contract_detail(contract_id: str, current_org: dict = Depends(get_current_organisation)):
    """Get details of a specific contract."""
    contract = EnterprisePaymentService.get_contract_by_id(contract_id, str(current_org["id"]))
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enterprise contract not found.")
    return contract


@router.get("/invoices", response_model=List[EnterpriseInvoiceResponse])
async def list_my_invoices(current_org: dict = Depends(get_current_organisation)):
    """List all proforma and paid institutional invoices for the organisation."""
    return EnterprisePaymentService.list_organisation_invoices(str(current_org["id"]))


@router.get("/invoices/{invoice_id}")
async def get_invoice_detail(invoice_id: str, current_org: dict = Depends(get_current_organisation)):
    """Get JSON detail of an invoice."""
    invoice = EnterprisePaymentService.get_invoice_by_id(invoice_id, str(current_org["id"]))
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return invoice


@router.get("/invoices/{invoice_id}/download", response_class=HTMLResponse)
async def download_invoice_html(invoice_id: str, current_org: dict = Depends(get_current_organisation)):
    """Download/render an official, print-ready GST Tax Invoice / Proforma HTML document."""
    invoice = EnterprisePaymentService.get_invoice_by_id(invoice_id, str(current_org["id"]))
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    
    html = EnterprisePaymentService.generate_invoice_html(invoice)
    return HTMLResponse(content=html, status_code=200)


@router.post("/invoices/{invoice_id}/submit-offline-payment", response_model=EnterpriseInvoiceResponse)
async def submit_offline_wire_payment(
    invoice_id: str,
    payload: OfflinePaymentSubmit,
    current_org: dict = Depends(get_current_organisation)
):
    """Submit Bank Wire UTR / Cheque / NEFT reference number after initiating the bank transfer."""
    try:
        return EnterprisePaymentService.submit_offline_payment_ref(
            invoice_id=invoice_id,
            org_id=str(current_org["id"]),
            payment_ref=payload.payment_reference,
            notes=payload.payment_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/invoices/{invoice_id}/verify-payment", response_model=EnterpriseInvoiceResponse)
async def verify_invoice_payment(
    invoice_id: str,
    current_org: dict = Depends(get_current_organisation)
):
    """Verify and confirm payment settlement for an invoice."""
    try:
        return EnterprisePaymentService.mark_invoice_paid(invoice_id, str(current_org["id"]))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/seats", response_model=SeatListResponse)
async def list_allocated_seats(current_org: dict = Depends(get_current_organisation)):
    """List all allocated seats and institutional capacity."""
    return EnterprisePaymentService.list_campus_seats(str(current_org["id"]))


@router.post("/seats/allocate", response_model=SeatAllocationItem, status_code=status.HTTP_201_CREATED)
async def allocate_campus_seat(
    payload: SeatAllocationCreate,
    current_org: dict = Depends(get_current_organisation)
):
    """Allocate an Enterprise license seat to a faculty member, researcher, or student."""
    try:
        return EnterprisePaymentService.allocate_campus_seat(
            org_id=str(current_org["id"]),
            payload=payload
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error allocating seat: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to allocate seat.")


@router.delete("/seats/{seat_id}", status_code=status.HTTP_200_OK)
async def revoke_campus_seat(
    seat_id: str,
    current_org: dict = Depends(get_current_organisation)
):
    """Revoke a campus seat allocation, returning the license back to the pool."""
    success = EnterprisePaymentService.revoke_campus_seat(org_id=str(current_org["id"]), seat_id=seat_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seat allocation not found.")
    return {"message": "Seat successfully revoked and license returned to pool.", "seat_id": seat_id}


@router.get("/summary", response_model=EnterpriseSummaryResponse)
async def get_enterprise_overview(current_org: dict = Depends(get_current_organisation)):
    """Retrieve full dashboard summary for institutional enterprise management."""
    return EnterprisePaymentService.get_enterprise_summary(str(current_org["id"]))
