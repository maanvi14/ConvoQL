"""LangGraph definition for ConvoQL with proper retry loop wiring."""
from langgraph.graph import StateGraph, END
from typing import Dict, Any

from agent.state import AgentState
from agent.nodes.intent_classifier import intent_classifier_node
from agent.nodes.query_decomposer import query_decomposer_node
from agent.nodes.structured_planner import structured_planner_node
from agent.nodes.dynamic_few_shot import dynamic_few_shot_node
from agent.nodes.column_linker import column_linker_node
from agent.nodes.sql_skeleton import sql_skeleton_node
from agent.nodes.validator import validator_node
from agent.nodes.typed_error_classifier import typed_error_classifier_node
from agent.nodes.result_set_validator import result_set_validator_node
from agent.nodes.enhanced_synthesizer import enhanced_synthesizer_node
from agent.nodes.trend_analyzer import trend_analyzer_node
from agent.nodes.narrative_generator import narrative_generator_node
from agent.nodes.generator import generator_node  # FIXED: Import generator_node
from db.connection import db_manager
from cache.schema_rag import schema_rag

# Build graph
workflow = StateGraph(AgentState)

# Layer 1: Query Understanding
workflow.add_node("intent_classifier", intent_classifier_node)
workflow.add_node("query_decomposer", query_decomposer_node)

# Layer 2: Schema Retrieval
workflow.add_node("structured_planner", structured_planner_node)
workflow.add_node("dynamic_few_shot", dynamic_few_shot_node)

# Layer 3: Generation
workflow.add_node("column_linker", column_linker_node)
workflow.add_node("sql_skeleton", sql_skeleton_node)
workflow.add_node("generator", generator_node)  # FIXED: Add generator node

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
workflow.add_edge("query_decomposer", "structured_planner")

# Layer 2 -> Layer 3
workflow.add_edge("structured_planner", "dynamic_few_shot")
workflow.add_edge("dynamic_few_shot", "column_linker")
workflow.add_edge("column_linker", "sql_skeleton")
workflow.add_edge("sql_skeleton", "generator")  # FIXED: Wire sql_skeleton -> generator

# Layer 3 -> Layer 4 (Validator)
workflow.add_edge("generator", "validator")  # FIXED: Wire generator -> validator

# === CONDITIONAL: Validator -> Retry or Continue ===
def route_after_validator(state: AgentState) -> str:
    """Route after validator: valid -> result_set_validator, invalid -> typed_error_classifier."""
    is_valid = state.get("valid", False)
    retry_count = state.get("retry_count", 0)

    print(f"[Router] valid={is_valid}, retry_count={retry_count}")

    if is_valid is True:
        return "result_set_validator"

    # Not valid -- route to error classifier (which increments retry_count)
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

    # If max retries reached, skip to result validation (will fail gracefully)
    if retry_count >= 3:
        print("[Retry] Max retries reached. Proceeding to synthesis with error.")
        return "result_set_validator"

    # Retry: go back to generator (NOT column_linker) so full regeneration happens
    return "generator"  # FIXED: Retry at generator, not column_linker

workflow.add_conditional_edges(
    "typed_error_classifier",
    route_after_error_classification,
    {
        "generator": "generator",  # FIXED: Route to generator for retry
        "result_set_validator": "result_set_validator",
    }
)

# === CONDITIONAL: Result Set Validation -> Retry or Synthesize ===
def route_after_result_check(state: AgentState) -> str:
    """Route after result set check: valid -> synthesizer, invalid -> retry if under limit."""
    is_valid = state.get("result_set_valid", True)
    retry_count = state.get("retry_count", 0)

    print(f"[ResultCheck] result_set_valid={is_valid}, retry_count={retry_count}")

    if is_valid is True:
        return "enhanced_synthesizer"

    # Result set invalid -- check if we should retry
    if retry_count < 3:
        # Route to typed_error_classifier to increment count and classify
        # The error was already set by result_set_validator
        return "typed_error_classifier"

    # Max retries reached, proceed with potentially bad data
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


# === EXPLICIT INITIALIZATION ===
# Call initialize_graph() from your entry point BEFORE using agent_graph.
# Do NOT auto-run at import time to avoid event loop conflicts.

async def initialize_graph():
    """Initialize database and SchemaRAG. Must be called before first agent_graph use."""
    await db_manager.initialize()
    print(f"[Graph] Database initialized: {db_manager.dialect}")

    # Index schema for RAG
    schema = await db_manager.get_schema()
    schema_rag.embed_schema(schema)
    stats = schema_rag.get_stats()
    print(f"[Graph] SchemaRAG indexed: {stats['tables_indexed']} tables, {stats['columns_indexed']} columns")
    return True
