import asyncio
import json
import os
import sys

# Ensure backend module path is available
sys.path.append(os.path.join(os.path.dirname(__file__)))

from core.agent import execute_agent
from models.schemas import UserData, ProductData

async def main():
    # Create a user with NO bad debt, solid balance, to avoid REJECT
    # But not a fundamental need purchase, to avoid APPROVE
    user_data = UserData(
        user_id="u_search_test",
        monthly_income=6500.0,
        current_balance=3500.0,
        pay_cycle="bi-weekly",
        days_until_payday=5,
        savings_goals=[
            {
                "name": "General Savings",
                "current_amount": 15000.0,
                "target_amount": 20000.0
            }
        ],
        debts=[], # No debt
        transactions=[
            {
                "id": "t1",
                "date": "2026-02-15",
                "merchant": "Whole Foods",
                "amount": 150.00,
                "category": "Groceries",
                "is_recurring": False
            }
        ]
    )
    
    # Create a "want" product that is moderately expensive, to avoid APPROVE
    product_data = ProductData(
        product_title="Dyson V8 Absolute Cordless Vacuum",
        price=450.00,
        category="Home Appliances",
        description="High-end cordless stick vacuum cleaner"
    )
    
    print(f"Testing Agent for user {user_data.user_id} with product {product_data.product_title} at ${product_data.price}")
    
    result = await execute_agent(user_data, product_data)
    
    print("\n--- Agent Result ---")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    asyncio.run(main())
