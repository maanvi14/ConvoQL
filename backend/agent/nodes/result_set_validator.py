"""Result-set validator: Checks semantic correctness and triggers retry."""
from typing import Dict, Any, List

async def result_set_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that query results make semantic sense. Detects suspicious 0-row results."""
    result = state.get("sql_result")
    question = state.get("question", "").lower()
    intent = state.get("intent", {})

    if not result:
        return {
            **state,
            "result_set_valid": True,
            "result_set_issue": None,
        }

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    issues = []
    force_retry = False
    retry_hint = None

    # Check 1: Empty results when they shouldn't be
    if len(rows) == 0:
        if not any(w in question for w in ["any", "exist", "have", "did i"]):
            issues.append("Query returned 0 rows. The requested date range or filters may have no matching data.")

            # SUSPICIOUS: tag/category/merchant search with 0 rows + type filter present
            type_filter = intent.get("type_filter") if intent else None
            if type_filter and any(w in question for w in ["tag", "category", "merchant"]):
                issues.append(f"Suspicious: question asks about tags/categories but type_filter={type_filter} may be blocking results.")
                retry_hint = f"Remove type = '{type_filter}' filter. The user asked about tags/categories, not transaction type. Tags exist on both debit and credit transactions."
                force_retry = True

    # Check 2: Single row for ranking questions — EXPECTED
    if any(w in question for w in ["highest", "lowest", "top", "most", "biggest", "maximum", "minimum"]):
        if len(rows) == 1:
            pass  # Correct
        elif len(rows) > 1 and not any(w in question for w in ["top 5", "top 10", "top 3"]):
            issues.append(f"Expected 1 row for ranking question but got {len(rows)}. LIMIT 1 may be missing.")

    # Check 3: Aggregation questions should have aggregated values
    primary_intent = intent.get("primary_intent", "") if intent else ""
    if primary_intent in ["aggregation", "trend"] and len(rows) > 0:
        first_row = rows[0]
        has_agg = any(
            k.lower() in ["total", "sum", "avg", "average", "count", "total_spent", "amount"]
            for k in first_row.keys()
        )
        if not has_agg and len(rows) > 5:
            issues.append("Question asks for aggregation but results show individual rows. GROUP BY or SUM() may be missing.")

    # Check 4: Date range sanity
    if any(w in question for w in ["this month", "last month", "january", "february", "march"]):
        if len(rows) == 0:
            issues.append("Date-specific query returned 0 rows. The database may not contain data for the requested month.")

    is_valid = len(issues) == 0 and not force_retry

    # === TRIGGER RETRY IF FIXABLE ISSUE DETECTED ===
    if force_retry and retry_hint:
        state["error"] = f"Result set validation failed: {' | '.join(issues)}"
        state["retry_hint"] = retry_hint
        state["valid"] = False  # Signal to router that we need to retry
        print(f"[ResultSetValidator] Forcing retry: {retry_hint}")

    return {
        **state,
        "result_set_valid": is_valid,
        "result_set_issue": " | ".join(issues) if issues else None,
        "retry_hint": retry_hint,
    }
