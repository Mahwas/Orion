from Orion.backend.models.schemas import ProductData, UserData
from Orion.backend.core.agent import execute_agent

from pathlib import Path
import json 
import asyncio
import os


def build_product_data(extracted):
    title = "Unknown product"

    if extracted["items"]:
        title = extracted["items"][0]["name"]

    return ProductData(
        product_title=title,
        price=extracted.get("total", 0),
        category=extracted.get("category", "other"),
        description=extracted.get("description", "")
    ) 

def load_user():
    user_file = Path(__file__).parent / "Orion" / "backend" / "data" / "users" / "mock_users.json"
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
            "name": "Demo User",
            "monthly_income": 3000,
            "transactions": [
                {"date": "2026-02-01", "amount": 45.00, "category": "groceries"},
                {"date": "2026-02-02", "amount": 20.00, "category": "dining"},
                {"date": "2026-02-05", "amount": 80.00, "category": "electronics"},
            ],
            "savings_goals": {"emergency_fund": 5000, "vacation": 2000},
            "current_savings": 2500,
            "days_until_payday": 8,
            "budget_limits": {"groceries": 300, "dining": 150, "electronics": 200}
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
            "agent_analysis": result,
            "should_buy": result.get("is_recommended", False),
            "reasoning": result.get("explanation", "")
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