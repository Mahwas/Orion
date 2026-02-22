"""
Billing endpoints — Stripe Checkout Session creation for credits and Pro.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import stripe
import os
import logging

from models.db_models import User, Entitlement
from core.database import get_db

logger = logging.getLogger(__name__)

billing_router = APIRouter(prefix="/billing", tags=["billing"])

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

CREDITS_PRICE_ID = os.getenv("STRIPE_CREDITS_PRICE_ID")
PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")
SUCCESS_URL = os.getenv("FRONTEND_SUCCESS_URL", "http://localhost:3000/success")
CANCEL_URL = os.getenv("FRONTEND_CANCEL_URL", "http://localhost:3000/cancel")

CREDITS_PER_PACK = 10  # each pack grants 10 analysis credits


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class CreditsCheckoutRequest(BaseModel):
    user_id: str
    quantity: int = 1  # number of packs


class ProCheckoutRequest(BaseModel):
    user_id: str


class CheckoutResponse(BaseModel):
    checkout_session_id: str
    checkout_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_stripe_customer(user: User, db: Session) -> str:
    """Return the Stripe Customer ID, creating one if it doesn't exist."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"orion_user_id": user.id},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def _ensure_user(user_id: str, db: Session) -> User:
    """Fetch or create a User row (minimal auth stub)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id)
        db.add(user)
        db.flush()
    return user


def _ensure_entitlement(user_id: str, db: Session) -> Entitlement:
    """Fetch or create an Entitlement row for the user."""
    ent = db.query(Entitlement).filter(Entitlement.user_id == user_id).first()
    if not ent:
        ent = Entitlement(user_id=user_id, credits_balance=0, pro_active=False)
        db.add(ent)
        db.flush()
    return ent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@billing_router.post("/checkout/credits", response_model=CheckoutResponse)
async def checkout_credits(payload: CreditsCheckoutRequest, db: Session = Depends(get_db)):
    """Create a Stripe Checkout Session for a one-time credits pack purchase."""

    if not CREDITS_PRICE_ID:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_CREDITS_PRICE_ID is not configured. "
                   "Create a Price in Stripe Dashboard and set the env var.",
        )

    user = _ensure_user(payload.user_id, db)
    _ensure_entitlement(payload.user_id, db)
    customer_id = _ensure_stripe_customer(user, db)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[
                {"price": CREDITS_PRICE_ID, "quantity": payload.quantity},
            ],
            success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=CANCEL_URL,
            metadata={
                "user_id": payload.user_id,
                "purchase_type": "credits",
                "credits_per_pack": str(CREDITS_PER_PACK),
                "packs": str(payload.quantity),
            },
        )
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating credits checkout: %s", e)
        raise HTTPException(status_code=502, detail="Failed to create checkout session.")

    db.commit()
    return CheckoutResponse(
        checkout_session_id=session.id,
        checkout_url=session.url,
    )


@billing_router.post("/checkout/pro", response_model=CheckoutResponse)
async def checkout_pro(payload: ProCheckoutRequest, db: Session = Depends(get_db)):
    """Create a Stripe Checkout Session for Orion Pro subscription."""

    if not PRO_PRICE_ID:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_PRO_PRICE_ID is not configured. "
                   "Create a Price in Stripe Dashboard and set the env var.",
        )

    user = _ensure_user(payload.user_id, db)
    _ensure_entitlement(payload.user_id, db)
    customer_id = _ensure_stripe_customer(user, db)

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[
                {"price": PRO_PRICE_ID, "quantity": 1},
            ],
            success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=CANCEL_URL,
            metadata={
                "user_id": payload.user_id,
                "purchase_type": "pro",
            },
        )
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating pro checkout: %s", e)
        raise HTTPException(status_code=502, detail="Failed to create checkout session.")

    db.commit()
    return CheckoutResponse(
        checkout_session_id=session.id,
        checkout_url=session.url,
    )
