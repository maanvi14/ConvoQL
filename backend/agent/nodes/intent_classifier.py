"""Intent classifier: Determines query type with deterministic type_filter enforcement."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import json
import re

from config import get_settings

settings = get_settings()

# === DETERMINISTIC TYPE FILTER SIGNALS ===
# These are checked AFTER the LLM to override hallucinations
# CRITICAL FIX: Removed "shopping" - it's a category name, not an expense signal
# Category names should NEVER trigger type_filter. Only explicit expense/income verbs should.
DEBIT_SIGNALS = {
    "expense", "expenses", "spent", "spending", "spend",
    "purchase", "purchased", "purchases",
    "paid", "pay", "payment", "payments",
    "buy", "bought",
    "debit", "debits",
    "cost", "costs",
    "withdrawal", "withdraw", "withdrawn",
    "charge", "charges",
    "fee", "fees",
    "outgoing", "outflow",
    "expenditure", "outgoings", "outgo", "spendings",
    "bills", "bill"
    # REMOVED: "shopping" — category name, not expense verb
}

CREDIT_SIGNALS = {
    "income", "incomes", "earned", "earn", "earnings",
    "receive", "received", "receiving",
    "salary", "salaries", "credited", "credit", "credits",
    "deposit", "deposited",
    "refund", "refunded", "refunds",
    "incoming", "inflow",
    "revenue", "revenues",
    "wage", "wages",
    "bonus", "bonuses",
    "dividend", "dividends",
    "interest",
    "profit", "profits",
    "gains", "gain"
}

# Signals that REQUIRE multi-table JOINs
JOIN_SIGNALS = {
    "budget", "budgets", "allocated", "over budget", "under budget", "budget vs",
    "budget limit", "budget utilization", "budget comparison",
    "account balance", "balances", "total balance", "highest balance",
    "bank balance", "account metadata"
}

INTENT_PROMPT = """You are a query intent classifier for a financial text-to-SQL system.

Classify the user's question into EXACTLY ONE primary intent and any secondary intents.

Available intents:
- "aggregation": SUM, COUNT, AVG, MAX, MIN (e.g., "how much", "total", "average")
- "filter_lookup": Find specific rows (e.g., "show me", "list", "find")
- "multi_table_join": Needs data from multiple tables (e.g., "budget vs actual", "compare")
- "trend": Time-series analysis (e.g., "over time", "monthly", "trend")
- "anomaly": Detect unusual patterns (e.g., "unusual", "strange", "anomaly")
- "budget_compare": Budget vs spending comparison
- "metadata": Account/category metadata (e.g., "what categories", "account balance")
- "ranking": Top/bottom N (e.g., "highest", "lowest", "top 5")

CRITICAL RULES for type_filter (debit/credit):
1. ONLY add a type_filter when the user EXPLICITLY mentions expense/spending words OR income/salary words
2. NEVER infer type_filter from category names, tags, or merchant names
3. Tags and categories exist on BOTH debit and credit transactions
4. When in doubt, type_filter MUST be null
5. "Shopping" is a CATEGORY — it does NOT mean expenses
6. "Food" is a CATEGORY — it does NOT mean expenses
7. "Travel" is a CATEGORY — it does NOT mean expenses

Return ONLY a JSON object:
{{
  "primary_intent": "...",
  "secondary_intents": ["..."],
  "confidence": 0.0-1.0,
  "requires_join": true/false,
  "time_dimension": null or "this_month" or "last_month" or "specific_month" or "range" or "all_time",
  "aggregation_type": null or "sum" or "count" or "avg" or "max" or "min",
  "type_filter": null or "debit" or "credit",
  "entities": ["category names", "account names", "merchant names", "tags", "dates mentioned"]
}}

User Question: {question}

JSON:"""


def _enforce_type_filter(question: str, intent_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic override of LLM type_filter hallucinations.
    The LLM often incorrectly infers type_filter from category/tag names.
    """
    q_lower = question.lower()
    # Extract words, removing punctuation
    words = set(re.findall(r'\b[a-z]+\b', q_lower))

    has_debit = bool(DEBIT_SIGNALS & words)
    has_credit = bool(CREDIT_SIGNALS & words)
    current = intent_data.get("type_filter")

    # Case 1: No explicit signals → FORCE null
    if not has_debit and not has_credit:
        if current is not None:
            print(f"[IntentClassifier] OVERRIDING type_filter from '{current}' to null. "
                  f"No explicit debit/credit signals in: '{question}'")
            intent_data["type_filter"] = None
        return intent_data

    # Case 2: Both signals present → null (let query handle both)
    if has_debit and has_credit:
        if current is not None:
            print(f"[IntentClassifier] Both debit and credit signals found. Setting type_filter to null.")
            intent_data["type_filter"] = None
        return intent_data

    # Case 3: Override to correct signal
    if has_debit and current != "debit":
        print(f"[IntentClassifier] Correcting type_filter to 'debit' based on explicit signals: {DEBIT_SIGNALS & words}")
        intent_data["type_filter"] = "debit"
    elif has_credit and current != "credit":
        print(f"[IntentClassifier] Correcting type_filter to 'credit' based on explicit signals: {CREDIT_SIGNALS & words}")
        intent_data["type_filter"] = "credit"

    # === JOIN DETECTION ===
    # Force requires_join=True for budget/account balance queries
    has_join_signal = bool(JOIN_SIGNALS & words)
    if has_join_signal:
        if not intent_data.get("requires_join", False):
            print(f"[IntentClassifier] Forcing requires_join=True for multi-table query: {JOIN_SIGNALS & words}")
            intent_data["requires_join"] = True
            intent_data["primary_intent"] = "multi_table_join"

    return intent_data


async def intent_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    prompt = ChatPromptTemplate.from_template(INTENT_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({"question": state["question"]})

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        intent_data = json.loads(content)

        # Validate required fields
        intent_data.setdefault("primary_intent", "filter_lookup")
        intent_data.setdefault("secondary_intents", [])
        intent_data.setdefault("confidence", 0.5)
        intent_data.setdefault("requires_join", False)
        intent_data.setdefault("time_dimension", None)
        intent_data.setdefault("aggregation_type", None)
        intent_data.setdefault("type_filter", None)
        intent_data.setdefault("entities", [])

        # === CRITICAL FIX: Enforce type_filter rules deterministically ===
        intent_data = _enforce_type_filter(state["question"], intent_data)

    except Exception as e:
        print(f"Intent classification failed: {e}. Falling back to filter_lookup.")
        intent_data = {
            "primary_intent": "filter_lookup",
            "secondary_intents": [],
            "confidence": 0.5,
            "requires_join": False,
            "time_dimension": None,
            "aggregation_type": None,
            "type_filter": None,
            "entities": [],
        }

    return {
        **state,
        "intent": intent_data,
    }


