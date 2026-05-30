"""Test runner for ConvoQL agent validation.

Usage:
    python agent/nodes/test_runner.py --quick
    python agent/nodes/test_runner.py --full --output results.json
    python agent/nodes/test_runner.py --query "How much did I spend?"
    python agent/nodes/test_runner.py --category EXPENSE_QUERIES_DEBIT
"""
import asyncio
import json
import argparse
import sys
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

# ─── Path Setup ────────────────────────────────────────────────
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# ─── Imports (deferred to avoid import-time side effects) ──────
from langgraph.errors import GraphRecursionError

from db.connection import db_manager
from cache.schema_rag import schema_rag
from agent.graph import agent_graph
from agent.nodes.test_queries import (
    TEST_QUERIES, VALIDATION_RULES, EXPECTED_RESULTS,
    get_all_queries, get_critical_queries, validate_sql
)


# ════════════════════════════════════════════════════════════════
#  COLORS & FORMATTING
# ════════════════════════════════════════════════════════════════

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


def print_header(text: str, width: int = 78):
    line = "═" * width
    print()
    print(Colors.BOLD + Colors.BLUE + line + Colors.END)
    print(Colors.BOLD + Colors.BLUE + text.center(width) + Colors.END)
    print(Colors.BOLD + Colors.BLUE + line + Colors.END)


def print_subheader(text: str):
    print()
    print(Colors.BOLD + Colors.CYAN + "▶ " + text + Colors.END)


def print_sql(sql: str, max_len: int = 140) -> str:
    """Pretty-print SQL with syntax highlighting hints."""
    preview = sql[:max_len] + "..." if len(sql) > max_len else sql
    # Replace newlines for compact display
    preview = preview.replace("\n", " ")
    return preview


# ════════════════════════════════════════════════════════════════
#  DATABASE INITIALIZATION (lazy, not at import time)
# ════════════════════════════════════════════════════════════════

_db_initialized = False


async def _ensure_db_initialized():
    """Initialize DB and SchemaRAG once per test run."""
    global _db_initialized
    if _db_initialized:
        return

    await db_manager.initialize()
    schema = await db_manager.get_schema()
    schema_rag.embed_schema(schema)
    stats = schema_rag.get_stats()

    print(Colors.DIM + f"[Init] DB ready: {db_manager.dialect}" + Colors.END)
    print(Colors.DIM + f"[Init] SchemaRAG: {stats['tables_indexed']} tables, {stats['columns_indexed']} columns" + Colors.END)

    # Show tables
    tables = schema.get("tables", [])
    if tables:
        table_names = [t["name"] for t in tables]
        print(Colors.DIM + f"[Init] Tables: {', '.join(table_names)}" + Colors.END)

    _db_initialized = True


# ════════════════════════════════════════════════════════════════
#  STATE BUILDER (fixes TypedDict initialization bug)
# ════════════════════════════════════════════════════════════════

def build_initial_state(question: str, dialect: str = "sqlite") -> Dict[str, Any]:
    """Build a clean initial state dict for AgentState (MessagesState/TypedDict).

    CRITICAL: AgentState extends MessagesState which is a TypedDict.
    TypedDict instances MUST be initialized as plain dicts, NOT as class constructors.
    The old code did `AgentState(question=query, dialect=dialect)` which is WRONG
    for TypedDict and causes silent state corruption.
    """
    return {
        "question": question,
        "dialect": dialect,
        "messages": [{"role": "user", "content": question}],
        # Initialize all state fields to prevent KeyError in nodes
        "intent": None,
        "decomposition": None,
        "schema_context": "",
        "structured_plan": None,
        "few_shot_examples": "",
        "entity_links": None,
        "generated_sql": "",
        "valid": None,
        "error": None,
        "error_classification": None,
        "retry_count": 0,
        "retry_hint": None,
        "result_set_valid": None,
        "result_set_issue": None,
        "sql_result": None,
        "result": None,
        "answer": "",
        "explanation": "",
        "has_chart": False,
        "chart_type": None,
        "chart_title": None,
        "has_table": False,
        "insight": None,
        "follow_ups": [],
        "anomaly": None,
        "trend_analysis": None,
        "narrative": None,
        "execution_time_ms": 0,
        "row_count": 0,
    }


