"""LangGraph definition for ConvoQL with proper retry loop wiring."""
from langgraph.graph import StateGraph, END
from typing import Dict, Any

from agent.state import AgentState
from agent.nodes.intent_classifier import intent_classifier_node
from agent.nodes.query_decomposer import query_decomposer_node
from agent.nodes.sub_query_executor import sub_query_executor_node
from agent.nodes.structured_planner import structured_planner_node
from agent.nodes.dynamic_few_shot import dynamic_few_shot_node
from agent.nodes.column_linker import column_linker_node
from agent.nodes.sql_skeleton import sql_skeleton_node
from agent.nodes.generator import generator_node
from agent.nodes.validator import validator_node
from agent.nodes.typed_error_classifier import typed_error_classifier_node
from agent.nodes.result_set_validator import result_set_validator_node
from agent.nodes.enhanced_synthesizer import enhanced_synthesizer_node
from agent.nodes.trend_analyzer import trend_analyzer_node
from agent.nodes.narrative_generator import narrative_generator_node
from db.connection import db_manager
from cache.schema_rag import schema_rag

# Build graph
workflow = StateGraph(AgentState)

# Layer 1: Query Understanding
workflow.add_node("intent_classifier", intent_classifier_node)
workflow.add_node("query_decomposer", query_decomposer_node)
workflow.add_node("sub_query_executor", sub_query_executor_node)

# Layer 2: Schema Retrieval
workflow.add_node("structured_planner", structured_planner_node)
workflow.add_node("dynamic_few_shot", dynamic_few_shot_node)

# Layer 3: Generation
workflow.add_node("column_linker", column_linker_node)
workflow.add_node("sql_skeleton", sql_skeleton_node)
workflow.add_node("generator", generator_node)

# Layer 4: Validation
workflow.add_node("validator", validator_node)
workflow.add_node("typed_error_classifier", typed_error_classifier_node)
workflow.add_node("result_set_validator", result_set_validator_node)

# Layer 5: Output
workflow.add_node("enhanced_synthesizer", enhanced_synthesizer_node)
workflow.add_node("trend_analyzer", trend_analyzer_node)
workflow.add_node("narrative_generator", narrative_generator_node)

# Entry point
workflow.set_entry_point("intent_classifier")

# Layer 1 -> Layer 2
workflow.add_edge("intent_classifier", "query_decomposer")

# === CONDITIONAL: Decomposition -> sub-query pipeline or single-query pipeline ===
# BUG FIX: query_decomposer_node's output (state["decomposition"]) used to be
# computed and then never read by anything — every question, compound or not,
# fell through to the single-query pipeline below, so "compare my HDFC
# spending vs ICICI spending" silently ran as one (usually wrong) query.
# Compound questions now route to sub_query_executor_node, which runs each
# sub-question through its own copy of the pipeline and merges the results.
def route_after_decomposition(state: AgentState) -> str:
    """Route after decomposition: compound -> sub_query_executor, else -> single-query pipeline."""
    decomposition = state.get("decomposition", {}) or {}
    is_compound = decomposition.get("is_compound", False)
    sub_queries = decomposition.get("sub_queries", [])

    print(f"[Router] is_compound={is_compound}, sub_queries={len(sub_queries)}")

    if is_compound and sub_queries:
        return "sub_query_executor"

    return "dynamic_few_shot"

workflow.add_conditional_edges(
    "query_decomposer",
    route_after_decomposition,
    {
        "sub_query_executor": "sub_query_executor",
        "dynamic_few_shot": "dynamic_few_shot",
    }
)

# sub_query_executor already validated and executed each sub-query itself,
# so it skips straight to synthesis rather than the single-query validator loop.
workflow.add_edge("sub_query_executor", "enhanced_synthesizer")

# BUG FIX: dynamic_few_shot_node reads state["intent"] (set by intent_classifier,
# available since the very first node) and writes state["few_shot_examples"].
# structured_planner_node reads state["few_shot_examples"] into its prompt.
# The old order (structured_planner -> dynamic_few_shot) ran the planner BEFORE
# the examples existed, so few_shot_context was always empty on the first pass
# — the selected examples only became visible on a retry, one full attempt late.
# dynamic_few_shot only depends on intent, not on decomposition/schema, so it's
# safe to run it right after query_decomposer and before structured_planner.
workflow.add_edge("dynamic_few_shot", "structured_planner")

# Layer 2 -> Layer 3
workflow.add_edge("structured_planner", "column_linker")
workflow.add_edge("column_linker", "sql_skeleton")

# Layer 3 -> Layer 4 (Validator)
workflow.add_edge("sql_skeleton", "validator")

