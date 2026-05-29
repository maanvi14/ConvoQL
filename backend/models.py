from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class SQLResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    rowCount: int
    executionTime: float

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    db_url: Optional[str] = None

class QueryResponse(BaseModel):
    sql: str
    result: Optional[SQLResult] = None
    explanation: str
    followUps: List[str] = []
    chartType: Optional[str] = None
    anomaly: Optional[str] = None
    executionTime: float
    retryCount: int = 0

class SchemaInfo(BaseModel):
    tables: List[Dict[str, Any]]

class SessionCreate(BaseModel):
    db_url: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    