"""Stripe integration — checkout sessions and webhook handling."""
import logging

from web.core.config import settings

logger = logging.getLogger("stripe_service")


def _get_stripe():
    import stripe as _stripe
    _stripe.api_key = settings.stripe.secret_key
    return _stripe


def create_checkout_session(user_id: int, price_id: str, success_url: str, cancel_url: str) -> str:
    """Returns the Stripe Checkout URL."""
    stripe = _get_stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user_id)},
    )
    return session.url


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Validates and parses a Stripe webhook event. Returns the event dict."""
    stripe = _get_stripe()
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe.webhook_secret
    )
    return event
