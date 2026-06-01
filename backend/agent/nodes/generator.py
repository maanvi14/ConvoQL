"""Generator node: Creates SQL from natural language with dialect awareness."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import re

from config import get_settings
from db.connection import db_manager

settings = get_settings()

# Dialect-specific date function examples - NOW WITH ROLLING WINDOWS
DIALECT_EXAMPLES = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')",
        "last_3_months": "date >= date('now', '-3 months')",
        "last_6_months": "date >= date('now', '-6 months')",
        "last_year": "date >= date('now', '-1 year')",
        "date_format": "strftime('%Y-%m', date)",
        "year_month": "strftime('%Y-%m', date)",
        "date_parse": "date",
    },
    "mysql": {
        "this_month": "DATE_FORMAT(date, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT(date, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "last_3_months": "date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)",
        "last_6_months": "date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)",
        "last_year": "date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)",
        "date_format": "DATE_FORMAT(date, '%Y-%m')",
        "year_month": "DATE_FORMAT(date, '%Y-%m')",
        "date_parse": "date",
    },
    "postgresql": {
        "this_month": "TO_CHAR(date, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR(date, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "last_3_months": "date >= NOW() - INTERVAL '3 months'",
        "last_6_months": "date >= NOW() - INTERVAL '6 months'",
        "last_year": "date >= NOW() - INTERVAL '1 year'",
        "date_format": "TO_CHAR(date, 'YYYY-MM')",
        "year_month": "TO_CHAR(date, 'YYYY-MM')",
        "date_parse": "date::date",
    }
}

# Column name mapping for common hallucinations (fallback only)
COLUMN_ALIASES = {
    "id": "transaction_id",
    "trans_id": "transaction_id",
    "txn_id": "transaction_id",
    "user_id": None,
    "customer_id": None,
    "created_at": "date",
    "timestamp": "date",
    "value": "amount",
    "price": "amount",
    "cost": "amount",
    "expense": "amount",
    "total": None,
    "sum": None,
}

# Tables and their columns — populated at runtime from DB
TABLE_COLUMNS: Dict[str, List[str]] = {}


async def _load_schema_from_db() -> str:
    """Fetch actual schema from database for LLM grounding."""
    schema = await db_manager.get_schema()
    schema_lines = []

    for table in schema.get("tables", []):
        table_name = table["name"]
        cols = table.get("columns", [])

        # Store for validation
        TABLE_COLUMNS[table_name] = [c["name"] for c in cols]

        col_defs = []
        for col in cols:
            col_name = col["name"]
            col_type = col.get("type", "TEXT")
            # CRITICAL: Annotate amount column with sign convention
            if col_name == "amount":
                col_defs.append(f"    {col_name} {col_type}  -- NEGATIVE for debits (expenses), POSITIVE for credits (income)")
            elif col_name == "type":
                col_defs.append(f"    {col_name} {col_type}  -- 'debit' or 'credit'")
            else:
                col_defs.append(f"    {col_name} {col_type}")

        schema_lines.append(f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);")

    return "\n\n".join(schema_lines)


TAGS_COLUMN_RULES = """
=== SPECIAL COLUMN: tags ===
The `tags` column is a COMMA-SEPARATED TEXT string, NOT a JSON object or sub-table.
Examples of tags values:
  'subscription'
  'subscription,health'
  'electronics,anomaly,big'
  'salary,monthly,raise'

To filter by tag, ALWAYS use: tags LIKE '%tag_name%'
NEVER use: tags.name = 'tag_name'  (this is WRONG — tags is not a JSON object)
NEVER use: tags = 'tag_name'       (this misses multi-tag rows)
"""

# CRITICAL SIGN CONVENTION RULES added to prompt
SIGN_CONVENTION_RULES = """
=== CRITICAL: AMOUNT SIGN CONVENTION ===
The `amount` column uses SIGNED values:
  - Debits (expenses, purchases, payments): NEGATIVE values (e.g., -28000.00, -4500.00)
  - Credits (income, salary, deposits): POSITIVE values (e.g., 80000.00, 5000.00)

THEREFORE:
1. For spending/expense analysis: ALWAYS use ABS(amount) in aggregations and ORDER BY
   CORRECT: SUM(ABS(amount)), ORDER BY ABS(amount) DESC
   WRONG: SUM(amount), MAX(amount), ORDER BY amount DESC (sorts debits at bottom!)

