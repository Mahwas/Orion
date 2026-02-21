from typing import TypedDict, Optional, List, Any
import os
import json
import asyncio
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
    synthesis_retries: int
    synthesis_error: Optional[str]

# Initialize LLM & Tools (allow fallback to mock if no key supplied)
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=os.getenv("GOOGLE_API_KEY", "mock_key"))
search_tool = DuckDuckGoSearchResults()

MAX_SYNTHESIS_RETRIES = 2

def _get_content_str(content: Any) -> str:
    """Helper to handle list content from some Google GenAI responses."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
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
    """Uses Google Shop Search (via SerpAPI) with triage context, or falls back to DDGS."""
    # Fix 4: Use triage reasoning to build a smarter search query
    triage_reasoning = state['triage_result'].get('reasoning', '')
    base_query = f"{state['product_data'].product_title} cheaper alternatives"
    query = f"{base_query} {triage_reasoning[:120]}"
    
    serp_key = os.getenv("SERPAPI_API_KEY")
    if serp_key:
        try:
            search = SerpAPIWrapper(search_engine="google", params={"tbm": "shop"}, serpapi_api_key=serp_key)
            # Fix 2: Non-blocking async call
            results = await asyncio.to_thread(search.run, query)
            return {"search_results": results}
        except Exception as e:
            print(f"Google Shop Search failed: {e}. Falling back to DuckDuckGo.")
    
    # Fallback to DuckDuckGo (also non-blocking)
    try:
        results = await asyncio.to_thread(search_tool.invoke, {"query": base_query})
    except Exception as e:
        results = f"Search failed: {e}"
    
    return {"search_results": results}

async def node_synthesize(state: AgentState):
    """Produces the final AnalysisResult with self-correction retry loop."""
    if not os.getenv("GOOGLE_API_KEY"):
        return {"final_decision": AnalysisResult(
            verdict="ALTERNATIVE_RECOMMENDED",
            reasoning="You can save money buying a refurbished unit.",
            similar_products_found=[AlternativeProduct(title=f"Refurbished {state['product_data'].product_title}", price=state['product_data'].price * 0.7)]
        )}

    # Build the prompt, including any prior error for self-correction
    error_context = ""
    if state.get("synthesis_error"):
        error_context = f"\n\n⚠️ YOUR PREVIOUS OUTPUT FAILED VALIDATION: {state['synthesis_error']}\nPlease fix the JSON and try again. Ensure it strictly matches the schema."

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
Triage Result: {json.dumps(state.get('triage_result'))}
Search Results: {state.get('search_results', 'None')}{error_context}
"""
    msgs = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    llm_json = llm.bind(response_format={"type": "json_object"})
    response = await llm_json.ainvoke(msgs)
    
    raw = _get_content_str(response.content)
    try:
        decision = AnalysisResult.model_validate_json(raw)
        return {"final_decision": decision, "synthesis_error": None}
    except Exception as e:
        retries = state.get("synthesis_retries", 0) + 1
        print(f"Synthesis parse failed (attempt {retries}/{MAX_SYNTHESIS_RETRIES}): {e}")
        return {
            "synthesis_retries": retries,
            "synthesis_error": f"{type(e).__name__}: {e}. Raw output was: {raw[:300]}",
            "final_decision": None
        }

# Fix 1: Fast paths now use the LLM's personalized triage reasoning
async def node_fast_reject(state: AgentState):
    """Returns an immediate reject using the LLM's own reasoning."""
    triage_reasoning = state['triage_result'].get('reasoning', 'This purchase was rejected based on your financial profile.')
    decision = AnalysisResult(verdict="DO_NOT_BUY", reasoning=triage_reasoning)
    return {"final_decision": decision}

async def node_fast_approve(state: AgentState):
    """Returns an immediate approve using the LLM's own reasoning."""
    triage_reasoning = state['triage_result'].get('reasoning', 'This purchase is approved based on your financial profile.')
    decision = AnalysisResult(verdict="BUY", reasoning=triage_reasoning)
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

def route_after_synthesize(state: AgentState) -> str:
    """Fix 3: Self-correction loop — retry synthesis if JSON parsing failed."""
    if state.get("final_decision") is not None:
        return END
    if state.get("synthesis_retries", 0) >= MAX_SYNTHESIS_RETRIES:
        return "synthesis_fallback"
    return "node_synthesize"  # Loop back for retry

async def node_synthesis_fallback(state: AgentState):
    """Graceful fallback after all retries are exhausted."""
    triage_reasoning = state.get('triage_result', {}).get('reasoning', 'Analysis could not be completed.')
    decision = AnalysisResult(
        verdict="DO_NOT_BUY",
        reasoning=f"We could not produce a structured recommendation after {MAX_SYNTHESIS_RETRIES} attempts. Based on initial triage: {triage_reasoning}"
    )
    return {"final_decision": decision}

# --- Graph Assembly ---
workflow = StateGraph(AgentState)

workflow.add_node("node_triage", node_triage)
workflow.add_node("node_search", node_search)
workflow.add_node("node_synthesize", node_synthesize)
workflow.add_node("fast_reject", node_fast_reject)
workflow.add_node("fast_approve", node_fast_approve)
workflow.add_node("synthesis_fallback", node_synthesis_fallback)

workflow.set_entry_point("node_triage")

workflow.add_conditional_edges("node_triage", route_after_triage)
workflow.add_edge("node_search", "node_synthesize")
workflow.add_conditional_edges("node_synthesize", route_after_synthesize)
workflow.add_edge("fast_reject", END)
workflow.add_edge("fast_approve", END)
workflow.add_edge("synthesis_fallback", END)

# Compile Graph
agent_app = workflow.compile()

# Entrypoint Function
async def execute_agent(user: UserData, product: ProductData) -> AnalysisResult:
    initial_state = {
        "user_data": user,
        "product_data": product,
        "triage_result": None,
        "search_results": None,
        "final_decision": None,
        "synthesis_retries": 0,
        "synthesis_error": None
    }
    
    final_state = await agent_app.ainvoke(initial_state)
    return final_state["final_decision"]
