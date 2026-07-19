"""Sub-query executor: Runs each decomposed sub-question through the SQL
generation pipeline and merges the results.

Wires up query_decomposer_node's output. Previously `state["decomposition"]`
was computed (is_compound, sub_queries, merge_strategy) but nothing in the
graph ever consumed it — every question, compound or not, was sent through
the pipeline as a single query, so "compare my HDFC spending vs ICICI
spending" or "show my food spending and my travel spending" silently ran as
one (usually wrong) query instead of two merged ones.

Each sub-question gets its own pass through the same deterministic pipeline
used for a standalone question: intent -> few-shot examples -> structured
plan -> column linking -> SQL skeleton -> validation -> execution, with a
small retry budget (kept intentionally short since this runs once per
sub-query, and a compound question with N sub-queries already costs ~N times
the LLM calls of a single question).
"""
from typing import Dict, Any, List

from agent.nodes.intent_classifier import intent_classifier_node
from agent.nodes.dynamic_few_shot import dynamic_few_shot_node
from agent.nodes.structured_planner import structured_planner_node
from agent.nodes.column_linker import column_linker_node
from agent.nodes.sql_skeleton import sql_skeleton_node
from agent.nodes.validator import validator_node
from db.connection import db_manager

# Kept deliberately small: this loop runs once per sub-query, on top of the
# already-multiplied cost of decomposing a compound question.
MAX_SUB_QUERY_ATTEMPTS = 2


async def _run_single_query_pipeline(question: str, dialect: str) -> Dict[str, Any]:
    """Run one sub-question through the standalone-question pipeline and
    execute the resulting SQL. Returns the question, SQL, result (or None),
    and error (or None)."""
    sub_state: Dict[str, Any] = {"question": question, "dialect": dialect, "retry_count": 0}

    sub_state = await intent_classifier_node(sub_state)
    sub_state = await dynamic_few_shot_node(sub_state)

    sql = None
    result = None
    error = None

    for attempt in range(MAX_SUB_QUERY_ATTEMPTS):
        sub_state = await structured_planner_node(sub_state)
        sub_state = await column_linker_node(sub_state)
        sub_state = await sql_skeleton_node(sub_state)
        sub_state = await validator_node(sub_state)

        sql = sub_state.get("generated_sql")

        if sub_state.get("valid"):
            try:
                result = await db_manager.execute_readonly(sql)
                error = None
                break
            except Exception as e:
                error = str(e)
        else:
            error = sub_state.get("error")

        # Feed the failure back in so the next attempt's structured_planner
        # call sees retry_context, same as the main single-query retry loop.
        sub_state["retry_count"] = attempt + 1
        sub_state["error"] = error
        sub_state["retry_hint"] = sub_state.get("retry_hint") or "Re-check the plan against the schema and rules."

    return {
        "question": question,
        "sql": sql,
        "result": result,
        "error": error if result is None else None,
    }


def _merge_sub_results(sub_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine per-sub-query results into a single result set shaped the way
    the rest of the pipeline (enhanced_synthesizer / trend_analyzer /
    narrative_generator) already expects, tagging each row with which
    sub-question it came from so the synthesizer can group its answer."""
    combined_rows: List[Dict[str, Any]] = []
    columns: List[str] = []
    sql_lines = []
    errors = []

    for sq in sub_results:
        sql_lines.append(f"-- {sq['question']}\n{sq['sql'] or '-- generation failed'}")
        if sq.get("error"):
            errors.append(f"[{sq['question']}] {sq['error']}")
            continue

        result = sq.get("result") or {}
        rows = result.get("rows", [])
        for row in rows:
            combined_rows.append({"sub_query": sq["question"], **row})
        for c in result.get("columns", []):
            if c not in columns:
                columns.append(c)

    display_columns = (["sub_query"] if combined_rows else []) + columns

    merged_sql_result = {
        "rows": combined_rows,
        "columns": display_columns,
        "executionTime": 0,
    }

    return {
        "sql_result": merged_sql_result,
        "generated_sql_display": "\n\n".join(sql_lines),
        "error": " | ".join(errors) if errors and not combined_rows else None,
    }


async def sub_query_executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute each sub-query from the decomposition and merge results into
    the shape enhanced_synthesizer_node expects, then hand off directly to
    synthesis (skipping the single-query validator retry loop, since each
    sub-query already went through its own validate/execute cycle)."""
    decomposition = state.get("decomposition", {}) or {}
    sub_queries = decomposition.get("sub_queries", [])
    merge_strategy = decomposition.get("merge_strategy") or "side_by_side"
    dialect = state.get("dialect", "sqlite")

    if not sub_queries:
        return {**state, "sub_query_results": [], "decomposition_executed": False}

    sub_results: List[Dict[str, Any]] = []
    for sq in sub_queries:
        sq_question = sq.get("question") or state["question"]
        try:
            outcome = await _run_single_query_pipeline(sq_question, dialect)
        except Exception as e:
            outcome = {"question": sq_question, "sql": None, "result": None, "error": str(e)}
        sub_results.append(outcome)

    merged = _merge_sub_results(sub_results)

    return {
        **state,
        "sub_query_results": sub_results,
        "decomposition_executed": True,
        "merge_strategy": merge_strategy,
        "sql_result": merged["sql_result"],
        "generated_sql": merged["generated_sql_display"],
        "error": merged["error"],
        "valid": merged["error"] is None,
    }
