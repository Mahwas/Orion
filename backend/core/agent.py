import os
import json
from openai import AsyncOpenAI
from models import PurchaseContext, FinancialSnapshot, BudgetMemory, DecisionOutput
from core.prompts import SYSTEM_PROMPT

# Default to a mock if API key isn't provided for the hackathon
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "mock_key"))

async def evaluate_purchase(
    context: PurchaseContext, 
    snapshot: FinancialSnapshot, 
    memory: BudgetMemory
) -> DecisionOutput:
    
    if os.getenv("OPENAI_API_KEY") is None:
        # Return fallback mock if no key is present for the demo
        return _fallback_decision(context, snapshot, memory)

    prompt = f"""
Financial Snapshot:
{snapshot.model_dump_json()}

Budget Memory:
{memory.model_dump_json()}

Purchase Request:
{context.model_dump_json()}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            # Use structured outputs via JSON schema matching our Pydantic model
            # For hackathon simplicity we'll just ask for json object and parse it
            response_format={"type": "json_object"}
        )
        
        raw_json = response.choices[0].message.content
        return DecisionOutput.model_validate_json(raw_json)
        
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return _fallback_decision(context, snapshot, memory)

def _fallback_decision(ctx: PurchaseContext, snap: FinancialSnapshot, mem: BudgetMemory) -> DecisionOutput:
    is_expensive = ctx.price > snap.discretionary_budget_remaining
    is_strict = mem.preferences.strictness > 0.7
    
    if is_expensive or (is_strict and ctx.price > snap.discretionary_budget_remaining * 0.5):
        verdict = "DISCOURAGE"
        reasons = [
            f"Item price (${ctx.price}) puts you {'over' if is_expensive else 'dangerously close to'} your discretionary budget matching your strictness level.",
            f"You have upcoming bills totaling ${snap.upcoming_bills_total}."
        ]
    else:
        verdict = "ENCOURAGE"
        reasons = [
            f"Within remaining discretionary budget (${snap.discretionary_budget_remaining}).",
            "Does not conflict with upcoming bills."
        ]

    return DecisionOutput(
        verdict=verdict,
        score=85 if verdict == "DISCOURAGE" else 90,
        reasons=reasons,
        conditions_to_yes=["Wait until payday"] if verdict == "DISCOURAGE" else [],
        alternatives=[{"title": f"Refurbished {ctx.product_title}", "price": round(ctx.price * 0.7, 2)}] if verdict == "DISCOURAGE" else [],
        followup_question="Is this purchase an absolute necessity today?"
    )
