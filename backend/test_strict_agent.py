import asyncio
import json
import os
import sys

# Ensure backend module path is available
sys.path.append(os.path.join(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from core.agent import execute_agent
from models.schemas import UserData, ProductData

async def main():
    # User with low balance and high-interest debt
    user_data = UserData(
        user_id="u_strict_test",
        monthly_income=3000.0,
        current_balance=200.0,
        pay_cycle="monthly",
        days_until_payday=15,
        savings_goals=[
            {
                "name": "Emergency Fund",
                "current_amount": 500.0,
                "target_amount": 5000.0
            }
        ],
        debts=[
            {
                "type": "Credit Card",
                "balance": 2500.0,
                "apr": 24.99
            }
        ],
        transactions=[]
    )
    
    # A luxury item that isn't really "replaceable" with a cheaper version easily 
    # (or even if it is, they shouldn't buy it)
    product_data = ProductData(
        product_title="Louis Vuitton Wallet",
        price=600.00,
        category="Fashion",
        description="Designer luxury wallet"
    )
    
    print(f"Testing Strict Agent for user with ${user_data.current_balance} and ${user_data.debts[0].balance} CC debt.")
    print(f"Product: {product_data.product_title} at ${product_data.price}")
    
    result = await execute_agent(user_data, product_data)
    
    print("\n--- Agent Result ---")
    print(result.model_dump_json(indent=2))
    
    if result.verdict == "DO_NOT_BUY":
        print("\n✅ SUCCESS: Agent correctly rejected the luxury purchase despite (likely) finding no better deals.")
    else:
        print("\n❌ FAILURE: Agent still recommended buying or an alternative for a user who is broke.")

if __name__ == "__main__":
    asyncio.run(main())
