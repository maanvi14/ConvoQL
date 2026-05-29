"""Agent state definition with dialect support for multi-database compatibility."""
from typing import Optional, List, Dict, Any
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    """Extended state for ConvoQL agent supporting SQLite, MySQL, and PostgreSQL."""

    # Input
    question: str = ""
    dialect: str = "sqlite"  # "sqlite" | "mysql" | "postgresql"

    # Layer 1: Query Understanding
    intent: Optional[Dict[str, Any]] = None
    decomposition: Optional[Dict[str, Any]] = None

    # Layer 2: Schema Retrieval
    schema_context: str = ""
    structured_plan: Optional[Dict[str, Any]] = None
    few_shot_examples: str = ""

    # Layer 3: Generation
    entity_links: Optional[Dict[str, Any]] = None
    generated_sql: str = ""

    # Layer 4: Validation
    valid: Optional[bool] = None
    error: Optional[str] = None
    error_classification: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    retry_hint: Optional[str] = None
    result_set_valid: Optional[bool] = None
    result_set_issue: Optional[str] = None

    # Layer 5: Output
    sql_result: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None  # Normalized result for API response
    answer: str = ""
    explanation: str = ""
    has_chart: bool = False
    chart_type: Optional[str] = None
    chart_title: Optional[str] = None
    has_table: bool = False
    insight: Optional[str] = None
    follow_ups: List[str] = []
    anomaly: Optional[str] = None
    trend_analysis: Optional[str] = None
    narrative: Optional[str] = None
    execution_time_ms: int = 0
    row_count: int = 0
    