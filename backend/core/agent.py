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
from core.prompts import (
    TRIAGE_SYSTEM_PROMPT,
    EVALUATE_PROMPT,
    COMPARE_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)

MAX_SEARCH_RETRIES = 2
MAX_SYNTHESIS_RETRIES = 2

# --- State Definition ---
class AgentState(TypedDict):
    user_data: UserData
    product_data: ProductData
    triage_result: Optional[dict]
    search_results: Optional[str]
    best_candidate: Optional[dict]       # Top pick from evaluate node
    is_better: Optional[bool]            # Result of compare node
    selected_alternative: Optional[dict] # Final chosen alternative
    search_retries: int                  # Tracks search loop count
    final_decision: Optional[AnalysisResult]
    synthesis_retries: int
    synthesis_error: Optional[str]

# --- Initialize LLM & Tools ---
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=os.getenv("GOOGLE_API_KEY", "mock_key"))
search_tool = DuckDuckGoSearchResults()

def _get_content_str(content: Any) -> str:
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

# =============================================================================
# NODES
# =============================================================================

async def node_triage(state: AgentState):
    """Analyzes product affordability and usefulness."""
    if not os.getenv("GOOGLE_API_KEY"):
        return {"triage_result": {"action": "SEARCH_ALTERNATIVES", "reasoning": "Mock evaluation needs alternatives."}}

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
"""
    msgs = [SystemMessage(content=TRIAGE_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    triage_data = json.loads(_get_content_str(response.content))
    return {"triage_result": triage_data}


async def node_search(state: AgentState):
    """Searches for alternatives using triage reasoning as context, non-blocking."""
    triage_reasoning = state['triage_result'].get('reasoning', '')
    base_query = f"{state['product_data'].product_title} cheaper alternatives"
    query = f"{base_query} {triage_reasoning[:120]}"

    serp_key = os.getenv("SERPAPI_API_KEY")
    if serp_key:
        try:
            search = SerpAPIWrapper(search_engine="google", params={"tbm": "shop"}, serpapi_api_key=serp_key)
            # Use .results() to get structured JSON with extracted_price, title, product_link
            raw = await asyncio.to_thread(search.results, query)
            # Extract just the shopping items list for the LLM
            items = raw.get("shopping_results", [])
            compact = [
                {
                    "title": r.get("title"),
                    "extracted_price": r.get("extracted_price"),
                    "rating": r.get("rating"),
                    "reviews": r.get("reviews"),
                    "product_link": r.get("product_link"),
                }
                for r in items[:8]
            ]
            results = json.dumps(compact)
            return {"search_results": results, "search_retries": state.get("search_retries", 0) + 1}
        except Exception as e:
            print(f"Google Shop Search failed: {e}. Falling back to DuckDuckGo.")

    try:
        results = await asyncio.to_thread(search_tool.invoke, {"query": base_query})
        results = str(results)
    except Exception as e:
        results = f"Search failed: {e}"

    return {"search_results": results, "search_retries": state.get("search_retries", 0) + 1}


async def node_evaluate_alternative(state: AgentState):
    """
    NEW: Parses raw search results to find the best viable candidate.
    Determines if any result is cheaper, same category, and purchasable.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        # Mock: pretend we found something reasonable
        return {"best_candidate": {"title": f"Budget {state['product_data'].product_title}", "price": state['product_data'].price * 0.6, "url": None}, "is_better": None}

    prompt = f"""
Original Product: {state['product_data'].model_dump_json()}
Raw Search Results:
{state.get('search_results', 'No results')}
"""
    msgs = [SystemMessage(content=EVALUATE_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    eval_data = json.loads(_get_content_str(response.content))
    return {"best_candidate": eval_data.get("best_candidate"), "is_better": None}  # reset is_better for this pass


async def node_compare(state: AgentState):
    """
    NEW: Compares the best candidate vs the original product for this specific user.
    Decides if the alternative is genuinely worth it.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        candidate = state.get("best_candidate") or {}
        return {"is_better": True, "selected_alternative": candidate}

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
Original Product: {state['product_data'].model_dump_json()}
Candidate Alternative: {json.dumps(state.get('best_candidate'))}
"""
    msgs = [SystemMessage(content=COMPARE_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    compare_data = json.loads(_get_content_str(response.content))
    return {
        "is_better": compare_data.get("is_better", False),
        "selected_alternative": compare_data.get("selected_alternative"),
    }


async def node_synthesize(state: AgentState):
    """Produces the final AnalysisResult using the validated alternative."""
    if not os.getenv("GOOGLE_API_KEY"):
        alt = state.get("selected_alternative") or {}
        return {"final_decision": AnalysisResult(
            verdict="ALTERNATIVE_RECOMMENDED",
            reasoning="You can save money buying this alternative.",
            similar_products_found=[AlternativeProduct(title=alt.get("title", "Alternative"), price=alt.get("price", 0))]
        )}

    error_context = ""
    if state.get("synthesis_error"):
        error_context = f"\n\n⚠️ PREVIOUS OUTPUT FAILED VALIDATION: {state['synthesis_error']}\nFix the JSON and strictly match the schema."

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
Triage Result: {json.dumps(state.get('triage_result'))}
Validated Alternative: {json.dumps(state.get('selected_alternative'))}{error_context}
"""
    msgs = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    raw = _get_content_str(response.content)

    try:
        decision = AnalysisResult.model_validate_json(raw)
        return {"final_decision": decision, "synthesis_error": None}
    except Exception as e:
        retries = state.get("synthesis_retries", 0) + 1
        print(f"Synthesis parse failed (attempt {retries}/{MAX_SYNTHESIS_RETRIES}): {e}")
        return {"synthesis_retries": retries, "synthesis_error": f"{type(e).__name__}: {e}. Raw: {raw[:300]}", "final_decision": None}


# Fast-path nodes use the LLM's own triage reasoning
async def node_fast_reject(state: AgentState):
    reasoning = state['triage_result'].get('reasoning', 'Purchase rejected based on your financial profile.')
    return {"final_decision": AnalysisResult(verdict="DO_NOT_BUY", reasoning=reasoning)}

async def node_fast_approve(state: AgentState):
    reasoning = state['triage_result'].get('reasoning', 'Purchase approved based on your financial profile.')
    return {"final_decision": AnalysisResult(verdict="BUY", reasoning=reasoning)}


async def node_no_alternative_found(state: AgentState):
    """
    NEW: Graceful exit after 2 search/evaluate/compare loops with no better product.
    Tells the user we tried twice and couldn't find anything better.
    """
    triage_reasoning = state.get('triage_result', {}).get('reasoning', '')
    decision = AnalysisResult(
        verdict="BUY",
        reasoning=(
            f"We searched {state.get('search_retries', MAX_SEARCH_RETRIES)} times but could not find a "
            f"meaningfully better or cheaper alternative for the {state['product_data'].product_title}. "
            f"If your budget allows, the original product appears to be the best available option. "
            f"Financial context: {triage_reasoning}"
        ),
        similar_products_found=[]
    )
    return {"final_decision": decision}


async def node_synthesis_fallback(state: AgentState):
    """Graceful fallback after synthesis retries are exhausted."""
    triage_reasoning = state.get('triage_result', {}).get('reasoning', 'Analysis could not be completed.')
    decision = AnalysisResult(
        verdict="DO_NOT_BUY",
        reasoning=f"Recommendation failed after {MAX_SYNTHESIS_RETRIES} attempts. Triage said: {triage_reasoning}"
    )
    return {"final_decision": decision}


# =============================================================================
# ROUTING
# =============================================================================

def route_after_triage(state: AgentState) -> str:
    action = state['triage_result'].get('action', 'SEARCH_ALTERNATIVES')
    if action == "REJECT":
        return "fast_reject"
    elif action == "APPROVE":
        return "fast_approve"
    return "node_search"


def route_after_evaluate(state: AgentState) -> str:
    """Route based on whether a viable candidate was found."""
    if state.get("best_candidate"):
        return "node_compare"
    if state.get("search_retries", 0) < MAX_SEARCH_RETRIES:
        return "node_search"  # Retry with a new search
    return "node_no_alternative_found"


def route_after_compare(state: AgentState) -> str:
    """Route based on whether the candidate is actually better."""
    if state.get("is_better"):
        return "node_synthesize"
    if state.get("search_retries", 0) < MAX_SEARCH_RETRIES:
        return "node_search"  # Retry with a fresh search
    return "node_no_alternative_found"


def route_after_synthesize(state: AgentState) -> str:
    """Self-correction: retry synthesis on JSON parse failure."""
    if state.get("final_decision") is not None:
        return END
    if state.get("synthesis_retries", 0) >= MAX_SYNTHESIS_RETRIES:
        return "synthesis_fallback"
    return "node_synthesize"


# =============================================================================
# GRAPH ASSEMBLY
# =============================================================================

workflow = StateGraph(AgentState)

workflow.add_node("node_triage", node_triage)
workflow.add_node("node_search", node_search)
workflow.add_node("node_evaluate_alternative", node_evaluate_alternative)
workflow.add_node("node_compare", node_compare)
workflow.add_node("node_synthesize", node_synthesize)
workflow.add_node("fast_reject", node_fast_reject)
workflow.add_node("fast_approve", node_fast_approve)
workflow.add_node("node_no_alternative_found", node_no_alternative_found)
workflow.add_node("synthesis_fallback", node_synthesis_fallback)

workflow.set_entry_point("node_triage")

workflow.add_conditional_edges("node_triage", route_after_triage)
workflow.add_edge("node_search", "node_evaluate_alternative")
workflow.add_conditional_edges("node_evaluate_alternative", route_after_evaluate)
workflow.add_conditional_edges("node_compare", route_after_compare)
workflow.add_conditional_edges("node_synthesize", route_after_synthesize)
workflow.add_edge("fast_reject", END)
workflow.add_edge("fast_approve", END)
workflow.add_edge("node_no_alternative_found", END)
workflow.add_edge("synthesis_fallback", END)

# Compile Graph
agent_app = workflow.compile()


# =============================================================================
# ENTRYPOINT
# =============================================================================

async def execute_agent(user: UserData, product: ProductData) -> AnalysisResult:
    initial_state = {
        "user_data": user,
        "product_data": product,
        "triage_result": None,
        "search_results": None,
        "best_candidate": None,
        "is_better": None,
        "selected_alternative": None,
        "search_retries": 0,
        "final_decision": None,
        "synthesis_retries": 0,
        "synthesis_error": None,
    }

    final_state = await agent_app.ainvoke(initial_state)
    return final_state["final_decision"]
