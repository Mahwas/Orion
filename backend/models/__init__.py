from pydantic import BaseModel
from typing import List, Optional

class PurchaseContext(BaseModel):
    source: str
    timestamp: str
    merchant: str
    product_title: str
    price: float
    currency: str
    category_hint: str
    url: str
    user_intent_hint: str
    image_crop_ref: Optional[str] = None

class Alternative(BaseModel):
    title: str
    price: float

class DecisionOutput(BaseModel):
    verdict: str  # e.g., "ENCOURAGE", "DISCOURAGE"
    score: int
    reasons: List[str]
    conditions_to_yes: List[str]
    alternatives: List[Alternative]
    followup_question: str

class BudgetMemoryPreferences(BaseModel):
    strictness: float
    savings_goal: float
    deal_breaker_categories: List[str]

class BudgetMemoryLearningWeights(BaseModel):
    importance_of_alternatives: float

class BudgetMemory(BaseModel):
    user_id: str
    preferences: BudgetMemoryPreferences
    learning_weights: BudgetMemoryLearningWeights

class FinancialSnapshot(BaseModel):
    user_id: str
    current_balance: float
    upcoming_bills_total: float
    discretionary_budget_remaining: float
    days_until_payday: int

class FeedbackEvent(BaseModel):
    user_id: str
    timestamp: str
    action_taken: str
    context_id: str
    user_chat_feedback: Optional[str] = None
