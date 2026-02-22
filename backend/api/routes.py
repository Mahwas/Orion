from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from models.schemas import UserData, ProductData, AnalysisResult
from models.db_models import Transaction, User, Entitlement
from core.database import get_db
from core.agent import execute_agent

router = APIRouter()


class AnalyzeRequest(BaseModel):
    user_data: UserData
    product_data: ProductData


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_purchase(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Kicks off the LangGraph agent to evaluate a purchase.
    Requires user to have an active Pro subscription OR at least 1 credit.
    """
    user_id = payload.user_data.user_id
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    ent = db.query(Entitlement).filter(Entitlement.user_id == user_id).first()

    # --- Entitlement check ---
    if ent and ent.pro_active:
        # Pro subscribers get unlimited analyses
        pass
    elif ent and ent.credits_balance > 0:
        # Deduct 1 credit
        ent.credits_balance -= 1
        db.commit()
    else:
        raise HTTPException(
            status_code=402,
            detail="No analysis credits remaining. "
                   "Buy a credits pack or upgrade to Orion Pro.",
        )

    result = await execute_agent(payload.user_data, payload.product_data)
    return result


@router.get("/transactions/{user_id}")
def get_user_transactions(user_id: str, db: Session = Depends(get_db)):
    """
    Fetches the transaction history for a given user.
    """
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .all()
    )
    return transactions
