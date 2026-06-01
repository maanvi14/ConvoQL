"""Structured planner: Outputs JSON query plan with dialect-aware date functions."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import json
import re

from config import get_settings
from db.connection import db_manager
from cache.schema_rag import schema_rag

settings = get_settings()

# Dialect-specific date function templates - NOW WITH ROLLING WINDOWS
DATE_TEMPLATES = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', {{col}}) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', {{col}}) = strftime('%Y-%m', 'now', '-1 month')",
        "last_3_months": "{{col}} >= date('now', '-3 months')",
        "last_6_months": "{{col}} >= date('now', '-6 months')",
        "this_year": "strftime('%Y', {{col}}) = strftime('%Y', 'now')",
        "last_year": "{{col}} >= date('now', '-1 year')",
        "format": "strftime('%Y-%m', {{col}})",
    },
    "mysql": {
        "this_month": "DATE_FORMAT({{col}}, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT({{col}}, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "last_3_months": "{{col}} >= DATE_SUB(NOW(), INTERVAL 3 MONTH)",
        "last_6_months": "{{col}} >= DATE_SUB(NOW(), INTERVAL 6 MONTH)",
        "this_year": "YEAR({{col}}) = YEAR(NOW())",
        "last_year": "{{col}} >= DATE_SUB(NOW(), INTERVAL 1 YEAR)",
        "format": "DATE_FORMAT({{col}}, '%Y-%m')",
    },
    "postgresql": {
        "this_month": "TO_CHAR({{col}}, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR({{col}}, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "last_3_months": "{{col}} >= NOW() - INTERVAL '3 months'",
        "last_6_months": "{{col}} >= NOW() - INTERVAL '6 months'",
        "this_year": "EXTRACT(YEAR FROM {{col}}) = EXTRACT(YEAR FROM NOW())",
        "last_year": "{{col}} >= NOW() - INTERVAL '1 year'",
        "format": "TO_CHAR({{col}}, 'YYYY-MM')",
    }
}

PLANNER_PROMPT = """You are a {dialect} query planner. Given the user's question, detected intent, and relevant schema, output a structured query plan.

DATABASE SCHEMA:
{schema_context}

SAMPLE DATA:
{sample_data}

USER QUESTION: {question}

DETECTED INTENT: {intent}

DECOMPOSITION: {decomposition}

=== CRITICAL AMOUNT SIGN CONVENTION ===
The `amount` column uses SIGNED values:
  - Debits (expenses, purchases, payments): NEGATIVE values
  - Credits (income, salary, deposits): POSITIVE values

THEREFORE:
- For spending/expense aggregations: ALWAYS use SUM(ABS(amount)) or ABS(amount)
- For income aggregations: Use SUM(amount) directly
- For "highest expense": ORDER BY ABS(amount) DESC LIMIT 1 (NEVER MAX(amount))
- NEVER use amount > 0 or amount < 0 as a filter — use type = 'debit' or type = 'credit'

=== DATE FILTER RULES ===
For time-based queries, use the CORRECT date range:
- "this month" or "current month": {date_this_month}
- "last month" or "previous month": {date_last_month}
- "last 3 months" or "past 3 months": {date_last_3_months}
- "last 6 months" or "past 6 months" or "last six months": {date_last_6_months}
- "last year" or "past year": {date_last_year}
- For specific months like "March 2026": strftime('%Y-%m', date) = '2026-03'
- NEVER combine rolling window (last 6 months) with specific month filter — use ONLY one
- The date column stores dates as TEXT in 'YYYY-MM-DD' format

Output a JSON object with this EXACT structure:
{{
  "tables": ["table_name"],
  "joins": [
    {{
      "type": "LEFT JOIN" or "INNER JOIN" or null,
      "left_table": "...",
      "right_table": "...",
      "on_condition": "left.col = right.col"
    }}
  ],
  "select_columns": ["col1", "col2 AS alias", "SUM(ABS(col3)) AS agg_alias"],
  "where_filters": ["type = 'debit'", "{date_this_month}"],
  "group_by": ["col1"],
  "order_by": "col DESC",
  "limit": 50,
  "aggregation": "SUM(ABS(amount)) AS total",
  "date_filter": {{
    "column": "date",
    "operator": ">=",
    "value": "{date_last_6_months}"
  }}
}}

