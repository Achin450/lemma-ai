"""
Enterprise Payment, Institutional Contracts, & Campus Seat Licensing Schemas
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EnterprisePlanDetail(BaseModel):
    id: str = Field(..., description="e.g. enterprise_department, enterprise_campus, enterprise_custom")
    name: str
    headline: str
    target_audience: str
    seats_included: int = Field(..., description="Number of bundled campus seats (-1 for unlimited)")
    price_inr: float
    price_usd: float
    billing_cycle: str = "annual"
    badge: Optional[str] = None
    features: List[str]
    sla: str
    payment_methods_accepted: List[str] = [
        "Purchase Order (Net-30 / Net-60)",
        "Bank Wire / NEFT / RTGS / SWIFT",
        "GST Tax Invoicing",
        "Institutional Cheque"
    ]
    limits: Dict[str, Any]


class EnterprisePlanListResponse(BaseModel):
    plans: List[EnterprisePlanDetail]
    institutional_payment_terms: List[str] = ["Net 30 Days", "Net 60 Days", "Annual Advance Wire"]
    supported_bank_wire: Dict[str, str] = {
        "beneficiary_name": "Lemma AI Technologies Private Limited",
        "bank_name": "HDFC Bank Ltd.",
        "account_type": "Institutional Current Account",
        "account_number": "50200084920194",
        "ifsc_code": "HDFC0001234",
        "swift_code": "HDFCINBB",
        "branch": "Technology & Science Park Branch, Bangalore, India"
    }


class QuoteRequestCreate(BaseModel):
    organisation_name: str = Field(..., min_length=2, description="University / Institution name")
    domain_email: str = Field(..., description="Official domain email of Dean or Procurement Officer")
    contact_person: str = Field(..., min_length=2, description="Full name of representative")
    contact_phone: Optional[str] = Field(None, description="Phone / WhatsApp number")
    estimated_seats: int = Field(500, ge=10, description="Estimated faculty and student seats needed")
    requested_tier: str = Field("enterprise_campus", description="enterprise_department, enterprise_campus, or enterprise_custom")
    requirements: Optional[str] = Field(None, description="Custom requirements")


class QuoteRequestResponse(BaseModel):
    id: str
    organisation_name: str
    domain_email: str
    contact_person: str
    estimated_seats: int
    requested_tier: str
    status: str
    created_at: str
    message: str = "Quote request received. An institutional solution engineer will prepare formal pricing within 1 business day."


class PurchaseOrderCreate(BaseModel):
    plan_id: str = Field(..., description="enterprise_department, enterprise_campus, or enterprise_custom")
    po_number: str = Field(..., min_length=3, description="Official University Purchase Order (PO) Number")
    gstin_tax_id: Optional[str] = Field(None, description="Organisation GSTIN or National Tax Identification Number")
    billing_contact_name: str = Field(..., description="Name of Accounts / Finance Officer")
    billing_contact_email: str = Field(..., description="Finance email for invoice delivery")
    billing_address: str = Field(..., description="Official institutional billing address")
    payment_terms: str = Field("Net-30", description="'Net-30', 'Net-60', or 'advance_wire'")
    custom_seats: Optional[int] = Field(None, ge=10, description="Optional custom seat quantity")
    currency: str = Field("INR", description="INR or USD")


class EnterpriseContractResponse(BaseModel):
    id: str
    organisation_id: str
    contract_number: str
    plan_id: str
    plan_name: str
    total_seats: int
    allocated_seats: int
    status: str
    billing_cycle: str
    contract_value_inr: float
    contract_value_usd: float
    payment_terms: str
    payment_status: str
    po_number: Optional[str] = None
    gstin_tax_id: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_contact_email: Optional[str] = None
    billing_address: Optional[str] = None
    start_date: str
    end_date: str
    created_at: str


class EnterpriseInvoiceResponse(BaseModel):
    id: str
    contract_id: str
    organisation_id: str
    invoice_number: str
    invoice_type: str
    subtotal_inr: float
    tax_inr: float
    total_inr: float
    subtotal_usd: float
    total_usd: float
    currency: str
    status: str
    due_date: str
    po_reference: Optional[str] = None
    bank_details: Dict[str, Any] = {}
    payment_reference: Optional[str] = None
    payment_notes: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str


class EnterpriseInvoiceListResponse(BaseModel):
    invoices: List[EnterpriseInvoiceResponse]


class OfflinePaymentSubmit(BaseModel):
    payment_reference: str = Field(..., min_length=4, description="Bank Transaction ID / UTR Number / Cheque Number / Wire Reference")
    payment_notes: Optional[str] = Field(None, description="Payment bank name, date of transfer, or remittance details")


class SeatAllocationCreate(BaseModel):
    user_email: str = Field(..., description="Official domain email of scholar / faculty member")
    user_name: Optional[str] = Field(None, description="Full Name of scholar")
    department: str = Field("Academic Faculty", description="Department / Research Division")
    seat_role: str = Field("faculty", description="'faculty', 'phd_scholar', 'student', or 'researcher'")


class SeatAllocationItem(BaseModel):
    id: str
    contract_id: str
    organisation_id: str
    user_id: Optional[str] = None
    user_email: str
    user_name: Optional[str] = None
    department: str
    seat_role: str
    status: str
    assigned_at: str


class SeatListResponse(BaseModel):
    total_seats: int
    allocated_seats: int
    available_seats: int
    seats: List[SeatAllocationItem]


class EnterpriseSummaryResponse(BaseModel):
    contract: Optional[EnterpriseContractResponse] = None
    total_seats: int = 0
    allocated_seats: int = 0
    available_seats: int = 0
    invoices_count: int = 0
    pending_invoices_count: int = 0
    active_plan: Optional[str] = None
    status: str = "no_contract"
