from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from database import get_db
from models.orm import User, BankAccount, Transaction
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

    # Store in history
    analysis_record = StripeTransaction(
        user_id=user_id,
        product_title=payload.product_data.product_title,
        price=payload.product_data.price,
        category=payload.product_data.category,
        url=payload.product_data.url,
        verdict=result.verdict,
        reasoning=result.reasoning
    )
    db.add(analysis_record)
    await db.commit()

    return result

@router.post("/analyze-demo", response_model=AnalysisResult)
async def analyze_purchase_demo(payload: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """
    Demo endpoint — runs the LangGraph agent with NO entitlement check.
    For testing only. Now saves to history too.
    """
    result = await execute_agent(payload.user_data, payload.product_data)

    # Store in history (demo users included)
    analysis_record = StripeTransaction(
        user_id=payload.user_data.user_id,
        product_title=payload.product_data.product_title,
        price=payload.product_data.price,
        category=payload.product_data.category,
        url=payload.product_data.url,
        verdict=result.verdict,
        reasoning=result.reasoning
    )
    db.add(analysis_record)
    await db.commit()

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
