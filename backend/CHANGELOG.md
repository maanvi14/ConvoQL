# Changelog - ConvoQL Reliable NL-to-SQL Fixes

All notable changes and fixes applied during this session are documented below.

## [2026-07-19] - Core Reliability Update

### Bug 1: Validator qualified-column false positives
- **Symptom**: Valid JOIN queries failed validation with `Schema error: Column 'transactions' does not exist in table(s) ['transactions']`.
- **Root Cause**: The regex `(?<![\w.])\b(\w+)\b` matched `'transactions'` from `'transactions.category'` because it only used a negative lookbehind.
- **Fix**: Added negative lookahead `(?!\.)` to all bare-column extraction regexes so the table prefix part of `table.column` is skipped, and filtered out matches that are known table names.
- **Files modified**: `backend/agent/nodes/validator.py`

### Bug 2: Column Linker year-as-amount extraction
- **Symptom**: Under-budget / monthly query responses returned 0 rows because `AND amount = '2026'` was injected into WHERE clauses.
- **Root Cause**: The regex for amounts captured `2026` from `"May 2026"` and passed it through because `2026 >= 100`.
- **Fix**: Checked if the amount match is a bare 4-digit number in the year-range (1900-2099) without any explicit currency marker (`₹`, `Rs`, `INR`) and skipped it.
- **Files modified**: `backend/agent/nodes/column_linker.py`

### Bug 3: Duplicate and Contradictory Date Filters
- **Symptom**: Specific-month queries (e.g., "What did I spend in January 2026?") returned 0 rows due to contradictory filters (e.g. `strftime('%Y-%m', date) = strftime('%Y-%m', 'now') AND strftime('%Y-%m', date) = '2026-01'`).
- **Root Cause**: `sql_skeleton.py` appended specific `linked_dates` filters alongside generic planner filters, and silently ignored `month_year`/`year_month` types.
- **Fix**: 
  1. Handled the previously dropped `month_year` and `year_month` filters.
  2. Substituted generic `strftime('%Y-%m', 'now')` filters when a specific month query is matched.
  3. Added a semantic deduplication step that normalizes table-prefixes (e.g. `transactions.date` to `date`) before comparing.
- **Files modified**: `backend/agent/nodes/sql_skeleton.py`

### Bug 4: SQLite GROUP BY syntax error
- **Symptom**: Group-by queries returned `sqlite3.OperationalError: near "AS": syntax error`.
- **Root Cause**: The LLM planner generated plans with `group_by: ["strftime('%Y-%m', date) AS month"]`, which is invalid syntax in SQLite and standard SQL.
- **Fix**: Cleaned the group-by plan elements in both the planner and the final skeleton builder by stripping any trailing `AS alias` clause using regex.
- **Files modified**: `backend/agent/nodes/structured_planner.py`, `backend/agent/nodes/sql_skeleton.py`

### Bug 5: Budget JOIN row-multiplication (missing month alignment)
- **Symptom**: "Compare my budget VS actual spending for May" returned multiplied actual totals (e.g., Travel spending shown as ₹42,000 instead of ₹14,000) and hallucinated extra categories (e.g., Entertainment).
- **Root Cause**: The `ON` clause joined `transactions` and `budgets` on category only (`transactions.category = budgets.category`), resulting in a Cartesian product across all budgeted months.
- **Fix**: 
  1. Implemented structural checks that automatically append `budgets.month_year` to `transactions.date` alignment in the join condition.
  2. Pruned raw unaggregated columns (date, description, amount, type) from SELECT clauses in grouped budget comparison queries.
- **Files modified**: `backend/agent/nodes/sql_skeleton.py`

### Bug 6: Synthesizer multi-row aggregate narration error
- **Symptom**: Narrative summaries stated a single category's value as the overall total (e.g., "You spent a total of ₹42,000 in May..." which was Travel's incorrect spending).
- **Root Cause**: `SYNTHESIZER_PROMPT` had no rules telling the LLM to summarize category breakdowns instead of presenting a single row's values as the overall total.
- **Fix**: Added explicit prompt instructions to `SYNTHESIZER_PROMPT` enforcing proper multi-row breakdown summaries.
- **Files modified**: `backend/agent/nodes/enhanced_synthesizer.py`

---

## Secondary Improvements
- **`ACCOUNT_METADATA` Hallucination**: Added `accounts.account -> accounts.account_name` table-scoped alias correction.
- **Dead Code documentation**: Added a comprehensive note to `generator.py` documenting it as dead/unreachable code.
- **Offline verification tests**: Created `test_fixes.py` containing 5 comprehensive unit tests (20+ assertions) covering all bug fixes without making any LLM calls.
