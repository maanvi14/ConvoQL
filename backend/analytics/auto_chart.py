"""Auto chart type classification based on result shape."""
from typing import Optional, Dict, Any

def classify_chart_type(result: Dict[str, Any]) -> Optional[str]:
    if not result or not result.get("rows"):
        return "table"
    
    columns = result["columns"]
    rows = result["rows"]
    
    if len(rows) == 0:
        return "table"
    
    has_date = any(
        "date" in c.lower() or "time" in c.lower() or "month" in c.lower()
        for c in columns
    )
    
    numeric_cols = 0
    for col in columns:
        try:
            float(rows[0].get(col, 0))
            numeric_cols += 1
        except (ValueError, TypeError):
            pass
    
    if len(columns) == 2 and numeric_cols == 1:
        if len(rows) <= 5:
            return "pie"
        return "bar"
    
    if has_date and numeric_cols >= 1:
        return "line"
    
    if numeric_cols >= 2 and len(columns) >= 3:
        return "bar"
    
    return "table"
