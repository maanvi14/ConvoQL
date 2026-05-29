"""Trend analyzer: Computes month-over-month and period comparisons."""
from typing import Dict, Any, List

async def trend_analyzer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze trends if the query involves time-series data."""
    question = state.get("question", "").lower()
    result = state.get("sql_result")

    if not result:
        return {**state, "trend_analysis": None}

    rows = result.get("rows", [])
    if len(rows) < 2:
        return {**state, "trend_analysis": "Insufficient data for trend analysis (need 2+ periods)."}

    # Check if results have time dimension
    has_time = any(
        any(k.lower() in ["month", "date", "year", "period", "week"] for k in row.keys())
        for row in rows[:3]
    )

    if not has_time and not any(w in question for w in ["trend", "over time", "monthly", "compare"]):
        return {**state, "trend_analysis": "No time dimension detected in results."}

    # Compute simple trend metrics
    try:
        # Find numeric column
        numeric_col = None
        for k in rows[0].keys():
            if any(w in k.lower() for w in ["total", "sum", "amount", "spent", "count", "avg"]):
                numeric_col = k
                break

        if not numeric_col:
            return {**state, "trend_analysis": "No numeric metric found for trend analysis."}

        values = []
        for row in rows:
            val = row.get(numeric_col)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass

        if len(values) < 2:
            return {**state, "trend_analysis": "Insufficient numeric data for trend analysis."}

        # Calculate trends
        latest = values[0]
        previous = values[1] if len(values) > 1 else values[-1]
        total = sum(values)
        avg = total / len(values)

        if previous != 0:
            change_pct = ((latest - previous) / abs(previous)) * 100
        else:
            change_pct = 0

        trend_text = f"""Trend Analysis:
- Latest period: {latest:,.2f}
- Previous period: {previous:,.2f}
- Change: {change_pct:+.1f}%
- Average across all periods: {avg:,.2f}
- Total across all periods: {total:,.2f}
- Number of periods: {len(values)}
"""

        return {
            **state,
            "trend_analysis": trend_text,
        }

    except Exception as e:
        return {
            **state,
            "trend_analysis": f"Trend analysis failed: {str(e)}",
        }
    