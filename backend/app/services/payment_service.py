import os
import uuid
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

import psycopg2.extras
from app.config import settings
from app.services.database import DatabaseService
from app.schemas.payment import (
    PlanDetail,
    SubscriptionResponse,
    UsageQuotaItem,
    UsageQuotaResponse,
    CheckoutResponse,
    PaymentVerificationResponse,
    InvoiceItemResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical Personal Account Plan Definitions
# ---------------------------------------------------------------------------
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free Explorer",
        "headline": "Essential academic writing and basic integrity verification for students.",
        "price_inr": 0.0,
        "price_usd": 0.0,
        "billing_cycle": "free",
        "badge": "Free Forever",
        "discount_label": None,
        "limits": {
            "plagiarism_scans": 5,
            "paper_generations": 3,
            "restructures": 3,
            "novelty_checks": 5,
            "humanizer_words": 1500,
            "priority_queue": False,
            "ad_free": False,
            "camera_ready_export": False,
        },
        "features": [
            "5 Plagiarism & similarity checks / month",
            "3 IEEE Paper Restructurings / month",
            "3 AI Paper Generations / month",
            "Standard queue processing speed",
            "Ad-supported research workspace",
            "Basic text & Markdown exports",
        ],
    },
    "pro_monthly": {
        "id": "pro_monthly",
        "name": "Lemma Pro (Monthly)",
        "headline": "Dedicated GPU compute and unrestricted research tools for active scholars.",
        "price_inr": 199.0,
        "price_usd": 9.99,
        "billing_cycle": "monthly",
        "badge": "Most Popular",
        "discount_label": None,
        "limits": {
            "plagiarism_scans": 150,
            "paper_generations": 50,
            "restructures": 100,
            "novelty_checks": 100,
            "humanizer_words": 50000,
            "priority_queue": True,
            "ad_free": True,
            "camera_ready_export": True,
        },
        "features": [
            "🚫 100% Ad-Free Research Studio",
            "⚡ 3x Faster Priority GPU & LLM Queue",
            "📄 100 Monthly IEEE & Springer Paper Restructures",
            "🔍 150 Dual-Tier Similarity & Plagiarism Scans",
            "💾 Unlimited Camera-Ready PDF, DOCX & BibTeX Exports",
            "💡 Novelty Claim Analysis & Rebuttal Advisor",
            "✉️ Priority Researcher Email Support",
        ],
    },
    "pro_annual": {
        "id": "pro_annual",
        "name": "Lemma Pro (Annual)",
        "headline": "All Pro capabilities with substantial 20% annual savings for researchers.",
        "price_inr": 1999.0,
        "price_usd": 79.99,
        "billing_cycle": "annual",
        "badge": "Best Value (Save 20%)",
        "discount_label": "Save 20%",
        "limits": {
            "plagiarism_scans": 500,
            "paper_generations": 200,
            "restructures": 350,
            "novelty_checks": 350,
            "humanizer_words": 200000,
            "priority_queue": True,
            "ad_free": True,
            "camera_ready_export": True,
        },
        "features": [
            "🚫 100% Ad-Free Research Studio",
            "⚡ Top Priority GPU & Multi-Agent Queue",
            "📄 350 IEEE & Springer Restructures / month",
            "🔍 500 Plagiarism & Similarity Scans / month",
            "💾 Unlimited Camera-Ready PDF, DOCX & BibTeX Exports",
            "🛡️ Cryptographically Signed Integrity Certificates",
            "🌟 Early Access to Next-Gen Deep Reasoning Models",
            "🎯 Dedicated 1-on-1 Academic Tech Support",
        ],
    },
    "scholar_ultra": {
        "id": "scholar_ultra",
        "name": "Scholar Ultra (Lab & Faculty)",
        "headline": "High-throughput synthesis, unlimited checks, and API keys for faculty and labs.",
        "price_inr": 4999.0,
        "price_usd": 199.00,
        "billing_cycle": "annual",
        "badge": "Institutional Grade",
        "discount_label": "Power User",
        "limits": {
            "plagiarism_scans": -1,  # unlimited
            "paper_generations": -1, # unlimited
            "restructures": -1,     # unlimited
            "novelty_checks": -1,    # unlimited
            "humanizer_words": -1,   # unlimited
            "priority_queue": True,
            "ad_free": True,
            "camera_ready_export": True,
        },
        "features": [
            "♾️ Unlimited Scans, Restructures & Generations",
            "🔑 Developer REST API Key Included (10k req/mo)",
            "⚡ Dedicated High-Speed Compute Instance",
            "🚫 100% Zero-Telemetry Enterprise Privacy",
            "📚 Automated Grant & Publication Venue Matching",
            "🎓 Multi-author Lab Collaboration (Up to 5 seats)",
            "📞 Direct Priority Engineer Channel",
        ],
    },
}


