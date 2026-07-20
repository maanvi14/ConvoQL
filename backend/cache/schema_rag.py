"""SchemaRAG: Embedding-based semantic retrieval of relevant tables/columns.

Replaces the old keyword/heuristic scorer with a ChromaDB in-memory
collection backed by SentenceTransformer (all-MiniLM-L6-v2) embeddings.

Public API is unchanged:
  - embed_schema(schema)        → indexes all tables into ChromaDB
  - retrieve_relevant(q, top_k) → vector-similarity top-k tables
  - build_context(schema, rel)  → formats them into a prompt string
  - get_stats()                 → returns table / column counts
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

# ── ChromaDB ──────────────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

# ── SentenceTransformers ──────────────────────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    HAS_SBERT = True
except ImportError:
    HAS_SBERT = False

# Fallback: simple overlap scorer used only when neither library is available.
import re


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _table_document(table: Dict[str, Any]) -> str:
    """Build a rich text document for a table so the embedder has full context.

    Format:
        table: <name>
        columns: col1 (TYPE), col2 (TYPE), ...

    Both the table name and every column name+type are embedded together so
    that questions phrased around column semantics (e.g. "balance", "amount")
    retrieve the right table even when the table name itself doesn't match.
    """
    col_parts = ", ".join(
        f"{c['name']} ({c.get('type', 'TEXT')})"
        for c in table.get("columns", [])
    )
    return f"table: {table['name']}\ncolumns: {col_parts}"


# ─────────────────────────────────────────────────────────────────────────────
# SchemaRAG
# ─────────────────────────────────────────────────────────────────────────────

class SchemaRAG:
    """Semantic schema retrieval using ChromaDB + SentenceTransformer embeddings.

    Falls back gracefully to keyword overlap scoring when the libraries are
    not installed, so the rest of the agent graph is never broken.
    """

    COLLECTION_NAME = "schema_rag"
    MODEL_NAME      = "all-MiniLM-L6-v2"   # same model used by SemanticCache

    def __init__(self) -> None:
        self.tables:   List[Dict[str, Any]] = []
        self.columns:  List[Dict[str, Any]] = []
        self._indexed: bool = False

        # ChromaDB client (ephemeral / in-memory — no disk writes needed)
        self._client:     Optional[Any] = None
        self._collection: Optional[Any] = None

        # Embedding model (shared across calls — loaded once at startup)
        self._model: Optional[Any] = None

        self._init_backends()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_backends(self) -> None:
        """Load ChromaDB client and SentenceTransformer model."""
        if HAS_CHROMA:
            try:
                self._client = chromadb.Client(
                    ChromaSettings(anonymized_telemetry=False)
                )
                print("[SchemaRAG] ChromaDB ephemeral client initialised")
            except Exception as exc:
                print(f"[SchemaRAG] ChromaDB init failed — falling back to keyword: {exc}")
                self._client = None

        if HAS_SBERT:
            try:
                self._model = SentenceTransformer(self.MODEL_NAME)
                print(f"[SchemaRAG] Loaded embedding model '{self.MODEL_NAME}'")
            except Exception as exc:
                print(f"[SchemaRAG] Model load failed — falling back to keyword: {exc}")
                self._model = None

    # ── Public API ────────────────────────────────────────────────────────────

    def embed_schema(self, schema: Dict[str, Any]) -> None:
        """Index all tables from *schema* into ChromaDB.

        Called once per session when a new database is connected (see
        graph.py).  Subsequent calls on the same schema are idempotent
        because the collection is recreated from scratch each time (schemas
        can change between sessions).
        """
        self.tables  = schema.get("tables", [])
        self.columns = []
        self._indexed = False

        # Rebuild flat column list for get_stats()
        for table in self.tables:
            for col in table.get("columns", []):
                self.columns.append({
                    "table":  table["name"],
                    "column": col["name"],
                    "type":   col.get("type", "TEXT"),
                })

        if not self.tables:
            return

        if self._client is not None and self._model is not None:
            self._build_chroma_index()
        else:
            print("[SchemaRAG] Embeddings unavailable — keyword fallback active")

        self._indexed = True

    def retrieve_relevant(
        self,
        question: str,
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Return the *top_k* most relevant tables for *question*.

        Each result dict has the shape expected by callers:
            {"name": str, "score": float, "reason": str, "table": dict}
        """
        if not self.tables:
            return []

        # Path 1 — ChromaDB vector search
        if self._collection is not None and self._model is not None:
            return self._chroma_retrieve(question, top_k)

        # Path 2 — Keyword overlap fallback
        return self._keyword_retrieve(question, top_k)

    def build_context(
        self,
        full_schema: Dict[str, Any],
        relevant: List[Dict[str, Any]],
    ) -> str:
        """Format relevant tables into the schema context string for LLM prompts."""
        lines: List[str] = []
        for rel in relevant:
            table = rel["table"]
            lines.append(f"Table: {table['name']}")
            for col in table.get("columns", []):
                lines.append(f"  - {col['name']}: {col.get('type', 'TEXT')}")
            lines.append("")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, int]:
        return {
            "tables_indexed":  len(self.tables),
            "columns_indexed": len(self.columns),
        }

    # ── ChromaDB internals ────────────────────────────────────────────────────

    def _build_chroma_index(self) -> None:
        """(Re)create the ChromaDB collection and upsert table documents."""
        # Delete existing collection if it exists (fresh index per session)
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass  # collection didn't exist yet — fine

        self._collection = self._client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        ids:       List[str] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for i, table in enumerate(self.tables):
            ids.append(str(i))
            documents.append(_table_document(table))
            metadatas.append({"table_name": table["name"], "idx": i})

        # Embed all documents synchronously (called at startup, not hot path)
        embeddings = self._model.encode(documents, show_progress_bar=False).tolist()

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(
            f"[SchemaRAG] Indexed {len(self.tables)} tables into ChromaDB "
            f"({len(self.columns)} columns total)"
        )

    def _chroma_retrieve(
        self,
        question: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB with the question's embedding and return top-k tables."""
        try:
            q_embedding = self._model.encode([question], show_progress_bar=False).tolist()
            results = self._collection.query(
                query_embeddings=q_embedding,
                n_results=min(top_k, len(self.tables)),
                include=["metadatas", "distances"],
            )

            output: List[Dict[str, Any]] = []
            for meta, distance in zip(
                results["metadatas"][0],
                results["distances"][0],
            ):
                idx   = meta["idx"]
                table = self.tables[idx]
                # ChromaDB cosine distance = 1 - cosine_similarity
                score = round(1.0 - distance, 4)
                output.append({
                    "name":   table["name"],
                    "score":  score,
                    "reason": f"embedding similarity {score:.3f}",
                    "table":  table,
                })

            return output

        except Exception as exc:
            print(f"[SchemaRAG] ChromaDB query failed — falling back to keyword: {exc}")
            return self._keyword_retrieve(question, top_k)

    # ── Keyword fallback (no external dependencies) ───────────────────────────

    def _keyword_retrieve(
        self,
        question: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Simple token-overlap scorer — used only when embeddings are absent."""
        q_tokens = set(re.findall(r"[a-z]+", question.lower()))
        scored: List[Dict[str, Any]] = []

        for table in self.tables:
            name_tokens = set(re.findall(r"[a-z]+", table["name"].lower()))
            col_tokens  = set(
                tok
                for col in table.get("columns", [])
                for tok in re.findall(r"[a-z]+", col["name"].lower())
            )
            all_tokens = name_tokens | col_tokens
            overlap    = len(q_tokens & all_tokens)
            score      = round(overlap / max(len(q_tokens), 1), 4)
            scored.append({
                "name":   table["name"],
                "score":  score,
                "reason": f"keyword overlap {overlap} tokens",
                "table":  table,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ── Global singleton (same pattern as semantic_cache.py) ─────────────────────
schema_rag = SchemaRAG()
