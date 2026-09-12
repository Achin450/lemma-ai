import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.payment_service import PaymentService, PLANS
from app.services.auth import create_access_token
from app.schemas.payment import SubscriptionResponse, InvoiceItemResponse


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, "researcher@university.edu", "student")
    return {"Authorization": f"Bearer {token}"}, user_id


def test_get_plans_public(test_client):
    """Verify that plans endpoint is public and returns canonical tiers."""
    resp = test_client.get("/api/v1/payment/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    plan_ids = [p["id"] for p in data["plans"]]
    assert "free" in plan_ids
    assert "pro_monthly" in plan_ids
    assert "pro_annual" in plan_ids
    assert "scholar_ultra" in plan_ids

    # Check pricing and features
    pro = next(p for p in data["plans"] if p["id"] == "pro_monthly")
    assert pro["price_inr"] == 199.0
    assert pro["price_usd"] == 9.99
    assert len(pro["features"]) >= 5


def test_get_subscription_and_usage_defaults(test_client, auth_headers):
    """Verify default free subscription and quota allocation for new users."""
    headers, user_id = auth_headers

    # Mock DB query for subscription and quota
    mock_sub = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan_id": "free",
        "status": "active",
        "billing_cycle": "free",
        "current_period_start": "2026-09-01T00:00:00Z",
        "current_period_end": "2026-10-01T00:00:00Z",
        "cancel_at_period_end": False,
        "payment_gateway": "simulated",
        "user_is_pro": False,
        "user_tier": "free",
    }

    mock_quota = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-10-01T00:00:00Z",
        "plagiarism_scans_used": 1,
        "paper_generations_used": 0,
        "restructures_used": 2,
        "novelty_checks_used": 0,
        "humanizer_words_used": 300,
    }

    with patch.object(PaymentService, "get_or_create_subscription", return_value=mock_sub), \
         patch.object(PaymentService, "get_or_create_quotas", return_value=mock_quota):
        # 1. Check subscription
        sub_resp = test_client.get("/api/v1/payment/subscription", headers=headers)
        assert sub_resp.status_code == 200
        sub_data = sub_resp.json()
        assert sub_data["plan_id"] == "free"
        assert sub_data["is_pro"] is False

        # 2. Check usage
        usage_resp = test_client.get("/api/v1/payment/usage", headers=headers)
        assert usage_resp.status_code == 200
        usage_data = usage_resp.json()
        assert usage_data["plan_id"] == "free"
        assert usage_data["plagiarism_scans"]["used"] == 1
        assert usage_data["plagiarism_scans"]["limit"] == 5
        assert usage_data["plagiarism_scans"]["remaining"] == 4
        assert usage_data["plagiarism_scans"]["percentage"] == 20.0


