"""SemanticCache: Redis-backed semantic cache with embedding-based similarity search.

Storage layout in Redis (all keys use prefix "convoql:cache:"):
  result:<question>   → JSON-serialised query result  (with TTL)
  emb:<question>      → numpy float32 bytes           (same TTL)
  index               → Redis SET of all cached question strings

On lookup:
  1. Exact key match  → O(1) Redis GET
  2. Semantic match   → load all embeddings from Redis, cosine-similarity scan
  3. Keyword fallback → Jaccard overlap (no Redis, no SBERT required)

Falls back gracefully to an in-process dict when Redis is unavailable so the
rest of the application is never broken.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── Redis (async) ─────────────────────────────────────────────────────────────
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

# ── SentenceTransformers ──────────────────────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    HAS_SBERT = True
except ImportError:
    HAS_SBERT = False


# ─────────────────────────────────────────────────────────────────────────────
# SemanticCache
# ─────────────────────────────────────────────────────────────────────────────

class SemanticCache:
    """Redis-backed semantic cache with embedding-based similarity search.

    Features:
    - Redis for persistent result + embedding storage (survives restarts)
    - SentenceTransformer (all-MiniLM-L6-v2) for semantic similarity
    - Configurable cosine similarity threshold (default 0.92)
    - TTL-based expiration enforced by Redis natively
    - Graceful double fallback: Redis failure → in-process dict;
      SBERT failure → Jaccard keyword overlap
    - Cache statistics tracking
    """

    KEY_PREFIX  = "convoql:cache:"
    INDEX_KEY   = "convoql:cache:index"   # Redis SET of cached question strings
    MODEL_NAME  = "all-MiniLM-L6-v2"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
    ) -> None:
        self.redis_url            = redis_url
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds          = ttl_seconds

        # Redis client (set during _connect)
        self._redis: Optional[Any] = None
        self._redis_ok: bool = False

        # In-process fallback store (used when Redis is down)
        self._fallback_cache:      Dict[str, Dict[str, Any]] = {}
        self._fallback_embeddings: Dict[str, np.ndarray]     = {}

        # Embedding model
        self._model: Optional[Any] = None

        self.stats = {
            "hits": 0, "misses": 0,
            "exact_hits": 0, "semantic_hits": 0,
            "redis_hits": 0, "fallback_hits": 0,
            "evictions": 0,
        }

        self._load_model()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if HAS_SBERT:
            try:
                self._model = SentenceTransformer(self.MODEL_NAME)
                print(f"[SemanticCache] Loaded embedding model '{self.MODEL_NAME}'")
            except Exception as exc:
                print(f"[SemanticCache] Model load failed, keyword fallback active: {exc}")
        else:
            print("[SemanticCache] sentence-transformers not installed, keyword fallback active")

    async def _connect(self) -> bool:
        """Attempt to connect to Redis. Returns True on success."""
        if not HAS_REDIS:
            print("[SemanticCache] redis package not installed — using in-process fallback")
            return False
        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,   # we handle raw bytes for embeddings
                socket_connect_timeout=2,
            )
            await self._redis.ping()
            self._redis_ok = True
            print(f"[SemanticCache] Connected to Redis at {self.redis_url}")
            return True
        except Exception as exc:
            print(f"[SemanticCache] Redis unavailable ({exc}) — using in-process fallback")
            self._redis = None
            self._redis_ok = False
            return False

    async def _ensure_connected(self) -> None:
        """Lazy-connect on first use."""
        if self._redis is None and not self._redis_ok:
            await self._connect()

    # ── Embedding helpers ─────────────────────────────────────────────────────

    def _encode_sync(self, text: str) -> Optional[np.ndarray]:
        if self._model is None:
            return None
        try:
            return self._model.encode(text, show_progress_bar=False)
        except Exception as exc:
            print(f"[SemanticCache] Encoding failed: {exc}")
            return None

    async def _encode_async(self, text: str) -> Optional[np.ndarray]:
        """Offload CPU-bound encoding to a thread to avoid blocking the event loop."""
        if self._model is None:
            return None
        return await asyncio.to_thread(self._encode_sync, text)

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(a, b) / (n1 * n2))

    @staticmethod
    def _emb_to_bytes(emb: np.ndarray) -> bytes:
        return emb.astype(np.float32).tobytes()

    @staticmethod
    def _bytes_to_emb(data: bytes) -> np.ndarray:
        return np.frombuffer(data, dtype=np.float32)

    # ── Redis key helpers ─────────────────────────────────────────────────────

    def _result_key(self, q: str) -> str:
        return f"{self.KEY_PREFIX}result:{q}"

    def _emb_key(self, q: str) -> str:
        return f"{self.KEY_PREFIX}emb:{q}"

    # ── Public API ────────────────────────────────────────────────────────────

    async def get(self, question: str) -> Optional[Dict[str, Any]]:
        """Return a cached result for *question* if one exists (exact or semantic match)."""
        question = question.lower().strip()
        if not question:
            return None

        await self._ensure_connected()

        if self._redis_ok:
            result = await self._get_from_redis(question)
        else:
            result = await self._get_from_fallback(question)

        if result is not None:
            self.stats["hits"] += 1
        else:
            self.stats["misses"] += 1

        return result

    async def set(self, question: str, data: Dict[str, Any]) -> None:
        """Store *data* under *question* in the cache."""
        question = question.lower().strip()
        if not question:
            return

        await self._ensure_connected()
        embedding = await self._encode_async(question)

        if self._redis_ok:
            await self._set_in_redis(question, data, embedding)
        else:
            self._set_in_fallback(question, data, embedding)

        print(f"[SemanticCache] STORED '{question[:60]}' (redis={self._redis_ok})")

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._ensure_connected()
        if self._redis_ok:
            try:
                # Get all keys belonging to this cache and delete them
                keys = await self._redis.smembers(self.INDEX_KEY)
                pipe = self._redis.pipeline()
                for q_bytes in keys:
                    q = q_bytes.decode("utf-8") if isinstance(q_bytes, bytes) else q_bytes
                    pipe.delete(self._result_key(q))
                    pipe.delete(self._emb_key(q))
                pipe.delete(self.INDEX_KEY)
                await pipe.execute()
                print("[SemanticCache] Redis cache cleared")
            except Exception as exc:
                print(f"[SemanticCache] Redis clear failed: {exc}")
        self._fallback_cache.clear()
        self._fallback_embeddings.clear()
        self.stats = {k: 0 for k in self.stats}

    def get_stats(self) -> Dict[str, Any]:
        total = self.stats["hits"] + self.stats["misses"]
        return {
            **self.stats,
            "hit_rate": round(self.stats["hits"] / total, 3) if total else 0.0,
            "total_queries": total,
            "redis_connected": self._redis_ok,
            "embedding_model_loaded": self._model is not None,
            "similarity_threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl_seconds,
        }

    # ── Redis backend ─────────────────────────────────────────────────────────

    async def _get_from_redis(self, question: str) -> Optional[Dict[str, Any]]:
        try:
            # 1. Exact match — O(1)
            raw = await self._redis.get(self._result_key(question))
            if raw:
                self.stats["exact_hits"] += 1
                self.stats["redis_hits"]  += 1
                print(f"[SemanticCache] REDIS EXACT HIT for '{question[:60]}'")
                return json.loads(raw)

            # 2. Semantic match
            if self._model is not None:
                match = await self._semantic_scan_redis(question)
                if match is not None:
                    self.stats["semantic_hits"] += 1
                    self.stats["redis_hits"]     += 1
                    return match

            return None

        except Exception as exc:
            print(f"[SemanticCache] Redis GET error ({exc}) — falling back to in-process")
            self._redis_ok = False
            return await self._get_from_fallback(question)

    async def _semantic_scan_redis(self, question: str) -> Optional[Dict[str, Any]]:
        """Encode the question and scan all cached embeddings in Redis."""
        try:
            q_emb = await self._encode_async(question)
            if q_emb is None:
                return None

            cached_questions_raw = await self._redis.smembers(self.INDEX_KEY)
            if not cached_questions_raw:
                return None

            best_score  = 0.0
            best_result = None

            for q_bytes in cached_questions_raw:
                cached_q = q_bytes.decode("utf-8") if isinstance(q_bytes, bytes) else q_bytes
                emb_raw  = await self._redis.get(self._emb_key(cached_q))
                if not emb_raw:
                    continue  # TTL expired
                c_emb = self._bytes_to_emb(emb_raw)
                score = self._cosine(q_emb, c_emb)
                if score > best_score:
                    best_score  = score
                    best_q      = cached_q

            if best_score >= self.similarity_threshold:
                raw = await self._redis.get(self._result_key(best_q))
                if raw:
                    print(
                        f"[SemanticCache] REDIS SEMANTIC HIT "
                        f"({best_score:.3f}) '{question[:50]}' → '{best_q[:50]}'"
                    )
                    return json.loads(raw)

            return None

        except Exception as exc:
            print(f"[SemanticCache] Redis semantic scan error: {exc}")
            return None

    async def _set_in_redis(
        self,
        question: str,
        data: Dict[str, Any],
        embedding: Optional[np.ndarray],
    ) -> None:
        try:
            pipe = self._redis.pipeline()
            pipe.set(self._result_key(question), json.dumps(data), ex=self.ttl_seconds)
            if embedding is not None:
                pipe.set(self._emb_key(question), self._emb_to_bytes(embedding), ex=self.ttl_seconds)
            pipe.sadd(self.INDEX_KEY, question)
            await pipe.execute()
        except Exception as exc:
            print(f"[SemanticCache] Redis SET error ({exc}) — storing in fallback")
            self._redis_ok = False
            self._set_in_fallback(question, data, embedding)

    # ── In-process fallback backend ───────────────────────────────────────────

    async def _get_from_fallback(self, question: str) -> Optional[Dict[str, Any]]:
        now = time.time()

        # Exact match
        entry = self._fallback_cache.get(question)
        if entry and (now - entry["ts"]) < self.ttl_seconds:
            self.stats["exact_hits"]   += 1
            self.stats["fallback_hits"] += 1
            print(f"[SemanticCache] FALLBACK EXACT HIT for '{question[:60]}'")
            return entry["data"]

        # Semantic scan
        if self._model is not None:
            q_emb = await self._encode_async(question)
            if q_emb is not None:
                best_score, best_key = 0.0, None
                for k, emb in self._fallback_embeddings.items():
                    e = self._fallback_cache.get(k)
                    if not e or (now - e["ts"]) >= self.ttl_seconds:
                        continue
                    s = self._cosine(q_emb, emb)
                    if s > best_score:
                        best_score, best_key = s, k

                if best_score >= self.similarity_threshold and best_key:
                    self.stats["semantic_hits"]  += 1
                    self.stats["fallback_hits"]  += 1
                    print(
                        f"[SemanticCache] FALLBACK SEMANTIC HIT "
                        f"({best_score:.3f}) '{question[:50]}' → '{best_key[:50]}'"
                    )
                    return self._fallback_cache[best_key]["data"]

        # Keyword fallback (Jaccard)
        q_words = set(question.split())
        best_score, best_key = 0.0, None
        for k, entry in self._fallback_cache.items():
            if (now - entry["ts"]) >= self.ttl_seconds:
                continue
            overlap = len(q_words & set(k.split())) / max(len(q_words | set(k.split())), 1)
            if overlap > best_score and overlap >= 0.8:
                best_score, best_key = overlap, k

        if best_key:
            self.stats["semantic_hits"]  += 1
            self.stats["fallback_hits"]  += 1
            print(f"[SemanticCache] FALLBACK KEYWORD HIT ({best_score:.2f})")
            return self._fallback_cache[best_key]["data"]

        return None

    def _set_in_fallback(
        self,
        question: str,
        data: Dict[str, Any],
        embedding: Optional[np.ndarray],
    ) -> None:
        self._fallback_cache[question] = {"data": data, "ts": time.time()}
        if embedding is not None:
            self._fallback_embeddings[question] = embedding


# ── Global singleton ──────────────────────────────────────────────────────────
semantic_cache = SemanticCache()