CRITICAL RULES:
1. ONLY use tables and columns from the schema above
2. For expenses: include "type = 'debit'" ONLY if type_filter is explicitly debit
3. For income: include "type = 'credit'" ONLY if type_filter is explicitly credit
4. For "highest expense": use ORDER BY ABS(amount) DESC LIMIT 1, NEVER MAX(amount)
5. For date filtering: use {dialect} date functions
6. TABLE SELECTION RULES:
   - For simple transaction/spending/category/merchant/tag/account queries: use ONLY the transactions table
   - For budget-related queries (budget vs actual, over budget, allocated vs spent): MUST JOIN with budgets table
   - For account balance queries (total balance, highest balance): MUST use accounts table
   - For category metadata (color, icon): MUST JOIN with categories table
   - When JOINs are needed, include the correct ON condition (e.g., "transactions.category = budgets.category")
7. select_columns must include all columns referenced in group_by
8. For "merchant" questions: merchant column is IN transactions table. No JOIN needed.
9. For "category" questions: category column is IN transactions table. No JOIN needed.
10. For "account" questions: account column is IN transactions table. No JOIN needed.
11. For "tag" questions: tags column is IN transactions table. No JOIN needed. NEVER add type filter for tag searches.
12. ABSOLUTE RULE: If type_filter in intent is null, do NOT add any type filter to where_filters.
13. NEVER hallucinate columns that don't exist in the schema. If a column is not in the schema, DO NOT use it.
14. The transactions table has: transaction_id, date, description, amount, type, category, account, merchant, payment_method, tags. ALL needed columns are here.
15. DO NOT JOIN with categories table unless the question explicitly asks for category metadata like color, icon, or category descriptions.
16. "Show me my Shopping transactions" only needs the transactions table — category is already a column there.
17. JOIN RULES:
    - NEVER join a table to itself (e.g., "budgets INNER JOIN budgets" is WRONG)
    - The left table in FROM must be different from the right table in JOIN
    - For budget queries, use: FROM transactions INNER JOIN budgets ON transactions.category = budgets.category
    - For account queries, use: FROM accounts (no JOIN needed for simple balance queries)
    - NEVER use "transactions.date" if transactions is not the primary table — check which table has the date column
18. COLUMN QUALIFICATION:
    - When multiple tables are used, ALWAYS qualify column names with table name: "table.column"
    - Example: "transactions.category" not just "category"
    - Example: "budgets.allocated" not just "allocated"
    - The validator will reject bare column names that exist in multiple tables
19. AMOUNT SIGN CONVENTION (CRITICAL):
    - Debits are NEGATIVE, Credits are POSITIVE
    - For spending queries in select_columns: use "SUM(ABS(amount)) AS total_spent" NOT "SUM(amount)"
    - For spending queries in order_by: use "ABS(amount) DESC" NOT "amount DESC"
    - NEVER add "amount > 0" or "amount < 0" to where_filters
20. DATE FILTER SELECTION:
    - For "last 6 months" or "past 6 months": use {date_last_6_months} (rolling window)
    - For "last 3 months" or "past 3 months": use {date_last_3_months} (rolling window)
    - For "last month": use {date_last_month} (single month)
    - For "this month": use {date_this_month} (single month)
    - For "last year": use {date_last_year} (rolling window)
    - NEVER use this_month for "last 6 months" — that would only show current month!

