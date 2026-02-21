from models import PurchaseContext, DecisionOutput, FeedbackEvent, FinancialSnapshot, BudgetMemoryPreferences, BudgetMemoryLearningWeights, BudgetMemory
from typing import Dict, Any
from core.agent import evaluate_purchase
from services.stripe_service import create_checkout

router = APIRouter()

# Global state to act as a buffer for the demo
latest_decision = None

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
