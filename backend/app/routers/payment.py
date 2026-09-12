import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse

from app.services.auth import get_current_user
from app.services.payment_service import PaymentService, PLANS
from app.schemas.payment import (
    PlanListResponse,
    SubscriptionResponse,
    UsageQuotaResponse,
    CheckoutRequest,
    CheckoutResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    SubscriptionActionResponse,
    InvoiceListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payment", tags=["Personal Account & Payments"])


@router.get("/plans", response_model=PlanListResponse)
def get_available_plans():
    """Returns all available personal subscription plans, pricing, and feature limits."""
    plans = PaymentService.get_plans()
    return PlanListResponse(plans=plans)


@router.get("/subscription", response_model=SubscriptionResponse)
def get_user_subscription(current_user: dict = Depends(get_current_user)):
    """Fetch active subscription details for the logged-in user."""
    user_id = current_user["sub"]
    sub = PaymentService.get_or_create_subscription(user_id)
    plan_meta = PLANS.get(sub.get("plan_id", "free"), PLANS["free"])
    is_pro = sub.get("plan_id") in ("pro_monthly", "pro_annual", "scholar_ultra")

    return SubscriptionResponse(
        id=str(sub["id"]),
        plan_id=sub["plan_id"],
        plan_name=plan_meta["name"],
        status=sub["status"],
        billing_cycle=sub["billing_cycle"],
        current_period_start=str(sub["current_period_start"]),
        current_period_end=str(sub["current_period_end"]),
        cancel_at_period_end=sub.get("cancel_at_period_end", False),
        is_pro=is_pro,
        payment_gateway=sub.get("payment_gateway"),
        features=plan_meta["features"],
    )


@router.get("/usage", response_model=UsageQuotaResponse)
def get_user_usage_quotas(current_user: dict = Depends(get_current_user)):
    """Fetch current period resource usage meters and remaining allowances."""
    user_id = current_user["sub"]
    return PaymentService.get_usage_summary(user_id)


@router.post("/checkout", response_model=CheckoutResponse)
def initiate_checkout(payload: CheckoutRequest, current_user: dict = Depends(get_current_user)):
    """
    Creates a payment checkout order via Razorpay, Stripe, or interactive simulation.
    Returns the order ID and client parameters needed by the frontend checkout dialog.
    """
    user_id = current_user["sub"]
    try:
        order = PaymentService.create_checkout_order(
            user_id=user_id,
            plan_id=payload.plan_id,
            currency=payload.currency,
            gateway=payload.gateway,
            billing_cycle=payload.billing_cycle or "monthly",
        )
        return order
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))
    except Exception as ex:
        logger.exception("Checkout initiation error:")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize checkout.")


@router.post("/verify", response_model=PaymentVerificationResponse)
def verify_payment(payload: PaymentVerificationRequest, current_user: dict = Depends(get_current_user)):
    """
    Verifies payment completion, immediately elevates the user account to Pro,
    generates a tax invoice, and replenishes allowances.
    """
    user_id = current_user["sub"]
    try:
        res = PaymentService.verify_and_activate_payment(
            user_id=user_id,
            gateway=payload.gateway,
            order_id=payload.order_id,
            payment_id=payload.payment_id,
            signature=payload.signature,
            plan_id=payload.plan_id,
            currency=payload.currency,
            payment_method=payload.payment_method or "upi",
            upi_id=payload.upi_id,
            card_last4=payload.card_last4,
            card_network=payload.card_network,
            cardholder_name=payload.cardholder_name,
        )
        return res
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))
    except Exception as ex:
        logger.exception("Payment verification error:")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payment verification failed.")


@router.post("/cancel", response_model=SubscriptionActionResponse)
def cancel_subscription(current_user: dict = Depends(get_current_user)):
    """Flags active subscription to cancel at the end of the billing period."""
    user_id = current_user["sub"]
    sub = PaymentService.cancel_subscription(user_id)
    return SubscriptionActionResponse(
        success=True,
        message="Subscription will end at the close of the current billing cycle. You retain full Pro access until then.",
        subscription=sub,
    )


@router.post("/reactivate", response_model=SubscriptionActionResponse)
def reactivate_subscription(current_user: dict = Depends(get_current_user)):
    """Reactivates auto-renewal for a cancelled subscription."""
    user_id = current_user["sub"]
    sub = PaymentService.reactivate_subscription(user_id)
    return SubscriptionActionResponse(
        success=True,
        message="Auto-renewal successfully restored! Your Pro privileges will continue uninterrupted.",
        subscription=sub,
    )


@router.get("/invoices", response_model=InvoiceListResponse)
def list_user_invoices(current_user: dict = Depends(get_current_user)):
    """Returns past payment receipts and downloadable invoices."""
    user_id = current_user["sub"]
    invoices = PaymentService.get_invoices(user_id)
    return InvoiceListResponse(invoices=invoices)


@router.get("/invoices/{invoice_number}/download", response_class=HTMLResponse)
def download_invoice(invoice_number: str, current_user: dict = Depends(get_current_user)):
    """Returns a printable HTML/PDF receipt for the specified invoice."""
    user_id = current_user["sub"]
    try:
        html = PaymentService.generate_invoice_html(invoice_number, user_id=user_id)
        return HTMLResponse(content=html)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")


@router.post("/webhook/{gateway}")
async def payment_webhook(gateway: str, request: Request):
    """Webhook ingestion endpoint for payment gateways (Razorpay, Stripe)."""
    try:
        body = await request.json()
        logger.info(f"Received webhook for gateway {gateway}: {body}")
        return {"received": True, "gateway": gateway}
    except Exception as e:
        logger.error(f"Error handling webhook for {gateway}: {e}")
        return {"received": False, "error": str(e)}
