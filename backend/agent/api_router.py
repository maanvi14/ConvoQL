"""ConvoQL API Router.

This file defines all API endpoints for the frontend.
Place this in: backend/agent/api_router.py
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import time
import uuid
import os
import shutil
import tempfile

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from agent.graph import agent_graph
from db.connection import db_manager
from cache.semantic_cache import semantic_cache

router = APIRouter()


# ─── Request / Response Models ──────────────────────────────────

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


class ConnectionTestRequest(BaseModel):
    db_type: str
    connection_string: Optional[str] = None
    filename: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    dialect: str
    tables_count: Optional[int] = None
    message: str


class ConnectionResponse(BaseModel):
    session_id: str
    dialect: str
    tables_count: int
    message: str


# ─── Session ──────────────────────────────────────────────────────

@router.post("/sessions")
async def create_session() -> Dict[str, str]:
    """Create a new session."""
    return {"session_id": str(uuid.uuid4())}


# ─── Query ──────────────────────────────────────────────────────

@router.post("/query")
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    """Process a natural language query and return structured response."""
    start_time = time.perf_counter()
    session_id = req.session_id or str(uuid.uuid4())

    try:
        # ── 1. Semantic cache check ──────────────────────────────────────────
        cached = await semantic_cache.get(req.question)
        if cached is not None:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            print(f"[API] Cache HIT in {elapsed_ms}ms for: '{req.question[:50]}'")
            cached["execution_time_ms"] = elapsed_ms
            return QueryResponse(**cached)

        # ── 2. Full LangGraph pipeline (cache miss) ──────────────────────────
        initial_state = {
            "question": req.question,
            "messages": [{"role": "user", "content": req.question}],
            "dialect": db_manager.dialect if db_manager.dialect else "sqlite",
        }

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

        # ── 3. Store in cache (only successful, non-error responses) ─────────
        if not response.error:
            await semantic_cache.set(req.question, response.model_dump())

        # Debug logging
        sql_preview = response.sql[:80] if response.sql else "None"
        print(f"[API] Query: {req.question[:50]}...")
        print(f"[API] SQL: {sql_preview}...")
        print(f"[API] Rows: {response.row_count}, Has chart: {response.has_chart}, Time: {elapsed_ms}ms")

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ─── Schema ───────────────────────────────────────────────────────

@router.get("/schema")
async def get_schema() -> Dict[str, Any]:
    """Get database schema for frontend sidebar."""
    try:
        schema = await db_manager.get_schema()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Connect / Test ───────────────────────────────────────────────

@router.post("/connect/test", response_model=ConnectionTestResponse)
async def test_connection(req: ConnectionTestRequest):
    """Test a database connection without saving it."""
    try:
        conn_str = req.connection_string

        # For SQLite, we can't really test without the file, but we can validate
        if req.db_type == "sqlite":
            if not req.filename:
                raise HTTPException(status_code=400, detail="SQLite file required")
            return ConnectionTestResponse(
                success=True,
                dialect="sqlite",
                message="SQLite file format valid. Upload to connect.",
            )

        # For MySQL/PostgreSQL, actually try connecting
        if req.db_type == "mysql":
            # Ensure aiomysql driver is used
            if "mysql" not in conn_str.lower():
                conn_str = conn_str.replace("mysql://", "mysql+aiomysql://")
                conn_str = conn_str.replace("mysql+pymysql://", "mysql+aiomysql://")
        elif req.db_type == "postgresql":
            if "postgres" not in conn_str.lower():
                conn_str = conn_str.replace("postgresql://", "postgresql+asyncpg://")

        # Test connection
        test_engine = create_async_engine(conn_str, echo=False, future=True, pool_pre_ping=True)

        async with test_engine.connect() as conn:
            if req.db_type == "mysql":
                result = await conn.execute(text("SHOW TABLES"))
            else:
                result = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                ))
            tables = result.fetchall()
            tables_count = len(tables)

        await test_engine.dispose()

        return ConnectionTestResponse(
            success=True,
            dialect=req.db_type,
            tables_count=tables_count,
            message=f"Connected successfully. Found {tables_count} tables.",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.post("/connect", response_model=ConnectionResponse)
async def connect_database(
    db_type: str = Form(...),
    connection_string: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Connect to a user-provided database and create a session."""
    try:
        session_id = str(uuid.uuid4())
        actual_conn_str = connection_string

        # Handle SQLite file upload
        if db_type == "sqlite":
            if not file:
                raise HTTPException(status_code=400, detail="SQLite database file required")

            # Save uploaded file to temp location
            temp_dir = tempfile.mkdtemp(prefix="convoql_")
            file_path = os.path.join(temp_dir, file.filename or "database.db")

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            actual_conn_str = f"sqlite+aiosqlite:///{file_path}"
            print(f"[Connect] Saved SQLite file to {file_path}")

        # Normalize connection string for MySQL/PostgreSQL
        elif db_type == "mysql":
            if actual_conn_str and "mysql" not in actual_conn_str.lower():
                actual_conn_str = actual_conn_str.replace("mysql://", "mysql+aiomysql://")
        elif db_type == "postgresql":
            if actual_conn_str and "postgres" not in actual_conn_str.lower():
                actual_conn_str = actual_conn_str.replace("postgresql://", "postgresql+asyncpg://")

        # Re-initialize DB manager with new connection
        await db_manager.initialize(actual_conn_str)

        # Get schema to verify connection
        schema = await db_manager.get_schema()
        tables_count = len(schema.get("tables", []))

        print(f"[Connect] Session {session_id} connected to {db_type}. Tables: {tables_count}")

        return ConnectionResponse(
            session_id=session_id,
            dialect=db_manager.dialect,
            tables_count=tables_count,
            message=f"Connected to {db_type}. Found {tables_count} tables.",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")