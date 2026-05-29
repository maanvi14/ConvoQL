"""Semantic cache for query results."""
from typing import Optional, Dict, Any

class SemanticCache:
    def __init__(self):
        self._cache = {}
    
    async def get(self, question: str) -> Optional[Dict[str, Any]]:
        """Check if similar question was asked before."""
        return self._cache.get(question.lower().strip())
    
    async def set(self, question: str, data: Dict[str, Any]):
        """Cache query result."""
        self._cache[question.lower().strip()] = data
    
    async def clear(self):
        """Clear cache."""
        self._cache = {}

semantic_cache = SemanticCache()