# ════════════════════════════════════════════════════════════════
#  SINGLE TEST RUNNER
# ════════════════════════════════════════════════════════════════

async def run_single_test(category: str, query: str, dialect: str = "sqlite") -> Dict[str, Any]:
    """Run a single test query through the agent graph.

    Returns a dict with full test results including:
    - category, query, sql, passed, message, row_count, duration
    - error details, execution trace, and raw state for debugging
    """
    start = time.perf_counter()

    result = {
        "category": category,
        "query": query,
        "sql": "",
        "passed": False,
        "message": "",
        "row_count": 0,
        "duration": 0.0,
        "error": None,
        "trace": [],
        "raw_state": None,
    }

    try:
        # Build clean initial state (TypedDict as dict)
        initial_state = build_initial_state(query, dialect)

        # Invoke graph with proper config
        config = {"recursion_limit": 50}
        final_state = await agent_graph.ainvoke(initial_state, config=config)

        # Extract results
        sql = final_state.get("generated_sql", "")
        sql_result = final_state.get("sql_result")
        error = final_state.get("error")
        retry_count = final_state.get("retry_count", 0)
        valid = final_state.get("valid")
        result_set_valid = final_state.get("result_set_valid")
        result_set_issue = final_state.get("result_set_issue")

        row_count = 0
        if sql_result and isinstance(sql_result, dict):
            row_count = len(sql_result.get("rows", []))

        duration = time.perf_counter() - start

        # Build execution trace for debugging
        trace = []
        trace.append(f"valid={valid}")
        trace.append(f"retry_count={retry_count}")
        trace.append(f"result_set_valid={result_set_valid}")
        if result_set_issue:
            trace.append(f"result_set_issue={result_set_issue}")
        if error:
            trace.append(f"error={error[:100]}")

        # ─── SQL Validation ─────────────────────────────────────
        passed, message = validate_sql(category, sql)

        # ─── Row Count Validation ─────────────────────────────────
        expected = EXPECTED_RESULTS.get(query)
        if expected and passed:
            if row_count < expected["min_rows"]:
                passed = False
                message += f" | Too few rows: {row_count} (expected >= {expected['min_rows']})"
            elif row_count > expected["max_rows"]:
                passed = False
                message += f" | Too many rows: {row_count} (expected <= {expected['max_rows']})"

        # ─── Error Check ──────────────────────────────────────────
        if error and not passed:
            message += f" | Execution error: {error[:200]}"

        # ─── SQL Execution Check ──────────────────────────────────
        # If SQL looks correct but returned 0 rows, flag as suspicious
        if passed and row_count == 0 and expected and expected.get("min_rows", 0) > 0:
            passed = False
            message += f" | WARNING: SQL passed validation but returned 0 rows (expected >= {expected['min_rows']}). Database may not contain matching data."

        result.update({
            "sql": sql,
            "passed": passed,
            "message": message,
            "row_count": row_count,
            "duration": duration,
            "error": error,
            "trace": trace,
            "raw_state": {k: v for k, v in final_state.items() if k not in ("messages",)},
        })

    except GraphRecursionError as e:
        duration = time.perf_counter() - start
        result.update({
            "passed": False,
            "message": f"GraphRecursionError: {str(e)} — retry loop may be infinite",
            "duration": duration,
            "error": str(e),
            "trace": ["GraphRecursionError caught"],
        })

    except Exception as e:
        duration = time.perf_counter() - start
        import traceback
        tb = traceback.format_exc()
        result.update({
            "passed": False,
            "message": f"Test runner exception: {type(e).__name__}: {str(e)}",
            "duration": duration,
            "error": str(e),
            "trace": tb.split("\n")[-5:],  # Last 5 lines of traceback
        })

    return result


