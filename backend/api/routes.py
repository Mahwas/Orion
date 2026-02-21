from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from models.schemas import UserData, ProductData, AnalysisResult
from models.db_models import Transaction
from core.database import get_db
from core.agent import execute_agent

router = APIRouter()

class AnalyzeRequest(BaseModel):
    user_data: UserData
    product_data: ProductData

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_purchase(payload: AnalyzeRequest):
    """
    Kicks off the LangGraph agent to evaluate a purchase.
    """
    result = await execute_agent(payload.user_data, payload.product_data)
    return result

@router.get("/transactions/{user_id}")
def get_user_transactions(user_id: str, db: Session = Depends(get_db)):
    """
    Fetches the transaction history for a given user.
    """
    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.timestamp.desc()).all()
    return transactions
