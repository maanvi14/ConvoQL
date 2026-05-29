"""Comprehensive test queries for ConvoQL validation.

Generated from demo dataset covering all intents, edge cases, and bug scenarios.
Run these to validate your agent after any code changes.
"""

TEST_QUERIES = {
    "TAG_SEARCH_NO_TYPE_FILTER": [
        # These MUST NOT have type = 'debit' or type = 'credit'
        # Tags exist on BOTH transaction types
        ("Show all transactions tagged with 'subscription'", "subscription"),
        ("Show all transactions tagged with 'anomaly'", "anomaly"),
        ("Show all transactions tagged with 'monthly'", "monthly"),
        ("Show all transactions tagged with 'weekend'", "weekend"),
        ("Show all transactions tagged with 'food'", "food"),
        ("Show all transactions tagged with 'travel'", "travel"),
    ],
    "CATEGORY_NO_TYPE_FILTER": [
        # These MUST NOT have type filter unless explicitly asked for expenses/income
        ("What are all my Health transactions?", "Health"),
        ("Show me my Shopping transactions", "Shopping"),
        ("List all Food transactions", "Food"),
        ("Show me Travel transactions", "Travel"),
        ("What Entertainment transactions do I have?", "Entertainment"),
    ],
    "MERCHANT_NO_TYPE_FILTER": [
        # These MUST NOT have type filter
        ("Show all transactions from Amazon", "Amazon"),
        ("Show all transactions from Apollo Pharmacy", "Apollo Pharmacy"),
        ("Show all transactions from Netflix", "Netflix"),
        ("Show all transactions from Uber", "Uber"),
    ],
    "EXPENSE_QUERIES_DEBIT": [
        # These MUST have type = 'debit'
        ("How much did I spend on Groceries this month?", None),
        ("What was my highest expense ever?", None),
        ("Show my spending by category this month", None),
        ("How much did I spend on Shopping in March 2025?", None),
        ("What was my biggest purchase?", None),
        ("Show me all expenses above 5000", None),
        ("How much did I spend on Food in June 2025?", None),
    ],
    "INCOME_QUERIES_CREDIT": [
        # These MUST have type = 'credit'
        ("What is my total income?", None),
        ("Show me all salary credits", None),
        ("How much freelance income did I get?", None),
        ("What was my total income in May 2025?", None),
        ("Show me all investment returns", None),
    ],
    "TIME_BASED": [
        ("Show my spending trend over the last 6 months", None),
        ("What did I spend in January 2025?", None),
        ("Compare my spending in March vs April", None),
        ("Show me transactions from last month", None),
        ("What were my expenses this month?", None),
        ("Show me all transactions from June 2025", None),
    ],
    "AGGREGATION": [
        ("What is my average daily spend?", None),
        ("How many transactions did I make this month?", None),
        ("What category has the highest spending?", None),
        ("Show me total spending by payment method", None),
        ("What is the total amount spent on Travel?", None),
    ],
    "RANKING": [
        ("What are my top 5 expenses?", None),
        ("Which month had the highest spending?", None),
        ("Show me the top 3 categories by spending", None),
        ("What was my most expensive transaction?", None),
    ],
    "ANOMALY": [
        ("Show me unusual transactions", None),
        ("What are my biggest outliers?", None),
        ("Show me transactions that are way above average", None),
        ("Any suspicious spending patterns?", None),
    ],
    "BUDGET_MULTI_TABLE": [
        # These MUST use JOINs with budgets table
        ("Which categories are over budget this month?", None),
        ("Compare my budget vs actual spending for June", None),
        ("Am I over budget on any category?", None),
        ("Show budget utilization by category", None),
    ],
    "ACCOUNT_METADATA": [
        # These MUST use accounts table
        ("What is my total balance across all accounts?", None),
        ("Show me my HDFC account transactions", None),
        ("Which account has the highest balance?", None),
    ],
    "COMPOUND": [
        ("Show me my income and expenses for May 2025", None),
        ("Compare my Shopping vs Groceries spending", None),
        ("What did I spend on Food and Entertainment this month?", None),
    ],
    "EDGE_CASES": [
        ("Show me transactions with no tags", None),
        ("What transactions used Cash payment?", None),
        ("Show me all UPI transactions", None),
        ("List transactions from ICICI account", None),
        ("Show me refunds and returns", None),
    ],
}

