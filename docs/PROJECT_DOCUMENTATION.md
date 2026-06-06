# ConvoQL — Project Documentation

## Overview

ConvoQL is a conversation-driven, query-first analytics assistant that bridges natural-language queries and SQL-backed data exploration. The workspace contains a Python-based backend that implements agent-style planning, synthesis, and execution components, and a Next.js TypeScript frontend that provides a chat-like UI and visualization components.

## Key Features

- Natural-language to SQL decomposition and execution via modular agent nodes.
- Schema-aware caching and semantic retrieval to improve query relevance and speed.
- Auto-charting and anomaly detection helpers in analytics.
- Frontend chat UI with query panel, schema explorer, and integrated charts.

## Repository layout (high level)

- `backend/` — Python backend, agents, analytics, and DB access.
- `frontend/` — Next.js + TypeScript frontend and UI components.
- `docs/` — Project documentation (this folder).
- `Dockerfile`, `render.yaml`, `runtime.txt` — deployment and runtime hints.

## Backend

Structure:

- `backend/main.py` — Backend application entrypoint (starts server or CLI).
- `backend/config.py` — Configuration values and environment integration.
- `backend/models.py` — Data models and domain objects.
- `backend/db/connection.py` — Database connection helpers.
- `backend/agent/` — Core agent orchestration and node implementations.
  - `api_router.py` — HTTP routes / API surface for agent queries.
  - `graph.py`, `state.py` — Agent orchestration graph and runtime state.
  - `nodes/` — Individual planner/synthesizer/validator nodes (decomposition, SQL skeleton, synthesizer, validator, etc.).

Data:

- `backend/finance_sqlite.sql` and `backend/results.json` are example data artifacts and exports.

Running the backend (local development):

1. Create and activate a Python virtualenv.
2. Install dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

3. Run the server (project defines `backend/main.py`):

```bash
python backend/main.py
```

Adjust configuration in `backend/config.py` or via environment variables as needed.

## Frontend

Structure:

- `frontend/app/` — Next.js App Router pages and API route at `app/api/query/route.ts`.
- `frontend/components/` — React components: `AutoChart.tsx`, `ChatThread.tsx`, `ConvoQLPage.tsx`, `SchemaExplorer.tsx`, `SQLPanel.tsx`.
- `frontend/lib/` — Client-side helpers and API wrappers.

Running the frontend (local development):

1. Change to `frontend/` and install packages:

```bash
cd frontend
npm install
```

2. Start the development server:

```bash
npm run dev
```

Note: if using a separate backend process, ensure the frontend's `lib/api.ts` points to the correct backend URL or proxy.

## API surface

- Backend agent HTTP endpoints are defined in `backend/agent/api_router.py` — these accept natural-language prompts or structured requests and return plans, SQL, or result sets.
- Frontend calls the API via `frontend/lib/api.ts` and the client API route `frontend/app/api/query/route.ts` proxies or enriches requests.

## Agents and Nodes

The `backend/agent/nodes/` directory contains modular steps used by the agent orchestration graph. Key node responsibilities include:

- Intent classification
- Query decomposition
- SQL skeleton generation
- Synthesizer (produces final SQL and parameters)
- Result validation and typed error classification

The agent graph (`backend/agent/graph.py`) wires nodes together to transform a user query into executable SQL and optional post-processing (e.g., auto-chart suggestions).

## Caching and Analytics

- `backend/cache/` implements schema-aware retrieval and semantic cache layers to accelerate repeated queries and context lookups.
- `backend/analytics/` includes anomaly detection and auto-charting helpers used to surface insights automatically.

## Data & Database

- A sample SQLite schema is included at `backend/finance_sqlite.sql`. The project can be configured to use SQLite or an external SQL database via `backend/config.py`.

## Tests and Validation

- Unit and integration style tests or example runners may be found under `backend/agent/nodes/test_*` (e.g., `test_queries.py`, `test_runner.py`). Run these directly with Python or via a test harness if available.

## Deployment

- A `Dockerfile` and `render.yaml` are present for containerized deployment. Ensure you set runtime Python/Node versions consistent with `runtime.txt` and `frontend/package.json`.

## Contributing

