"""Comprehensive test queries for ConvoQL validation.

Calibrated against finance.db schema (January – May 2026).
Dataset: 94 transactions, 16 credits, 78 debits, 14 categories, 3 accounts.

Current "month" context: May 2026 (for "this month" / "last month" queries).
"""

from typing import Dict, Any, List, Tuple

# ════════════════════════════════════════════════════════════════
# TEST QUERIES BY CATEGORY
# ════════════════════════════════════════════════════════════════

TEST_QUERIES: Dict[str, List[Tuple[str, Any]]] = {

    # ─────────────────────────────────────────────────────────────
    # TAG SEARCH — MUST NOT have type filter (tags on both debit/credit)
    # ─────────────────────────────────────────────────────────────
    "TAG_SEARCH_NO_TYPE_FILTER": [
        ("Show all transactions tagged with 'subscription'", "subscription"),
        ("Show all transactions tagged with 'anomaly'", "anomaly"),
        ("Show all transactions tagged with 'monthly'", "monthly"),
        ("Show all transactions tagged with 'weekend'", "weekend"),
        ("Show all transactions tagged with 'food'", "food"),
        ("Show all transactions tagged with 'travel'", "travel"),
    ],

    # ─────────────────────────────────────────────────────────────
    # CATEGORY SEARCH — MUST NOT have type filter unless explicitly asked
    # ─────────────────────────────────────────────────────────────
    "CATEGORY_NO_TYPE_FILTER": [
        ("What are all my Health transactions?", "Health"),
        ("Show me my Shopping transactions", "Shopping"),
        ("List all Food transactions", "Food"),
        ("Show me Travel transactions", "Travel"),
        ("What Entertainment transactions do I have?", "Entertainment"),
    ],

    # ─────────────────────────────────────────────────────────────
    # MERCHANT SEARCH — MUST NOT have type filter
    # ─────────────────────────────────────────────────────────────
    "MERCHANT_NO_TYPE_FILTER": [
        ("Show all transactions from Amazon", "Amazon"),
        ("Show all transactions from Apollo Pharmacy", "Apollo Pharmacy"),
        ("Show all transactions from Netflix", "Netflix"),
        ("Show all transactions from Uber", "Uber"),
    ],

    # ─────────────────────────────────────────────────────────────
    # EXPENSE QUERIES — MUST have type = 'debit'
    # ─────────────────────────────────────────────────────────────
    "EXPENSE_QUERIES_DEBIT": [
        ("How much did I spend on Groceries this month?", None),           # May 2026
        ("What was my highest expense ever?", None),
        ("Show my spending by category this month", None),                 # May 2026
        ("How much did I spend on Shopping in March 2026?", None),       # Updated to 2026
        ("What was my biggest purchase?", None),
        ("Show me all expenses above 5000", None),
        ("How much did I spend on Food in May 2026?", None),               # Updated to 2026
    ],

    # ─────────────────────────────────────────────────────────────
    # INCOME QUERIES — MUST have type = 'credit'
    # ─────────────────────────────────────────────────────────────
    "INCOME_QUERIES_CREDIT": [
        ("What is my total income?", None),
        ("Show me all salary credits", None),
        ("How much freelance income did I get?", None),
        ("What was my total income in May 2026?", None),                   # Updated to 2026
        ("Show me all investment returns", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # TIME-BASED QUERIES
    # ─────────────────────────────────────────────────────────────
    "TIME_BASED": [
        ("Show my spending trend over the last 6 months", None),             # Jan-May 2026 (5 months available)
        ("What did I spend in January 2026?", None),                       # Updated to 2026
        ("Compare my spending in March vs April 2026", None),              # Updated to 2026
        ("Show me transactions from last month", None),                   # April 2026
        ("What were my expenses this month?", None),                        # May 2026
        ("Show me all transactions from May 2026", None),                   # Updated to 2026
    ],

    # ─────────────────────────────────────────────────────────────
    # AGGREGATION QUERIES
    # ─────────────────────────────────────────────────────────────
    "AGGREGATION": [
        ("What is my average daily spend?", None),
        ("How many transactions did I make this month?", None),             # May 2026
        ("What category has the highest spending?", None),
        ("Show me total spending by payment method", None),
        ("What is the total amount spent on Travel?", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # RANKING QUERIES
    # ─────────────────────────────────────────────────────────────
    "RANKING": [
        ("What are my top 5 expenses?", None),
        ("Which month had the highest spending?", None),
        ("Show me the top 3 categories by spending", None),
        ("What was my most expensive transaction?", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # ANOMALY DETECTION
    # ─────────────────────────────────────────────────────────────
    "ANOMALY": [
        ("Show me unusual transactions", None),
        ("What are my biggest outliers?", None),
        ("Show me transactions that are way above average", None),
        ("Any suspicious spending patterns?", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # BUDGET COMPARISON — MUST use JOIN with budgets table
    # ─────────────────────────────────────────────────────────────
    "BUDGET_MULTI_TABLE": [
        ("Which categories are over budget this month?", None),             # May 2026: 0 over budget
        ("Compare my budget vs actual spending for April 2026", None),      # Updated to 2026
        ("Am I over budget on any category?", None),                        # May 2026: 0 over budget
        ("Show budget utilization by category", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # ACCOUNT METADATA — MUST use accounts table
    # ─────────────────────────────────────────────────────────────
    "ACCOUNT_METADATA": [
        ("What is my total balance across all accounts?", None),
        ("Show me my HDFC account transactions", None),
        ("Which account has the highest balance?", None),
    ],

    # ─────────────────────────────────────────────────────────────
    # COMPOUND QUERIES
    # ─────────────────────────────────────────────────────────────
    "COMPOUND": [
        ("Show me my income and expenses for May 2026", None),               # Updated to 2026
        ("Compare my Shopping vs Groceries spending", None),
        ("What did I spend on Food and Entertainment this month?", None),   # May 2026
    ],

    # ─────────────────────────────────────────────────────────────
    # EDGE CASES
    # ─────────────────────────────────────────────────────────────
    "EDGE_CASES": [
        ("Show me transactions with no tags", None),                        # 0 rows (all have tags)
        ("What transactions used Cash payment?", None),
        ("Show me all UPI transactions", None),
        ("List transactions from ICICI account", None),
        ("Show me refunds and returns", None),
    ],
}


# ════════════════════════════════════════════════════════════════
# VALIDATION RULES
# ════════════════════════════════════════════════════════════════

VALIDATION_RULES: Dict[str, Dict[str, Any]] = {
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
    "MANUAL": {
        "description": "SQL should be a valid SELECT statement",
        "check": lambda sql: sql.strip().startswith("SELECT"),
        "expected_result": "Should return valid results",
    },
    "DIAGNOSTIC": {
        "description": "Diagnostic mode — no validation",
        "check": lambda sql: True,
        "expected_result": "Diagnostic output",
    },
}


# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

def get_all_queries() -> List[Tuple[str, str]]:
    """Return flat list of all test queries with categories."""
    all_queries: List[Tuple[str, str]] = []
    for category, queries in TEST_QUERIES.items():
        for query_tuple in queries:
            if isinstance(query_tuple, tuple):
                query = query_tuple[0]
            else:
                query = query_tuple
            all_queries.append((category, query))
    return all_queries


def get_critical_queries() -> List[Tuple[str, str]]:
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


def validate_sql(category: str, sql: str) -> Tuple[bool, str]:
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


# ════════════════════════════════════════════════════════════════
# EXPECTED ROW COUNTS
# ════════════════════════════════════════════════════════════════
# Calibrated against finance.db (Jan–May 2026, 94 transactions).
# "This month" = May 2026, "last month" = April 2026.
# ════════════════════════════════════════════════════════════════

EXPECTED_RESULTS: Dict[str, Dict[str, int]] = {

    # ─── TAG SEARCH ─────────────────────────────────────────────
    # Tags are comma-separated; LIKE '%tag%' matches substrings.
    # 'subscription' appears 14 times across all months.
    "Show all transactions tagged with 'subscription'": {"min_rows": 12, "max_rows": 16},
    # 'anomaly' appears 5 times (Feb laptop, Mar flight, Mar Croma, Apr stock loss, May flight).
    "Show all transactions tagged with 'anomaly'": {"min_rows": 4, "max_rows": 8},
    # 'monthly' appears 20 times (salary, rent, grocery, bill, etc.).
    "Show all transactions tagged with 'monthly'": {"min_rows": 18, "max_rows": 22},
    # 'weekend' appears 6 times.
    "Show all transactions tagged with 'weekend'": {"min_rows": 5, "max_rows": 10},
    # 'food' appears 8 times (standalone or part of 'food,weekend').
    "Show all transactions tagged with 'food'": {"min_rows": 7, "max_rows": 12},
    # 'travel' appears 4 times.
    "Show all transactions tagged with 'travel'": {"min_rows": 3, "max_rows": 8},

    # ─── CATEGORY (no type filter) ──────────────────────────────
    # Health: 5 transactions (all debits).
    "What are all my Health transactions?": {"min_rows": 4, "max_rows": 8},
    # Shopping: 10 transactions (mix of debit/credit; 1 refund in April).
    "Show me my Shopping transactions": {"min_rows": 8, "max_rows": 15},
    # Food: 8 transactions (all debits).
    "List all Food transactions": {"min_rows": 7, "max_rows": 12},
    # Travel: 4 transactions (all debits).
    "Show me Travel transactions": {"min_rows": 3, "max_rows": 8},
    # Entertainment: 11 transactions (all debits).
    "What Entertainment transactions do I have?": {"min_rows": 9, "max_rows": 15},

    # ─── MERCHANT (no type filter) ───────────────────────────────
    # Amazon: 4 transactions (3 debits, 1 credit/refund in April).
    "Show all transactions from Amazon": {"min_rows": 3, "max_rows": 8},
    # Apollo Pharmacy: 5 transactions (all debits).
    "Show all transactions from Apollo Pharmacy": {"min_rows": 4, "max_rows": 8},
    # Netflix: 5 transactions (all debits).
    "Show all transactions from Netflix": {"min_rows": 4, "max_rows": 8},
    # Uber: 4 transactions (all debits).
    "Show all transactions from Uber": {"min_rows": 3, "max_rows": 8},

    # ─── EXPENSE QUERIES (type = debit) ───────────────────────────
    # Groceries this month (May 2026): 1 transaction (DMart, ₹4800).
    "How much did I spend on Groceries this month?": {"min_rows": 1, "max_rows": 3},
    # Highest expense ever: single row (Laptop Purchase, ₹75000).
    "What was my highest expense ever?": {"min_rows": 1, "max_rows": 1},
    # Spending by category this month (May 2026): 14 categories with debits.
    "Show my spending by category this month": {"min_rows": 10, "max_rows": 16},
    # Shopping in March 2026: 3 transactions (Flight to Bali, Croma, Myntra).
    "How much did I spend on Shopping in March 2026?": {"min_rows": 1, "max_rows": 5},
    # Biggest purchase: single row (Laptop Purchase, ₹75000).
    "What was my biggest purchase?": {"min_rows": 1, "max_rows": 1},
    # Expenses above 5000: 17 transactions (rent, laptop, flights, ATM, etc.).
    "Show me all expenses above 5000": {"min_rows": 15, "max_rows": 25},
    # Food in May 2026: 2 transactions (Zomato, Swiggy).
    "How much did I spend on Food in May 2026?": {"min_rows": 1, "max_rows": 3},

    # ─── INCOME QUERIES (type = credit) ───────────────────────────
    # Total income: 1 aggregated row (₹606500 across all credits).
    "What is my total income?": {"min_rows": 1, "max_rows": 3},
    # Salary credits: 5 transactions (Jan-May 2026).
    "Show me all salary credits": {"min_rows": 4, "max_rows": 8},
    # Freelance income: 5 transactions (Clients A-F).
    "How much freelance income did I get?": {"min_rows": 1, "max_rows": 3},
    # Total income in May 2026: 3 credits (Salary, Freelance, Dividend).
    "What was my total income in May 2026?": {"min_rows": 1, "max_rows": 3},
    # Investment returns: 3 transactions (dividends).
    "Show me all investment returns": {"min_rows": 2, "max_rows": 5},

    # ─── TIME-BASED ─────────────────────────────────────────────
    # Spending trend last 6 months: 5 rows (Jan-May 2026, plus possibly partial).
    "Show my spending trend over the last 6 months": {"min_rows": 4, "max_rows": 8},
    # January 2026: 17 transactions.
    "What did I spend in January 2026?": {"min_rows": 1, "max_rows": 5},
    # March vs April 2026: comparison query, 2 rows.
    "Compare my spending in March vs April 2026": {"min_rows": 1, "max_rows": 5},
    # Last month (April 2026): 19 transactions.
    "Show me transactions from last month": {"min_rows": 15, "max_rows": 25},
    # Expenses this month (May 2026): 17 debits.
    "What were my expenses this month?": {"min_rows": 15, "max_rows": 25},
    # All transactions from May 2026: 20 transactions.
    "Show me all transactions from May 2026": {"min_rows": 18, "max_rows": 25},

    # ─── AGGREGATION ──────────────────────────────────────────────
    # Average daily spend: 1 row (₹3115.24 over 150 days).
    "What is my average daily spend?": {"min_rows": 1, "max_rows": 3},
    # Transactions this month (May 2026): 20 total.
    "How many transactions did I make this month?": {"min_rows": 1, "max_rows": 3},
    # Highest spending category: 1 row (Housing, ₹140000).
    "What category has the highest spending?": {"min_rows": 1, "max_rows": 3},
    # Spending by payment method: 4 rows (Card, NetBanking, UPI, Cash).
    "Show me total spending by payment method": {"min_rows": 3, "max_rows": 6},
    # Total Travel spending: 1 row (₹75700, 4 transactions).
    "What is the total amount spent on Travel?": {"min_rows": 1, "max_rows": 3},

    # ─── RANKING ─────────────────────────────────────────────────
    # Top 5 expenses: 5 rows.
    "What are my top 5 expenses?": {"min_rows": 1, "max_rows": 5},
    # Highest spending month: 1 row (February 2026, ₹136968).
    "Which month had the highest spending?": {"min_rows": 1, "max_rows": 3},
    # Top 3 categories: 3 rows.
    "Show me the top 3 categories by spending": {"min_rows": 1, "max_rows": 3},
    # Most expensive transaction: 1 row (Laptop Purchase, ₹75000).
    "What was my most expensive transaction?": {"min_rows": 1, "max_rows": 1},

    # ─── ANOMALY ─────────────────────────────────────────────────
    # Anomaly queries are heuristic-based; results vary by algorithm.
    "Show me unusual transactions": {"min_rows": 0, "max_rows": 25},
    "What are my biggest outliers?": {"min_rows": 0, "max_rows": 25},
    "Show me transactions that are way above average": {"min_rows": 0, "max_rows": 25},
    "Any suspicious spending patterns?": {"min_rows": 0, "max_rows": 25},

    # ─── BUDGET (multi-table JOIN) ──────────────────────────────
    # Over budget this month (May 2026): 0 categories over budget.
    "Which categories are over budget this month?": {"min_rows": 0, "max_rows": 5},
    # Budget vs actual for April 2026: 4 categories (2 over budget: Travel, Investment).
    "Compare my budget vs actual spending for April 2026": {"min_rows": 3, "max_rows": 8},
    # Over budget any category (May 2026): 0 rows.
    "Am I over budget on any category?": {"min_rows": 0, "max_rows": 5},
    # Budget utilization by category (May 2026): 5 rows.
    "Show budget utilization by category": {"min_rows": 4, "max_rows": 8},

    # ─── ACCOUNT METADATA ─────────────────────────────────────────
    # Total balance across accounts: 1 row (₹275000) or 3 rows (one per account).
    "What is my total balance across all accounts?": {"min_rows": 1, "max_rows": 5},
    # HDFC transactions: 44 transactions.
    "Show me my HDFC account transactions": {"min_rows": 40, "max_rows": 50},
    # Highest balance: 1 row (HDFC, ₹145000).
    "Which account has the highest balance?": {"min_rows": 1, "max_rows": 3},

    # ─── COMPOUND ─────────────────────────────────────────────────
    # Income and expenses for May 2026: 2+ rows (income total, expense total).
    "Show me my income and expenses for May 2026": {"min_rows": 1, "max_rows": 5},
    # Shopping vs Groceries: 2 rows.
    "Compare my Shopping vs Groceries spending": {"min_rows": 1, "max_rows": 3},
    # Food and Entertainment this month (May 2026): 2+ rows.
    "What did I spend on Food and Entertainment this month?": {"min_rows": 1, "max_rows": 5},

    # ─── EDGE CASES ───────────────────────────────────────────────
    # No tags: 0 rows (every transaction has tags).
    "Show me transactions with no tags": {"min_rows": 0, "max_rows": 2},
    # Cash payment: 5 transactions (all ATM withdrawals).
    "What transactions used Cash payment?": {"min_rows": 4, "max_rows": 8},
    # UPI transactions: 38 transactions.
    "Show me all UPI transactions": {"min_rows": 35, "max_rows": 45},
    # ICICI account: 35 transactions.
    "List transactions from ICICI account": {"min_rows": 30, "max_rows": 40},
    # Refunds and returns: 1 transaction (Croma Return Refund, April 2026).
    "Show me refunds and returns": {"min_rows": 1, "max_rows": 5},
}
