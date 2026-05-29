"""Test runner for ConvoQL agent validation.

Usage:
    python agent/nodes/test_runner.py --quick
    python agent/nodes/test_runner.py --full --output results.json
"""
import asyncio
import json
import argparse
import sys
import os
from datetime import datetime

# Auto-detect project root
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.connection import db_manager
from cache.schema_rag import schema_rag

# === CRITICAL: Initialize DB BEFORE importing graph nodes ===
async def _pre_init():
    await db_manager.initialize()
    schema = await db_manager.get_schema()
    schema_rag.embed_schema(schema)
    stats = schema_rag.get_stats()
    print(f"[Init] DB ready: {db_manager.dialect}, SchemaRAG: {stats['tables_indexed']} tables")

# Run init in a temporary event loop (closed immediately after)
asyncio.run(_pre_init())

# NOW safe to import graph (db_manager.engine is set)
from agent.state import AgentState
from agent.graph import agent_graph
from agent.nodes.test_queries import (
    TEST_QUERIES, VALIDATION_RULES, EXPECTED_RESULTS,
    get_all_queries, get_critical_queries, validate_sql
)


class Colors:
    GREEN = "[92m"
    RED = "[91m"
    YELLOW = "[93m"
    BLUE = "[94m"
    CYAN = "[96m"
    BOLD = "[1m"
    END = "[0m"


def print_header(text):
    line = "=" * 70
    print()
    print(Colors.BOLD + Colors.BLUE + line + Colors.END)
    print(Colors.BOLD + Colors.BLUE + text.center(70) + Colors.END)
    print(Colors.BOLD + Colors.BLUE + line + Colors.END)


def print_result(category, query, sql, passed, message, row_count=None, duration=None):
    if passed:
        status = Colors.GREEN + "PASS" + Colors.END
    else:
        status = Colors.RED + "FAIL" + Colors.END

    print()
    print(Colors.BOLD + "[" + category + "]" + Colors.END)
    print("  Query: " + query)
    sql_preview = sql[:120] + "..." if len(sql) > 120 else sql
    print("  SQL:   " + Colors.CYAN + sql_preview + Colors.END)
    print("  Result: " + status)
    if row_count is not None:
        print("  Rows:   " + str(row_count))
    if duration:
        print("  Time:   " + str(round(duration, 2)) + "s")
    if not passed:
        print("  " + Colors.YELLOW + "Details: " + message + Colors.END)


async def run_test(category, query, dialect="sqlite"):
    import time
    start = time.time()

    try:
        state = AgentState(
            question=query,
            dialect=dialect,
        )

        result = await agent_graph.ainvoke(state)

        sql = result.get("generated_sql", "")
        sql_result = result.get("sql_result", {})
        row_count = len(sql_result.get("rows", [])) if sql_result else 0
        error = result.get("error")

        duration = time.time() - start

        passed, message = validate_sql(category, sql)

        expected = EXPECTED_RESULTS.get(query)
        if expected and passed:
            if row_count < expected["min_rows"]:
                passed = False
                msg_parts = [
                    message,
                    "Too few rows: " + str(row_count),
                    "expected >= " + str(expected["min_rows"])
                ]
                message = " | ".join(msg_parts)
            elif row_count > expected["max_rows"]:
                passed = False
                msg_parts = [
                    message,
                    "Too many rows: " + str(row_count),
                    "expected <= " + str(expected["max_rows"])
                ]
                message = " | ".join(msg_parts)

        if error:
            passed = False
            message = "Execution error: " + str(error)

        return {
            "category": category,
            "query": query,
            "sql": sql,
            "passed": passed,
            "message": message,
            "row_count": row_count,
            "duration": duration,
            "error": error,
        }

    except Exception as e:
        return {
            "category": category,
            "query": query,
            "sql": "",
            "passed": False,
            "message": "Test runner error: " + str(e),
            "row_count": 0,
            "duration": time.time() - start,
            "error": str(e),
        }


async def run_tests(tests, dialect="sqlite"):
    results = []

    for category, query in tests:
        result = await run_test(category, query, dialect)
        results.append(result)

        print_result(
            result["category"],
            result["query"],
            result["sql"],
            result["passed"],
            result["message"],
            result["row_count"],
            result["duration"],
        )

    return results


def print_summary(results):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print_header("TEST SUMMARY")

    print()
    print(Colors.BOLD + "Total Tests: " + str(total) + Colors.END)
    print(Colors.GREEN + "Passed: " + str(passed) + Colors.END)
    print(Colors.RED + "Failed: " + str(failed) + Colors.END)
    print(Colors.BOLD + "Success Rate: " + str(round(passed/total*100, 1)) + "%" + Colors.END)

    if failed > 0:
        print()
        print(Colors.RED + Colors.BOLD + "Failed Tests:" + Colors.END)
        for r in results:
            if not r["passed"]:
                print("  [" + r["category"] + "] " + r["query"])
                print("     SQL: " + r["sql"][:100] + "...")
                print("     Error: " + r["message"])

    print()
    print(Colors.BOLD + "By Category:" + Colors.END)
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1

    for cat, stats in categories.items():
        if stats["passed"] == stats["total"]:
            status = Colors.GREEN
        else:
            status = Colors.RED
        print("  " + status + cat + ": " + str(stats["passed"]) + "/" + str(stats["total"]) + Colors.END)


def save_results(results, filename):
    output = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "results": results,
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print()
    print(Colors.GREEN + "Results saved to " + filename + Colors.END)


async def main():
    parser = argparse.ArgumentParser(description="Test ConvoQL agent")
    parser.add_argument("--quick", action="store_true", help="Run 8 critical tests")
    parser.add_argument("--full", action="store_true", help="Run all 61 tests")
    parser.add_argument("--category", type=str, help="Test specific category")
    parser.add_argument("--query", type=str, help="Test single query")
    parser.add_argument("--dialect", type=str, default="sqlite", help="Database dialect")
    parser.add_argument("--output", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    if args.query:
        tests = [("MANUAL", args.query)]
    elif args.category:
        if args.category not in TEST_QUERIES:
            print(Colors.RED + "Unknown category: " + args.category + Colors.END)
            print("Available: " + str(list(TEST_QUERIES.keys())))
            return
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

    print_header("CONVOQL TEST RUNNER - " + str(len(tests)) + " QUERIES")
    print("Dialect: " + args.dialect)
    print("Time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    results = await run_tests(tests, args.dialect)
    print_summary(results)

    if args.output:
        save_results(results, args.output)

    failed = sum(1 for r in results if not r["passed"])
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
    