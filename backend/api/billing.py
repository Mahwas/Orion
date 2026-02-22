"""
Billing endpoints — Stripe Checkout Session creation for credits and Pro.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import os
import logging

from models.db_models import StripeUser, Entitlement
from database import get_db

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
async def _ensure_stripe_customer(user: StripeUser, db: AsyncSession) -> str:
    """Return the Stripe Customer ID, creating one if it doesn't exist."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"orion_user_id": user.id},
    )
    user.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


async def _ensure_user(user_id: str, db: AsyncSession) -> StripeUser:
    """Fetch or create a User row (minimal auth stub)."""
    result = await db.execute(select(StripeUser).where(StripeUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = StripeUser(id=user_id)
        db.add(user)
        await db.flush()
    return user


async def _ensure_entitlement(user_id: str, db: AsyncSession) -> Entitlement:
    """Fetch or create an Entitlement row for the user."""
    result = await db.execute(select(Entitlement).where(Entitlement.user_id == user_id))
    ent = result.scalar_one_or_none()
    if not ent:
        ent = Entitlement(user_id=user_id, credits_balance=0, pro_active=False)
        db.add(ent)
        await db.flush()
    return ent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@billing_router.post("/checkout/credits", response_model=CheckoutResponse)
async def checkout_credits(payload: CreditsCheckoutRequest, db: AsyncSession = Depends(get_db)):
    """Create a Stripe Checkout Session for a one-time credits pack purchase."""

    if not CREDITS_PRICE_ID:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_CREDITS_PRICE_ID is not configured. "
                   "Create a Price in Stripe Dashboard and set the env var.",
        )

    user = await _ensure_user(payload.user_id, db)
    await _ensure_entitlement(payload.user_id, db)
    customer_id = await _ensure_stripe_customer(user, db)

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

    await db.commit()
    return CheckoutResponse(
        checkout_session_id=session.id,
        checkout_url=session.url,
    )


@billing_router.post("/checkout/pro", response_model=CheckoutResponse)
async def checkout_pro(payload: ProCheckoutRequest, db: AsyncSession = Depends(get_db)):
    """Create a Stripe Checkout Session for Orion Pro subscription."""

    if not PRO_PRICE_ID:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_PRO_PRICE_ID is not configured. "
                   "Create a Price in Stripe Dashboard and set the env var.",
        )

    user = await _ensure_user(payload.user_id, db)
    await _ensure_entitlement(payload.user_id, db)
    customer_id = await _ensure_stripe_customer(user, db)

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

    await db.commit()
    return CheckoutResponse(
        checkout_session_id=session.id,
        checkout_url=session.url,
    )
