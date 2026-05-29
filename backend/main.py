"""ConvoQL backend main entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
    await initialize_graph()
    print("[Startup] Database and SchemaRAG initialized")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)