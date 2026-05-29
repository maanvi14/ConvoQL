"""ConvoQL API Router.

This file defines all API endpoints for the frontend.
Place this in: backend/agent/api_router.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import time
import uuid

from agent.graph import agent_graph

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str = ""
    sql: Optional[str] = None
    generated_sql: Optional[str] = None
    has_chart: bool = False
    has_table: bool = False
    chart_type: Optional[str] = None
    chart_title: Optional[str] = None
    insight: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    rows: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    execution_time_ms: int = 0
    anomaly: Optional[str] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    narrative: Optional[str] = None


@router.post("/sessions")
async def create_session() -> Dict[str, str]:
    """Create a new session."""
    return {"session_id": str(uuid.uuid4())}


@router.post("/query")
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    """Process a natural language query and return structured response."""
    start_time = time.perf_counter()
    session_id = req.session_id or str(uuid.uuid4())

    try:
        # Build initial state
        initial_state = {
            "question": req.question,
            "messages": [{"role": "user", "content": req.question}],
            "dialect": "sqlite",
        }

        # Run the LangGraph
        final_state = await agent_graph.ainvoke(initial_state, config={"recursion_limit": 50})

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract sql_result (where DB result is stored by enhanced_synthesizer)
        sql_result = final_state.get("sql_result")

        # Build normalized result object for frontend
        normalized_result = None
        if sql_result:
            rows = sql_result.get("rows", [])
            columns = sql_result.get("columns", [])
            normalized_result = {
                "columns": columns,
                "rows": rows,
                "rowCount": len(rows),
                "totalRows": len(rows),
                "executionTime": elapsed_ms,
            }

        # Build response with ALL fields frontend expects
        response = QueryResponse(
            answer=final_state.get("answer", final_state.get("explanation", "Here's what I found.")),
            sql=final_state.get("generated_sql"),
            generated_sql=final_state.get("generated_sql"),
            has_chart=final_state.get("has_chart", False),
            has_table=final_state.get("has_table", False),
            chart_type=final_state.get("chart_type"),
            chart_title=final_state.get("chart_title"),
            insight=final_state.get("insight"),
            # CRITICAL: Pass normalized result
            result=normalized_result,
            columns=normalized_result.get("columns") if normalized_result else None,
            rows=normalized_result.get("rows") if normalized_result else None,
            row_count=len(normalized_result.get("rows", [])) if normalized_result else 0,
            execution_time_ms=elapsed_ms,
            anomaly=final_state.get("anomaly"),
            explanation=final_state.get("explanation") or final_state.get("answer"),
            narrative=final_state.get("narrative"),
            error=final_state.get("error"),
        )

        # Debug logging
        sql_preview = response.sql[:80] if response.sql else "None"
        print(f"[API] Query: {req.question[:50]}...")
        print(f"[API] SQL: {sql_preview}...")
        print(f"[API] Rows: {response.row_count}, Has chart: {response.has_chart}")

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
async def get_schema() -> Dict[str, Any]:
    """Get database schema for frontend sidebar."""
    from db.connection import db_manager
    try:
        schema = await db_manager.get_schema()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    