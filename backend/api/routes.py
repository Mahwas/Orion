from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

# Imports from HEAD (database branch)
from models import PurchaseContext, DecisionOutput, FeedbackEvent, FinancialSnapshot, BudgetMemoryPreferences, BudgetMemoryLearningWeights, BudgetMemory
from core.agent import evaluate_purchase
from services.stripe_service import create_checkout
from database import get_db
from models.orm import User, BankAccount, Transaction

# Imports from feature branch
from models.schemas import UserData, ProductData, AnalysisResult
from models.db_models import StripeTransaction, StripeUser, Entitlement
from core.agent import execute_agent

router = APIRouter()

class BankAccountCreate(BaseModel):
    user_id: int
    account_type: str
    balance: float

class AnalyzeRequest(BaseModel):
    user_data: UserData
    product_data: ProductData

# Global state to act as a buffer for the demo
latest_decision = None

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_purchase(payload: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """
    Kicks off the LangGraph agent to evaluate a purchase.
    Requires user to have an active Pro subscription OR at least 1 credit.
    """
    user_id = payload.user_data.user_id
    # Note: Using StripeUser from db_models since this logic expects that schema
    result = await db.execute(select(StripeUser).where(StripeUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await db.execute(select(Entitlement).where(Entitlement.user_id == user_id))
    ent = result.scalar_one_or_none()

    # --- Entitlement check ---
    if ent and ent.pro_active:
        # Pro subscribers get unlimited analyses
        pass
    elif ent and ent.credits_balance > 0:
        # Deduct 1 credit
        ent.credits_balance -= 1
        # No await needed for simple attribute change, but we need to commit
        await db.commit()
    else:
        raise HTTPException(
            status_code=402,
            detail="No analysis credits remaining. "
                   "Buy a credits pack or upgrade to Orion Pro.",
        )

    result = await execute_agent(payload.user_data, payload.product_data)
    return result

@router.get("/transactions/{user_id}")
async def get_user_transactions(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetches the transaction history for a given user.
    """
    result = await db.execute(
        select(StripeTransaction)
        .where(StripeTransaction.user_id == user_id)
        .order_by(StripeTransaction.timestamp.desc())
    )
    transactions = result.scalars().all()
    return transactions

@router.post("/context", response_model=Dict[str, Any])
async def ingest_context(context: PurchaseContext):
    global latest_decision
    
    # Mocking user data for demo since there's no DB
    snapshot = FinancialSnapshot(
        user_id="u123",
        current_balance=1500.50,
        upcoming_bills_total=850.00,
        discretionary_budget_remaining=150.00,
        days_until_payday=5
    )
    
    memory = BudgetMemory(
        user_id="u123",
        preferences=BudgetMemoryPreferences(
            strictness=0.8,
            savings_goal=500.0,
            deal_breaker_categories=["luxury_clothing"]
        ),
        learning_weights=BudgetMemoryLearningWeights(
            importance_of_alternatives=1.2
        )
    )
    
    latest_decision = await evaluate_purchase(context, snapshot, memory)
    
    return {"status": "success", "message": "Context ingested and assigned to agent"}

@router.get("/advice", response_model=DecisionOutput)
async def get_latest_advice():
    global latest_decision
    if not latest_decision:
        return DecisionOutput(
            verdict="PENDING",
            score=0,
            reasons=[],
            conditions_to_yes=[],
            alternatives=[],
            followup_question=""
        )
    return latest_decision

@router.post("/checkout")
async def create_checkout_session(item_name: str, price: float):
    url = create_checkout(item_name, price)
    return {"url": url}

@router.post("/webhooks/stripe")
async def stripe_webhook():
    return {"status": "received"}

@router.get("/user/config")
async def get_user_config():
    return {
        "snapshot": {
            "user_id": "u123",
            "current_balance": 1500.50,
            "upcoming_bills_total": 850.00,
            "discretionary_budget_remaining": 150.00,
            "days_until_payday": 5
        },
        "memory": {
            "strictness": 0.8,
            "savings_goal": 500.0,
            "deal_breaker_categories": ["luxury_clothing"]
        }
    }

@router.post("/user/feedback")
async def receive_feedback(event: FeedbackEvent):
    return {"status": "recorded"}

@router.get("/all-data")
async def get_all_data(db: AsyncSession = Depends(get_db)):
    # Fetch users with their accounts and transactions
    users_result = await db.execute(
        select(User).options(
            selectinload(User.accounts).selectinload(BankAccount.transactions)
        )
    )
    users = users_result.scalars().all()
    
    data = []
    for user in users:
        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "accounts": []
        }
        for account in user.accounts:
            acc_data = {
                "id": account.id,
                "type": account.account_type,
                "balance": account.balance,
                "currency": account.currency,
                "transactions": []
            }
            for tx in account.transactions:
                acc_data["transactions"].append({
                    "id": tx.id,
                    "merchant": tx.merchant,
                    "amount": tx.amount,
                    "category": tx.category,
                    "timestamp": tx.timestamp.isoformat(),
                    "type": tx.transaction_type
                })
            user_data["accounts"].append(acc_data)
        data.append(user_data)
        
    return {"users": data}

@router.post("/bank-accounts")
async def create_bank_account(account_data: BankAccountCreate, db: AsyncSession = Depends(get_db)):
    # Create the account
    new_account = BankAccount(
        user_id=account_data.user_id,
        account_type=account_data.account_type,
        balance=account_data.balance
    )
    db.add(new_account)
    await db.flush()
    
    # Create the initial transaction
    initial_tx = Transaction(
        account_id=new_account.id,
        merchant="Account Opening",
        amount=account_data.balance,
        category="Initial Deposit",
        transaction_type="CREDIT"
    )
    db.add(initial_tx)
    
    await db.commit()
    await db.refresh(new_account)
    
    return {"status": "success", "account_id": new_account.id}

@router.delete("/bank-accounts/{account_id}")
async def delete_bank_account(account_id: int, db: AsyncSession = Depends(get_db)):
    # Find the account
    result = await db.execute(select(BankAccount).where(BankAccount.id == account_id))
    account = result.scalar_one_or_none()
    
    if not account:
        return {"status": "error", "message": "Account not found"}
        
    await db.delete(account)
    await db.commit()
    
    return {"status": "success", "message": "Account deleted"}
