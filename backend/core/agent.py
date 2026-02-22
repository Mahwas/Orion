from typing import TypedDict, Optional, List, Any
import os
import json
import asyncio
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    # Simple mock LLM for environments without the package
    class ChatGoogleGenerativeAI:
        def __init__(self, model: str, google_api_key: str):
            self.model = model
            self.google_api_key = google_api_key
        def bind(self, **kwargs):
            class MockResponse:
                def __init__(self):
                    self.content = "{}"
                async def ainvoke(self, msgs):
                    return self
            return MockResponse()
try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    # Minimal mock message classes for environments without langchain_core
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content
    class SystemMessage:
        def __init__(self, content: str):
            self.content = content

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    # Simple mock StateGraph and END for testing
    class END:
        pass
    class StateGraph:
        def __init__(self, state_type):
            self.state_type = state_type
            self.nodes = {}
            self.edges = {}
            self.cond_edges = {}
            self.entry = None
        def add_node(self, name, fn):
            self.nodes[name] = fn
        def add_edge(self, src, dst):
            self.edges.setdefault(src, []).append(dst)
        def add_conditional_edges(self, src, fn):
            self.cond_edges[src] = fn
        def set_entry_point(self, name):
            self.entry = name
        def compile(self):
            class AgentApp:
                async def ainvoke(self, state):
                    return state
            return AgentApp()

try:
    from langchain_community.tools import DuckDuckGoSearchResults
except ImportError:
    class DuckDuckGoSearchResults:
        async def invoke(self, params):
            return ""

try:
    from langchain_community.utilities import SerpAPIWrapper
except ImportError:
    class SerpAPIWrapper:
        def __init__(self, *args, **kwargs):
            pass
        def results(self, query):
            return {"shopping_results": []}
from models.schemas import UserData, ProductData, AnalysisResult, AlternativeProduct
from core.prompts import (
    TRIAGE_SYSTEM_PROMPT,
    EVALUATE_PROMPT,
    COMPARE_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    FINAL_DECISION_NO_ALT_PROMPT,
)

MAX_SEARCH_RETRIES = 2
MAX_SYNTHESIS_RETRIES = 2