2. For income analysis: Use amount directly (no ABS needed)
   CORRECT: SUM(amount) for total income

3. For "highest expense": ORDER BY ABS(amount) DESC LIMIT 1
   For "highest income": ORDER BY amount DESC LIMIT 1

4. NEVER filter with amount > 0 or amount < 0 to determine debit/credit.
   ALWAYS use: type = 'debit' or type = 'credit'
   WRONG: WHERE amount > 0 (this filters OUT all debits!)
   WRONG: WHERE amount < 0 (this filters OUT all credits!)
"""

# ROLLING WINDOW DATE RULES
DATE_FILTER_RULES = """
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
"""

GENERATOR_PROMPT = """You are an expert {dialect} SQL generator. You write ONLY correct, executable {dialect} queries.

=== EXACT DATABASE SCHEMA (use these exact column names, NEVER hallucinate) ===
{exact_schema}

{sample_data}

{tags_rules}

{sign_rules}

{date_rules}

USER QUESTION: {question}

PREVIOUS ERROR (if any): {error}
RETRY INSTRUCTION (if any): {retry_hint}

DETECTED INTENT:
- Primary: {primary_intent}
- Type Filter: {type_filter}
- Time Dimension: {time_dimension}
- Aggregation: {aggregation_type}
- Dialect: {dialect}

=== CRITICAL RULES ===
1. ONLY SELECT statements. NEVER INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT.
2. Use ONLY column names from the schema above. NEVER make up columns.
3. For "highest expense", "biggest purchase", "most expensive": ALWAYS use: ORDER BY ABS(amount) DESC LIMIT 1
   NEVER use MAX(amount) because debit amounts are negative.
4. For expenses/spending: ALWAYS filter with type = 'debit' AND use ABS(amount) in SELECT
5. For income: ALWAYS filter with type = 'credit' AND use amount directly (no ABS)
6. SINGLE TABLE PREFERENCE: The transactions table has ALL needed columns. DO NOT JOIN unless question explicitly asks for data from other tables.
7. Date filtering: use {dialect} date functions
8. This month: {date_this_month}
9. Last month: {date_last_month}
10. Last 3 months: {date_last_3_months}
11. Last 6 months: {date_last_6_months}
12. Last year: {date_last_year}
13. LIMIT: Use LIMIT 50 unless user asks for specific number.
14. NEVER compare dates from different tables directly. Normalize both with date function.
15. TYPE FILTER RULE: Only add type = 'debit' or type = 'credit' when the question EXPLICITLY asks for expenses or income. NEVER add type filter for tag, category, or merchant searches.
16. COLUMN NAMES: Use exact names from schema. If a table has transaction_id, NEVER use id.
17. TAG FILTERING: The tags column is comma-separated TEXT. Use tags LIKE '%value%' — NEVER tags.name or JSON syntax.
18. DATE FILTERING:
    - For specific months like "March 2026": use strftime('%Y-%m', date) = '2026-03'
    - NEVER use strftime('%Y-%m', date) = strftime('%Y-%m', '2026-03') — this is WRONG
    - NEVER combine this_month/last_month with a specific month — use ONLY one date filter
    - For "May 2026": strftime('%Y-%m', date) = '2026-05' (direct string comparison)
    - The date column stores dates as TEXT in 'YYYY-MM-DD' format
19. AMOUNT SIGN CONVENTION (CRITICAL):
    - Debits are NEGATIVE, Credits are POSITIVE
    - For spending queries: SELECT SUM(ABS(amount)) — NOT SUM(amount)
    - For spending queries: ORDER BY ABS(amount) DESC — NOT ORDER BY amount DESC
    - NEVER use amount > 0 or amount < 0 as a filter

=== CORRECT EXAMPLES ===

Example A — Simple highest expense (single table, NO JOIN):
Question: "What was my highest expense ever?"
```sql
SELECT transaction_id, description, ABS(amount) AS expense_amount, date, category, account
FROM transactions
WHERE type = 'debit'
ORDER BY ABS(amount) DESC
LIMIT 1
```

Example B — Spending by category last month (single table, NO JOIN):
Question: "How much did I spend by category last month?"
```sql
SELECT category, SUM(ABS(amount)) AS total_spent, COUNT(*) AS num_transactions
FROM transactions
WHERE type = 'debit'
  AND {date_last_month}
GROUP BY category
ORDER BY total_spent DESC
```

