"""Dynamic few-shot: Selects examples based on detected intent."""
from typing import Dict, Any, List

EXAMPLE_BANK = {
    "ranking": """Question: "What was my highest expense ever?"
SQL:
```sql
SELECT description, ABS(amount) AS expense_amount, date, category, account
FROM transactions
WHERE type = 'debit'
ORDER BY ABS(amount) DESC
LIMIT 1
```""",

    "aggregation": """Question: "How much did I spend by category last month?"
SQL:
```sql
SELECT category, SUM(ABS(amount)) AS total_spent, COUNT(*) AS num_transactions
FROM transactions
WHERE type = 'debit'
  AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')
GROUP BY category
ORDER BY total_spent DESC
```""",

    "filter_lookup": """Question: "Show me all transactions above 10000"
SQL:
```sql
SELECT date, description, ABS(amount) AS amount, category, account, merchant
FROM transactions
WHERE ABS(amount) > 10000
ORDER BY ABS(amount) DESC
LIMIT 50
```""",

    "budget_compare": """Question: "Which categories are over budget this month?"
SQL:
```sql
SELECT b.category, b.allocated AS budget, b.spent,
       ROUND((b.spent / b.allocated) * 100, 2) AS pct_used
FROM budgets b
WHERE strftime('%Y-%m', b.month_year) = strftime('%Y-%m', 'now')
  AND b.spent > b.allocated
ORDER BY pct_used DESC
```""",

    "trend": """Question: "Show my monthly spending trend"
SQL:
```sql
SELECT strftime('%Y-%m', date) AS month,
       SUM(ABS(amount)) AS total_spent,
       COUNT(*) AS transaction_count
FROM transactions
WHERE type = 'debit'
GROUP BY month
ORDER BY month DESC
LIMIT 12
```""",

    "anomaly": """Question: "Show me unusual transactions this month"
SQL:
```sql
SELECT t.*
FROM transactions t
WHERE strftime('%Y-%m', t.date) = strftime('%Y-%m', 'now')
  AND ABS(t.amount) > (
      SELECT AVG(ABS(amount)) + 2 * (
          SELECT SQRT(AVG((ABS(amount) - avg_amt) * (ABS(amount) - avg_amt)))
          FROM (SELECT AVG(ABS(amount)) AS avg_amt FROM transactions WHERE category = t.category)
      )
      FROM transactions
      WHERE category = t.category
  )
ORDER BY ABS(t.amount) DESC
LIMIT 20
```""",

    "metadata": """Question: "What is my total balance across all accounts?"
SQL:
```sql
SELECT account_name, balance, currency
FROM accounts
ORDER BY balance DESC
```""",
}

def select_examples(intent_data: Dict[str, Any]) -> str:
    """Select relevant few-shot examples based on intent."""
    primary = intent_data.get("primary_intent", "filter_lookup")
    secondary = intent_data.get("secondary_intents", [])

    examples = []

    # Primary intent example
    if primary in EXAMPLE_BANK:
        examples.append(EXAMPLE_BANK[primary])

    # Secondary intent example (if different from primary)
    for sec in secondary:
        if sec in EXAMPLE_BANK and sec != primary:
            examples.append(EXAMPLE_BANK[sec])
            break  # Only add one secondary

    # Default fallback
    if not examples:
        examples.append(EXAMPLE_BANK["filter_lookup"])

    return "\n\n---\n\n".join(examples)

async def dynamic_few_shot_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node wrapper for dynamic few-shot selection."""
    intent = state.get("intent", {})
    examples = select_examples(intent)

    return {
        **state,
        "few_shot_examples": examples,
    }