# === CONDITIONAL: Validator -> Retry or Continue ===
def route_after_validator(state: AgentState) -> str:
    """Route after validator: valid -> result_set_validator, invalid -> typed_error_classifier."""
    is_valid = state.get("valid", False)
    retry_count = state.get("retry_count", 0)

    print(f"[Router] valid={is_valid}, retry_count={retry_count}")

    if is_valid is True:
        return "result_set_validator"

    return "typed_error_classifier"

workflow.add_conditional_edges(
    "validator",
    route_after_validator,
    {
        "typed_error_classifier": "typed_error_classifier",
        "result_set_validator": "result_set_validator",
    }
)

# === CONDITIONAL: Error Classification -> Retry or Give Up ===
def route_after_error_classification(state: AgentState) -> str:
    """Route after error classification: under limit -> retry, max reached -> synthesizer."""
    retry_count = state.get("retry_count", 0)
    print(f"[Retry] Attempt {retry_count}/3")

    if retry_count >= 3:
        print("[Retry] Max retries reached. Proceeding to synthesis with error.")
        return "result_set_validator"

    # BUG 3b FIX: sql_skeleton_node is a pure deterministic function of
    # `structured_plan` / `entity_links` / `intent` — none of which change
    # between attempts. Routing retries back to it just rebuilds byte-identical
    # SQL and silently burns all 3 retries with no chance of success. Retries
    # now go back to structured_planner_node so the LLM is actually re-invoked
    # with the retry_hint, and the graph's static edges
    # (structured_planner -> dynamic_few_shot -> column_linker -> sql_skeleton)
    # naturally regenerate the whole pipeline from a corrected plan.
    if retry_count == 2:
        # The deterministic structured_planner -> column_linker -> sql_skeleton
        # pipeline has now failed twice with the SAME strategy. Rather than
        # spend the last retry repeating that strategy a third time, fall back
        # to generator_node's LLM-direct SQL generation (previously written
        # but never wired into the graph) for this final attempt — it takes a
        # different path through the problem and sometimes succeeds where the
        # structured plan keeps failing the same way.
        print("[Retry] Falling back to generator_node (LLM-direct strategy) for final attempt.")
        return "generator"

    return "structured_planner"

workflow.add_conditional_edges(
    "typed_error_classifier",
    route_after_error_classification,
    {
        "structured_planner": "structured_planner",
        "generator": "generator",
        "result_set_validator": "result_set_validator",
    }
)

# generator_node's SQL goes through the same validator as the structured
# pipeline's SQL — the validator is generic over state["generated_sql"].
workflow.add_edge("generator", "validator")

# === CONDITIONAL: Result Set Validation -> Retry or Synthesize ===
def route_after_result_check(state: AgentState) -> str:
    """Route after result set check: valid -> synthesizer, invalid -> retry if under limit."""
    is_valid = state.get("result_set_valid", True)
    retry_count = state.get("retry_count", 0)

    print(f"[ResultCheck] result_set_valid={is_valid}, retry_count={retry_count}")

    if is_valid is True:
        return "enhanced_synthesizer"

    if retry_count < 3:
        return "typed_error_classifier"

    print("[ResultCheck] Max retries reached. Proceeding with current data.")
    return "enhanced_synthesizer"

workflow.add_conditional_edges(
    "result_set_validator",
    route_after_result_check,
    {
        "enhanced_synthesizer": "enhanced_synthesizer",
        "typed_error_classifier": "typed_error_classifier",
    }
)

# Layer 5: Sequential output processing
workflow.add_edge("enhanced_synthesizer", "trend_analyzer")
workflow.add_edge("trend_analyzer", "narrative_generator")
workflow.add_edge("narrative_generator", END)

# Compile with recursion limit
agent_graph = workflow.compile()

# Monkey-patch to increase recursion limit
original_invoke = agent_graph.invoke
original_ainvoke = agent_graph.ainvoke

def invoke_with_limit(state, config=None):
    if config is None:
        config = {}
    config["recursion_limit"] = 50
    return original_invoke(state, config)

def ainvoke_with_limit(state, config=None):
    if config is None:
        config = {}
    config["recursion_limit"] = 50
    return original_ainvoke(state, config)

agent_graph.invoke = invoke_with_limit
agent_graph.ainvoke = ainvoke_with_limit


async def initialize_graph():
    """Initialize database and SchemaRAG. Must be called before first agent_graph use."""
    await db_manager.initialize()
    print(f"[Graph] Database initialized: {db_manager.dialect}")

    schema = await db_manager.get_schema()
    schema_rag.embed_schema(schema)
    stats = schema_rag.get_stats()
    print(f"[Graph] SchemaRAG indexed: {stats['tables_indexed']} tables, {stats['columns_indexed']} columns")
    return True