Example C — Spending last 6 months (ROLLING WINDOW):
Question: "Analyze my spending patterns for the last 6 months"
```sql
SELECT strftime('%Y-%m', date) AS month, category, SUM(ABS(amount)) AS total_spent
FROM transactions
WHERE type = 'debit'
  AND {date_last_6_months}
GROUP BY month, category
ORDER BY month, total_spent DESC
```

Example D — Total income (single table, NO JOIN):
Question: "What is my total income?"
```sql
SELECT SUM(amount) AS total_income
FROM transactions
WHERE type = 'credit'
```

Example E — Tag search (NO type filter, tags is comma-separated TEXT):
Question: "Show all transactions tagged with 'subscription'"
```sql
SELECT transaction_id, date, description, amount, type, category, account, merchant, payment_method, tags
FROM transactions
WHERE tags LIKE '%subscription%'
ORDER BY date DESC
LIMIT 50
```

Example F — Specific month query:
Question: "How much did I spend on Food in May 2026?"
```sql
SELECT category, SUM(ABS(amount)) AS total
FROM transactions
WHERE type = 'debit'
  AND category = 'Food'
  AND strftime('%Y-%m', date) = '2026-05'
GROUP BY category
```

Example G — Monthly spending trend (use ABS for debits):
Question: "Show my monthly spending trend"
```sql
SELECT strftime('%Y-%m', date) AS month, SUM(ABS(amount)) AS total_spent, COUNT(*) AS num_transactions
FROM transactions
WHERE type = 'debit'
GROUP BY month
ORDER BY month
```

Generate ONLY the SQL query inside the code block:

