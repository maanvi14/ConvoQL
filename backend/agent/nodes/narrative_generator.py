"""Narrative generator: Creates insight-first summary from results."""
from typing import Dict, Any

async def narrative_generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a concise narrative summary for the frontend insight card."""
    result = state.get("sql_result")
    question = state.get("question", "")

    if not result or not result.get("rows"):
        return {
            **state,
            "narrative": "No data available to generate insights.",
        }

    rows = result["rows"]
    columns = result.get("columns", [])

    # Generate quick narrative based on result shape
    if len(rows) == 1:
        # Single result — extract key value
        row = rows[0]
        key_val = None
        key_name = None

        for k, v in row.items():
            if any(w in k.lower() for w in ["total", "sum", "amount", "spent", "count", "avg", "balance"]):
                key_val = v
                key_name = k
                break

        if key_val is not None:
            try:
                numeric_val = float(key_val)
                narrative = f"Your {key_name.replace('_', ' ')} is ₹{numeric_val:,.2f}."
            except (ValueError, TypeError):
                narrative = f"Your {key_name.replace('_', ' ')} is {key_val}."
        else:
            # Just show first 3 key-value pairs
            items = []
            for k, v in list(row.items())[:3]:
                label = k.replace('_', ' ')
                if isinstance(v, (int, float)):
                    items.append(f"{label}: ₹{v:,.2f}")
                else:
                    items.append(f"{label}: {v}")
            narrative = f"Found result: {', '.join(items)}."
    else:
        # Multiple results
        narrative = f"Found {len(rows)} results. "

        # Try to find top item
        if len(rows) > 0:
            first = rows[0]
            name_col = None
            val_col = None

            for k in first.keys():
                if any(w in k.lower() for w in ["name", "category", "description", "merchant"]):
                    name_col = k
                if any(w in k.lower() for w in ["total", "sum", "amount", "spent", "count", "value"]):
                    val_col = k

            if name_col and val_col and name_col in first and val_col in first:
                try:
                    val = float(first[val_col])
                    narrative += f"Top: {first[name_col]} at ₹{val:,.2f}."
                except (ValueError, TypeError):
                    narrative += f"Top: {first[name_col]} at {first[val_col]}."
            elif columns:
                # Fallback: show column names
                narrative += f"Columns: {', '.join(columns[:4])}."

    return {
        **state,
        "narrative": narrative,
    }
