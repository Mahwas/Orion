"""
Stripe webhook handler — signature verification, idempotency, and fulfillment.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe
import os
import logging
from datetime import datetime, timezone

from models.db_models import User, Entitlement, WebhookEvent
from core.database import get_db

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/stripe", tags=["stripe-webhooks"])

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_create_entitlement(user_id: str, db: Session) -> Entitlement:
    """Return the entitlement row for a user, creating it if needed."""
    ent = db.query(Entitlement).filter(Entitlement.user_id == user_id).first()
    if not ent:
        # Also ensure user row exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id)
            db.add(user)
            db.flush()
        ent = Entitlement(user_id=user_id, credits_balance=0, pro_active=False)
        db.add(ent)
        db.flush()
    return ent


def _find_user_id_from_session(session_obj: dict) -> str | None:
    """Extract user_id from Checkout Session metadata or client_reference_id."""
    metadata = session_obj.get("metadata") or {}
    user_id = metadata.get("user_id")
    if not user_id:
        user_id = session_obj.get("client_reference_id")
    return user_id


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------
def _handle_checkout_completed(session_obj: dict, db: Session) -> None:
    """Fulfill a completed Checkout Session (credits or pro)."""
    metadata = session_obj.get("metadata") or {}
    purchase_type = metadata.get("purchase_type")
    user_id = _find_user_id_from_session(session_obj)

    if not user_id:
        logger.warning("checkout.session.completed without user_id; skipping.")
        return

    ent = _get_or_create_entitlement(user_id, db)

    if purchase_type == "credits":
        credits_per_pack = int(metadata.get("credits_per_pack", 10))
        packs = int(metadata.get("packs", 1))
        credits_to_add = credits_per_pack * packs
        ent.credits_balance += credits_to_add
        logger.info("Credited %d credits to user %s (balance: %d)",
                     credits_to_add, user_id, ent.credits_balance)

    elif purchase_type == "pro":
        ent.pro_active = True
        subscription_id = session_obj.get("subscription")
        if subscription_id:
            ent.pro_subscription_id = subscription_id
        logger.info("Activated Pro for user %s (sub: %s)", user_id, subscription_id)

    else:
        logger.warning("Unknown purchase_type '%s' for user %s", purchase_type, user_id)


def _handle_invoice_paid(invoice_obj: dict, db: Session) -> None:
    """Safety net: re-activate Pro on successful renewal invoice."""
    subscription_id = invoice_obj.get("subscription")
    if not subscription_id:
        return

    ent = (
        db.query(Entitlement)
        .filter(Entitlement.pro_subscription_id == subscription_id)
        .first()
    )
    if ent and not ent.pro_active:
        ent.pro_active = True
        logger.info("Re-activated Pro for user %s via invoice.paid", ent.user_id)


def _handle_subscription_deleted(sub_obj: dict, db: Session) -> None:
    """Deactivate Pro when subscription is cancelled / expired."""
    subscription_id = sub_obj.get("id")
    if not subscription_id:
        return

    ent = (
        db.query(Entitlement)
        .filter(Entitlement.pro_subscription_id == subscription_id)
        .first()
    )
    if ent:
        ent.pro_active = False
        logger.info("Deactivated Pro for user %s (sub deleted: %s)",
                     ent.user_id, subscription_id)


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------
@webhook_router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive and process Stripe webhook events.

    - Verifies Stripe-Signature header
    - Ensures idempotency via WebhookEvent table
    - Dispatches to per-event-type handlers
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # --- Signature verification ---
    if not WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_WEBHOOK_SECRET is not configured.",
        )

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_id: str = event["id"]
    event_type: str = event["type"]

    # --- Idempotency check ---
    existing = db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == event_id).first()
    if existing:
        logger.info("Duplicate event %s (%s); skipping.", event_id, event_type)
        return {"status": "already_processed"}

    # --- Dispatch ---
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data_object, db)
    elif event_type == "invoice.paid":
        _handle_invoice_paid(data_object, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data_object, db)
    else:
        logger.debug("Unhandled event type: %s", event_type)

    # --- Record event ---
    webhook_event = WebhookEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(webhook_event)
    db.commit()

    return {"status": "success"}
