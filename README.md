# ConvoQL - "Agentic NL-to-SQL Analytics Platform"

![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-Frontend-38BDF8)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Orchestration-orange)
![LangChain](https://img.shields.io/badge/LangChain-LLM_Framework-green)
![RAG](https://img.shields.io/badge/RAG-Schema_Retrieval-purple)
![LLaMA 3](https://img.shields.io/badge/LLaMA_3-Groq_Inference-red)
![Groq](https://img.shields.io/badge/Groq-Low_Latency_LLM-red)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-blue)
![Python Asyncio](https://img.shields.io/badge/Python-Asyncio-yellow)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED)
![SQLite](https://img.shields.io/badge/SQLite-Supported-lightgrey)
![MySQL](https://img.shields.io/badge/MySQL-Supported-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supported-blue)
![Hugging Face Spaces](https://img.shields.io/badge/HuggingFace-Deployed-yellow)
![Vercel](https://img.shields.io/badge/Vercel-Frontend-black)
![Status](https://img.shields.io/badge/Status-Active-success)

https://github.com/user-attachments/assets/b1df17ef-0101-499b-9539-5a705d429fd1

## What is ConvoQL?

ConvoQL is an agentic AI-powered analytics platform that allows users to interact with databases conversationally.

Users can ask questions in plain English, while ConvoQL automatically retrieves relevant schema context, generates SQL, validates queries, executes them safely, and returns actionable insights—all without requiring SQL expertise.

Powered by LangGraph, LangChain, Groq LLaMA 3, and FastAPI, the system employs schema-aware RAG, structured planning, validation layers, and self-correcting workflows to deliver reliable natural-language analytics across SQLite, MySQL, and PostgreSQL databases.

---
## 🚀 Live Workflow

🔗 *Frontend:*  https://convo-ql.vercel.app/ | 🔗 *Backend:*   https://huggingface.co/spaces/Maanviiii/ConvoQL-backend
---
<img width="1800" height="1960" alt="ConvoQL_Architecture" src="https://github.com/user-attachments/assets/3f01a822-1ae3-4d4b-b99d-5fad8c813828" />

## Key Engineering Features

### Agentic LangGraph Workflow

ConvoQL uses a 13-node LangGraph pipeline where each stage performs a specific responsibility, including intent classification, schema retrieval, query planning, SQL generation, validation, error recovery, and response synthesis. Shared state management and conditional routing enable reliable multi-step reasoning and self-correcting workflows.

---

### Schema-Aware Retrieval (RAG)

A custom SchemaRAG module retrieves only the database tables relevant to the user's question rather than exposing the entire schema to the LLM. This reduces token usage, improves query accuracy, and minimizes schema hallucinations.

---

### Multi-Layer SQL Validation

Every generated query passes through multiple validation layers before execution:

* Read-only security checks
* Live schema validation
* SQL syntax verification
* Query plan inspection

This ensures generated SQL is safe, valid, and aligned with the underlying database structure.

---

### Automated Error Recovery

When query generation fails, ConvoQL classifies the failure, generates targeted correction hints, and retries automatically. This self-correcting mechanism improves reliability compared to traditional single-prompt text-to-SQL systems.

---

### Hallucination Mitigation

The system combines schema grounding, deterministic rule enforcement, validation layers, and retry-based correction to reduce common LLM failure modes such as invalid column references, incorrect filters, and misleading query logic.

---

### Intelligent Analytics Layer

Beyond SQL generation, ConvoQL performs trend analysis and anomaly detection on query results, enabling users to uncover patterns, outliers, and business insights automatically.

---

### Multi-Database Support

ConvoQL supports SQLite, MySQL, and PostgreSQL through a unified database abstraction layer, automatically adapting SQL generation and execution to the selected database dialect.

---
## Tech Stack

| Layer | Technology |
|---------|------------|
| Frontend | Next.js 14, Tailwind CSS, Recharts |
| Backend | FastAPI, Python, Asyncio |
| Agent Orchestration | LangGraph |
| LLM Framework | LangChain |
| LLM Inference | LLaMA 3.1 8B (Groq API) |
| Retrieval Layer | Custom SchemaRAG |
| Database Layer | SQLAlchemy |
| Databases | SQLite, MySQL, PostgreSQL |
| Analytics | Pandas, NumPy |
| Containerization | Docker |
| Frontend Deployment | Vercel |
| Backend Deployment | Hugging Face Spaces, Render |

---


title: ConvoQL
emoji: 💬
sdk: docker
---




