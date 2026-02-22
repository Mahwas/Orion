# Orion Financial Agent: Current Issues & Future Roadmap

This document outlines the logical gaps discovered during simulation testing of the Orion Backend and proposes architectural improvements.

## 🔴 Current Logical Issues

### 1. Financial "Blind Spot" in Verdicts
**The Problem:** The agent's reasoning is financially sound, but its final verdict (`BUY`) is often contradictory. During simulation, the agent correctly identified that a $3,500 purchase would deplete 28% of a user's savings and significantly delay their house downpayment goal. However, it still returned `BUY`.
- **Root Cause:** The agent defaults to `BUY` if it fails to find a cheaper alternative product. It essentially says: *"This is a bad financial move for you, but since I can't find it cheaper elsewhere, buy it."*
- **Impact:** Low trustworthiness. The agent behaves like a shopping assistant rather than a financial advisor.

### 2. Search Precedence Over Analysis
**The Problem:** The "Alternative Search" loop has too much weight in the final decision-making process.
- **Root Cause:** The LangGraph logic likely prioritizes the `verdict` based on whether `similar_products_found` is empty or not.

---

## 🚀 Future Implementation Ideas

### 1. Shift Paradigms: From "Price" to "Impact"
- **Opportunity Cost Calculator:** Instead of just finding a cheaper item, show the user the "Cost of Not Investing." (e.g., *"This $500 purchase is actually $1,200 of lost retirement savings if invested in an index fund for 10 years."*)
- **Goal Timeline Impact:** Dynamically calculate the delay on current savings goals. (e.g., *"Buying this today pushes your 'Emergency Fund' completion date from June to August."*)

### 2. Strict Financial Guardrails
- **The Debt-First Rule:** If `user_data.debts` contains high-interest items (APR > 15%), the agent should automatically return `DO_NOT_BUY` for any "Want" above $50. The reasoning should explicitly prioritize debt payoff as a "guaranteed return."
- **Liquidity Buffers:** Introduce a rule that no discretionary purchase can exceed 5% of `current_balance`. If it does, the agent must advise waiting until the balance grows.

### 3. Behavioral Intervention
- **The "Cooling Off" Verdict:** For luxury items above a certain price threshold, the agent should return a mandatory "WAIT" status. It could say: *"Financial sanity check: Come back in 48 hours. If you still want it then, we will re-evaluate based on your budget."*
- **Alternative Financial "Products":** When the agent rejects a buy, it should recommend a "Financial Alternative" instead of a product. (e.g., *"I don't recommend this laptop. Instead, I suggest moving this $1,000 into your High-Yield Savings Account which is currently underfunded."*)

### 4. Logic Re-Structuring
- **Priority Stack (The "Decision Tree"):** Currently, "Search Results" seem to drive the verdict. The logic should be inverted to:
    1. **Financial Health Check** (Can they afford it without debt?)
    2. **Goal Alignment** (Does it slow down their house/car goals too much?)
    3. **Optimization** (Only here search for a better price).
- **Verdict Transparency:** Provide a "Financial Scorecard" for the purchase (e.g., Affordability: 2/10, Goal Alignment: 1/10, Necessity: 0/10).