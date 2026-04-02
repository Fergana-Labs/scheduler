"""Stripe billing integration for subscriptions and payments."""

import logging

import stripe

from scheduler.config import config

logger = logging.getLogger(__name__)


def _ensure_stripe():
    if not config.stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = config.stripe_secret_key


def create_customer(email: str, user_id: str) -> stripe.Customer:
    _ensure_stripe()
    return stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )


def create_checkout_session(
    customer_id: str,
    success_url: str,
    cancel_url: str,
    price_id: str | None = None,
) -> stripe.checkout.Session:
    _ensure_stripe()
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        payment_method_collection="always",
        subscription_data={"trial_period_days": 7},
        line_items=[{"price": price_id or config.stripe_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )


def create_portal_session(customer_id: str, return_url: str) -> stripe.billing_portal.Session:
    _ensure_stripe()
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    _ensure_stripe()
    return stripe.Webhook.construct_event(
        payload,
        sig_header,
        config.stripe_webhook_secret,
    )
