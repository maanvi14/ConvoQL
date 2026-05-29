"""Query decomposer: Splits compound questions into sub-queries."""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import json

from config import get_settings

settings = get_settings()

DECOMPOSER_PROMPT = """You are a query decomposer for a financial text-to-SQL system.

Analyze the user's question and determine if it contains multiple independent sub-questions that need separate SQL queries.

Compound indicators: "and", "vs", "compare", "also", "plus", "in addition", "meanwhile", "at the same time"

If the question is a single query, return empty sub_queries.
If it has multiple parts, split them into independent sub-questions.

Return ONLY JSON:
{{
  "is_compound": true/false,
  "sub_queries": [
    {{"id": 1, "question": "...", "intent": "...", "tables_needed": ["..."]}},
    {{"id": 2, "question": "...", "intent": "...", "tables_needed": ["..."]}}
  ],
  "merge_strategy": "sequential" or "side_by_side" or "ratio" or null
}}

User Question: {question}
Detected Intent: {intent}

JSON:"""

async def query_decomposer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    prompt = ChatPromptTemplate.from_template(DECOMPOSER_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "intent": json.dumps(state.get("intent", {}), indent=2),
    })

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decomp = json.loads(content)
        decomp.setdefault("is_compound", False)
        decomp.setdefault("sub_queries", [])
        decomp.setdefault("merge_strategy", None)

    except Exception as e:
        print(f"Query decomposition failed: {e}")
        decomp = {"is_compound": False, "sub_queries": [], "merge_strategy": None}

    return {
        **state,
        "decomposition": decomp,
    }
