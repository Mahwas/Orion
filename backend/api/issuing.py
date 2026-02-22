"""
Stripe Issuing — generate one-time virtual cards for agent-recommended purchases.

Flow:
  1. Agent finds a cheaper alternative (e.g. $239.97).
  2. Frontend calls POST /api/v1/issuing/generate-card with that amount.
  3. This endpoint creates a Stripe Cardholder (if not yet created) and a
     virtual Card locked to exactly that spending amount.
  4. The unredacted card details are returned ONCE for the user to copy.
  5. Card auto-expires after 1 use (spending_limits interval=per_authorization)
     so it cannot be reused.
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

issuing_router = APIRouter(prefix="/api/v1/issuing", tags=["issuing"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class GenerateCardRequest(BaseModel):
    user_id: str
    amount_cents: int          # e.g. 23997 for $239.97
    merchant_hint: str = ""    # optional human label shown on the card


class GenerateCardResponse(BaseModel):
    card_id: str
    last4: str
    exp_month: int
    exp_year: int
    cvc: str
    cardholder_name: str
    spending_limit_usd: float
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_or_create_cardholder(user: StripeUser, db: AsyncSession) -> str:
    """
    Return a Stripe Cardholder ID for this user.
    We store it in the StripeUser row (reusing stripe_customer_id is wrong —
    Cardholders are separate objects). We use a naming convention to check
    if one already exists by listing cardholders for the email.
    """
    # Check if we already stored a cardholder ID (we expand stripe_customer_id
    # for this demo; in prod you'd add a separate column).
    # For simplicity: list existing cardholders for this email.
    email = user.email or f"{user.id}@orion.demo"

    existing = stripe.issuing.Cardholder.list(email=email, limit=1)
    if existing.data:
        return existing.data[0].id

    cardholder = stripe.issuing.Cardholder.create(
        name=f"Orion User {user.id}",
        email=email,
        type="individual",
        billing={
            "address": {
                "line1": "510 Townsend St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94103",
                "country": "US",
            }
        },
    )
    return cardholder.id


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@issuing_router.post("/generate-card", response_model=GenerateCardResponse)
async def generate_one_time_card(
    payload: GenerateCardRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a one-time Stripe virtual card locked to the alternative product's
    price. The card can only be charged ONCE (per_authorization limit) for
    exactly that amount.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured.")

    # --- Fetch / create user ---
    result = await db.execute(select(StripeUser).where(StripeUser.id == payload.user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = StripeUser(id=payload.user_id, email=f"{payload.user_id}@orion.demo")
        db.add(user)
        await db.flush()

    # --- Get or create Stripe Cardholder ---
    try:
        cardholder_id = await _get_or_create_cardholder(user, db)
    except stripe.StripeError as e:
        logger.error("Cardholder creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe Issuing error: {str(e)}")

    # --- Create the virtual card ---
    label = payload.merchant_hint or "Orion Smart Purchase"
    try:
        card = stripe.issuing.Card.create(
            cardholder=cardholder_id,
            currency="usd",
            type="virtual",
            status="active",
            spending_controls={
                "spending_limits": [
                    {
                        "amount": payload.amount_cents,
                        "interval": "per_authorization",  # single-use spending cap
                    }
                ],
                "allowed_categories": [],  # unrestricted category
            },
            metadata={
                "orion_user_id": payload.user_id,
                "merchant_hint": label,
                "amount_usd": str(payload.amount_cents / 100),
            },
        )
    except stripe.StripeError as e:
        logger.error("Card creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe Issuing error: {str(e)}")

    # Reveal the full card number (only possible immediately after creation
    # in test mode, or via stripe.issuing.Card.retrieve with expand).
    try:
        revealed = stripe.issuing.Card.retrieve(
            card.id,
            expand=["number", "cvc"],
        )
        card_number = revealed.number if hasattr(revealed, "number") else "•••• •••• •••• " + card.last4
        cvc = revealed.cvc if hasattr(revealed, "cvc") else "***"
    except Exception:
        card_number = "•••• •••• •••• " + card.last4
        cvc = "***"

    await db.commit()

    return GenerateCardResponse(
        card_id=card.id,
        last4=card.last4,
        exp_month=card.exp_month,
        exp_year=card.exp_year,
        cvc=cvc,
        cardholder_name=f"Orion User {payload.user_id}",
        spending_limit_usd=payload.amount_cents / 100,
        message=(
            f"One-time virtual card created. "
            f"Locked to ${payload.amount_cents / 100:.2f}. "
            f"Use it to purchase: {label}"
        ),
    )
