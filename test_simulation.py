import asyncio
import json
import reasoningLLM
import bridge_Orion

print("Starting Simulated User Test...")
print("==============================")

# 1. We mock the image capture process and just send our downloaded image
image_path = "fake_receipt.png"
print(f"Simulating screenshot capture: {image_path}")

# 2. Extract Data using teammate's Gemini 2.5 flash logic
print("\n[AI Vision] Sending screenshot to Gemini 2.5 Flash for parsing...")
result = reasoningLLM.send_to_gemini(image_path)
extracted_data = result["extracted_data"]

print("\n--- Extracted Raw Data ---")
print(json.dumps(extracted_data, indent=2))

print("\n--- Gemini Advice ---")
print(result["gemini_advice"])

# 3. If extracted safely, run the LangGraph reasoning bridge
if reasoningLLM.AGENT_AVAILABLE:
    print("\n[LangGraph Bridge] Passing extracted product to core agent...")
    try:
        # Mocking user context inside the bridge (done previously in create_mock_user_data)
        agent_recommendations = asyncio.run(bridge_Orion.get_agent_recommendations(extracted_data))
        extracted_data = bridge_Orion.enhance_extracted_data(extracted_data, agent_recommendations)
        
        print("\n--- Final Agent Verdict ---")
        if "should_buy" in extracted_data:
            print(f"Should Buy: {extracted_data['should_buy']}")
            print(f"Reasoning: {extracted_data['agent_reasoning']}")
            
        print("\n[Storage] Appending to expenses.json")
        reasoningLLM.add_expense_to_history(extracted_data)
        print("Done!")
    except Exception as e:
        print(f"Bridge failed: {e}")