- Follow existing code patterns inside `backend/agent/nodes/` when adding new agent behaviors.
- Keep functions small and testable; add tests for new synthesis or validation logic.

## Troubleshooting

- If the frontend cannot reach the backend, verify backend is running and CORS/proxy settings are correct.
- Check `backend/config.py` for environment-based configuration issues.

## Where to look in the codebase

- Backend entry: `backend/main.py`
- Agent orchestration: `backend/agent/graph.py`, `backend/agent/state.py`
- Node implementations: `backend/agent/nodes/` (see nodes for planner, synthesizer, validator)
- Frontend entry: `frontend/app/page.tsx` and `frontend/components/ConvoQLPage.tsx`

## Detailed features and important files

This section lists important subsystems, representative files, and a short description of their responsibilities.

- Agent orchestration
  - `backend/agent/graph.py`: wires nodes into executable pipelines and defines run logic.
  - `backend/agent/state.py`: runtime state, context propagation, and execution traces.
  - `backend/agent/api_router.py`: HTTP endpoints exposing planning, SQL generation, and execution.

- Agent nodes (responsibilities)
  - `backend/agent/nodes/intent_classifier.py`: classifies user intent and determines high-level actions.
  - `backend/agent/nodes/query_decomposer.py`: breaks complex prompts into smaller sub-queries.
  - `backend/agent/nodes/planner.py` / `structured_planner.py`: builds ordered plans of nodes to execute.
  - `backend/agent/nodes/sql_skeleton.py`: generates SQL skeletons (SELECT, FROM, JOIN scaffolding).
  - `backend/agent/nodes/synthesizer.py` / `enhanced_synthesizer.py`: fills skeletons into executable SQL with parameters.
  - `backend/agent/nodes/db_adapter.py`: converts synthesized queries into database-specific SQL and runs them.
  - `backend/agent/nodes/result_set_validator.py`: validates result shapes and suggests fixes or clarifications.
  - `backend/agent/nodes/typed_error_classifier.py`: classifies errors returned from DB or synthesis step.
  - `backend/agent/nodes/auto_charting` (functions in `narrative_generator.py` and `generator.py`): suggest chart types and narratives.
  - `backend/agent/nodes/test_queries.py`, `test_runner.py`: example queries and small test harnesses for nodes.

- Caching & retrieval
  - `backend/cache/semantic_cache.py`: semantic embeddings cache for prompt-context matching.
  - `backend/cache/schema_rag.py`: schema-focused RAG (retrieval-augmented generation) helpers.

- Analytics
  - `backend/analytics/auto_chart.py`: algorithmic suggestions for chart type and encodings.
  - `backend/analytics/anomaly.py`: lightweight anomaly scoring for numeric time-series.

- Database & data
  - `backend/db/connection.py`: database connection pooling, adapters, and query helpers.
  - `backend/finance_sqlite.sql`: sample SQLite schema and seed data for quick testing.
  - `backend/results.json`: sample exported results and example payloads.

- Core backend files
  - `backend/main.py`: app entrypoint, server startup or CLI commands.
  - `backend/config.py`: configuration via env vars and defaults (DB URLs, API keys, timeouts).
  - `backend/models.py`: domain models and shared types used across nodes.

- Frontend
  - `frontend/app/page.tsx` and `frontend/components/ConvoQLPage.tsx`: main app shell and page layout.
  - `frontend/components/ChatThread.tsx`: chat UI and message rendering.
  - `frontend/components/SQLPanel.tsx`: editor-like panel for previewing SQL and running ad-hoc queries.
  - `frontend/components/SchemaExplorer.tsx`: visual schema browser for tables and columns.
  - `frontend/components/AutoChart.tsx`: visual suggestions and small chart renderer used by the UI.
  - `frontend/lib/api.ts`: client-side API wrappers and fetch helpers.
  - `frontend/app/api/query/route.ts`: optional server-side API route used for proxying or augmenting requests.

- Deployment & infra
  - `Dockerfile`: containerize backend (and optionally frontend) for production.
  - `render.yaml`: example deployment configuration for Render or similar PaaS.
  - `runtime.txt`: pinned runtime versions (useful for deployments that read this file).

- Misc
  - `README.md`: high-level project landing content (do not modify per request).