# --- State Definition ---
class AgentState(TypedDict):
    user_data: UserData
    product_data: ProductData
    triage_result: Optional[dict]
    search_results: Optional[str]
    viable_candidates: List[dict]        # Top picks from evaluate node
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
    product_title = state['product_data'].product_title
    base_query = f"{product_title} cheaper alternatives"
    
    allow_second_hand = getattr(state['user_data'], 'allow_second_hand', True)
    if not allow_second_hand:
        base_query += " new -used -refurbished"
        
    retries = state.get("search_retries", 0)
    if retries > 0:
        # If we're retrying, it means the first search probably yielded the exact same product or bad results
        base_query = f"{product_title} alternative brands different models"
        if not allow_second_hand:
            base_query += " new condition"

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
        mock_cand = {"title": f"Budget {state['product_data'].product_title}", "price": state['product_data'].price * 0.6, "url": "https://example.com/mock-product"}
        return {"viable_candidates": [mock_cand], "is_better": None}

    # Include user's second-hand preference in the evaluation prompt
    allow_second_hand = getattr(state['user_data'], 'allow_second_hand', True)
    prompt = f"""
Original Product: {state['product_data'].model_dump_json()}
User Preference - Allow Second Hand: {allow_second_hand}
Raw Search Results:
{state.get('search_results', 'No results')}
"""
    msgs = [SystemMessage(content=EVALUATE_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    eval_data = json.loads(_get_content_str(response.content))
    # After receiving evaluation data, filter out second-hand items if user disallows them
    allow_second_hand = getattr(state['user_data'], 'allow_second_hand', True)
    candidates = eval_data.get("viable_candidates", [])
    if not allow_second_hand:
        second_hand_keywords = ["used", "refurbished", "pre-owned", "second hand", "second-hand", "secondhand"]
        def is_second_hand(title: str) -> bool:
            lower = title.lower()
            return any(kw in lower for kw in second_hand_keywords)
        candidates = [c for c in candidates if not is_second_hand(c.get("title", ""))]
    # Exclude candidates that are the same product as the original (by title similarity)
    original_title = state['product_data'].product_title.lower()
    def is_same_product(title: str) -> bool:
        t = title.lower()
        return original_title in t or t in original_title
    candidates = [c for c in candidates if not is_same_product(c.get("title", ""))]
    return {"viable_candidates": candidates, "is_better": None}  # reset is_better for this pass


async def node_compare(state: AgentState):
    """
    NEW: Compares the best candidate vs the original product for this specific user.
    Decides if the alternative is genuinely worth it.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        candidates = state.get("viable_candidates", [])
        return {"is_better": True}

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
Original Product: {state['product_data'].model_dump_json()}
Candidate Alternatives: {json.dumps(state.get('viable_candidates'))}
"""
    msgs = [SystemMessage(content=COMPARE_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    compare_data = json.loads(_get_content_str(response.content))
    return {
        "is_better": compare_data.get("is_better", False),
    }


async def node_synthesize(state: AgentState):
    """Produces the final AnalysisResult using the validated alternative."""
    if not os.getenv("GOOGLE_API_KEY"):
        cands = state.get("viable_candidates", [])
        alt_list = [AlternativeProduct(title=c.get("title", "Alt"), price=c.get("price", 0), url=c.get("url")) for c in cands]
        return {"final_decision": AnalysisResult(
            verdict="ALTERNATIVE_RECOMMENDED",
            reasoning="You can save money buying these alternatives.",
            original_product_url=state['product_data'].url,
            similar_products_found=alt_list
        )}

    error_context = ""
    if state.get("synthesis_error"):
        error_context = f"\n\n⚠️ PREVIOUS OUTPUT FAILED VALIDATION: {state['synthesis_error']}\nFix the JSON and strictly match the schema."

    prompt = f"""
UserData: {state['user_data'].model_dump_json()}
ProductData: {state['product_data'].model_dump_json()}
Triage Result: {json.dumps(state.get('triage_result'))}
Validated Alternatives: {json.dumps(state.get('viable_candidates'))}{error_context}
"""
    msgs = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    raw = _get_content_str(response.content)

    try:
        decision = AnalysisResult.model_validate_json(raw)
        # Always inject the original URL so the frontend can offer a buy button
        decision.original_product_url = state['product_data'].url
        return {"final_decision": decision, "synthesis_error": None}
    except Exception as e:
        retries = state.get("synthesis_retries", 0) + 1
        print(f"Synthesis parse failed (attempt {retries}/{MAX_SYNTHESIS_RETRIES}): {e}")
        return {"synthesis_retries": retries, "synthesis_error": f"{type(e).__name__}: {e}. Raw: {raw[:300]}", "final_decision": None}



async def node_no_alternative_found(state: AgentState):
    """
    NEW: Graceful exit after 2 search/evaluate/compare loops with no better product.
    Tells the user we tried twice and couldn't find anything better.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        return {"final_decision": AnalysisResult(verdict="BUY", reasoning="Mock: no alternatives found.", original_product_url=state['product_data'].url)}

    prompt = FINAL_DECISION_NO_ALT_PROMPT.format(
        user_data=state['user_data'].model_dump_json(),
        product_data=state['product_data'].model_dump_json(),
        triage_reasoning=state.get('triage_result', {}).get('reasoning', '')
    )
    
    msgs = [HumanMessage(content=prompt)]
    response = await llm.bind(response_format={"type": "json_object"}).ainvoke(msgs)
    raw = _get_content_str(response.content)
    
    try:
        decision = AnalysisResult.model_validate_json(raw)
        decision.original_product_url = state['product_data'].url
        return {"final_decision": decision}
    except Exception as e:
        print(f"Final Decision Fallback failed: {e}")
        return {"final_decision": AnalysisResult(
            verdict="DO_NOT_BUY", 
            reasoning="We could not find a better price, and the final safety check failed to validate a purchase.",
            original_product_url=state['product_data'].url
        )}


async def node_synthesis_fallback(state: AgentState):
    """Graceful fallback after synthesis retries are exhausted."""
    triage_reasoning = state.get('triage_result', {}).get('reasoning', 'Analysis could not be completed.')
    decision = AnalysisResult(
        verdict="DO_NOT_BUY",
        reasoning=f"Recommendation failed after {MAX_SYNTHESIS_RETRIES} attempts. Triage said: {triage_reasoning}",
        original_product_url=state['product_data'].url
    )
    return {"final_decision": decision}


# =============================================================================
# ROUTING
# =============================================================================


def route_after_evaluate(state: AgentState) -> str:
    """Route based on whether a viable candidate was found."""
    if state.get("viable_candidates"):
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
workflow.add_node("node_no_alternative_found", node_no_alternative_found)
workflow.add_node("synthesis_fallback", node_synthesis_fallback)

workflow.set_entry_point("node_triage")

workflow.add_edge("node_triage", "node_search")
workflow.add_edge("node_search", "node_evaluate_alternative")
workflow.add_conditional_edges("node_evaluate_alternative", route_after_evaluate)
workflow.add_conditional_edges("node_compare", route_after_compare)
workflow.add_conditional_edges("node_synthesize", route_after_synthesize)
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
        "viable_candidates": [],
        "is_better": None,
        "search_retries": 0,
        "final_decision": None,
        "synthesis_retries": 0,
        "synthesis_error": None,
    }

    final_state = await agent_app.ainvoke(initial_state)
    return final_state["final_decision"]
