"""
Intelligent Caching System for TaskPilot AI

Features:
- In-memory caching with TTL
- Query result caching
- Agent output caching
- Cache warming and invalidation
"""

import hashlib
import json
import time
from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
import pickle


class CacheEntry:
    """Single cache entry with metadata."""
    
    def __init__(self, value: Any, ttl: int = 3600):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
        self.last_accessed = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return (time.time() - self.created_at) > self.ttl
    
    def access(self) -> Any:
        """Access the cached value."""
        self.hits += 1
        self.last_accessed = time.time()
        return self.value


class IntelligentCache:
    """
    In-memory cache with intelligent eviction policies.
    
    Features:
    - TTL-based expiration
    - LRU eviction
    - Hit rate tracking
    - Size limits
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.cache = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _make_key(self, key: Any) -> str:
        """Generate cache key from any object."""
        if isinstance(key, str):
            return key
        
        # Serialize and hash non-string keys
        try:
            serialized = json.dumps(key, sort_keys=True)
        except (TypeError, ValueError):
            serialized = str(key)
        
        return hashlib.md5(serialized.encode()).hexdigest()
    
    def get(self, key: Any) -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._make_key(key)
        
        if cache_key not in self.cache:
            self.stats['misses'] += 1
            return None
        
        entry = self.cache[cache_key]
        
        if entry.is_expired():
            del self.cache[cache_key]
            self.stats['misses'] += 1
            return None
        
        self.stats['hits'] += 1
        return entry.access()
    
    def set(self, key: Any, value: Any, ttl: Optional[int] = None):
        """Set value in cache."""
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        cache_key = self._make_key(key)
        ttl = ttl if ttl is not None else self.default_ttl
        
        self.cache[cache_key] = CacheEntry(value, ttl)
    
    def delete(self, key: Any):
        """Delete key from cache."""
        cache_key = self._make_key(key)
        if cache_key in self.cache:
            del self.cache[cache_key]
    
    def clear(self):
        """Clear entire cache."""
        self.cache.clear()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self.cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].last_accessed
        )
        
        del self.cache[lru_key]
        self.stats['evictions'] += 1
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_rate': round(hit_rate, 2)
        }
    
    def cleanup_expired(self):
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


class AgentCache:
    """
    Specialized cache for agent outputs.
    
    Caches agent results based on input context to avoid redundant processing.
    """
    
    def __init__(self, agent_name: str, ttl: int = 1800):
        self.agent_name = agent_name
        self.cache = IntelligentCache(max_size=500, default_ttl=ttl)
    
    def _make_context_key(self, user_input: str, context: dict) -> str:
        """Create cache key from user input and context."""
        key_data = {
            'agent': self.agent_name,
            'user_input': user_input,
            'context_keys': sorted(context.keys()),
            # Only hash context values, don't include full content
            'context_hash': hashlib.md5(
                json.dumps(context, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
        }
        return json.dumps(key_data, sort_keys=True)
    
    def get_cached_result(self, user_input: str, context: dict) -> Optional[Any]:
        """Get cached agent result."""
        cache_key = self._make_context_key(user_input, context)
        return self.cache.get(cache_key)
    
    def cache_result(self, user_input: str, context: dict, result: Any, ttl: Optional[int] = None):
        """Cache agent result."""
        cache_key = self._make_context_key(user_input, context)
        self.cache.set(cache_key, result, ttl)
    
    def clear(self):
        """Clear agent cache."""
        self.cache.clear()
    
    def get_stats(self) -> dict:
        """Get agent cache statistics."""
        return {
            'agent': self.agent_name,
            **self.cache.get_stats()
        }


class QueryCache:
    """
    Cache for frequently executed queries (web search, API calls).
    
    Reduces redundant external API calls.
    """
    
    def __init__(self, ttl: int = 3600):
        self.cache = IntelligentCache(max_size=1000, default_ttl=ttl)
    
    def _make_query_key(self, query_type: str, query: str, params: Optional[dict] = None) -> str:
        """Create cache key for query."""
        key_data = {
            'type': query_type,
            'query': query.lower().strip(),
            'params': params or {}
        }
        return json.dumps(key_data, sort_keys=True)
    
    def get_cached_query(self, query_type: str, query: str, params: Optional[dict] = None) -> Optional[Any]:
        """Get cached query result."""
        cache_key = self._make_query_key(query_type, query, params)
        return self.cache.get(cache_key)
    
    def cache_query(self, query_type: str, query: str, result: Any, params: Optional[dict] = None, ttl: Optional[int] = None):
        """Cache query result."""
        cache_key = self._make_query_key(query_type, query, params)
        self.cache.set(cache_key, result, ttl)
    
    def get_stats(self) -> dict:
        """Get query cache statistics."""
        return self.cache.get_stats()


def cached(ttl: int = 3600, cache_instance: Optional[IntelligentCache] = None):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(ttl=1800)
        def expensive_function(arg1, arg2):
            # ... expensive operation
            return result
    """
    def decorator(func: Callable):
        cache = cache_instance or IntelligentCache(default_ttl=ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        # Attach cache to function for inspection
        wrapper.cache = cache
        return wrapper
    
    return decorator


# Global cache instances
_agent_caches = {}
_query_cache = None


def get_agent_cache(agent_name: str, ttl: int = 1800) -> AgentCache:
    """Get or create agent cache."""
    if agent_name not in _agent_caches:
        _agent_caches[agent_name] = AgentCache(agent_name, ttl)
    return _agent_caches[agent_name]


def get_query_cache(ttl: int = 3600) -> QueryCache:
    """Get the global query cache."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(ttl)
    return _query_cache


def clear_all_caches():
    """Clear all caches."""
    for cache in _agent_caches.values():
        cache.clear()
    
    if _query_cache:
        _query_cache.cache.clear()


def get_all_cache_stats() -> dict:
    """Get statistics from all caches."""
    return {
        'agent_caches': {
            name: cache.get_stats()
            for name, cache in _agent_caches.items()
        },
        'query_cache': _query_cache.get_stats() if _query_cache else None
    }
