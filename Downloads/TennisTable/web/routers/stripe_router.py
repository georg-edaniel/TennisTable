"""Stripe routes — pricing page, checkout, webhook, subscription pages."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from web.core.config import settings
from web.core.database import get_db
from web.core.security import decode_token
from web.core.templating import templates
from web.services.auth_service import get_user_by_id

router = APIRouter(tags=["stripe"])

ACCESS_COOKIE = "access_token"
logger = logging.getLogger("stripe_router")


def _get_user(request: Request, db: Session):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        data = decode_token(token)
        uid = data.get("sub", "")
        if not uid.isdigit():
            return None
        return get_user_by_id(db, int(uid))
    except Exception:
        return None


@router.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    token = request.cookies.get(ACCESS_COOKIE, "")
    return templates.TemplateResponse(
        request, "pricing.html",
        {
            "user": user,
            "access_token": token,
            "stripe_publishable_key": settings.stripe.publishable_key,
        },
    )


@router.post("/api/stripe/checkout")
async def create_checkout(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Connexion requise")

    if not settings.stripe.secret_key or not settings.stripe.price_club_id:
        raise HTTPException(status_code=503, detail="Stripe non configuré")

    from web.core.stripe_service import create_checkout_session
    app_url = settings.email.app_url
    try:
        checkout_url = create_checkout_session(
            user_id=user.id,
            price_id=settings.stripe.price_club_id,
            success_url=f"{app_url}/subscription/success",
            cancel_url=f"{app_url}/pricing",
        )
    except Exception as exc:
        logger.error("Stripe checkout error: %s", exc)
        raise HTTPException(status_code=500, detail="Erreur Stripe")

    return {"checkout_url": checkout_url}


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    from web.core.stripe_service import handle_webhook
    try:
        event = handle_webhook(payload, sig_header)
    except Exception as exc:
        logger.warning("Webhook validation failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        user_id = int(session_data.get("metadata", {}).get("user_id", 0))
        if user_id:
            from web.models.user import User
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                u.subscription_tier = "club"
                db.commit()
                logger.info("User %s upgraded to club", user_id)

    return {"ok": True}


@router.get("/subscription/success", response_class=HTMLResponse)
def subscription_success(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    token = request.cookies.get(ACCESS_COOKIE, "")
    return templates.TemplateResponse(
        request, "subscription_success.html",
        {"user": user, "access_token": token},
    )


@router.get("/subscription/cancel")
def subscription_cancel():
    return RedirectResponse("/pricing")
