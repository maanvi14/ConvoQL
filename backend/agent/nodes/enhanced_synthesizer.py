"""Enhanced synthesizer: Returns structured JSON for frontend rendering."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, Optional
import json
import re

from config import get_settings
from db.connection import db_manager
from analytics.anomaly import detect_anomalies
from analytics.auto_chart import classify_chart_type

settings = get_settings()

SYNTHESIZER_PROMPT = """You are a friendly, conversational data analyst. Answer the user's question in plain English, like you're texting a friend.

User Question: {question}

SQL Executed:
```sql
{sql}
```

Results (first 15 rows):
{results}

Total Rows: {total_rows}

Columns: {columns}

Anomalies: {anomaly}

INSTRUCTIONS:
Respond with ONLY a JSON object in this exact format:

{{
  "answer": "Your conversational answer here. 2-3 sentences max. Include key numbers naturally. Don't say 'Key Insight' or 'Details'.",
  "has_chart": true or false,
  "chart_type": "bar" or "line" or "pie" or "table" or null,
  "chart_title": "Title for chart if has_chart is true, else null",
  "has_table": true or false,
  "insight": "One interesting observation about the data (optional, can be null)"
}}

RULES:
- answer must be conversational, no markdown, no bold, no sections
- has_chart: true if data has categories/values to visualize (e.g., spending by category, monthly trends)
- has_chart: false for single-value answers (e.g., "How much did I spend?")
- chart_type: "bar" for categories, "line" for time trends, "pie" for proportions, "table" for lists
- has_table: true if there are multiple rows the user might want to browse
- insight: optional fun fact or warning (e.g., "Food spending is 22% above your budget")
- NEVER make up data. Use exact values from results.
- Use ₹ for INR amounts.
- No follow-up questions. No "Key Insight". No "Details". Just plain English.
- IMPORTANT: Debits (expenses) have NEGATIVE amounts in the database. When displaying spending, show the absolute value with ₹.
- IMPORTANT: Credits (income) have POSITIVE amounts. Display as-is.
- IMPORTANT: If Total Rows > 1, you are looking at a breakdown across multiple categories/rows, NOT a single total. Never state one row's value as if it were the answer for the whole time period. Summarize the set (e.g. 'You have 5 budgeted categories in May; Travel is closest to its limit at ₹14,000 of ₹15,000 allocated') rather than picking the top row and presenting it as an aggregate.

