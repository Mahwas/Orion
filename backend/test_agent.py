import asyncio
import json
import os
import sys

# Ensure backend module path is available
sys.path.append(os.path.join(os.path.dirname(__file__)))

from core.agent import execute_agent
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
    
    result = await execute_agent(user_data, product_data)
    
    print("\n--- Agent Result ---")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    asyncio.run(main())
