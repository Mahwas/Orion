import sys
from pathlib import Path
import json 
import asyncio
import os

# Add backend to path so we can import internal models cleanly
backend_path = Path(__file__).parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from models.schemas import ProductData, UserData
from core.agent import execute_agent

def build_product_data(extracted):
    title = "Unknown product"

    if extracted.get("items"):
        title = extracted["items"][0]["name"]

    return ProductData(
        product_title=title,
        price=extracted.get("total", 0),
        category=extracted.get("category", "other"),
        description=extracted.get("description", "")
    ) 

def load_user():
    user_file = Path(__file__).parent / "backend" / "data" / "users" / "mock_users.json"
    if not user_file.exists():
        create_mock_user_data(user_file)
    with open(user_file) as f:
        users = json.load(f)
    return UserData(**users[0])


def create_mock_user_data(file_path):
    """Create mock user data for MVP demo"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mock_users = [
        {
            "user_id": "demo_user_001",
            "monthly_income": 3000.0,
            "current_balance": 2500.0,
            "pay_cycle": "monthly",
            "days_until_payday": 8,
            "savings_goals": [{"name": "vacation", "current_amount": 500.0, "target_amount": 2000.0}],
            "debts": [],
            "transactions": [
                {"id": "t1", "date": "2026-02-01", "amount": 45.00, "merchant": "groceries", "category": "groceries"}
            ],
            # Pass whatever else without crashing
        }
    ]
    with open(file_path, "w") as f:
        json.dump(mock_users, f, indent=2)


async def get_agent_recommendations(extracted_data):
    """Run teammate's agent to get enhanced recommendations"""
    try:
        product = build_product_data(extracted_data)
        user = load_user()
        
        # Execute agent analysis
        result = await execute_agent(user, product)
        
        return {
            "agent_analysis": result.model_dump(),
            "should_buy": result.verdict == "BUY",
            "reasoning": result.reasoning
        }
    except Exception as e:
        print(f"Agent analysis error: {e}")
        return {
            "agent_analysis": None,
            "should_buy": None,
            "reasoning": f"Could not analyze: {str(e)}"
        }


def enhance_extracted_data(extracted_data, agent_recommendations):
    """Combine Gemini extraction with agent recommendations"""
    return {
        **extracted_data,
        "agent_recommendations": agent_recommendations.get("agent_analysis"),
        "should_buy": agent_recommendations.get("should_buy"),
        "agent_reasoning": agent_recommendations.get("reasoning")
    }