# Validation rules per category
VALIDATION_RULES = {
    "TAG_SEARCH_NO_TYPE_FILTER": {
        "description": "SQL must NOT contain 'type = ' (neither debit nor credit)",
        "check": lambda sql: "type =" not in sql.lower(),
        "expected_result": "Should return rows (tags exist on both debit and credit)",
    },
    "CATEGORY_NO_TYPE_FILTER": {
        "description": "SQL must NOT contain 'type = ' unless explicitly asking for expenses/income",
        "check": lambda sql: "type =" not in sql.lower(),
        "expected_result": "Should return all transactions in that category",
    },
    "MERCHANT_NO_TYPE_FILTER": {
        "description": "SQL must NOT contain 'type = '",
        "check": lambda sql: "type =" not in sql.lower(),
        "expected_result": "Should return all transactions from that merchant",
    },
    "EXPENSE_QUERIES_DEBIT": {
        "description": "SQL MUST contain 'type = 'debit''",
        "check": lambda sql: "type = 'debit'" in sql.lower(),
        "expected_result": "Should only return expense transactions",
    },
    "INCOME_QUERIES_CREDIT": {
        "description": "SQL MUST contain 'type = 'credit''",
        "check": lambda sql: "type = 'credit'" in sql.lower(),
        "expected_result": "Should only return income transactions",
    },
    "BUDGET_MULTI_TABLE": {
        "description": "SQL MUST contain 'budgets' table and JOIN",
        "check": lambda sql: "budgets" in sql.lower(),
        "expected_result": "Should compare budget vs actual spending",
    },
    "ACCOUNT_METADATA": {
        "description": "SQL MUST contain 'accounts' table",
        "check": lambda sql: "accounts" in sql.lower(),
        "expected_result": "Should return account metadata",
    },
    "RANKING": {
        "description": "SQL MUST contain 'LIMIT' clause",
        "check": lambda sql: "limit" in sql.lower(),
        "expected_result": "Should return top N results",
    },
    "ANOMALY": {
        "description": "SQL should identify unusual transactions (ABS, ORDER BY, or LIMIT)",
        "check": lambda sql: "abs" in sql.lower() or "order by" in sql.lower() or "limit" in sql.lower(),
        "expected_result": "Should identify unusually large or small transactions",
    },
    "TIME_BASED": {
        "description": "SQL MUST use date filtering",
        "check": lambda sql: any(f in sql.lower() for f in ["strftime", "date_format", "to_char", "year", "month"]),
        "expected_result": "Should filter by time period",
    },
    "AGGREGATION": {
        "description": "SQL MUST use aggregate function (SUM, COUNT, AVG)",
        "check": lambda sql: any(f in sql.lower() for f in ["sum", "count", "avg"]),
        "expected_result": "Should return aggregated values",
    },
    "COMPOUND": {
        "description": "SQL should handle multiple conditions",
        "check": lambda sql: "and" in sql.lower() or "or" in sql.lower() or "union" in sql.lower(),
        "expected_result": "Should handle compound question",
    },
    "EDGE_CASES": {
        "description": "SQL should handle edge cases correctly",
        "check": lambda sql: sql.strip().startswith("SELECT"),
        "expected_result": "Should return valid results for edge case",
    },
}


def get_all_queries() -> list:
    """Return flat list of all test queries with categories."""
    all_queries = []
    for category, queries in TEST_QUERIES.items():
        for query_tuple in queries:
            if isinstance(query_tuple, tuple):
                query = query_tuple[0]
            else:
                query = query_tuple
            all_queries.append((category, query))
    return all_queries


def get_critical_queries() -> list:
    """Return only the most critical queries for quick validation."""
    return [
        ("TAG_SEARCH_NO_TYPE_FILTER", "Show all transactions tagged with 'subscription'"),
        ("EXPENSE_QUERIES_DEBIT", "How much did I spend on Groceries this month?"),
        ("INCOME_QUERIES_CREDIT", "What is my total income?"),
        ("BUDGET_MULTI_TABLE", "Which categories are over budget this month?"),
        ("RANKING", "What was my highest expense ever?"),
        ("ANOMALY", "Show me unusual transactions"),
        ("TIME_BASED", "Show my spending trend over the last 6 months"),
        ("CATEGORY_NO_TYPE_FILTER", "What are all my Health transactions?"),
    ]


def validate_sql(category: str, sql: str) -> tuple:
    """Validate generated SQL against category rules.

    Returns:
        (passed: bool, message: str)
    """
    rule = VALIDATION_RULES.get(category)
    if not rule:
        return True, "No validation rule for this category"

    try:
        passed = rule["check"](sql)
        if passed:
            return True, "✅ " + rule['description'] + " - PASSED"
        else:
            return False, "❌ " + rule['description'] + " - FAILED | SQL: " + sql[:150] + "..."
    except Exception as e:
        return False, "⚠️ Validation error: " + str(e)


# Expected row counts for critical queries (from 2026 dataset analysis)
EXPECTED_RESULTS = {
    "Show all transactions tagged with 'subscription'": {"min_rows": 5, "max_rows": 20},
    "Show all transactions tagged with 'anomaly'": {"min_rows": 3, "max_rows": 15},
    "How much did I spend on Groceries this month?": {"min_rows": 1, "max_rows": 15},
    "What is my total income?": {"min_rows": 1, "max_rows": 10},
    "Which categories are over budget this month?": {"min_rows": 1, "max_rows": 15},
    "What was my highest expense ever?": {"min_rows": 1, "max_rows": 1},
    "Show me unusual transactions": {"min_rows": 0, "max_rows": 25},
    "Show my spending trend over the last 6 months": {"min_rows": 1, "max_rows": 20},
    "What are all my Health transactions?": {"min_rows": 1, "max_rows": 10},
}
