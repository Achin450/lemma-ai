from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field


class PlanDetail(BaseModel):
    id: str = Field(..., description="Unique plan key: free, pro_monthly, pro_annual, scholar_ultra")
    name: str
    headline: str
    price_inr: float
    price_usd: float
    billing_cycle: str
    discount_label: Optional[str] = None
    badge: Optional[str] = None
    features: list[str]
    limits: dict[str, Any]


class PlanListResponse(BaseModel):
    plans: list[PlanDetail]
    currencies_supported: list[str] = ["INR", "USD"]
    gateways_supported: list[str] = ["razorpay", "stripe", "simulated"]


class SubscriptionResponse(BaseModel):
    id: Optional[str] = None
    plan_id: str
    plan_name: str
    status: str
    billing_cycle: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool = False
    is_pro: bool = False
    payment_gateway: Optional[str] = None
    features: list[str] = []


class UsageQuotaItem(BaseModel):
    used: int
    limit: int  # -1 for unlimited
    remaining: int  # -1 for unlimited
    percentage: float


class UsageQuotaResponse(BaseModel):
    plan_id: str
    is_pro: bool
    plagiarism_scans: UsageQuotaItem
    paper_generations: UsageQuotaItem
    restructures: UsageQuotaItem
    novelty_checks: UsageQuotaItem
    humanizer_words: UsageQuotaItem
    period_start: str
    period_end: str


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID to subscribe to (e.g. pro_monthly, pro_annual, scholar_ultra)")
    currency: str = Field("INR", description="INR or USD")
    gateway: str = Field("razorpay", description="razorpay, stripe, or simulated")
    billing_cycle: Optional[str] = Field("monthly", description="monthly or annual")


class CheckoutResponse(BaseModel):
    order_id: str
    gateway: str
    plan_id: str
    amount: float
    currency: str
    key_id: Optional[str] = None
    client_secret: Optional[str] = None
    upi_intent_url: Optional[str] = None
    upi_qr_data: Optional[str] = None
    supported_card_networks: list[str] = ["Visa", "MasterCard", "RuPay", "American Express", "Maestro"]
    supported_upi_apps: list[str] = ["Google Pay", "PhonePe", "Paytm", "BHIM UPI", "Cred", "Amazon Pay"]
    notes: dict[str, Any] = {}
    is_simulation: bool = False


class PaymentVerificationRequest(BaseModel):
    gateway: str
    order_id: str
    payment_id: Optional[str] = None
    signature: Optional[str] = None
    plan_id: str
    currency: str = "INR"
    payment_method: Optional[str] = "upi"  # "upi" or "card"
    upi_id: Optional[str] = None           # e.g. "scholar@okhdfcbank"
    card_last4: Optional[str] = None       # e.g. "4242"
    card_network: Optional[str] = None     # e.g. "Visa", "MasterCard", "RuPay"
    cardholder_name: Optional[str] = None


class PaymentVerificationResponse(BaseModel):
    success: bool
    message: str
    subscription: SubscriptionResponse
    invoice_number: str
    invoice_id: str
    payment_method_details: Optional[dict[str, Any]] = None


class SubscriptionActionResponse(BaseModel):
    success: bool
    message: str
    subscription: SubscriptionResponse


class InvoiceItemResponse(BaseModel):
    id: str
    invoice_number: str
    amount: float
    currency: str
    status: str
    payment_method: str
    gateway: str
    created_at: str
    description: str
    receipt_url: Optional[str] = None


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceItemResponse]
