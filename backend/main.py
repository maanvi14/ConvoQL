"""ConvoQL backend main entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys

# ============================================================================
# FIX: Clear Python module cache to force reload of modified agent nodes
# This ensures generator.py and column_linker.py changes are picked up
# ============================================================================
# Remove cached modules so fresh code is loaded
modules_to_clear = [
    k for k in sys.modules.keys()
    if k.startswith("agent.nodes.") or k in ("agent.graph", "agent.api_router")
]
for mod in modules_to_clear:
    del sys.modules[mod]

from agent.api_router import router as agent_router
from agent.graph import initialize_graph
from db.connection import db_manager

app = FastAPI(title="ConvoQL API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the agent router
app.include_router(agent_router, prefix="/api")

@app.on_event("startup")
async def startup():
    # ============================================================================
    # FIX: Initialize graph (db + schema_rag) BEFORE first request
    # This ensures generator.py's TABLE_COLUMNS is populated
    # ============================================================================
    await initialize_graph()
    print("[Startup] Database and SchemaRAG initialized")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    