def test_checkout_initiation(test_client, auth_headers):
    """Test initiating checkout for monthly and annual plans across gateways."""
    headers, _ = auth_headers

    # INR / Razorpay
    payload_inr = {
        "plan_id": "pro_monthly",
        "currency": "INR",
        "gateway": "razorpay",
        "billing_cycle": "monthly",
    }
    resp = test_client.post("/api/v1/payment/checkout", json=payload_inr, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_id"] == "pro_monthly"
    assert data["amount"] == 199.0
    assert data["currency"] == "INR"
    assert "order_id" in data
    assert "key_id" in data

    # USD / Stripe
    payload_usd = {
        "plan_id": "pro_annual",
        "currency": "USD",
        "gateway": "stripe",
        "billing_cycle": "annual",
    }
    resp_usd = test_client.post("/api/v1/payment/checkout", json=payload_usd, headers=headers)
    assert resp_usd.status_code == 200
    data_usd = resp_usd.json()
    assert data_usd["plan_id"] == "pro_annual"
    assert data_usd["amount"] == 79.99
    assert data_usd["currency"] == "USD"


def test_payment_verification_and_pro_activation(test_client, auth_headers):
    """Test successful verification upgrades user account to Pro and generates invoice."""
    headers, user_id = auth_headers

    mock_resp = {
        "success": True,
        "message": "Successfully upgraded to Lemma Pro (Monthly)! Pro capabilities are active.",
        "subscription": {
            "id": str(uuid.uuid4()),
            "plan_id": "pro_monthly",
            "plan_name": "Lemma Pro (Monthly)",
            "status": "active",
            "billing_cycle": "monthly",
            "current_period_start": "2026-09-12T00:00:00Z",
            "current_period_end": "2026-10-12T00:00:00Z",
            "cancel_at_period_end": False,
            "is_pro": True,
            "payment_gateway": "razorpay",
            "features": PLANS["pro_monthly"]["features"],
        },
        "invoice_number": "INV-202609-AB12CD",
        "invoice_id": str(uuid.uuid4()),
    }

    # 1. Verify UPI Payment with VPA
    with patch.object(PaymentService, "verify_and_activate_payment", return_value=mock_resp) as mock_verify:
        payload_upi = {
            "gateway": "razorpay",
            "order_id": "order_sim_12345",
            "payment_id": "pay_sim_67890",
            "signature": "simulated_sig",
            "plan_id": "pro_monthly",
            "currency": "INR",
            "payment_method": "upi",
            "upi_id": "researcher@okhdfcbank",
        }
        res = test_client.post("/api/v1/payment/verify", json=payload_upi, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["subscription"]["is_pro"] is True
        assert data["subscription"]["plan_id"] == "pro_monthly"
        assert data["invoice_number"].startswith("INV-")
        mock_verify.assert_called_once()
        call_kwargs = mock_verify.call_args.kwargs
        assert call_kwargs["payment_method"] == "upi"
        assert call_kwargs["upi_id"] == "researcher@okhdfcbank"

    # 2. Verify Card Payment with Network and Last4
    with patch.object(PaymentService, "verify_and_activate_payment", return_value=mock_resp) as mock_verify_card:
        payload_card = {
            "gateway": "stripe",
            "order_id": "order_str_998877",
            "payment_id": "pay_str_112233",
            "signature": "simulated_sig",
            "plan_id": "pro_monthly",
            "currency": "USD",
            "payment_method": "card",
            "card_last4": "4242",
            "card_network": "Visa",
            "cardholder_name": "Dr. Jane Doe",
        }
        res_card = test_client.post("/api/v1/payment/verify", json=payload_card, headers=headers)
        assert res_card.status_code == 200
        data_card = res_card.json()
        assert data_card["success"] is True
        mock_verify_card.assert_called_once()
        card_call_kwargs = mock_verify_card.call_args.kwargs
        assert card_call_kwargs["payment_method"] == "card"
        assert card_call_kwargs["card_last4"] == "4242"
        assert card_call_kwargs["card_network"] == "Visa"
        assert card_call_kwargs["cardholder_name"] == "Dr. Jane Doe"


def test_cancel_and_reactivate_subscription(test_client, auth_headers):
    """Test cancelling and reactivating auto-renew on subscription."""
    headers, _ = auth_headers

    mock_sub_cancelled = SubscriptionResponse(
        id=str(uuid.uuid4()),
        plan_id="pro_monthly",
        plan_name="Lemma Pro (Monthly)",
        status="active",
        billing_cycle="monthly",
        current_period_start="2026-09-01T00:00:00Z",
        current_period_end="2026-10-01T00:00:00Z",
        cancel_at_period_end=True,
        is_pro=True,
        payment_gateway="razorpay",
        features=PLANS["pro_monthly"]["features"],
    )

    mock_sub_reactivated = SubscriptionResponse(
        id=str(uuid.uuid4()),
        plan_id="pro_monthly",
        plan_name="Lemma Pro (Monthly)",
        status="active",
        billing_cycle="monthly",
        current_period_start="2026-09-01T00:00:00Z",
        current_period_end="2026-10-01T00:00:00Z",
        cancel_at_period_end=False,
        is_pro=True,
        payment_gateway="razorpay",
        features=PLANS["pro_monthly"]["features"],
    )

    with patch.object(PaymentService, "cancel_subscription", return_value=mock_sub_cancelled):
        cancel_res = test_client.post("/api/v1/payment/cancel", headers=headers)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["subscription"]["cancel_at_period_end"] is True

    with patch.object(PaymentService, "reactivate_subscription", return_value=mock_sub_reactivated):
        reactivate_res = test_client.post("/api/v1/payment/reactivate", headers=headers)
        assert reactivate_res.status_code == 200
        assert reactivate_res.json()["subscription"]["cancel_at_period_end"] is False


def test_invoices_and_download(test_client, auth_headers):
    """Test listing user invoices and generating printable HTML receipt."""
    headers, _ = auth_headers

    mock_invoices = [
        InvoiceItemResponse(
            id=str(uuid.uuid4()),
            invoice_number="INV-202609-TEST01",
            amount=199.0,
            currency="INR",
            status="succeeded",
            payment_method="upi",
            gateway="razorpay",
            created_at="2026-09-12 11:30:00",
            description="Lemma AI Pro Plan Subscription (₹199.00)",
            receipt_url="/api/v1/payment/invoices/INV-202609-TEST01/download",
        )
    ]

    mock_html = "<html><body><h1>Lemma AI Academic Receipt</h1><p>PAID IN FULL</p></body></html>"

    with patch.object(PaymentService, "get_invoices", return_value=mock_invoices), \
         patch.object(PaymentService, "generate_invoice_html", return_value=mock_html):
        # List invoices
        list_res = test_client.get("/api/v1/payment/invoices", headers=headers)
        assert list_res.status_code == 200
        inv_data = list_res.json()
        assert len(inv_data["invoices"]) == 1
        assert inv_data["invoices"][0]["invoice_number"] == "INV-202609-TEST01"

        # Download invoice
        dl_res = test_client.get("/api/v1/payment/invoices/INV-202609-TEST01/download", headers=headers)
        assert dl_res.status_code == 200
        assert "PAID IN FULL" in dl_res.text


def test_webhook_endpoint(test_client):
    """Test webhook receiver."""
    payload = {"event": "payment.captured", "id": "pay_test_123"}
    resp = test_client.post("/api/v1/payment/webhook/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["received"] is True
