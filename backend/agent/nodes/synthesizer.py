"""Synthesizer node: Creates precise natural language response from SQL results."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
import json

from config import get_settings
from db.connection import db_manager
from analytics.anomaly import detect_anomalies
from analytics.auto_chart import classify_chart_type

settings = get_settings()

SYNTHESIZER_PROMPT = """You are a precise data analyst assistant. Your job is to answer the user's question using ONLY the data provided in the query results. Do not make up numbers, dates, or categories. If the data is insufficient to fully answer, say so explicitly.

User Question: {question}

SQL Query Executed:
```sql
{sql}
```

Query Results (JSON format — first 15 rows):
{results}

Total Rows Returned: {total_rows}

Column Names and Types: {columns}

Anomaly Detection Report:
{anomaly}

INSTRUCTIONS — Follow this exact structure:
1. **Direct Answer**: Start with a 1-2 sentence direct answer that includes the specific key numbers/dates/categories from the data. Use the exact values from the results — do not round or approximate unless the user asked for an estimate.

2. **Detailed Breakdown**: Provide a structured breakdown:
   - If results show categories: list each category with its exact value.
   - If results show dates: mention the specific date range and trends.
   - If results show transactions: describe the top 3-5 most significant entries with exact amounts and descriptions.
   - Use bullet points for clarity.

3. **Anomalies**: If anomalies were detected, describe them specifically (e.g., "A transaction of Rs.12,500 on 2024-03-15 is 3.2x higher than the average for the 'Shopping' category").

4. **Data Limitations**: If the query returned 0 rows or fewer than expected, mention this and suggest why (e.g., "No transactions found for March 2024 — you may not have recorded any expenses that month").

5. **Follow-up Questions**: Suggest 3 specific, relevant follow-up questions based on the actual data. They should be concrete enough to generate new SQL (e.g., "What were my top 3 expenses in the 'Groceries' category?" not "Tell me more about my spending").

RULES:
- NEVER hallucinate data. If the result is empty, say "No data found" and explain possible reasons.
- Use exact currency symbols and formatting if present in the data.
- When comparing, compute the difference/percentage from the actual numbers provided.
- Keep the tone professional but conversational.
- Do NOT mention the SQL query itself in the final answer unless the user asks for it.

Response:"""

async def synthesizer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.2,  # Slightly higher for natural language variety, but low enough to stay grounded
    )

    # Execute the validated SQL
    try:
        result = await db_manager.execute_readonly(state["generated_sql"])
        state["sql_result"] = result
    except Exception as e:
        state["error"] = f"Execution failed after validation: {str(e)}"
        state["sql_result"] = None
        return state

    # Run analytics
    anomaly = detect_anomalies(result, sql=state["generated_sql"])
    state["anomaly"] = anomaly

    chart_type = classify_chart_type(result)
    state["chart_type"] = chart_type

    # Build rich context for the LLM
    rows = result.get("rows", [])
    columns = result.get("columns", [])
    total_rows = len(rows)

    # Truncate to first 15 rows for token efficiency, but keep full count
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
        "anomaly": anomaly if anomaly else "No anomalies detected in the result set.",
    })

    content = response.content

    # Extract follow-up questions with improved parsing
    follow_ups = []
    lines = content.split("\n")
    in_followup_section = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # Detect follow-up section headers
        if any(marker in lower for marker in ["follow-up", "follow up", "followup", "suggested questions"]):
            in_followup_section = True
            continue

        if in_followup_section and stripped:
            # Match numbered lists, bullet points, or lines with question marks
            if (stripped.startswith(("1.", "2.", "3.", "4.", "5.", "-", "•", "*")) and "?" in stripped) or \
               ("?" in stripped and len(stripped) > 10):
                # Clean the prefix
                clean = stripped
                for prefix in ["1.", "2.", "3.", "4.", "5.", "-", "•", "*"]:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):].strip()
                        break
                follow_ups.append(clean)
            elif stripped and not stripped.startswith("#") and "?" not in stripped:
                # End of follow-up section
                in_followup_section = False

    # Deduplicate and limit
    seen = set()
    unique_follow_ups = []
    for fu in follow_ups:
        if fu.lower() not in seen and len(fu) > 5:
            seen.add(fu.lower())
            unique_follow_ups.append(fu)

    state["explanation"] = content
    state["follow_ups"] = unique_follow_ups[:3]

    return state