```sql
"""


def _extract_all_column_refs(sql: str) -> List[str]:
    """Extract all bare column references (not table.column) from SQL."""
    # Remove string literals first
    sql_no_strings = re.sub(r"'[^']*'", "''", sql)
    sql_no_strings = re.sub(r'"[^"]*"', '""', sql_no_strings)

    # Find bare column names (not preceded by table.)
    # Pattern: word not preceded by word.
    refs = re.findall(r'(?<![\w.])\b([a-zA-Z_][a-zA-Z0-9_]*)\b', sql_no_strings)

    # Filter out SQL keywords
    sql_keywords = {
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL', 'IS', 'IN', 'BETWEEN',
        'LIKE', 'LIMIT', 'ORDER', 'BY', 'GROUP', 'HAVING', 'ASC', 'DESC', 'AS',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'DISTINCT', 'ALL',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'ABS', 'ROUND', 'CAST', 'COALESCE',
        'strftime', 'DATE_FORMAT', 'TO_CHAR', 'NOW', 'CURRENT_DATE', 'CURRENT_TIMESTAMP',
        'WHEN', 'THEN', 'ELSE', 'END', 'CASE', 'IF', 'TRUE', 'FALSE',
        'EXISTS', 'UNION', 'INTERSECT', 'EXCEPT', 'WITH',
    }

    return [r for r in refs if r.upper() not in sql_keywords and not r.upper().startswith('SQLITE_')]


def _validate_and_fix_columns(sql: str) -> str:
    """Validate column names against schema and fix common hallucinations."""
    if not sql or not TABLE_COLUMNS:
        return sql

    original = sql

    # --- Fix 1: Replace known hallucinated bare column names ---
    for bad_col, good_col in COLUMN_ALIASES.items():
        # Match as whole word in SELECT, WHERE, GROUP BY, ORDER BY, HAVING
        pattern = r'(?<![\w.])' + re.escape(bad_col) + r'(?![\w])'

        if re.search(pattern, sql, re.IGNORECASE):
            if good_col is None:
                # Column doesn't exist — remove from SELECT list
                # Pattern: "bad_col," or ", bad_col" at SELECT time
                sql = re.sub(
                    r'(?i)SELECT\s+([^\n]*?)\b' + re.escape(bad_col) + r'\b\s*,?\s*',
                    lambda m: 'SELECT ' + m.group(1).replace(m.group(0).split()[-1], '').rstrip(',').rstrip(),
                    sql
                )
                # Remove trailing comma before FROM
                sql = re.sub(r',\s*FROM', ' FROM', sql, flags=re.IGNORECASE)
                print(f"[Generator] Removed hallucinated column '{bad_col}'")
            else:
                sql = re.sub(pattern, good_col, sql, flags=re.IGNORECASE)
                print(f"[Generator] Fixed column name: '{bad_col}' -> '{good_col}'")

    # --- Fix 2: CRITICAL — catch tags.name, tags.value, tags->> etc. (JSON hallucinations) ---
    json_hallucinations = [
        (r'\btags\.name\b', "tags LIKE '%subscription%'"),  # Most common
        (r'\btags\.value\b', "tags LIKE '%value%'"),
        (r'\btags\[[^\]]+\]', "tags LIKE '%value%'"),
        (r'\btags\s*->>', "tags"),
        (r'\btags\s*#>', "tags"),
    ]

    for pattern, replacement in json_hallucinations:
        if re.search(pattern, sql, re.IGNORECASE):
            print(f"[Generator] FIXED JSON hallucination: removed tags.dot notation")
            # We can't auto-replace the whole WHERE clause safely, so we mark for retry
            # But we CAN fix the SELECT part
            sql = re.sub(pattern, "tags", sql, flags=re.IGNORECASE)

    # --- Fix 3: Ensure WHERE tags = 'x' becomes WHERE tags LIKE '%x%' ---
    sql = re.sub(
        r"(?i)WHERE\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"WHERE {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )

    # --- Fix 4: Remove double commas and fix spacing ---
    sql = re.sub(r',\s*,', ',', sql)
    sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s+FROM', ' FROM', sql, flags=re.IGNORECASE)

    return sql


def _enforce_abs_for_debits(sql: str, intent_data: Dict[str, Any]) -> str:
    """CRITICAL: Ensure ABS(amount) is used for debit/spending queries."""
    type_filter = intent_data.get("type_filter") if intent_data else None
    sql_upper = sql.upper()

    # If this is a debit/spending query, enforce ABS(amount)
    if type_filter == "debit" or "type = 'debit'" in sql.lower():
        # Check if SUM(amount) or ORDER BY amount exists without ABS
        # Fix SUM(amount) -> SUM(ABS(amount))
        sql = re.sub(
            r'(?i)SUM\s*\(\s*amount\s*\)',
            'SUM(ABS(amount))',
            sql
        )
        # Fix ORDER BY amount DESC -> ORDER BY ABS(amount) DESC
        sql = re.sub(
            r'(?i)ORDER\s+BY\s+amount\s+DESC',
            'ORDER BY ABS(amount) DESC',
            sql
        )
        # Fix ORDER BY amount ASC -> ORDER BY ABS(amount) ASC
        sql = re.sub(
            r'(?i)ORDER\s+BY\s+amount\s+ASC',
            'ORDER BY ABS(amount) ASC',
            sql
        )
        # Fix MAX(amount) -> ORDER BY ABS(amount) DESC LIMIT 1 (but only in SELECT)
        sql = re.sub(
            r'(?i)MAX\s*\(\s*amount\s*\)',
            'MAX(ABS(amount))',
            sql
        )

    return sql


def _post_process_sql(sql: str, intent_data: Dict[str, Any], retry_hint: str, dialect: str = "sqlite") -> str:
    """Apply deterministic fixes based on retry hints and intent."""

    # Fix 1: Validate and fix column names
    sql = _validate_and_fix_columns(sql)

    # Fix 1b: CRITICAL - Enforce ABS(amount) for debit queries
    sql = _enforce_abs_for_debits(sql, intent_data)

    # Fix 2: Remove erroneous type filters based on retry hint
    if retry_hint and "Remove type" in retry_hint:
        original = sql
        sql = re.sub(r"\s*AND\s+type\s*=\s*['\"](debit|credit)['\"]", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"type\s*=\s*['\"](debit|credit)['\"]\s*AND\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]", "WHERE 1=1", sql, flags=re.IGNORECASE)
        if sql != original:
            print(f"[Generator] Removed type filter based on retry_hint")

    # Fix 3: If intent says no type filter, ensure none exists
    type_filter = intent_data.get("type_filter")
    if type_filter is None and "type =" in sql.lower():
        original = sql
        sql = re.sub(r"\s*AND\s+type\s*=\s*['\"](debit|credit)['\"]", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]\s*AND", "WHERE", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]", "WHERE 1=1", sql, flags=re.IGNORECASE)
        if sql != original:
            print(f"[Generator] Removed hallucinated type filter (intent.type_filter is null)")

    # Fix 4: Dialect-specific fixes
    if dialect == "sqlite":
        # Ensure date comparisons use strftime, not direct string comparison for month ranges
        pass  # Already handled by examples

    # Fix 5: Ensure proper LIMIT
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(';') + " LIMIT 50"

    # Clean up
    sql = re.sub(r'\s+', ' ', sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return sql


async def generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    dialect = state.get("dialect", "sqlite")
    date_examples = DIALECT_EXAMPLES.get(dialect, DIALECT_EXAMPLES["sqlite"])

    # ============================================================================
    # FIX: Load ACTUAL schema from database instead of hardcoded EXACT_SCHEMA
    # ============================================================================
    try:
        exact_schema = await _load_schema_from_db()
    except Exception as e:
        print(f"[Generator] Failed to load schema from DB: {e}")
        exact_schema = "-- Schema unavailable --"

    # Get sample data from database
    sample_data_parts = []
    try:
        schema = await db_manager.get_schema()
        tables = schema.get("tables", []) if isinstance(schema, dict) else schema
        for table in tables[:4]:
            table_name = table.get("name") if isinstance(table, dict) else table
            if not table_name:
                continue
            try:
                sample = await db_manager.execute_readonly(
                    f"SELECT * FROM {table_name} LIMIT 2"
                )
                rows = sample.get("rows", []) if isinstance(sample, dict) else []
                if rows:
                    cols = list(rows[0].keys()) if rows else []
                    sample_data_parts.append(
                        f"Table `{table_name}` (columns: {', '.join(cols)}):\n" +
                        "\n".join([str(r) for r in rows[:2]])
                    )
            except Exception as e:
                print(f"[Generator] Could not sample {table_name}: {e}")
    except Exception as e:
        print(f"[Generator] Could not get schema: {e}")

    sample_data_text = "\n\n".join(sample_data_parts) if sample_data_parts else "No sample data available."

    # Format sample data section
    sample_data_section = f"SAMPLE DATA FROM TABLES:\n{sample_data_text}" if sample_data_text else ""

    intent = state.get("intent", {})

    # Detect rolling window from question
    question_lower = state["question"].lower()
    time_dimension = intent.get("time_dimension", "")

    # Map time dimension to correct date filter key
    date_filter_key = "this_month"  # default
    if "6 month" in question_lower or "six month" in question_lower or time_dimension == "last_6_months":
        date_filter_key = "last_6_months"
    elif "3 month" in question_lower or "three month" in question_lower or time_dimension == "last_3_months":
        date_filter_key = "last_3_months"
    elif "last month" in question_lower or time_dimension == "last_month":
        date_filter_key = "last_month"
    elif "last year" in question_lower or time_dimension == "last_year":
        date_filter_key = "last_year"
    elif "this month" in question_lower or time_dimension == "this_month":
        date_filter_key = "this_month"

    prompt = ChatPromptTemplate.from_template(GENERATOR_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "exact_schema": exact_schema,
        "sample_data": sample_data_section,
        "tags_rules": TAGS_COLUMN_RULES,
        "sign_rules": SIGN_CONVENTION_RULES,
        "date_rules": DATE_FILTER_RULES.format(
            date_this_month=date_examples["this_month"],
            date_last_month=date_examples["last_month"],
            date_last_3_months=date_examples["last_3_months"],
            date_last_6_months=date_examples["last_6_months"],
            date_last_year=date_examples["last_year"],
        ),
        "error": state.get("error", "None"),
        "retry_hint": state.get("retry_hint", "None"),
        "primary_intent": intent.get("primary_intent", "filter_lookup"),
        "type_filter": str(intent.get("type_filter", "null")),
        "time_dimension": str(intent.get("time_dimension", "null")),
        "aggregation_type": str(intent.get("aggregation_type", "null")),
        "dialect": dialect,
        "date_this_month": date_examples["this_month"],
        "date_last_month": date_examples["last_month"],
        "date_last_3_months": date_examples["last_3_months"],
        "date_last_6_months": date_examples["last_6_months"],
        "date_last_year": date_examples["last_year"],
    })

    sql = response.content
    if "```sql" in sql:
        sql = sql.split("```sql")[1].split("```")[0].strip()
    elif "```" in sql:
        sql = sql.split("```")[1].split("```")[0].strip()

    # Post-process: fix columns, type filters, ABS enforcement, cleanup
    sql = _post_process_sql(sql, intent, state.get("retry_hint", ""), dialect)

    return {
        **state,
        "generated_sql": sql,
        "error": None,
    }
