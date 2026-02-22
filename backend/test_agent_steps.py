import asyncio
import json
import os
import sys

# Ensure backend module path is available
sys.path.append(os.path.join(os.path.dirname(__file__)))

from core.agent import agent_app
from models.schemas import UserData, ProductData

async def main():
    with open("data/users/mock_users.json", "r") as f:
        mock_users = json.load(f)
    
    user_data = UserData(**mock_users[0])
    
    product_data = ProductData(
        product_title="Sony WH-1000XM5 Noise Cancelling Headphones",
        price=350.00,
        category="Electronics",
        description="Premium noise cancelling headphones"
    )
    
    print(f"Testing Agent for user {user_data.user_id} with product {product_data.product_title} at ${product_data.price}")
    
    initial_state = {
        "user_data": user_data,
        "product_data": product_data,
        "triage_result": None,
        "search_results": None,
        "viable_candidates": [],
        "is_better": None,
        "search_retries": 0,
        "final_decision": None,
        "synthesis_retries": 0,
        "synthesis_error": None,
    }

    print("\n--- Agent Execution Steps ---")
    async for event in agent_app.astream(initial_state):
        for node_name, node_state in event.items():
            print(f"\n--- Node: {node_name} ---")
            filtered_state = {k: v for k, v in node_state.items() if k not in ["user_data", "product_data"] and v is not None}
            print(json.dumps(filtered_state, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