class PaymentService:
    """Manages plans, subscriptions, payment gateways, quota limits, and invoices."""

    @classmethod
    def get_plans(cls) -> list[PlanDetail]:
        """Returns the list of all available personal account plans."""
        return [
            PlanDetail(
                id=p["id"],
                name=p["name"],
                headline=p["headline"],
                price_inr=p["price_inr"],
                price_usd=p["price_usd"],
                billing_cycle=p["billing_cycle"],
                discount_label=p.get("discount_label"),
                badge=p.get("badge"),
                features=p["features"],
                limits=p["limits"],
            )
            for p in PLANS.values()
        ]

    @classmethod
    def get_or_create_subscription(cls, user_id: str) -> dict:
        """Fetch active user subscription; provisions default 'free' plan if none exists."""
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT s.*, u.is_pro AS user_is_pro, u.subscription_tier AS user_tier
                       FROM subscriptions s
                       JOIN users u ON s.user_id = u.id
                       WHERE s.user_id = %s
                       ORDER BY s.created_at DESC
                       LIMIT 1""",
                    (user_id,),
                )
                sub = cur.fetchone()

                if not sub:
                    # Check user row to see if tier was set directly
                    cur.execute("SELECT id, subscription_tier, is_pro FROM users WHERE id = %s", (user_id,))
                    u = cur.fetchone()
                    tier = (u and u.get("subscription_tier")) or "free"
                    is_pro = bool(u and (u.get("is_pro") or tier in ("pro_monthly", "pro_annual", "scholar_ultra")))

                    sub_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    end_time = now + (timedelta(days=365) if "annual" in tier else timedelta(days=30))
                    billing_cycle = "annual" if "annual" in tier else ("monthly" if "monthly" in tier else "free")

                    cur.execute(
                        """INSERT INTO subscriptions 
                           (id, user_id, plan_id, status, billing_cycle, current_period_start, current_period_end, payment_gateway)
                           VALUES (%s, %s, %s, 'active', %s, %s, %s, 'simulated')
                           RETURNING *""",
                        (sub_id, user_id, tier, billing_cycle, now, end_time),
                    )
                    sub = cur.fetchone()
                    sub["user_is_pro"] = is_pro
                    sub["user_tier"] = tier
            conn.commit()

        return dict(sub)

    @classmethod
    def get_or_create_quotas(cls, user_id: str) -> dict:
        """Fetches or resets user usage counters for the current period."""
        now = datetime.now(timezone.utc)
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM user_quotas WHERE user_id = %s", (user_id,))
                quota = cur.fetchone()

                if not quota:
                    quota_id = str(uuid.uuid4())
                    end_time = now + timedelta(days=30)
                    cur.execute(
                        """INSERT INTO user_quotas (id, user_id, period_start, period_end)
                           VALUES (%s, %s, %s, %s)
                           RETURNING *""",
                        (quota_id, user_id, now, end_time),
                    )
                    quota = cur.fetchone()
                elif quota.get("period_end") and quota["period_end"] < now:
                    # Period has expired: reset quotas for new cycle
                    new_end = now + timedelta(days=30)
                    cur.execute(
                        """UPDATE user_quotas 
                           SET period_start = %s,
                               period_end = %s,
                               plagiarism_scans_used = 0,
                               paper_generations_used = 0,
                               restructures_used = 0,
                               novelty_checks_used = 0,
                               humanizer_words_used = 0,
                               updated_at = NOW()
                           WHERE user_id = %s
                           RETURNING *""",
                        (now, new_end, user_id),
                    )
                    quota = cur.fetchone()
            conn.commit()

        return dict(quota)

    @classmethod
    def get_usage_summary(cls, user_id: str) -> UsageQuotaResponse:
        """Calculates usage numbers and percentages against current plan allowances."""
        sub = cls.get_or_create_subscription(user_id)
        quota = cls.get_or_create_quotas(user_id)

        plan_id = sub.get("plan_id", "free")
        plan_meta = PLANS.get(plan_id, PLANS["free"])
        limits = plan_meta["limits"]

        is_pro = bool(sub.get("user_is_pro") or plan_id in ("pro_monthly", "pro_annual", "scholar_ultra"))

        def _build_item(used: int, limit: int) -> UsageQuotaItem:
            if limit == -1:
                return UsageQuotaItem(used=used, limit=-1, remaining=-1, percentage=0.0)
            remaining = max(0, limit - used)
            pct = round(min(100.0, (used / limit) * 100.0), 1) if limit > 0 else 100.0
            return UsageQuotaItem(used=used, limit=limit, remaining=remaining, percentage=pct)

        return UsageQuotaResponse(
            plan_id=plan_id,
            is_pro=is_pro,
            plagiarism_scans=_build_item(quota.get("plagiarism_scans_used", 0), limits["plagiarism_scans"]),
            paper_generations=_build_item(quota.get("paper_generations_used", 0), limits["paper_generations"]),
            restructures=_build_item(quota.get("restructures_used", 0), limits["restructures"]),
            novelty_checks=_build_item(quota.get("novelty_checks_used", 0), limits["novelty_checks"]),
            humanizer_words=_build_item(quota.get("humanizer_words_used", 0), limits["humanizer_words"]),
            period_start=str(quota.get("period_start", "")),
            period_end=str(quota.get("period_end", "")),
        )

    @classmethod
    def check_and_consume_quota(cls, user_id: str, feature_type: str, count: int = 1) -> tuple[bool, int, int]:
        """
        Validates whether user has quota remaining for feature_type, and if so increments it.
        Returns: (allowed: bool, current_used: int, limit: int)
        """
        col_map = {
            "plagiarism_scans": ("plagiarism_scans_used", "plagiarism_scans"),
            "paper_generations": ("paper_generations_used", "paper_generations"),
            "restructures": ("restructures_used", "restructures"),
            "novelty_checks": ("novelty_checks_used", "novelty_checks"),
            "humanizer_words": ("humanizer_words_used", "humanizer_words"),
        }
        if feature_type not in col_map:
            return True, 0, -1

        db_col, limit_key = col_map[feature_type]
        sub = cls.get_or_create_subscription(user_id)
        plan_id = sub.get("plan_id", "free")
        plan_meta = PLANS.get(plan_id, PLANS["free"])
        limit = plan_meta["limits"].get(limit_key, -1)

        # -1 indicates unlimited
        if limit == -1:
            cls._increment_usage(user_id, db_col, count)
            return True, 0, -1

        quota = cls.get_or_create_quotas(user_id)
        current = quota.get(db_col, 0)
        if current + count > limit:
            return False, current, limit

        new_used = cls._increment_usage(user_id, db_col, count)
        return True, new_used, limit

    @classmethod
    def _increment_usage(cls, user_id: str, column_name: str, count: int = 1) -> int:
        with DatabaseService.get_connection() as conn:
            with conn.cursor() as cur:
                query = f"""
                    UPDATE user_quotas 
                    SET {column_name} = {column_name} + %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING {column_name}
                """
                cur.execute(query, (count, user_id))
                res = cur.fetchone()
                conn.commit()
                return res[0] if res else 0

    @classmethod
    def create_checkout_order(
        cls,
        user_id: str,
        plan_id: str,
        currency: str = "INR",
        gateway: str = "razorpay",
        billing_cycle: str = "monthly",
    ) -> CheckoutResponse:
        """
        Initiates a checkout transaction.
        Uses Razorpay / Stripe if configured, or simulated checkout engine with complete validation.
        """
        if plan_id not in PLANS or plan_id == "free":
            raise ValueError(f"Invalid plan for checkout: {plan_id}")

        plan = PLANS[plan_id]
        currency = currency.upper()
        amount = plan["price_inr"] if currency == "INR" else plan["price_usd"]

        # Check for live Razorpay credentials
        rzp_key_id = os.getenv("RAZORPAY_KEY_ID") or settings.RAZORPAY_KEY_ID
        rzp_key_secret = os.getenv("RAZORPAY_KEY_SECRET") or settings.RAZORPAY_KEY_SECRET

        # Check for live Stripe credentials
        stripe_key = os.getenv("STRIPE_SECRET_KEY") or settings.STRIPE_SECRET_KEY
        stripe_pub = os.getenv("STRIPE_PUBLISHABLE_KEY") or settings.STRIPE_PUBLISHABLE_KEY

        # Generate UPI Intent & Dynamic QR payload for Indian payments
        upi_intent_url = f"upi://pay?pa=lemmaai@icici&pn=Lemma%20AI&am={amount:.2f}&cu={currency}&tn={plan['name'].replace(' ', '%20')}" if currency == "INR" else None
        upi_qr_data = upi_intent_url

        if gateway == "razorpay" and rzp_key_id and rzp_key_secret:
            try:
                import razorpay
                client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
                order_data = {
                    "amount": int(amount * 100),  # paise
                    "currency": currency,
                    "receipt": f"rcpt_{uuid.uuid4().hex[:8]}",
                    "notes": {"user_id": user_id, "plan_id": plan_id},
                }
                rzp_order = client.order.create(data=order_data)
                return CheckoutResponse(
                    order_id=rzp_order["id"],
                    gateway="razorpay",
                    plan_id=plan_id,
                    amount=amount,
                    currency=currency,
                    key_id=rzp_key_id,
                    upi_intent_url=upi_intent_url,
                    upi_qr_data=upi_qr_data,
                    notes={"receipt": order_data["receipt"]},
                    is_simulation=False,
                )
            except Exception as e:
                logger.warning(f"Live Razorpay order creation failed: {e}. Falling back to simulation.")

        if gateway == "stripe" and stripe_key:
            try:
                import stripe
                stripe.api_key = stripe_key
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),
                    currency=currency.lower(),
                    metadata={"user_id": user_id, "plan_id": plan_id},
                )
                return CheckoutResponse(
                    order_id=intent.id,
                    gateway="stripe",
                    plan_id=plan_id,
                    amount=amount,
                    currency=currency,
                    key_id=stripe_pub or "pk_live_lemma",
                    client_secret=intent.client_secret,
                    upi_intent_url=upi_intent_url,
                    upi_qr_data=upi_qr_data,
                    notes={"status": intent.status},
                    is_simulation=False,
                )
            except Exception as e:
                logger.warning(f"Live Stripe intent creation failed: {e}. Falling back to simulation.")

        # Interactive Simulation / Local Test-Mode Engine
        simulated_order_id = f"order_{gateway[:3]}_{uuid.uuid4().hex[:14]}"
        test_key = "rzp_test_lemma_pro_sandbox" if gateway == "razorpay" else "pk_test_lemma_stripe_sandbox"
        return CheckoutResponse(
            order_id=simulated_order_id,
            gateway=gateway,
            plan_id=plan_id,
            amount=amount,
            currency=currency,
            key_id=test_key,
            client_secret=f"cs_test_{uuid.uuid4().hex[:20]}",
            upi_intent_url=upi_intent_url,
            upi_qr_data=upi_qr_data,
            notes={"mode": "instant_test_simulation", "user_id": user_id},
            is_simulation=True,
        )

    @classmethod
    def verify_and_activate_payment(
        cls,
        user_id: str,
        gateway: str,
        order_id: str,
        payment_id: Optional[str],
        signature: Optional[str],
        plan_id: str,
        currency: str = "INR",
        payment_method: str = "upi",
        upi_id: Optional[str] = None,
        card_last4: Optional[str] = None,
        card_network: Optional[str] = None,
        cardholder_name: Optional[str] = None,
    ) -> PaymentVerificationResponse:
        """
        Verifies transaction signature, activates user subscription to Pro/Ultra,
        generates academic invoice, and grants expanded quota allowances.
        Supports rich UPI IDs and Credit/Debit card networks.
        """
        if plan_id not in PLANS:
            raise ValueError(f"Unknown plan: {plan_id}")

        plan = PLANS[plan_id]
        currency = currency.upper()
        amount = plan["price_inr"] if currency == "INR" else plan["price_usd"]

        # If live Razorpay secret is present and signature is provided, verify HMAC
        rzp_key_secret = os.getenv("RAZORPAY_KEY_SECRET") or settings.RAZORPAY_KEY_SECRET
        if gateway == "razorpay" and rzp_key_secret and signature and payment_id and not order_id.startswith("order_raz_"):
            expected_sign = hmac.new(
                rzp_key_secret.encode(),
                f"{order_id}|{payment_id}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if expected_sign != signature:
                raise ValueError("Invalid Razorpay payment signature.")

        # Ensure payment_id exists
        effective_payment_id = payment_id or f"pay_{uuid.uuid4().hex[:14]}"
        invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        now = datetime.now(timezone.utc)
        billing_cycle = "annual" if "annual" in plan_id else "monthly"
        period_duration = timedelta(days=365) if billing_cycle == "annual" else timedelta(days=30)
        period_end = now + period_duration

        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. Update or Insert Subscription
                cur.execute("SELECT id FROM subscriptions WHERE user_id = %s", (user_id,))
                existing_sub = cur.fetchone()

                if existing_sub:
                    cur.execute(
                        """UPDATE subscriptions 
                           SET plan_id = %s,
                               status = 'active',
                               billing_cycle = %s,
                               current_period_start = %s,
                               current_period_end = %s,
                               cancel_at_period_end = FALSE,
                               payment_gateway = %s,
                               updated_at = NOW()
                           WHERE user_id = %s
                           RETURNING id""",
                        (plan_id, billing_cycle, now, period_end, gateway, user_id),
                    )
                    sub_id = str(existing_sub["id"])
                else:
                    sub_id = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO subscriptions 
                           (id, user_id, plan_id, status, billing_cycle, current_period_start, current_period_end, payment_gateway)
                           VALUES (%s, %s, %s, 'active', %s, %s, %s, %s)
                           RETURNING id""",
                        (sub_id, user_id, plan_id, billing_cycle, now, period_end, gateway),
                    )

                # 2. Update User Record
                cur.execute(
                    """UPDATE users 
                       SET subscription_tier = %s,
                           is_pro = TRUE,
                           subscription_status = 'active'
                       WHERE id = %s""",
                    (plan_id, user_id),
                )

                # 3. Create Payment Transaction Record
                tx_id = str(uuid.uuid4())
                receipt_url = f"/api/v1/payment/invoices/{invoice_number}/download"
                
                # Format descriptive payment method for academic invoice
                method_desc = payment_method.upper()
                if payment_method.lower() == "upi" and upi_id:
                    method_desc = f"UPI ({upi_id})"
                elif payment_method.lower() == "card" and card_last4:
                    network_str = card_network or "Card"
                    method_desc = f"{network_str} •••• {card_last4}"

                cur.execute(
                    """INSERT INTO payment_transactions
                       (id, user_id, subscription_id, amount, currency, status, payment_method, gateway, gateway_order_id, gateway_payment_id, invoice_number, receipt_url)
                       VALUES (%s, %s, %s, %s, %s, 'succeeded', %s, %s, %s, %s, %s, %s)""",
                    (tx_id, user_id, sub_id, amount, currency, method_desc, gateway, order_id, effective_payment_id, invoice_number, receipt_url),
                )

                # 4. Refresh Quota Period and reset usage
                cur.execute(
                    """UPDATE user_quotas 
                       SET period_start = %s,
                           period_end = %s,
                           plagiarism_scans_used = 0,
                           paper_generations_used = 0,
                           restructures_used = 0,
                           novelty_checks_used = 0,
                           humanizer_words_used = 0,
                           updated_at = NOW()
                       WHERE user_id = %s""",
                    (now, period_end, user_id),
                )
            conn.commit()

        sub_resp = SubscriptionResponse(
            id=sub_id,
            plan_id=plan_id,
            plan_name=plan["name"],
            status="active",
            billing_cycle=billing_cycle,
            current_period_start=str(now),
            current_period_end=str(period_end),
            cancel_at_period_end=False,
            is_pro=True,
            payment_gateway=gateway,
            features=plan["features"],
        )

        method_details = {
            "method": payment_method,
            "display": method_desc,
            "upi_id": upi_id if payment_method.lower() == "upi" else None,
            "card_last4": card_last4 if payment_method.lower() == "card" else None,
            "card_network": card_network if payment_method.lower() == "card" else None,
            "cardholder_name": cardholder_name if payment_method.lower() == "card" else None,
        }

        return PaymentVerificationResponse(
            success=True,
            message=f"Successfully upgraded to {plan['name']}! Pro capabilities are active.",
            subscription=sub_resp,
            invoice_number=invoice_number,
            invoice_id=tx_id,
            payment_method_details=method_details,
        )

    @classmethod
    def cancel_subscription(cls, user_id: str) -> SubscriptionResponse:
        """Flags subscription to cancel at the end of the current billing cycle."""
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """UPDATE subscriptions 
                       SET cancel_at_period_end = TRUE,
                           updated_at = NOW()
                       WHERE user_id = %s
                       RETURNING *""",
                    (user_id,),
                )
                sub = cur.fetchone()
            conn.commit()

        if not sub:
            sub = cls.get_or_create_subscription(user_id)

        plan_meta = PLANS.get(sub.get("plan_id", "free"), PLANS["free"])
        return SubscriptionResponse(
            id=str(sub["id"]),
            plan_id=sub["plan_id"],
            plan_name=plan_meta["name"],
            status=sub["status"],
            billing_cycle=sub["billing_cycle"],
            current_period_start=str(sub["current_period_start"]),
            current_period_end=str(sub["current_period_end"]),
            cancel_at_period_end=True,
            is_pro=sub["plan_id"] in ("pro_monthly", "pro_annual", "scholar_ultra"),
            payment_gateway=sub.get("payment_gateway"),
            features=plan_meta["features"],
        )

    @classmethod
    def reactivate_subscription(cls, user_id: str) -> SubscriptionResponse:
        """Removes the cancellation flag and keeps subscription auto-renewing."""
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """UPDATE subscriptions 
                       SET cancel_at_period_end = FALSE,
                           updated_at = NOW()
                       WHERE user_id = %s
                       RETURNING *""",
                    (user_id,),
                )
                sub = cur.fetchone()
            conn.commit()

        if not sub:
            sub = cls.get_or_create_subscription(user_id)

        plan_meta = PLANS.get(sub.get("plan_id", "free"), PLANS["free"])
        return SubscriptionResponse(
            id=str(sub["id"]),
            plan_id=sub["plan_id"],
            plan_name=plan_meta["name"],
            status=sub["status"],
            billing_cycle=sub["billing_cycle"],
            current_period_start=str(sub["current_period_start"]),
            current_period_end=str(sub["current_period_end"]),
            cancel_at_period_end=False,
            is_pro=sub["plan_id"] in ("pro_monthly", "pro_annual", "scholar_ultra"),
            payment_gateway=sub.get("payment_gateway"),
            features=plan_meta["features"],
        )

    @classmethod
    def get_invoices(cls, user_id: str) -> list[InvoiceItemResponse]:
        """Retrieves user's historical invoices and transaction receipts."""
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM payment_transactions 
                       WHERE user_id = %s 
                       ORDER BY created_at DESC""",
                    (user_id,),
                )
                rows = cur.fetchall()

        items = []
        for r in rows:
            amount_display = f"₹{r['amount']:,.2f}" if r["currency"] == "INR" else f"${r['amount']:,.2f}"
            items.append(
                InvoiceItemResponse(
                    id=str(r["id"]),
                    invoice_number=r["invoice_number"],
                    amount=float(r["amount"]),
                    currency=r["currency"],
                    status=r["status"],
                    payment_method=r.get("payment_method", "card"),
                    gateway=r.get("gateway", "simulated"),
                    created_at=str(r["created_at"]),
                    description=f"Lemma AI Pro Plan Subscription ({amount_display})",
                    receipt_url=r.get("receipt_url") or f"/api/v1/payment/invoices/{r['invoice_number']}/download",
                )
            )
        return items

    @classmethod
    def generate_invoice_html(cls, invoice_number: str, user_id: Optional[str] = None) -> str:
        """Generates a professional, printable academic PDF/HTML invoice."""
        with DatabaseService.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if user_id:
                    cur.execute(
                        """SELECT t.*, u.full_name, u.email 
                           FROM payment_transactions t
                           JOIN users u ON t.user_id = u.id
                           WHERE t.invoice_number = %s AND t.user_id = %s""",
                        (invoice_number, user_id),
                    )
                else:
                    cur.execute(
                        """SELECT t.*, u.full_name, u.email 
                           FROM payment_transactions t
                           JOIN users u ON t.user_id = u.id
                           WHERE t.invoice_number = %s""",
                        (invoice_number,),
                    )
                record = cur.fetchone()

        if not record:
            raise ValueError(f"Invoice {invoice_number} not found.")

        sym = "₹" if record["currency"] == "INR" else "$"
        amount = f"{sym}{record['amount']:,.2f}"
        created_date = record["created_at"].strftime("%B %d, %Y") if hasattr(record["created_at"], "strftime") else str(record["created_at"])[:10]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Lemma AI Academic Receipt - {record['invoice_number']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background: #f8fafc;
            padding: 40px;
            margin: 0;
        }}
        .invoice-card {{
            max-width: 720px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            border: 1px solid #e2e8f0;
            padding: 40px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #6366f1;
            padding-bottom: 24px;
            margin-bottom: 28px;
        }}
        .brand h1 {{
            margin: 0;
            font-size: 26px;
            color: #4338ca;
            letter-spacing: -0.5px;
        }}
        .brand p {{
            margin: 4px 0 0 0;
            font-size: 13px;
            color: #64748b;
        }}
        .status-badge {{
            background: #dcfce7;
            color: #15803d;
            font-weight: 700;
            font-size: 12px;
            padding: 6px 14px;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
            font-size: 13.5px;
        }}
        .meta-box h4 {{
            margin: 0 0 6px 0;
            color: #475569;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .meta-box p {{
            margin: 0;
            color: #0f172a;
            font-weight: 500;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 28px;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            font-size: 12px;
            text-transform: uppercase;
            text-align: left;
            padding: 12px;
        }}
        td {{
            padding: 14px 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }}
        .total-row {{
            font-size: 18px;
            font-weight: 800;
            color: #0f172a;
        }}
        .footer {{
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
            font-size: 12px;
            color: #64748b;
            text-align: center;
            line-height: 1.6;
        }}
        .print-btn {{
            display: inline-block;
            background: #4f46e5;
            color: #ffffff;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            margin-top: 20px;
            cursor: pointer;
            border: none;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .invoice-card {{ box-shadow: none; border: none; padding: 0; }}
            .print-btn {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="invoice-card">
        <div class="header">
            <div class="brand">
                <h1>Lemma AI Research Studio</h1>
                <p>Tax Invoice &amp; Academic Payment Receipt</p>
            </div>
            <div class="status-badge">PAID IN FULL</div>
        </div>

        <div class="meta-grid">
            <div class="meta-box">
                <h4>Billed To:</h4>
                <p><strong>{record['full_name']}</strong></p>
                <p>{record['email']}</p>
                <p>Personal Academic Account</p>
            </div>
            <div class="meta-box" style="text-align: right;">
                <h4>Invoice Details:</h4>
                <p><strong>Invoice #:</strong> {record['invoice_number']}</p>
                <p><strong>Date:</strong> {created_date}</p>
                <p><strong>Payment Method:</strong> {record['payment_method'].upper()} ({record['gateway'].capitalize()})</p>
                <p><strong>Transaction ID:</strong> {record['gateway_payment_id']}</p>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Billing Cycle</th>
                    <th>Tax Rate</th>
                    <th style="text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <strong>Lemma AI Pro Academic Subscription</strong><br>
                        <span style="font-size: 12px; color: #64748b;">
                            Ad-Free Studio, Priority GPU Compute, Unlimited Restructures &amp; Integrity Verification
                        </span>
                    </td>
                    <td>Monthly / Annual</td>
                    <td>0% (Academic Software Exemption)</td>
                    <td style="text-align: right; font-weight: 600;">{amount}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="3" style="text-align: right; border-bottom: none;">Grand Total Paid:</td>
                    <td style="text-align: right; border-bottom: none; color: #4338ca;">{amount}</td>
                </tr>
            </tbody>
        </table>

        <div class="footer">
            <p>Thank you for accelerating open, rigorous academic scholarship with Lemma AI.</p>
            <p>For grant reimbursements, accounting questions, or institutional enterprise invoicing, contact <strong>billing@lemma.ai</strong>.</p>
            <button class="print-btn" onclick="window.print()">Print / Save as PDF</button>
        </div>
    </div>
</body>
</html>"""
        return html