# ════════════════════════════════════════════════════════════════
#  BATCH TEST RUNNER
# ════════════════════════════════════════════════════════════════

async def run_tests(tests: List[Tuple[str, str]], dialect: str = "sqlite") -> List[Dict[str, Any]]:
    """Run all tests sequentially and collect results."""
    results = []

    for idx, (category, query) in enumerate(tests, 1):
        print_subheader(f"[{idx}/{len(tests)}] {category}")
        print(f"  Query: {query}")

        result = await run_single_test(category, query, dialect)
        results.append(result)

        # Print result
        status_color = Colors.GREEN if result["passed"] else Colors.RED
        status_text = "PASS" if result["passed"] else "FAIL"
        print(f"  Status: {status_color}{status_text}{Colors.END}")

        if result["sql"]:
            sql_preview = print_sql(result["sql"])
            print(f"  SQL:    {Colors.CYAN}{sql_preview}{Colors.END}")

        print(f"  Rows:   {result['row_count']}")
        print(f"  Time:   {result['duration']:.2f}s")

        if result["trace"]:
            print(f"  Trace:  {Colors.DIM}{' | '.join(result['trace'])}{Colors.END}")

        if not result["passed"]:
            print(f"  {Colors.YELLOW}Details: {result['message']}{Colors.END}")

        if result["error"] and not result["passed"]:
            err_preview = result["error"][:200]
            print(f"  {Colors.RED}Error:   {err_preview}{Colors.END}")

    return results


# ════════════════════════════════════════════════════════════════
#  REPORTING
# ════════════════════════════════════════════════════════════════

def print_summary(results: List[Dict[str, Any]]):
    """Print comprehensive test summary."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print_header("TEST SUMMARY")

    # Overall stats
    print()
    print(Colors.BOLD + f"Total Tests: {total}" + Colors.END)
    print(Colors.GREEN + f"  Passed:  {passed}" + Colors.END)
    print(Colors.RED + f"  Failed:  {failed}" + Colors.END)
    if total > 0:
        rate = passed / total * 100
        rate_color = Colors.GREEN if rate >= 80 else Colors.YELLOW if rate >= 50 else Colors.RED
        print(rate_color + Colors.BOLD + f"  Success Rate: {rate:.1f}%" + Colors.END)

    # Failed tests detail
    if failed > 0:
        print()
        print(Colors.RED + Colors.BOLD + "Failed Tests:" + Colors.END)
        for r in results:
            if not r["passed"]:
                print(f"  [{Colors.RED}{r['category']}{Colors.END}] {r['query']}")
                if r["sql"]:
                    sql_short = r["sql"][:80] + "..." if len(r["sql"]) > 80 else r["sql"]
                    print(f"     SQL: {Colors.CYAN}{sql_short}{Colors.END}")
                print(f"     {Colors.YELLOW}{r['message']}{Colors.END}")

    # Category breakdown
    print()
    print(Colors.BOLD + "By Category:" + Colors.END)
    categories: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1

    for cat, stats in sorted(categories.items()):
        if stats["passed"] == stats["total"]:
            status = Colors.GREEN
            icon = "✓"
        else:
            status = Colors.RED
            icon = "✗"
        print(f"  {status}{icon} {cat}: {stats['passed']}/{stats['total']}{Colors.END}")

    # Timing
    total_time = sum(r["duration"] for r in results)
    avg_time = total_time / total if total > 0 else 0
    max_time = max((r["duration"] for r in results), default=0)
    print()
    print(Colors.DIM + f"Total time: {total_time:.1f}s | Avg: {avg_time:.2f}s | Max: {max_time:.2f}s" + Colors.END)


def save_results(results: List[Dict[str, Any]], filename: str):
    """Save results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "dialect": db_manager.dialect if db_manager.dialect else "unknown",
        "results": results,
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print()
    print(Colors.GREEN + f"Results saved to {filename}" + Colors.END)


