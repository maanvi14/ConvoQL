"""Structured planner: Outputs JSON query plan with dialect-aware date functions."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import json

from config import get_settings
from db.connection import db_manager
from cache.schema_rag import schema_rag

settings = get_settings()

# Dialect-specific date function templates
DATE_TEMPLATES = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', {{col}}) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', {{col}}) = strftime('%Y-%m', 'now', '-1 month')",
        "this_year": "strftime('%Y', {{col}}) = strftime('%Y', 'now')",
        "last_year": "strftime('%Y', {{col}}) = strftime('%Y', 'now', '-1 year')",
        "format": "strftime('%Y-%m', {{col}})",
    },
    "mysql": {
        "this_month": "DATE_FORMAT({{col}}, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT({{col}}, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "this_year": "YEAR({{col}}) = YEAR(NOW())",
        "last_year": "YEAR({{col}}) = YEAR(NOW()) - 1",
        "format": "DATE_FORMAT({{col}}, '%Y-%m')",
    },
    "postgresql": {
        "this_month": "TO_CHAR({{col}}, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR({{col}}, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "this_year": "EXTRACT(YEAR FROM {{col}}) = EXTRACT(YEAR FROM NOW())",
        "last_year": "EXTRACT(YEAR FROM {{col}}) = EXTRACT(YEAR FROM NOW()) - 1",
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
    "operator": "=",
    "value": "{date_this_month}"
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
        elif type_filter == "credit":
            # Ensure credit filter exists
            if not any("type = 'credit'" in f.lower() for f in where_filters if isinstance(f, str)):
                plan["where_filters"].append("type = 'credit'")

        # Clean invalid joins
        joins = plan.get("joins", [])
        cleaned_joins = []
        for join in joins:
            if join and join.get("on_condition"):
                on_cond = join["on_condition"].lower()
                if "categories.category" in on_cond or "category = category" in on_cond:
                    print(f"[Planner] Removing incorrect join: {join}")
                    continue
            cleaned_joins.append(join)
        plan["joins"] = cleaned_joins

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
