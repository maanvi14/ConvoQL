"""Typed error classifier: Categorizes SQL errors for targeted retry."""
from typing import Dict, Any

ERROR_PATTERNS = {
    "no_such_column": [
        "no such column",
        "unknown column",
        "column not found",
    ],
    "no_such_table": [
        "no such table",
        "unknown table",
        "table not found",
    ],
    "syntax_error": [
        "syntax error",
        "near",
        "unexpected",
    ],
    "type_mismatch": [
        "datatype mismatch",
        "type mismatch",
        "cannot convert",
    ],
    "ambiguous_column": [
        "ambiguous column",
        "ambiguous",
    ],
    "constraint_violation": [
        "constraint failed",
        "foreign key",
        "not null",
    ],
    "empty_result": [
        "returned 0 rows",
        "no results",
    ],
    "logic_error": [
        "logic error",
    ],
}

def classify_error(error_msg: str) -> Dict[str, Any]:
    """Classify SQL error into typed category."""
    error_lower = error_msg.lower()

    for error_type, patterns in ERROR_PATTERNS.items():
        for pattern in patterns:
            if pattern in error_lower:
                return {
                    "type": error_type,
                    "message": error_msg,
                    "retry_hint": get_retry_hint(error_type),
                }

    return {
        "type": "unknown",
        "message": error_msg,
        "retry_hint": "Check SQL syntax and table/column names.",
    }

def get_retry_hint(error_type: str) -> str:
    """Get specific retry hint based on error type."""
    hints = {
        "no_such_column": "The column name is wrong. Check the schema for correct column names. Use only columns that exist in the specified tables.",
        "no_such_table": "The table name is wrong. Check available tables in the schema.",
        "syntax_error": "SQLite syntax error. Check for missing commas, wrong keywords, or unclosed parentheses.",
        "type_mismatch": "Data type mismatch. Ensure comparisons use compatible types. Use strftime() for dates and ABS() for amounts.",
        "ambiguous_column": "Column name exists in multiple tables. Use table_alias.column_name format.",
        "constraint_violation": "Database constraint violated. This should not happen for SELECT queries.",
        "empty_result": "Query returned no rows. Check if filters are too restrictive or date range has no data.",
        "logic_error": "Query logic may be wrong. Check JOIN conditions and WHERE clauses.",
    }
    return hints.get(error_type, "Review and fix the SQL query.")

async def typed_error_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Classify error from validator for targeted retry.

    This is the ONLY place retry_count is mutated. Router functions must remain pure.
    """
    # Increment retry count HERE — routers must not mutate state
    state["retry_count"] = state.get("retry_count", 0) + 1
    print(f"[typed_error_classifier] retry_count = {state['retry_count']}/3")

    error_msg = state.get("error", "")

    if not error_msg:
        return {
            **state,
            "error_classification": None,
        }

    classification = classify_error(error_msg)

    return {
        **state,
        "error_classification": classification,
        "retry_hint": classification["retry_hint"],
    }
