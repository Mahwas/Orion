from pydantic import BaseModel
from typing import List, Optional

class UserData(BaseModel):
    user_id: str
    monthly_income: float
    current_balance: float
    buying_behavior: str
    discretionary_budget: float
    monthly_fixed_costs: float
    days_until_payday: int
    upcoming_bills_total: float
    monthly_savings_goal: float
    recent_large_purchases: List[str]
    has_credit_card_debt: bool

class ProductData(BaseModel):
    product_title: str
    price: float
    category: str
    description: Optional[str] = None

class AlternativeProduct(BaseModel):
    title: str
    price: float
    url: Optional[str] = None

class AnalysisResult(BaseModel):
    verdict: str  # "BUY", "ALTERNATIVE_RECOMMENDED", "DO_NOT_BUY"
    reasoning: str
    similar_products_found: List[AlternativeProduct] = []
