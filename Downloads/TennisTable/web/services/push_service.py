"""Web Push notification service using pywebpush.

Requires VAPID keys configured via environment:
  VAPID_PRIVATE_KEY  — base64url-encoded private key
  VAPID_PUBLIC_KEY   — base64url-encoded public key
  VAPID_CLAIM_EMAIL  — mailto: claim (e.g. admin@tttracker.com)

If pywebpush is not installed or VAPID keys are missing the service degrades
gracefully (all calls are no-ops).
"""
import logging
import os

from sqlalchemy.orm import Session

from web.models.push_subscription import PushSubscription

logger = logging.getLogger("push_service")

_VAPID_PRIVATE = os.getenv("VAPID_PRIVATE_KEY", "")
_VAPID_PUBLIC  = os.getenv("VAPID_PUBLIC_KEY", "")
_VAPID_EMAIL   = os.getenv("VAPID_CLAIM_EMAIL", "mailto:admin@tttracker.com")


def _available() -> bool:
    """Return True if pywebpush is installed and VAPID keys are configured."""
    if not _VAPID_PRIVATE or not _VAPID_PUBLIC:
        return False
    try:
        import pywebpush  # noqa: F401
        return True
    except ImportError:
        return False


def send_push(endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str = "/") -> bool:
    """Send a single push notification. Returns True on success."""
    if not _available():
        return False
    try:
        from pywebpush import webpush, WebPushException
        import json
        webpush(
            subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=_VAPID_PRIVATE,
            vapid_claims={"sub": _VAPID_EMAIL},
        )
        return True
    except Exception as exc:
        logger.debug("Push failed: %s", exc)
        return False


def notify_user(db: Session, user_id: int, title: str, body: str, url: str = "/") -> int:
    """Send push notification to all active subscriptions of a user.

    Returns number of successful deliveries.
    """
    subs = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,
        )
        .all()
    )
    if not subs:
        return 0

    sent = 0
    stale = []
    for sub in subs:
        ok = send_push(sub.endpoint, sub.p256dh, sub.auth, title, body, url)
        if ok:
            sent += 1
        else:
            # Mark subscription as inactive after failure (endpoint gone)
            stale.append(sub)

    for sub in stale:
        sub.is_active = False
    if stale:
        db.commit()

    return sent


def get_vapid_public_key() -> str:
    """Return the VAPID public key for the client-side subscription."""
    return _VAPID_PUBLIC
