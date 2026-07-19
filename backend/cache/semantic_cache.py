"""Semantic cache for query results with embedding-based similarity search."""
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import json
import time
import asyncio

# Try to use sentence-transformers, fallback to keyword matching
try:
    from sentence_transformers import SentenceTransformer
    HAS_SBERT = True
except ImportError:
    HAS_SBERT = False

class SemanticCache:
    """Production-grade semantic cache with embedding-based similarity search.

    Features:
    - Embedding-based similarity (not just exact string match)
    - Configurable similarity threshold
    - TTL-based expiration
    - Cache statistics tracking
    - Graceful fallback to keyword matching if embeddings unavailable
    """

    def __init__(self, similarity_threshold: float = 0.92, ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}  # question -> {data, embedding, timestamp, hit_count}
        self._embeddings: Dict[str, np.ndarray] = {}  # question -> embedding vector
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.model = None
        self.stats = {"hits": 0, "misses": 0, "exact_hits": 0, "semantic_hits": 0, "evictions": 0}

        if HAS_SBERT:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                print("[SemanticCache] Loaded sentence-transformers model")
            except Exception as e:
                print(f"[SemanticCache] Could not load model: {e}")
                self.model = None
        else:
            print("[SemanticCache] sentence-transformers not available, using keyword fallback")

    def _compute_embedding(self, text: str) -> Optional[np.ndarray]:
        """Compute embedding vector for a text. Synchronous/CPU-bound — call
        via _compute_embedding_async from async code, never directly."""
        if self.model is None:
            return None
        try:
            return self.model.encode(text)
        except Exception as e:
            print(f"[SemanticCache] Embedding failed: {e}")
            return None

    async def _compute_embedding_async(self, text: str) -> Optional[np.ndarray]:
        """Async wrapper around _compute_embedding.

        BUG FIX: get()/set() are async (they're called from an async
        LangGraph node pipeline serving concurrent requests), but this used
        to call self.model.encode() directly and synchronously inline.
        SentenceTransformer.encode() is CPU-bound and can take tens to
        hundreds of milliseconds per call — running it un-awaited inside an
        async function blocks the entire event loop for that duration,
        stalling every other in-flight request on the server, not just this
        one. Offloading it to a thread via asyncio.to_thread lets the event
        loop keep serving other coroutines while the embedding computes.
        """
        if self.model is None:
            return None
        return await asyncio.to_thread(self._compute_embedding, text)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot / (norm1 * norm2))

    def _is_expired(self, timestamp: float) -> bool:
        """Check if a cached entry has expired."""
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - timestamp) > self.ttl_seconds

    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        expired_keys = []
        for key, entry in self._cache.items():
            if self._is_expired(entry.get("timestamp", 0)):
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            if key in self._embeddings:
                del self._embeddings[key]
            self.stats["evictions"] += 1

        if expired_keys:
            print(f"[SemanticCache] Cleaned up {len(expired_keys)} expired entries")

    async def get(self, question: str) -> Optional[Dict[str, Any]]:
        """Check if a similar question was asked before.

        Returns cached result if:
        1. Exact match found
        2. Semantic similarity >= threshold (embedding-based)
        3. Keyword overlap >= 80% (fallback if no embeddings)

        Also checks TTL and cleans up expired entries.
        """
        question = question.lower().strip()
        if not question:
            return None

        # Periodic cleanup (every 10 calls)
        if (self.stats["hits"] + self.stats["misses"]) % 10 == 0:
            self._cleanup_expired()

        # 1. Exact match check
        if question in self._cache:
            entry = self._cache[question]
            if not self._is_expired(entry.get("timestamp", 0)):
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                self.stats["hits"] += 1
                self.stats["exact_hits"] += 1
                print(f"[SemanticCache] EXACT HIT for: '{question[:50]}...'")
                return entry["data"]
            else:
                # Expired exact match
                del self._cache[question]
                if question in self._embeddings:
                    del self._embeddings[question]
                self.stats["evictions"] += 1

        # 2. Semantic similarity check (if embeddings available)
        if self.model is not None:
            query_vec = await self._compute_embedding_async(question)
            if query_vec is not None:
                best_match = None
                best_score = 0.0
                best_key = None

                for cached_key, cached_vec in self._embeddings.items():
                    if cached_key not in self._cache:  # Shouldn't happen, but safety check
                        continue

                    # Skip expired entries
                    if self._is_expired(self._cache[cached_key].get("timestamp", 0)):
                        continue

                    similarity = self._cosine_similarity(query_vec, cached_vec)
                    if similarity > best_score:
                        best_score = similarity
                        best_match = self._cache[cached_key]
                        best_key = cached_key

                if best_score >= self.similarity_threshold and best_match is not None:
                    best_match["hit_count"] = best_match.get("hit_count", 0) + 1
                    self.stats["hits"] += 1
                    self.stats["semantic_hits"] += 1
                    print(f"[SemanticCache] SEMANTIC HIT ({best_score:.3f}) for: '{question[:50]}...' -> matched '{best_key[:50]}...'")
                    return best_match["data"]

        # 3. Keyword fallback (if no embeddings or no semantic match)
        best_keyword_match = None
        best_keyword_score = 0.0
        best_key = None

        query_words = set(question.split())
        for cached_key, entry in self._cache.items():
            if self._is_expired(entry.get("timestamp", 0)):
                continue

            cached_words = set(cached_key.split())
            if not cached_words:
                continue

            overlap = len(query_words & cached_words) / len(query_words | cached_words)
            if overlap > best_keyword_score and overlap >= 0.8:  # 80% Jaccard similarity
                best_keyword_score = overlap
                best_keyword_match = entry
                best_key = cached_key

        if best_keyword_match is not None:
            best_keyword_match["hit_count"] = best_keyword_match.get("hit_count", 0) + 1
            self.stats["hits"] += 1
            self.stats["semantic_hits"] += 1  # Count as semantic hit
            print(f"[SemanticCache] KEYWORD HIT ({best_keyword_score:.2f}) for: '{question[:50]}...' -> matched '{best_key[:50]}...'")
            return best_keyword_match["data"]

        self.stats["misses"] += 1
        print(f"[SemanticCache] MISS for: '{question[:50]}...'")
        return None

    async def set(self, question: str, data: Dict[str, Any]):
        """Cache a query result with embedding.

        Stores:
        - The result data
        - Embedding vector (for future semantic matching)
        - Timestamp (for TTL)
        - Hit count (for cache analytics)
        """
        question = question.lower().strip()
        if not question:
            return

        # Compute embedding if model available
        embedding = None
        if self.model is not None:
            embedding = await self._compute_embedding_async(question)

        self._cache[question] = {
            "data": data,
            "timestamp": time.time(),
            "hit_count": 0,
        }

        if embedding is not None:
            self._embeddings[question] = embedding

        print(f"[SemanticCache] STORED: '{question[:50]}...' (embedding={embedding is not None})")

    async def clear(self):
        """Clear all cached entries."""
        self._cache = {}
        self._embeddings = {}
        self.stats = {"hits": 0, "misses": 0, "exact_hits": 0, "semantic_hits": 0, "evictions": 0}
        print("[SemanticCache] Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0.0

        return {
            **self.stats,
            "hit_rate": round(hit_rate, 3),
            "total_queries": total,
            "cached_entries": len(self._cache),
            "embedding_model_loaded": self.model is not None,
            "similarity_threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl_seconds,
        }

    def get_cache_entries(self) -> List[Dict[str, Any]]:
        """Get all cached entries with metadata (for debugging)."""
        entries = []
        for question, entry in self._cache.items():
            entries.append({
                "question": question,
                "hit_count": entry.get("hit_count", 0),
                "age_seconds": round(time.time() - entry.get("timestamp", 0), 1),
                "is_expired": self._is_expired(entry.get("timestamp", 0)),
            })
        return entries

# Singleton instance
semantic_cache = SemanticCache()

