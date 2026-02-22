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
from core.agent import execute_agent, capture_screen, extract_product_from_image
from services.voice_service import synthesize_speech
import base64
from langchain_core.messages import HumanMessage

router = APIRouter()

class BankAccountCreate(BaseModel):
    user_id: int
    account_type: str
    balance: float

class AnalyzeRequest(BaseModel):
    user_data: UserData
    product_data: ProductData

class VoiceReplyRequest(BaseModel):
    user_id: str
    text: str
    thread_id: Optional[str] = "default"

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

@router.post("/voice-reply")
async def voice_reply(payload: VoiceReplyRequest, db: AsyncSession = Depends(get_db)):
    """
    Handles user text/voice input, runs the agent, and returns text + voice response.
    """
    # 1. Fetch user data for context
    # (Simplified for the demo: fetching all data and picking the first user)
    users_result = await db.execute(
        select(User).where(User.id == 1).options(
            selectinload(User.accounts).selectinload(BankAccount.transactions)
        )
    )
    user = users_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Map DB user to UserData schema
    user_data = UserData(
        user_id=str(user.id),
        monthly_income=5000.0, # Placeholder
        current_balance=sum(acc.balance for acc in user.accounts),
        transactions=[
            {
                "id": str(tx.id),
                "date": tx.timestamp.isoformat()[:10],
                "merchant": tx.merchant,
                "amount": tx.amount,
                "category": tx.category,
                "is_recurring": False
            }
            for acc in user.accounts for tx in acc.transactions
        ]
    )

    # 2. Execute Agent with memory
    messages = [HumanMessage(content=payload.text)]
    result = await execute_agent(user_data, messages=messages, thread_id=payload.thread_id)
    
    # 3. Synthesize speech
    audio_content = await synthesize_speech(result.reasoning)
    audio_base64 = base64.b64encode(audio_content).decode('utf-8') if audio_content else None

    return {
        "text": result.reasoning,
        "audio": audio_base64
    }

@router.post("/analyze-screen")
async def analyze_screen(payload: VoiceReplyRequest, db: AsyncSession = Depends(get_db)):
    """
    Captures a screenshot, extracts product info via Gemini Vision, 
    and then runs the full analysis agent. Returns JSON + Vocal response.
    """
    # 1. Capture and extract
    screenshot_path = await capture_screen()
    product_data = await extract_product_from_image(screenshot_path)
    
    if not product_data:
        # Fallback to standard voice chat if no product is found on screen
        messages = [HumanMessage(content="I'm looking at my screen, what do you see?")]
        # Fetch user data (reusing logic from voice_reply)
        users_result = await db.execute(
            select(User).where(User.id == 1).options(
                selectinload(User.accounts).selectinload(BankAccount.transactions)
            )
        )
        user = users_result.scalar_one_or_none()
        user_data = UserData(
            user_id="1",
            monthly_income=5000.0,
            current_balance=sum(acc.balance for acc in user.accounts),
            transactions=[
                {
                    "id": str(tx.id),
                    "date": tx.timestamp.isoformat()[:10],
                    "merchant": tx.merchant,
                    "amount": tx.amount,
                    "category": tx.category,
                    "is_recurring": False
                }
                for acc in user.accounts for tx in acc.transactions
            ]
        )
        result = await execute_agent(user_data, messages=messages, thread_id=payload.thread_id)
    else:
        # 2. Run analysis agent with found product
        # Fetch user data
        users_result = await db.execute(
            select(User).where(User.id == 1).options(
                selectinload(User.accounts).selectinload(BankAccount.transactions)
            )
        )
        user = users_result.scalar_one_or_none()
        user_data = UserData(
            user_id="1",
            monthly_income=5000.0,
            current_balance=sum(acc.balance for acc in user.accounts),
            transactions=[
                {
                    "id": str(tx.id),
                    "date": tx.timestamp.isoformat()[:10],
                    "merchant": tx.merchant,
                    "amount": tx.amount,
                    "category": tx.category,
                    "is_recurring": False
                }
                for acc in user.accounts for tx in acc.transactions
            ]
        )
        
        # Add a message to the agent context explaining we found this on screen
        messages = [HumanMessage(content=f"I just scanned my screen and found this: {product_data.product_title} for ${product_data.price}. Should I buy it?")]
        result = await execute_agent(user_data, product=product_data, messages=messages, thread_id=payload.thread_id)

    # 3. Synthesize speech
    audio_content = await synthesize_speech(result.reasoning)
    audio_base64 = base64.b64encode(audio_content).decode('utf-8') if audio_content else None

    return {
        "text": result.reasoning,
        "audio": audio_base64,
        "product_found": product_data.model_dump() if product_data else None
    }

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

@router.get("/user-profile/{user_id}", response_model=UserData)
async def get_user_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns a structured UserData profile for the agent, 
    syncing live balance and profile data from the database.
    """
    # Fetch user with accounts
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.accounts))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create a default user if none exists (demo simplicity)
        user = User(
            id=user_id,
            name="Demo User",
            email="demo@orion.ai",
            monthly_income=5000.0,
            pay_cycle="monthly",
            days_until_payday=15,
            savings_goals=[{"name": "Emergency Fund", "current_amount": 1000, "target_amount": 10000}]
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    total_balance = sum(acc.balance for acc in user.accounts)
    
    return UserData(
        user_id=str(user.id),
        monthly_income=user.monthly_income,
        current_balance=total_balance,
        pay_cycle=user.pay_cycle,
        days_until_payday=user.days_until_payday,
        savings_goals=user.savings_goals,
        debts=user.debts,
        transactions=[]
    )

class UserProfileUpdate(BaseModel):
    monthly_income: Optional[float] = None
    pay_cycle: Optional[str] = None
    days_until_payday: Optional[int] = None
    savings_goals: Optional[List[Dict[str, Any]]] = None
    debts: Optional[List[Dict[str, Any]]] = None

@router.post("/user-profile/{user_id}/update")
async def update_user_profile(user_id: int, profile: UserProfileUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if profile.monthly_income is not None:
        user.monthly_income = profile.monthly_income
    if profile.pay_cycle is not None:
        user.pay_cycle = profile.pay_cycle
    if profile.days_until_payday is not None:
        user.days_until_payday = profile.days_until_payday
    if profile.savings_goals is not None:
        user.savings_goals = profile.savings_goals
    if profile.debts is not None:
        user.debts = profile.debts
        
    await db.commit()
    return {"status": "success"}
