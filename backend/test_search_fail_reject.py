import asyncio
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure backend module path is available
sys.path.append(os.path.join(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from core.agent import execute_agent
from models.schemas import UserData, ProductData, AnalysisResult

async def main():
    # Borderline user: Can technically afford it, but has low income and a goal.
    user_data = UserData(
        user_id="u_rich",
        monthly_income=15000.0,
        current_balance=25000.0,
        pay_cycle="monthly",
        days_until_payday=5,
        savings_goals=[
            {"name": "Emergency Fund", "current_amount": 14500.0, "target_amount": 15000.0}
        ],
        debts=[],
        transactions=[]
    )
    
    product_data = ProductData(
        product_title="High-End Mechanical Keyboard",
        price=450.00,
        category="Electronics",
        description="Custom mechanical keyboard"
    )
    
    print(f"Testing 'No Alternative' Path for product: {product_data.product_title} at ${product_data.price}")
    
    # We mock node_triage to force search
    triage_mock = {"action": "SEARCH_ALTERNATIVES", "reasoning": "Standard keyboard, let's look for deals."}
    
    with patch('core.agent.node_triage', return_value={"triage_result": triage_mock}):
        with patch('core.agent.node_search', return_value={"search_results": "[]", "search_retries": 2}):
            with patch('core.agent.MAX_SEARCH_RETRIES', 1): 
                result = await execute_agent(user_data, product_data)
    
    print("\n--- Agent Result ---")
    print(result.model_dump_json(indent=2))
    
    # The agent might still say BUY if it thinks $450 is okay for a $200 income user 
    # (wait, 2500 income). 
    # But it shouldn't say BUY just because it failed to find alternatives.
    # It should justify it using the NO_ALT prompt.
    
    if "no alternatives were found" in result.reasoning.lower():
        print("\n✅ SUCCESS: Agent reasoning acknowledges that no alternatives were found.")
    else:
        print("\n❌ FAILURE: Agent reasoning did not mention the search failure.")

if __name__ == "__main__":
    asyncio.run(main())
