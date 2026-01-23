"""
PipelineCache module for Redis-based caching of pipeline pass results.

This module provides:
- cache_key(): Generate deterministic cache keys from pass name and input content
- PipelineCache: Redis wrapper for storing/retrieving Pydantic model results with TTL

Cache keys are based on SHA256 hash of input content, ensuring:
- Same inputs = same key (deterministic)
- Different inputs = different key (collision-resistant)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional, Type, TypeVar

from pydantic import BaseModel
from redis import Redis


logger = logging.getLogger("vip-parse.pipeline.cache")

T = TypeVar("T", bound=BaseModel)


def cache_key(pass_name: str, inputs: BaseModel) -> str:
    """
    Generate a deterministic cache key from pass name and input content.

    The key is based on:
    - Pass name (e.g., "analysis", "writer")
    - SHA256 hash of input content (sorted JSON for determinism)

    Args:
        pass_name: Name of the pipeline pass
        inputs: Pydantic model containing pass inputs

    Returns:
        Cache key string in format: pipeline:{pass_name}:{hash}
    """
    # Use sorted keys for deterministic serialization
    content = inputs.model_dump_json(exclude_none=True)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"pipeline:{pass_name}:{content_hash}"


class PipelineCache:
    """
    Redis cache wrapper for pipeline pass results.

    Stores Pydantic model results with configurable TTL.
    Cache keys are deterministic based on input content hash.

    Usage:
        cache = PipelineCache(redis_client, default_ttl_seconds=3600)
        key = cache_key("analysis", analysis_input)

        # Try cache first
        result = cache.get(key, AnalysisResult)
        if result is None:
            result = run_analysis_pass(...)
            cache.set(key, result, ttl_seconds=3600)
    """

    def __init__(
        self,
        redis: Redis,
        default_ttl_seconds: int = 3600,
    ):
        """
        Initialize PipelineCache with Redis connection.

        Args:
            redis: Redis client instance
            default_ttl_seconds: Default TTL for cache entries (default: 1 hour)
        """
        self.redis = redis
        self.default_ttl = default_ttl_seconds
        self.logger = logging.getLogger("vip-parse.pipeline.cache")

    def get(
        self,
        key: str,
        model_cls: Type[T],
    ) -> Optional[T]:
        """
        Retrieve cached result and deserialize to Pydantic model.

        Args:
            key: Cache key from cache_key()
            model_cls: Pydantic model class to deserialize into

        Returns:
            Deserialized model instance, or None if not in cache or on error
        """
        try:
            data = self.redis.get(key)
        except Exception as exc:
            self.logger.warning("cache get error: %s %s", key[:60], exc)
            return None

        if data is None:
            self.logger.debug("cache miss: %s", key[:60])
            return None

        try:
            # Redis returns bytes, decode if needed
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            result = model_cls.model_validate_json(data)
            self.logger.info("cache hit: %s", key[:60])
            return result
        except Exception as exc:
            self.logger.warning("cache deserialize failed: %s %s", key[:60], exc)
            return None

    def set(
        self,
        key: str,
        result: BaseModel,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Serialize Pydantic model and store in cache with TTL.

        Args:
            key: Cache key from cache_key()
            result: Pydantic model instance to cache
            ttl_seconds: TTL in seconds (uses default if not specified)

        Returns:
            True if stored successfully, False on error
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        try:
            data = result.model_dump_json()
            self.redis.setex(key, ttl, data)
            self.logger.info("cache set: %s ttl=%d", key[:60], ttl)
            return True
        except Exception as exc:
            self.logger.warning("cache set failed: %s %s", key[:60], exc)
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a cache entry.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted successfully, False on error
        """
        try:
            self.redis.delete(key)
            return True
        except Exception as exc:
            self.logger.warning("cache delete failed: %s %s", key[:60], exc)
            return False
