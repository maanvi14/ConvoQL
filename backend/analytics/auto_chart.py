"""Auto chart type classifier with context-aware handling."""
from typing import Dict, Any, Optional


def classify_chart_type(result: Dict[str, Any], context: str = "all") -> Optional[str]:
    """
    Classify the best chart type for the given query result.

    Args:
        result: SQL query result with rows and columns
        context: "spending", "income", or "all"

    Returns:
        Chart type string: "bar", "line", "pie", "table", or None
    """
    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if not rows:
        return None

    if len(rows) == 1:
        return None

    # Check for time series columns
    has_date_col = any(
        c.lower() in ["date", "month", "year", "week", "day"] or 
        "date" in c.lower() or "month" in c.lower() or "time" in c.lower()
        for c in columns
    )

    # Check for categorical columns
    categorical_cols = []
    for c in columns:
        if c.lower() in ["category", "merchant", "account", "type", "payment_method", "description"]:
            categorical_cols.append(c)

    # Check for numeric columns (excluding IDs)
    numeric_cols = []
    for c in columns:
        if any(w in c.lower() for w in ["id", "_id"]):
            continue
        if any(w in c.lower() for w in ["amount", "total", "sum", "count", "spent", "income", "value", "avg", "mean"]):
            numeric_cols.append(c)

    # Determine chart type
    if has_date_col and len(numeric_cols) > 0:
        return "line"

    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        if len(rows) <= 6:
            return "pie"
        return "bar"

    if len(rows) > 1:
        return "table"

    return None
