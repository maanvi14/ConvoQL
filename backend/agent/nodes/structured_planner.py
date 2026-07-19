
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
{retry_context}
{few_shot_context}
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
21. LISTING QUERY RULE (CRITICAL - READ CAREFULLY):
    - For "Show all transactions tagged with 'Subscription'": select_columns = ["*"], group_by = [], NO type filter
    - For "Show all transactions from uber": select_columns = ["*"], group_by = [], where_filters = ["merchant = 'uber'"]
    - For "Show all transactions": select_columns = ["*"], group_by = [], where_filters = []
    - LISTING queries (show all, show me, find all, list all, get all) should NEVER have GROUP BY
    - group_by MUST be [] for any query that just lists/shows transactions
    - group_by MUST ONLY contain actual column names, NEVER "*"
22. AGGREGATION QUERY RULE:
    - Only use GROUP BY when the query asks for totals, sums, averages, counts, or comparisons
    - "Show me total spending by category" -> group_by = ["category"]
    - "Which category has highest spending" -> group_by = ["category"]
    - "Show all transactions" -> group_by = []

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

    # Detect if this is a simple listing query (no aggregation needed)
    is_listing_query = any(w in question_lower for w in ["show all", "show me all", "find all", "list all", "get all", "all transactions"])
    is_tag_query = any(w in question_lower for w in ["tag", "tagged", "subscription", "label"])
    is_merchant_query = any(w in question_lower for w in ["from uber", "from amazon", "merchant"])

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
    category_metadata_signals = ["color", "icon", "description", "category metadata", "category info"]
    needs_category_join = any(signal in question_lower for signal in category_metadata_signals)

    if has_categories and not needs_category_join:
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

    date_filter_template = "this_month"
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
    print(f"[Planner] Query type: listing={is_listing_query}, tag={is_tag_query}, merchant={is_merchant_query}")

    # === BUG 3b FIX: Surface retry context to the LLM ===
    # typed_error_classifier_node is the only place retry_count is incremented,
    # and it stores a targeted retry_hint. On the first call retry_count is 0
    # (or unset) and there's nothing to show. On a retry, tell the LLM exactly
    # what the last SQL attempt was and why it failed so it doesn't just
    # regenerate the same plan.
    retry_count = state.get("retry_count", 0)
    retry_hint = state.get("retry_hint")
    previous_sql = state.get("generated_sql")
    previous_error = state.get("error")

    if retry_count > 0 and (retry_hint or previous_error):
        retry_context = f"""
=== RETRY CONTEXT (attempt {retry_count + 1} of 4) ===
Your previous plan produced this SQL, which FAILED:
{previous_sql}

Failure reason: {previous_error or "N/A"}
Specific fix required: {retry_hint or "Re-examine the plan against the schema and rules above."}

Produce a NEW plan that specifically addresses this failure. Do not repeat the same mistake.
"""
    else:
        retry_context = ""

    # === DEAD CODE FIX: Actually inject the selected few-shot examples ===
    # dynamic_few_shot_node computes this and writes it to
    # state["few_shot_examples"], but nothing ever read it — the planner
    # prompt had no {few_shot_examples} placeholder at all. Combined with the
    # graph now running dynamic_few_shot BEFORE this node, the examples are
    # actually present in state by the time we get here.
    few_shot_examples = state.get("few_shot_examples")
    if few_shot_examples:
        few_shot_context = f"""
=== RELEVANT EXAMPLES FOR THIS QUERY TYPE ===
{few_shot_examples}
"""
    else:
        few_shot_context = ""

    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "schema_context": schema_text,
        "sample_data": sample_data_text,
        "intent": json.dumps(intent_data, indent=2),
        "decomposition": json.dumps(state.get("decomposition", {}), indent=2),
        "retry_context": retry_context,
        "few_shot_context": few_shot_context,
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

        # === CRITICAL FIX: Force empty group_by for listing/tag/merchant queries ===
        if is_listing_query or is_tag_query or is_merchant_query:
            if plan.get("group_by"):
                print(f"[Planner] Forcing empty group_by for listing/tag/merchant query")
                plan["group_by"] = []
            # Ensure select_columns is ["*"] for raw listings
            if not any(agg in str(plan.get("select_columns", [])).lower() for agg in ["sum", "count", "avg", "max", "min"]):
                plan["select_columns"] = ["*"]

        # === CRITICAL FIX: Sanitize group_by - NEVER allow "*" ===
        # BUG 4 FIX: Also strip trailing "AS alias" from GROUP BY entries.
        # SQLite rejects `GROUP BY strftime('%Y-%m', date) AS month` with a
        # syntax error. Strip the alias here at the plan level so it never
        # reaches sql_skeleton or the validator.
        group_by = plan.get("group_by", [])
        sanitized_group_by = []
        for g in group_by:
            if isinstance(g, str) and g.strip() == "*":
                print(f"[Planner] REMOVING invalid '*' from group_by")
                continue
            if isinstance(g, str):
                # Strip trailing AS alias (SQLite GROUP BY does not allow it)
                g_clean = re.sub(r'(?i)\s+AS\s+\w+\s*$', '', g).strip()
                if g_clean != g:
                    print(f"[Planner] Stripped AS alias from group_by: '{g}' -> '{g_clean}'")
                sanitized_group_by.append(g_clean)
            else:
                sanitized_group_by.append(g)
        plan["group_by"] = sanitized_group_by

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
                if right_table == "categories" and not needs_category_join:
                    print(f"[Planner] REMOVING unnecessary categories table join: {join}")
                    continue
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

        if type_filter is None or is_tag_query or is_listing_query or is_merchant_query:
            # Remove ANY type filter for tag/merchant/listing searches or when type_filter is null
            cleaned_filters = []
            for f in where_filters:
                if isinstance(f, str) and "type =" in f.lower():
                    print(f"[Planner] Removing type filter '{f}' because intent.type_filter is null or query is listing/tag/merchant")
                    continue
                cleaned_filters.append(f)
            plan["where_filters"] = cleaned_filters
        elif type_filter == "debit":
            if not any("type = 'debit'" in f.lower() for f in where_filters if isinstance(f, str)):
                plan["where_filters"].append("type = 'debit'")

            select_cols = plan.get("select_columns", [])
            fixed_select = []
            for col in select_cols:
                if isinstance(col, str):
                    if re.search(r'(?i)SUM\s*\(\s*amount\s*\)', col):
                        col = re.sub(r'(?i)SUM\s*\(\s*amount\s*\)', 'SUM(ABS(amount))', col)
                        print(f"[Planner] Fixed select_column: SUM(amount) -> SUM(ABS(amount))")
                    fixed_select.append(col)
                else:
                    fixed_select.append(col)
            plan["select_columns"] = fixed_select

            order_by = plan.get("order_by", "")
            if isinstance(order_by, str) and re.search(r'(?i)^amount\s+desc$', order_by.strip()):
                plan["order_by"] = "ABS(amount) DESC"
                print(f"[Planner] Fixed order_by: amount DESC -> ABS(amount) DESC")

        elif type_filter == "credit":
            if not any("type = 'credit'" in f.lower() for f in where_filters if isinstance(f, str)):
                plan["where_filters"].append("type = 'credit'")

        # === DATE FILTER ENFORCEMENT ===
        if date_filter_template in ["last_6_months", "last_3_months", "last_year"]:
            has_rolling = False
            for f in where_filters:
                if isinstance(f, str) and (">=" in f or "date('now'" in f or "DATE_SUB" in f or "INTERVAL" in f):
                    has_rolling = True
                    break

            if not has_rolling:
                cleaned_filters = []
                for f in where_filters:
                    if isinstance(f, str) and ("strftime('%Y-%m'" in f and "= strftime('%Y-%m', 'now')" in f):
                        print(f"[Planner] Removing single-month filter '{f}' for rolling window query")
                        continue
                    cleaned_filters.append(f)

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

    # === BUG 3b FIX: Don't reset retry_count here. ===
    # This used to unconditionally set retry_count=0, which is correct on the
    # very first call (no state exists yet) but WRONG once retries route back
    # through this node: it would silently erase typed_error_classifier_node's
    # count and defeat the 3-attempt cap, letting the graph retry forever.
    # `state.get("retry_count", 0)` is 0 on first entry (same as before) and
    # preserves whatever typed_error_classifier_node has already counted on
    # subsequent entries.
    return {
        **state,
        "schema_context": schema_text,
        "structured_plan": plan,
        "plan_json": plan_json_str,
        "retry_count": state.get("retry_count", 0),
    }
