"""Query decomposer: Splits compound questions into sub-queries.

BUG FIX (budget-vs-actual split): The previous version split budget-vs-actual
comparison questions (e.g. "Compare my budget VS actual spending for May") into
two independent sub-queries ("What is my budget for May?" / "What is my actual
spending for May?"). This destroyed the JOIN context: the isolated "What is my
budget?" sub-query had no signal that "budget" means budgets.allocated, so the
planner joined transactions to budgets and summed transaction amounts —
recomputing actual spending restricted to budgeted categories and mislabeling it
as "budget". Both bars in the chart were spending figures, not one allocated
budget vs one actual spending.

The system already has a correct single-query path for budget comparisons
(dynamic_few_shot.py's budget_compare example produces a JOIN that selects
budgets.allocated AS budget alongside b.spent). The fix: detect budget-vs-actual
comparison questions and pass them through UNSPLIT, so the single-query pipeline
generates the correct JOIN.
"""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import json
import re

from config import get_settings

settings = get_settings()

# ── Budget-vs-actual comparison detection ──────────────────────
# These patterns match questions that compare budget (allocated/planned) against
# actual spending. Such questions MUST NOT be split — they require a single JOIN
# query that preserves the semantic distinction between budgets.allocated and
# SUM(ABS(transactions.amount)).
BUDGET_VS_ACTUAL_PATTERNS = [
    # "budget vs actual", "budget versus actual", "budget against actual"
    r"budget\s+(?:vs\.?|versus|against|compared\s+to)\s+actual",
    # "actual spending vs budget"
    r"actual\s+(?:spending|spent|expenses?)\s+(?:vs\.?|versus|against)\s+budget",
    # "compare my budget and actual"
    r"compare\s+(?:my\s+)?budget\s+(?:and|with|to|\s+vs\s+)\s+(?:actual|spending|spent)",
    # "budget vs spending"
    r"budget\s+(?:vs\.?|versus|against)\s+(?:spending|spent|expenses?)",
    # "allocated vs spent"
    r"allocated\s+(?:vs\.?|versus|against)\s+(?:spent|actual)",
    # "am I over/under budget"
    r"(?:am\s+i|are\s+any\s+categories)\s+(?:over|under)\s+budget",
    # "budget utilization"
    r"budget\s+utili[sz]ation",
    # "which categories are over budget"
    r"which\s+categories\s+are\s+(?:over|under)\s+budget",
]


def _is_budget_vs_actual_comparison(question: str) -> bool:
    """Return True if the question is a budget-vs-actual comparison that
    must NOT be split (requires a single JOIN query)."""
    q_lower = question.lower()
    for pattern in BUDGET_VS_ACTUAL_PATTERNS:
        if re.search(pattern, q_lower):
            return True
    return False


DECOMPOSER_PROMPT = """You are a query decomposer for a financial text-to-SQL system.

Analyze the user's question and determine if it contains multiple independent sub-questions that need separate SQL queries.

Compound indicators: "and", "vs", "compare", "also", "plus", "in addition", "meanwhile", "at the same time"

IMPORTANT EXCEPTION — NEVER split these:
- Budget-vs-actual comparisons (e.g. "Compare my budget vs actual spending for May", "Am I over budget?", "Which categories are over budget?", "Show budget utilization"). These require a single JOIN query across the budgets and transactions tables. Pass them through as a single query (is_compound=false, sub_queries=[]).

If the question is a single query, return empty sub_queries.
If it has multiple parts, split them into independent sub-questions.

Return ONLY JSON:
{{
  "is_compound": true/false,
  "sub_queries": [
    {{"id": 1, "question": "...", "intent": "...", "tables_needed": ["..."]}},
    {{"id": 2, "question": "...", "intent": "...", "tables_needed": ["..."]}}
  ],
  "merge_strategy": "sequential" or "side_by_side" or "ratio" or null
}}

User Question: {question}
Detected Intent: {intent}

JSON:"""


async def query_decomposer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    question = state["question"]

    # ── GUARD CLAUSE: Budget-vs-actual comparisons must NOT be split ──
    if _is_budget_vs_actual_comparison(question):
        print(f"[QueryDecomposer] BUDGET_VS_ACTUAL detected: '{question}' — passing through unsplit")
        return {
            **state,
            "decomposition": {
                "is_compound": False,
                "sub_queries": [],
                "merge_strategy": None,
            },
        }

    prompt = ChatPromptTemplate.from_template(DECOMPOSER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": question,
        "intent": json.dumps(state.get("intent", {}), indent=2),
    })

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decomp = json.loads(content)
        decomp.setdefault("is_compound", False)
        decomp.setdefault("sub_queries", [])
        decomp.setdefault("merge_strategy", None)

    except Exception as e:
        print(f"Query decomposition failed: {e}")
        decomp = {"is_compound": False, "sub_queries": [], "merge_strategy": None}

    return {
        **state,
        "decomposition": decomp,
    }
