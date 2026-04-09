"""
Stripe billing integration — checkout sessions, webhooks, subscription management.

Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "http://localhost:3000/billing?success=1")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "http://localhost:3000/billing?cancelled=1")

# Map tiers to Stripe price IDs — set these in your Stripe dashboard
TIER_PRICE_IDS = {
    "pro": os.environ.get("STRIPE_PRO_PRICE_ID", "price_pro_placeholder"),
    "business": os.environ.get("STRIPE_BUSINESS_PRICE_ID", "price_business_placeholder"),
}


class StripeBilling:
    """Wraps Stripe API for subscription management."""

    def __init__(self):
        self._stripe = None

    @property
    def stripe(self):
        if self._stripe is None:
            try:
                import stripe
                stripe.api_key = STRIPE_SECRET_KEY
                self._stripe = stripe
            except ImportError:
                raise RuntimeError("stripe package not installed. Run: pip install stripe")
        return self._stripe

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        tier: str,
    ) -> Any:
        """Create a Stripe Checkout session for a subscription."""
        price_id = TIER_PRICE_IDS.get(tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {tier}")

        session = self.stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=user_email,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": user_id, "tier": tier},
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
        )
        return session

    def verify_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Verify and parse a Stripe webhook event."""
        event = self.stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event

    def cancel_subscription(self, subscription_id: str) -> None:
        """Cancel a Stripe subscription."""
        self.stripe.Subscription.delete(subscription_id)
