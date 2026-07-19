"""Anomaly detection with proper debit/credit separation and sign handling."""
import numpy as np
from typing import Dict, Any, Optional


def detect_anomalies(result: Dict[str, Any], threshold: float = 2.5, context: str = "all", sql: str = "") -> Optional[str]:
    """
    Detect anomalies in transaction data with proper sign handling.

    Args:
        result: SQL query result with rows and columns
        threshold: Z-score threshold for anomaly detection (default 2.5)
        context: "spending", "income", or "all" — determines how to interpret amounts
        sql: the SQL that produced `result`, used to refine context when the
            caller passes context="all". BUG FIX: this used to be read from
            result.get("sql", ""), but `result` is always the raw dict
            returned by db_manager.execute_readonly() (rows/columns/
            executionTime only) — it never has a "sql" key, so that lookup
            was silently always "" and this whole inference branch was dead
            code. Callers now pass the actual SQL string explicitly.

    Returns:
        String description of anomalies found, or None
    """
    if not result or not result.get("rows"):
        return None

    rows = result["rows"]
    if len(rows) < 3:
        return None

    # Find the amount column (could be 'amount', 'total_spent', 'total_income', etc.)
    amount_col = None
    for c in result["columns"]:
        if c.lower() == "amount":
            amount_col = c
            break

    # Fallback: look for aggregated amount columns
    if not amount_col:
        for c in result["columns"]:
            if any(w in c.lower() for w in ["total", "sum", "spent", "income", "expense", "value"]):
                amount_col = c
                break

    if not amount_col:
        return None

    # Determine context from SQL if not explicitly provided
    sql_str = (sql or str(result.get("sql", ""))).lower()
    if context == "all":
        if "debit" in sql_str or "abs(amount)" in sql_str or "total_spent" in sql_str:
            context = "spending"
        elif "credit" in sql_str or "total_income" in sql_str:
            context = "income"

    # Separate rows by transaction type if 'type' column exists
    has_type_col = "type" in [c.lower() for c in result["columns"]]

    debit_rows = []
    credit_rows = []
    ambiguous_rows = []

    for row in rows:
        val = row.get(amount_col)
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue

        txn_type = str(row.get("type", "")).lower() if has_type_col else ""

        if txn_type == "debit":
            debit_rows.append((row, abs(val)))
        elif txn_type == "credit":
            credit_rows.append((row, val))
        elif context == "spending":
            # BUG FIX: grouped/aggregated spending queries (e.g. "spending by
            # category" -> SUM(ABS(amount)) AS total_spent GROUP BY category)
            # have no 'type' column and the values are already positive
            # (post-ABS). The old check `context == "spending" and val < 0`
            # never matched these rows, so every row fell into
            # ambiguous_rows, and the ambiguous-population check only runs
            # when context == "all" — so anomaly detection silently found
            # nothing for one of the most common query shapes in this app.
            # The caller already told us this is a spending population via
            # `context`, regardless of the row's raw sign, so trust it.
            debit_rows.append((row, abs(val)))
        elif context == "income":
            credit_rows.append((row, val))
        elif val < 0:
            debit_rows.append((row, abs(val)))
        elif val > 0:
            credit_rows.append((row, val))
        else:
            ambiguous_rows.append((row, abs(val)))

    # Analyze each population separately
    anomalies = []

    def _find_anomalies(population_rows, population_name):
        """Find anomalies within a homogeneous population."""
        if len(population_rows) < 3:
            return

        values = [v for _, v in population_rows]
        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return

        for row, val in population_rows:
            z_score = abs((val - mean) / std)
            if z_score > threshold:
                # Get best label
                label = ""
                for label_col in ["description", "merchant", "category"]:
                    if label_col in row and row[label_col]:
                        label = str(row[label_col])
                        break

                if not label:
                    # Fallback to first string column
                    for c in result["columns"]:
                        if c != amount_col and isinstance(row.get(c), str):
                            label = str(row[c])
                            break

                anomalies.append({
                    "row": row,
                    "value": val,
                    "z_score": z_score,
                    "label": label,
                    "population": population_name,
                    "is_debit": population_name == "expense"
                })

    # Analyze each population
    if context in ("all", "spending") and debit_rows:
        _find_anomalies(debit_rows, "expense")

    if context in ("all", "income") and credit_rows:
        _find_anomalies(credit_rows, "income")

    if context == "all" and ambiguous_rows and not (debit_rows or credit_rows):
        _find_anomalies(ambiguous_rows, "transaction")

    if not anomalies:
        return None

    # Sort by Z-score (most anomalous first)
    anomalies.sort(key=lambda x: x["z_score"], reverse=True)

    # Build report for top anomaly
    top = anomalies[0]
    val = top["value"]
    label = top["label"]
    z_score = top["z_score"]
    population = top["population"]

    label_str = f" ({label})" if label else ""

    return (
        f"Unusually large {population}: ₹{val:,.0f}{label_str} is {z_score:.1f}x "
        f"the standard deviation from the mean."
    )