JSON Response ONLY:"""


def _extract_json(content: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from LLM response."""
    content = content.strip()

    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(\{.*?\})\s*```',
        r'(\{[\s\S]*\})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    return None


def _build_fallback_answer(result: Dict[str, Any], question: str, chart_type: Optional[str]) -> Dict[str, Any]:
    """Build a fallback response when JSON parsing fails."""
    rows = result.get("rows", [])
    columns = result.get("columns", [])
    total_rows = len(rows)

    has_multiple_rows = total_rows > 1
    has_numeric = any(
        any(isinstance(row.get(c), (int, float)) for row in rows[:3])
        for c in columns
    )
    has_categorical = any(
        any(isinstance(row.get(c), str) for row in rows[:3])
        for c in columns
    )

    should_chart = has_multiple_rows and has_numeric and has_categorical

    # Detect query context
    question_lower = question.lower()
    is_spending_query = any(w in question_lower for w in [
        "spend", "spent", "expense", "expenses", "debit", "purchase", "purchased",
        "bought", "payment", "paid", "cost", "price", "fee", "bill"
    ])
    is_income_query = any(w in question_lower for w in [
        "income", "salary", "credit", "earned", "received", "deposit"
    ])

    # Build simple answer
    if total_rows == 0:
        answer = "I couldn't find any data matching your query."
    elif total_rows == 1:
        row = rows[0]
        parts = []
        for k, v in row.items():
            key_lower = k.lower()
            is_amount_col = any(w in key_lower for w in ["amount", "spent", "total", "sum", "expense", "income", "value"])

            if isinstance(v, (int, float)):
                if is_amount_col:
                    if is_spending_query or ("debit" in key_lower or "spent" in key_lower or "expense" in key_lower):
                        # Spending should be shown as positive
                        parts.append(f"{k.replace('_', ' ')} is ₹{abs(v):,.2f}")
                    elif is_income_query or "income" in key_lower or "credit" in key_lower:
                        parts.append(f"{k.replace('_', ' ')} is ₹{v:,.2f}")
                    else:
                        # Ambiguous - show absolute for safety if value is negative
                        display_val = abs(v) if v < 0 else v
                        parts.append(f"{k.replace('_', ' ')} is ₹{display_val:,.2f}")
                else:
                    parts.append(f"{k.replace('_', ' ')} is {v}")
            else:
                parts.append(f"{k.replace('_', ' ')} is {v}")
        answer = f"Here's what I found: {', '.join(parts[:3])}."
    else:
        # Multiple rows - summarize top items
        answer = f"I found {total_rows} results. "
        if rows:
            first = rows[0]
            name_col = None
            val_col = None
            for c in columns:
                if any(w in c.lower() for w in ["name", "category", "description", "merchant"]):
                    name_col = c
                if any(w in c.lower() for w in ["total", "sum", "amount", "spent", "count", "value"]):
                    val_col = c

            if name_col and val_col and name_col in first and val_col in first:
                try:
                    val = float(first[val_col])
                    # For spending queries, show absolute value
                    display_val = abs(val) if is_spending_query else val
                    answer += f"Top result: {first[name_col]} at ₹{display_val:,.2f}."
                except (ValueError, TypeError):
                    answer += f"Top result: {first[name_col]}."

    return {
        "answer": answer,
        "has_chart": should_chart,
        "chart_type": chart_type if should_chart else None,
        "chart_title": f"Results for: {question[:40]}" if should_chart else None,
        "has_table": total_rows > 0 and total_rows <= 50,
        "insight": None,
    }


async def enhanced_synthesizer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.2,
    )

    # Execute SQL
    try:
        if not state.get("sql_result"):
            result = await db_manager.execute_readonly(state["generated_sql"])
            state["sql_result"] = result
        else:
            result = state["sql_result"]
    except Exception as e:
        state["error"] = str(e)
        state["sql_result"] = None
        state["answer"] = f"I ran into an issue: {str(e)}. Want to try rephrasing that?"
        state["has_chart"] = False
        state["chart_type"] = None
        state["has_table"] = False
        state["insight"] = None
        state["chart_title"] = None
        state["result"] = None
        return state

    # Determine analysis context from question
    question_lower = state["question"].lower()
    is_spending_query = any(w in question_lower for w in [
        "spend", "spent", "expense", "expenses", "debit", "purchase", "purchased",
        "bought", "payment", "paid", "cost", "price", "fee", "bill"
    ])
    is_income_query = any(w in question_lower for w in [
        "income", "salary", "credit", "earned", "received", "deposit"
    ])

    analysis_context = "spending" if is_spending_query else ("income" if is_income_query else "all")

    # Pass context to anomaly detector and chart classifier
    anomaly = detect_anomalies(result, context=analysis_context)
    chart_type = classify_chart_type(result, context=analysis_context)

    rows = result.get("rows", [])
    columns = result.get("columns", [])
    total_rows = len(rows)

    results_text = json.dumps(rows[:15], indent=2, default=str, ensure_ascii=False)
    columns_text = json.dumps(columns, indent=2, default=str, ensure_ascii=False)

    prompt = ChatPromptTemplate.from_template(SYNTHESIZER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "sql": state["generated_sql"],
        "results": results_text,
        "total_rows": total_rows,
        "columns": columns_text,
        "anomaly": anomaly if anomaly else "No anomalies detected.",
    })

    content = response.content.strip()

    parsed = _extract_json(content)

    if parsed:
        state["answer"] = parsed.get("answer", "Here's what I found.")
        state["has_chart"] = parsed.get("has_chart", False)
        state["chart_type"] = parsed.get("chart_type") if parsed.get("has_chart") else None
        state["chart_title"] = parsed.get("chart_title")
        state["has_table"] = parsed.get("has_table", total_rows > 0)
        state["insight"] = parsed.get("insight")
    else:
        fallback = _build_fallback_answer(result, state["question"], chart_type)
        state["answer"] = content.replace("**", "").replace("*", "").replace("#", "").strip() or fallback["answer"]
        state["has_chart"] = fallback["has_chart"]
        state["chart_type"] = fallback["chart_type"]
        state["chart_title"] = fallback["chart_title"]
        state["has_table"] = fallback["has_table"]
        state["insight"] = fallback["insight"]

    if state.get("chart_type") and not state.get("has_chart"):
        state["has_chart"] = True

    if state.get("has_chart") and not state.get("chart_type"):
        state["chart_type"] = chart_type or "bar"

    if state.get("has_chart") and not state.get("chart_title"):
        state["chart_title"] = state["question"][:50]

    state["explanation"] = state["answer"]
    state["follow_ups"] = []
    state["anomaly"] = anomaly
    state["chart_type"] = state.get("chart_type") or chart_type

    state["result"] = result
    state["sql"] = state["generated_sql"]
    state["execution_time_ms"] = result.get("executionTime", 0)
    state["row_count"] = total_rows

    return state


