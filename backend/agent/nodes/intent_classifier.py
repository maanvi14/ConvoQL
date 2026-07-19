"""Intent classifier: Determines query type with deterministic type_filter enforcement."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List, Set, Tuple
import json
import re

from config import get_settings
from db.connection import db_manager

settings = get_settings()

# === GREETING / IRRELEVANCE DETECTION ===
# Deterministic guard: catch greetings, small talk, and non-data questions
# BEFORE the LLM call to avoid burning tokens and generating garbage SQL.
GREETING_PATTERNS = [
    r'^\s*hello\s*$',
    r'^\s*hi\s*$',
    r'^\s*hey\s*$',
    r'^\s*howdy\s*$',
    r'^\s*greetings\s*$',
    r'^\s*good morning\s*$',
    r'^\s*good afternoon\s*$',
    r'^\s*good evening\s*$',
    r'^\s*what\s+up\s*$',
    r'^\s*sup\s*$',
    r'^\s*yo\s*$',
    r'^\s*thanks?\s*$',
    r'^\s*thank you\s*$',
    r'^\s*bye\s*$',
    r'^\s*goodbye\s*$',
    r'^\s*see ya\s*$',
    r'^\s*ok\s*$',
    r'^\s*okay\s*$',
    r'^\s*sure\s*$',
    r'^\s*yes\s*$',
    r'^\s*no\s*$',
    r'^\s*maybe\s*$',
    r'^\s*\?+\s*$',
]

IRRELEVANT_PATTERNS = [
    r'\bweather\b',
    r'\bnews\b',
    r'\bjoke\b',
    r'\bstory\b',
    r'\btime is it\b',
    r'\bwho are you\b',
    r'\bwhat can you do\b',
]

# Financial/data keywords that indicate a valid query
DATA_KEYWORDS = {
    "spend", "spent", "spending", "expense", "expenses", "budget", "allocated",
    "transaction", "transactions", "account", "accounts", "balance", "income",
    "salary", "credit", "debit", "purchase", "purchased", "bought", "paid",
    "payment", "category", "categories", "merchant", "tag", "tags",
    "month", "year", "date", "trend", "compare", "vs", "versus", "highest",
    "lowest", "top", "average", "total", "sum", "amount", "money", "cash",
    "saving", "savings", "investment", "dividend", "interest", "refund",
    "bill", "bills", "rent", "groceries", "food", "travel", "shopping",
    "health", "entertainment", "uber", "amazon", "netflix", "zomato",
    "swiggy", "hdfc", "icici", "paytm", "upi", "card", "loan", "emi",
    "over", "under", "utilization",
}


def _is_greeting_or_irrelevant(question: str) -> Tuple[bool, str]:
    """Return (True, reason) if the question is a greeting, small talk,
    or completely irrelevant to financial data analysis."""
    q_lower = question.lower().strip()

    for pattern in GREETING_PATTERNS:
        if re.search(pattern, q_lower):
            return True, "greeting"

    for pattern in IRRELEVANT_PATTERNS:
        if re.search(pattern, q_lower):
            return True, "irrelevant"

    words = set(re.findall(r'\b[a-z]+\b', q_lower))
    if not (words & DATA_KEYWORDS):
        if len(q_lower.split()) <= 2 and not any(c.isdigit() for c in q_lower):
            return True, "no_data_keywords"

    return False, ""


# === DETERMINISTIC TYPE FILTER SIGNALS ===
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
    words = set(re.findall(r'\b[a-z]+\b', q_lower))

    has_debit = bool(DEBIT_SIGNALS & words)
    has_credit = bool(CREDIT_SIGNALS & words)
    current = intent_data.get("type_filter")

    if not has_debit and not has_credit:
        if current is not None:
            print(f"[IntentClassifier] OVERRIDING type_filter from '{current}' to null. "
                  f"No explicit debit/credit signals in: '{question}'")
            intent_data["type_filter"] = None
        return intent_data

    if has_debit and has_credit:
        if current is not None:
            print(f"[IntentClassifier] Both debit and credit signals found. Setting type_filter to null.")
            intent_data["type_filter"] = None
        return intent_data

    if has_debit and current != "debit":
        print(f"[IntentClassifier] Correcting type_filter to 'debit' based on explicit signals: {DEBIT_SIGNALS & words}")
        intent_data["type_filter"] = "debit"
    elif has_credit and current != "credit":
        print(f"[IntentClassifier] Correcting type_filter to 'credit' based on explicit signals: {CREDIT_SIGNALS & words}")
        intent_data["type_filter"] = "credit"

    return intent_data


async def _detect_join_signals(question: str) -> Tuple[bool, Set[str]]:
    """Determine whether the question likely needs a multi-table JOIN."""
    try:
        schema = await db_manager.get_schema()
    except Exception as e:
        print(f"[IntentClassifier] Could not load schema for join detection: {e}")
        return False, set()

    tables = schema.get("tables", [])
    if len(tables) <= 1:
        return False, set()

    primary = max(tables, key=lambda t: len(t.get("columns", [])))
    primary_cols = {c["name"].lower() for c in primary.get("columns", [])}

    q_lower = question.lower()
    hits: Set[str] = set()

    for table in tables:
        table_name_lower = table["name"].lower()
        if table_name_lower == primary["name"].lower():
            continue

        singular = table_name_lower[:-1] if table_name_lower.endswith("s") else table_name_lower

        if table_name_lower in q_lower or (singular and singular in q_lower):
            hits.add(table_name_lower)
            continue

        for col in table.get("columns", []):
            col_lower = col["name"].lower()
            if col_lower in primary_cols:
                continue
            spaced = col_lower.replace("_", " ")
            if col_lower in q_lower or spaced in q_lower:
                hits.add(f"{table_name_lower}.{col_lower}")

    return bool(hits), hits


async def intent_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    question = state["question"]

    # === DETERMINISTIC GUARD: Greeting / small talk / irrelevant ===
    is_irrelevant, reason = _is_greeting_or_irrelevant(question)
    if is_irrelevant:
        print(f"[IntentClassifier] GUARD triggered: '{question}' -> {reason}. Skipping LLM.")
        return {
            **state,
            "intent": {
                "primary_intent": "greeting",
                "secondary_intents": [],
                "confidence": 1.0,
                "requires_join": False,
                "time_dimension": None,
                "aggregation_type": None,
                "type_filter": None,
                "entities": [],
                "is_greeting": True,
                "greeting_reason": reason,
            },
        }

    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    prompt = ChatPromptTemplate.from_template(INTENT_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({"question": question})

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        intent_data = json.loads(content)

        intent_data.setdefault("primary_intent", "filter_lookup")
        intent_data.setdefault("secondary_intents", [])
        intent_data.setdefault("confidence", 0.5)
        intent_data.setdefault("requires_join", False)
        intent_data.setdefault("time_dimension", None)
        intent_data.setdefault("aggregation_type", None)
        intent_data.setdefault("type_filter", None)
        intent_data.setdefault("entities", [])

        intent_data = _enforce_type_filter(question, intent_data)

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

    has_join_signal, join_hits = await _detect_join_signals(question)
    if has_join_signal and not intent_data.get("requires_join", False):
        print(f"[IntentClassifier] Forcing requires_join=True based on schema signals: {join_hits}")
        intent_data["requires_join"] = True
        if intent_data.get("primary_intent") not in {"multi_table_join", "budget_compare"}:
            intent_data["primary_intent"] = "multi_table_join"

    return {
        **state,
        "intent": intent_data,
    }
