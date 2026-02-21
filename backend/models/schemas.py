from pydantic import BaseModel
from typing import List, Optional


# --- Sub-models used in UserData ---

class SavingsGoal(BaseModel):
    name: str
    current_amount: float
    target_amount: float

class Debt(BaseModel):
    type: str
    balance: float
    apr: float

class Transaction(BaseModel):
    id: str
    date: str
    merchant: str
    amount: float
    category: str
    is_recurring: bool


# --- Core input models ---

class UserData(BaseModel):
    user_id: str
    monthly_income: float
    current_balance: float

    # Pay schedule
    pay_cycle: str = "monthly"           # e.g. "monthly", "biweekly"
    days_until_payday: int = 0

    # Financial context (legacy flat fields kept for backward compat)
    buying_behavior: str = ""
    discretionary_budget: float = 0.0
    monthly_fixed_costs: float = 0.0     # rent + insurance + subscriptions
    upcoming_bills_total: float = 0.0
    monthly_savings_goal: float = 0.0
    recent_large_purchases: List[str] = []
    has_credit_card_debt: bool = False

    # Rich structured data (from the DB / frontend)
    savings_goals: List[SavingsGoal] = []
    debts: List[Debt] = []
    transactions: List[Transaction] = []


# --- Product models ---

class ProductData(BaseModel):
    product_title: str
    price: float
    category: str
    description: Optional[str] = None


# --- Output models ---

class AlternativeProduct(BaseModel):
    title: str
    price: float
    url: Optional[str] = None

class AnalysisResult(BaseModel):
    verdict: str  # "BUY", "ALTERNATIVE_RECOMMENDED", "DO_NOT_BUY"
    reasoning: str
    similar_products_found: List[AlternativeProduct] = []