# ════════════════════════════════════════════════════════════════
#  DIAGNOSTIC TOOLS
# ════════════════════════════════════════════════════════════════

async def run_diagnostic(query: str, dialect: str = "sqlite"):
    """Run a single query with full diagnostic output for debugging."""
    print_header("DIAGNOSTIC MODE")
    print(f"Query: {query}")
    print(f"Dialect: {dialect}")
    print()

    await _ensure_db_initialized()

    result = await run_single_test("DIAGNOSTIC", query, dialect)

    print()
    print(Colors.BOLD + "Generated SQL:" + Colors.END)
    print(Colors.CYAN + result["sql"] + Colors.END)

    print()
    print(Colors.BOLD + "Execution Trace:" + Colors.END)
    for line in result["trace"]:
        print(f"  {line}")

    if result["raw_state"]:
        print()
        print(Colors.BOLD + "Key State Fields:" + Colors.END)
        raw = result["raw_state"]
        for key in ["intent", "valid", "error", "retry_count", "result_set_valid", "row_count"]:
            if key in raw:
                print(f"  {key}: {raw[key]}")

    print()
    print(Colors.BOLD + "Result:" + Colors.END)
    print(f"  Passed: {result['passed']}")
    print(f"  Rows: {result['row_count']}")
    print(f"  Message: {result['message']}")

    if result["error"]:
        print()
        print(Colors.RED + f"Error: {result['error']}" + Colors.END)

    return result


# ════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(
        description="Test ConvoQL agent — validates SQL generation and execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py --quick                    # Run 8 critical tests
  python test_runner.py --full --output results.json # Run all tests, save to JSON
  python test_runner.py --query "How much did I spend?"
  python test_runner.py --category TAG_SEARCH_NO_TYPE_FILTER
  python test_runner.py --diagnostic "Show all transactions tagged with 'subscription'"
        """
    )
    parser.add_argument("--quick", action="store_true", help="Run 8 critical tests")
    parser.add_argument("--full", action="store_true", help="Run all 61 tests")
    parser.add_argument("--category", type=str, help="Test specific category")
    parser.add_argument("--query", type=str, help="Test single query")
    parser.add_argument("--diagnostic", type=str, help="Run single query with full diagnostics")
    parser.add_argument("--dialect", type=str, default="sqlite", help="Database dialect (sqlite/mysql/postgresql)")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--no-init", action="store_true", help="Skip DB init (assume already initialized)")

    args = parser.parse_args()

    # ─── Determine test set ───────────────────────────────────
    if args.diagnostic:
        await _ensure_db_initialized()
        await run_diagnostic(args.diagnostic, args.dialect)
        return

    if args.query:
        tests = [("MANUAL", args.query)]
    elif args.category:
        if args.category not in TEST_QUERIES:
            print(Colors.RED + f"Unknown category: {args.category}" + Colors.END)
            print("Available categories:")
            for cat in sorted(TEST_QUERIES.keys()):
                print(f"  - {cat}")
            sys.exit(1)
        tests = []
        for q in TEST_QUERIES[args.category]:
            if isinstance(q, tuple):
                tests.append((args.category, q[0]))
            else:
                tests.append((args.category, q))
    elif args.full:
        tests = get_all_queries()
    else:
        tests = get_critical_queries()

    # ─── Initialize DB ──────────────────────────────────────────
    if not args.no_init:
        await _ensure_db_initialized()

    # ─── Run tests ──────────────────────────────────────────────
    print_header(f"CONVOQL TEST RUNNER — {len(tests)} QUERIES")
    print(f"Dialect:    {args.dialect}")
    print(f"Database:   {db_manager.dialect if db_manager.dialect else 'not initialized'}")
    print(f"Time:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = await run_tests(tests, args.dialect)
    print_summary(results)

    # ─── Save results ───────────────────────────────────────────
    if args.output:
        save_results(results, args.output)

    # ─── Exit code ──────────────────────────────────────────────
    failed = sum(1 for r in results if not r["passed"])
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
    