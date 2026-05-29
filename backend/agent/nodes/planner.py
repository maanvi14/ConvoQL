"""Planner node: Retrieves relevant schema using RAG and plans the query approach."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any

from config import get_settings
from db.connection import db_manager
from cache.schema_rag import schema_rag

settings = get_settings()

PLANNER_PROMPT = """You are a SQLite query planner. Given the user's question and the relevant database schema, determine the exact tables, columns, joins, filters, and aggregations needed.

User Question: {question}

Relevant Database Schema (retrieved via semantic search):
{schema}

Sample Data from Relevant Tables (first 3 rows each):
{sample_data}

Your task:
1. Identify which tables are absolutely required to answer the question
2. Identify the exact columns needed (for SELECT, WHERE, JOIN, GROUP BY, ORDER BY)
3. Note any JOIN conditions needed (specify ON clause columns)
4. Note any date filters, amount comparisons, or text filters
5. Note any aggregations (SUM, COUNT, AVG, MAX, MIN) and GROUP BY needs
6. Note any sorting or LIMIT requirements

Return a brief but specific plan (3-5 sentences). Be concrete about column names and conditions.

Plan:"""

async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    # RAG: Get full schema then retrieve only relevant tables
    full_schema = await db_manager.get_schema()
    relevant = schema_rag.retrieve_relevant(state["question"], top_k=4)
    schema_text = schema_rag.build_context(full_schema, relevant)

    # Fetch sample data for relevant tables to ground the LLM
    sample_data_parts = []
    for rel in relevant:
        try:
            sample = await db_manager.execute_readonly(
                f"SELECT * FROM {rel['name']} LIMIT 3"
            )
            rows = sample.get("rows", [])
            if rows:
                sample_data_parts.append(
                    f"Table `{rel['name']}` sample:\n" +
                    "\n".join([str(r) for r in rows])
                )
        except Exception:
            pass
    sample_data_text = "\n\n".join(sample_data_parts) if sample_data_parts else "No sample data available."

    # Log RAG stats for debugging
    stats = schema_rag.get_stats()
    print(f"SchemaRAG: {stats['tables_indexed']} tables, retrieved {len(relevant)} relevant")
    for r in relevant:
        print(f"  - {r['name']} (score: {r['score']:.3f}, reason: {r['reason']})")

    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "schema": schema_text,
        "sample_data": sample_data_text,
    })

    return {
        **state,
        "schema_context": schema_text + "\n\nSample Data:\n" + sample_data_text + "\n\nPlan: " + response.content,
        "retry_count": 0,
    }