JSON PLAN ONLY:"""


async def structured_planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    dialect = state.get("dialect", "sqlite")
    date_templates = DATE_TEMPLATES.get(dialect, DATE_TEMPLATES["sqlite"])

    # RAG: Get relevant tables based on intent
    full_schema = await db_manager.get_schema()

    # Get actual table names from schema for portable detection
    table_names = [t["name"].lower() for t in full_schema.get("tables", [])]
    has_budgets = "budgets" in table_names
    has_accounts = "accounts" in table_names
    has_categories = "categories" in table_names

    intent_data = state.get("intent", {})
    requires_join = intent_data.get("requires_join", False)

    # === SCHEMA-AWARE MULTI-TABLE OVERRIDE ===
    question_lower = state["question"].lower()

    # Force multi-table mode for budget queries (if budgets table exists)
    if has_budgets and any(word in question_lower for word in ["budget", "allocated", "over budget", "under budget", "budget vs", "budget limit"]):
        if not requires_join:
            print(f"[Planner] Schema override: budgets table exists + budget query detected. Forcing requires_join=True")
            intent_data["requires_join"] = True
            requires_join = True

    # Force multi-table mode for account balance queries (if accounts table exists)
    if has_accounts and any(word in question_lower for word in ["account balance", "total balance", "highest balance", "balances"]):
        if not requires_join:
            print(f"[Planner] Schema override: accounts table exists + balance query detected. Forcing requires_join=True")
            intent_data["requires_join"] = True
            requires_join = True

    # === CRITICAL FIX: NEVER force categories table join for simple category queries ===
    # Category names like "Shopping", "Food", "Travel" are columns IN the transactions table.
    # Only join with categories table if explicitly asking for metadata (color, icon, etc.)
    category_metadata_signals = ["color", "icon", "description", "category metadata", "category info"]
    needs_category_join = any(signal in question_lower for signal in category_metadata_signals)

    if has_categories and not needs_category_join:
        # If the question only mentions a category name but not metadata, don't use categories table
        if any(cat in question_lower for cat in ["shopping", "food", "travel", "health", "entertainment", "groceries"]):
            print(f"[Planner] Category query detected without metadata request. Forcing single-table mode.")
            intent_data["requires_join"] = False
            requires_join = False

    top_k = 4 if requires_join else 1

    relevant = schema_rag.retrieve_relevant(state["question"], top_k=top_k)
    schema_text = schema_rag.build_context(full_schema, relevant)

    # Fetch sample data
    sample_data_parts = []
    for rel in relevant:
        try:
            sample = await db_manager.execute_readonly(
                f"SELECT * FROM {rel['name']} LIMIT 2"
            )
            rows = sample.get("rows", [])
            if rows:
                sample_data_parts.append(
                    f"Table `{rel['name']}`:\n" + "\n".join([str(r) for r in rows])
                )
        except Exception:
            pass
    sample_data_text = "\n\n".join(sample_data_parts) if sample_data_parts else "No sample data."

    # Log
    stats = schema_rag.get_stats()
    print(f"SchemaRAG: {stats['tables_indexed']} tables, retrieved {len(relevant)} relevant")
    for r in relevant:
        print(f"  - {r['name']} (score: {r['score']:.3f}, reason: {r['reason']})")

    # Detect rolling window from question for correct date template
    time_dimension = intent_data.get("time_dimension", "")

    # Map question to correct date filter template
    date_filter_template = "this_month"  # default
    if "6 month" in question_lower or "six month" in question_lower or time_dimension == "last_6_months":
        date_filter_template = "last_6_months"
    elif "3 month" in question_lower or "three month" in question_lower or time_dimension == "last_3_months":
        date_filter_template = "last_3_months"
    elif "last month" in question_lower or time_dimension == "last_month":
        date_filter_template = "last_month"
    elif "last year" in question_lower or time_dimension == "last_year":
        date_filter_template = "last_year"
    elif "this month" in question_lower or time_dimension == "this_month":
        date_filter_template = "this_month"

    print(f"[Planner] Detected date filter template: {date_filter_template}")

    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "schema_context": schema_text,
        "sample_data": sample_data_text,
        "intent": json.dumps(intent_data, indent=2),
        "decomposition": json.dumps(state.get("decomposition", {}), indent=2),
        "dialect": dialect,
        "date_this_month": date_templates["this_month"].replace("{{col}}", "date"),
        "date_last_month": date_templates["last_month"].replace("{{col}}", "date"),
        "date_last_3_months": date_templates["last_3_months"].replace("{{col}}", "date"),
        "date_last_6_months": date_templates["last_6_months"].replace("{{col}}", "date"),
        "date_last_year": date_templates["last_year"].replace("{{col}}", "date"),
    })

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        plan = json.loads(content)

        # Validate and set defaults
        plan.setdefault("tables", ["transactions"])
        plan.setdefault("joins", [])
        plan.setdefault("select_columns", ["*"])
        plan.setdefault("where_filters", [])
        plan.setdefault("group_by", [])
        plan.setdefault("order_by", None)
        plan.setdefault("limit", 50)
        plan.setdefault("aggregation", None)
        plan.setdefault("date_filter", None)

        # === AGGRESSIVE SINGLE-TABLE ENFORCEMENT ===
        tables = plan.get("tables", [])
        if len(tables) == 1 and tables[0].lower() == "transactions":
            plan["joins"] = []
            print("[Planner] Single transactions table detected. Forcing empty joins.")

        # === CRITICAL FIX: Remove categories table joins for simple category queries ===
        joins = plan.get("joins", [])
        cleaned_joins = []
        for join in joins:
            if join and join.get("right_table"):
                right_table = join["right_table"].lower()
                # Remove categories joins unless explicitly needed
                if right_table == "categories" and not needs_category_join:
                    print(f"[Planner] REMOVING unnecessary categories table join: {join}")
                    continue
                # Remove invalid joins
                if join.get("on_condition"):
                    on_cond = join["on_condition"].lower()
                    if "categories.category" in on_cond or "category = category" in on_cond:
                        print(f"[Planner] Removing incorrect join: {join}")
                        continue
            cleaned_joins.append(join)
        plan["joins"] = cleaned_joins

        # === TYPE FILTER ENFORCEMENT ===
        type_filter = intent_data.get("type_filter")
        where_filters = plan.get("where_filters", [])

        if type_filter is None:
            # Remove ANY type filter from where_filters
            cleaned_filters = []
            for f in where_filters:
                if isinstance(f, str) and "type =" in f.lower():
                    print(f"[Planner] Removing type filter '{f}' because intent.type_filter is null")
                    continue
                cleaned_filters.append(f)
            plan["where_filters"] = cleaned_filters
        elif type_filter == "debit":
            # Ensure debit filter exists
            if not any("type = 'debit'" in f.lower() for f in where_filters if isinstance(f, str)):
                plan["where_filters"].append("type = 'debit'")

            # CRITICAL: Also ensure select_columns use ABS(amount) for spending
            select_cols = plan.get("select_columns", [])
            fixed_select = []
            for col in select_cols:
                if isinstance(col, str):
                    # Fix SUM(amount) -> SUM(ABS(amount)) for debit queries
                    if re.search(r'(?i)SUM\s*\(\s*amount\s*\)', col):
                        col = re.sub(r'(?i)SUM\s*\(\s*amount\s*\)', 'SUM(ABS(amount))', col)
                        print(f"[Planner] Fixed select_column: SUM(amount) -> SUM(ABS(amount))")
                    fixed_select.append(col)
                else:
                    fixed_select.append(col)
            plan["select_columns"] = fixed_select

            # Fix order_by for debit queries
            order_by = plan.get("order_by", "")
            if isinstance(order_by, str) and re.search(r'(?i)^amount\s+desc$', order_by.strip()):
                plan["order_by"] = "ABS(amount) DESC"
                print(f"[Planner] Fixed order_by: amount DESC -> ABS(amount) DESC")

        elif type_filter == "credit":
            # Ensure credit filter exists
            if not any("type = 'credit'" in f.lower() for f in where_filters if isinstance(f, str)):
                plan["where_filters"].append("type = 'credit'")

        # === DATE FILTER ENFORCEMENT ===
        # If the question asks for rolling window but plan has single month, fix it
        if date_filter_template in ["last_6_months", "last_3_months", "last_year"]:
            # Check if where_filters contains a single-month filter when it should be rolling
            has_rolling = False
            for f in where_filters:
                if isinstance(f, str) and (">=" in f or "date('now'" in f or "DATE_SUB" in f or "INTERVAL" in f):
                    has_rolling = True
                    break

            if not has_rolling:
                # Remove any single-month strftime equality filters
                cleaned_filters = []
                for f in where_filters:
                    if isinstance(f, str) and ("strftime('%Y-%m'" in f and "= strftime('%Y-%m', 'now')" in f):
                        print(f"[Planner] Removing single-month filter '{f}' for rolling window query")
                        continue
                    cleaned_filters.append(f)

                # Add the correct rolling window filter
                rolling_filter = date_templates[date_filter_template].replace("{{col}}", "date")
                cleaned_filters.append(rolling_filter)
                plan["where_filters"] = cleaned_filters
                print(f"[Planner] Added rolling window filter: {rolling_filter}")

    except Exception as e:
        print(f"Structured planning failed: {e}. Using fallback plan.")
        plan = {
            "tables": ["transactions"],
            "joins": [],
            "select_columns": ["*"],
            "where_filters": [],
            "group_by": [],
            "order_by": None,
            "limit": 50,
            "aggregation": None,
            "date_filter": None,
        }

    plan_json_str = json.dumps(plan, indent=2, ensure_ascii=False)

    return {
        **state,
        "schema_context": schema_text,
        "structured_plan": plan,
        "plan_json": plan_json_str,
        "retry_count": 0,
    }
