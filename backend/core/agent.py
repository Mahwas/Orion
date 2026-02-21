from typing import TypedDict, Optional, List, Any
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import SerpAPIWrapper
from models.schemas import UserData, ProductData, AnalysisResult, AlternativeProduct
from core.prompts import TRIAGE_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT

# State Definition
class AgentState(TypedDict):
    user_data: UserData
    product_data: ProductData
    triage_result: Optional[dict]
    search_results: Optional[str]
    final_decision: Optional[AnalysisResult]

# Initialize LLM & Tools (allow fallback to mock if no key supplied)
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=os.getenv("GOOGLE_API_KEY", "mock_key"))
search_tool = DuckDuckGoSearchResults()

def _get_content_str(content: Any) -> str:
    """Helper to handle list content from some Google GenAI responses."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Join text parts
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
        return "".join(texts)
    return str(content)

# --- Nodes ---

async def node_triage(state: AgentState):
    """Analyzes the product affordability and usefulness."""
    if not os.getenv("GOOGLE_API_KEY"):
        # Static mock for Hackathon without API keys
        return {"triage_result": {"action": "SEARCH_ALTERNATIVES", "reasoning": "Mock evaluation needs alternatives."}}
    
    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
"""
    msgs = [SystemMessage(content=TRIAGE_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    llm_json = llm.bind(response_format={"type": "json_object"})
    response = await llm_json.ainvoke(msgs)
    triage_data = json.loads(_get_content_str(response.content))
    
    return {"triage_result": triage_data}

async def node_search(state: AgentState):
    """Uses Google Shop Search (via SerpAPI) or DDGS tool to find similar or cheaper items."""
    query = f"cheap alternatives to {state['product_data'].product_title} price"
    
    serp_key = os.getenv("SERPAPI_API_KEY")
    if serp_key:
        try:
            search = SerpAPIWrapper(search_engine="google", params={"tbm": "shop"}, serpapi_api_key=serp_key)
            results = search.run(query)
            return {"search_results": results}
        except Exception as e:
            print(f"Google Shop Search failed: {e}. Falling back to DuckDuckGo.")
    
    # Fallback to DuckDuckGo
    try:
        results = search_tool.invoke({"query": query})
    except Exception as e:
        results = f"Search failed: {e}"
    
    return {"search_results": results}

async def node_synthesize(state: AgentState):
    """Produces the final AnalysisResult."""
    if not os.getenv("GOOGLE_API_KEY"):
        # Mock Response
        return {"final_decision": AnalysisResult(
            verdict="ALTERNATIVE_RECOMMENDED",
            reasoning="You can save money buying a refurbished unit.",
            similar_products_found=[AlternativeProduct(title=f"Refurbished {state['product_data'].product_title}", price=state['product_data'].price * 0.7)]
        )}

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
Triage Result: {json.dumps(state.get('triage_result'))}
Search Results: {state.get('search_results', 'None')}
"""
    msgs = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    llm_json = llm.bind(response_format={"type": "json_object"})
    response = await llm_json.ainvoke(msgs)
    
    try:
        decision = AnalysisResult.model_validate_json(_get_content_str(response.content))
    except Exception as e:
        print("Failed to parse synthesis:", e)
        decision = AnalysisResult(verdict="DO_NOT_BUY", reasoning="Parsing failed due to LLM hallucination.")
        
    return {"final_decision": decision}

async def node_fast_reject(state: AgentState):
    """Returns an immediate reject if triage deems it extremely dangerous."""
    decision = AnalysisResult(
        verdict="DO_NOT_BUY",
        reasoning="This purchase drastically exceeds your discretionary budget and goals."
    )
    return {"final_decision": decision}

async def node_fast_approve(state: AgentState):
    """Returns an immediate approve for basic needs."""
    decision = AnalysisResult(
        verdict="BUY",
        reasoning="This is classified as a fundamental need and is within budget."
    )
    return {"final_decision": decision}


# --- Routing ---
def route_after_triage(state: AgentState) -> str:
    action = state['triage_result'].get('action', 'SEARCH_ALTERNATIVES')
    if action == "REJECT":
        return "fast_reject"
    elif action == "APPROVE":
        return "fast_approve"
    else:
        return "node_search"

# --- Graph Assembly ---
workflow = StateGraph(AgentState)

workflow.add_node("node_triage", node_triage)
workflow.add_node("node_search", node_search)
workflow.add_node("node_synthesize", node_synthesize)
workflow.add_node("fast_reject", node_fast_reject)
workflow.add_node("fast_approve", node_fast_approve)

workflow.set_entry_point("node_triage")

workflow.add_conditional_edges("node_triage", route_after_triage)
workflow.add_edge("node_search", "node_synthesize")
workflow.add_edge("node_synthesize", END)
workflow.add_edge("fast_reject", END)
workflow.add_edge("fast_approve", END)

# Compile Graph
agent_app = workflow.compile()

# Entrypoint Function
async def execute_agent(user: UserData, product: ProductData) -> AnalysisResult:
    initial_state = {
        "user_data": user,
        "product_data": product,
        "triage_result": None,
        "search_results": None,
        "final_decision": None
    }
    
    final_state = await agent_app.ainvoke(initial_state)
    return final_state["final_decision"]
