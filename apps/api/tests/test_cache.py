"""
Unit tests for PipelineCache module.

Tests cover:
- cache_key() determinism and uniqueness
- PipelineCache get/set/delete operations
- TTL handling
- Error handling for corrupt data
"""

import pytest
from pydantic import BaseModel

import fakeredis

from vip_shared.pipeline import PipelineCache, cache_key
from vip_shared.pipeline.models import AnalysisResult, CategoryAnalysis


# ---------------------------------------------------------------------------
# Test Models
# ---------------------------------------------------------------------------


class SimpleTestModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    value: int


class NestedTestModel(BaseModel):
    """Nested Pydantic model for testing."""

    id: str
    items: list[str]
    metadata: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """Create a FakeRedis instance for testing."""
    return fakeredis.FakeRedis(decode_responses=False)


@pytest.fixture
def cache(fake_redis: fakeredis.FakeRedis) -> PipelineCache:
    """Create PipelineCache with FakeRedis."""
    return PipelineCache(redis=fake_redis, default_ttl_seconds=3600)


@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    """Create a sample AnalysisResult for testing."""
    return AnalysisResult(
        category_analyses=[
            CategoryAnalysis(
                category="HVAC / Mechanical",
                primary_total=6300.00,
                comparison_total=5100.00,
                delta=1200.00,
                delta_drivers=["Primary includes condenser replacement"],
                line_item_evidence=["Replace condenser $4,500"],
            ),
        ],
        scope_gaps=["Comparison missing demo allowance"],
        overall_delta_direction="primary_higher",
        confidence="high",
    )


# ---------------------------------------------------------------------------
# TestCacheKey
# ---------------------------------------------------------------------------


class TestCacheKey:
    """Tests for cache_key() function."""

    def test_cache_key_deterministic(self):
        """Same inputs produce same key."""
        model1 = SimpleTestModel(name="test", value=42)
        model2 = SimpleTestModel(name="test", value=42)

        key1 = cache_key("analysis", model1)
        key2 = cache_key("analysis", model2)

        assert key1 == key2
        assert key1.startswith("pipeline:analysis:")

    def test_cache_key_different_pass_names(self):
        """Different pass names produce different keys."""
        model = SimpleTestModel(name="test", value=42)

        key1 = cache_key("analysis", model)
        key2 = cache_key("writer", model)

        assert key1 != key2
        assert "analysis" in key1
        assert "writer" in key2

    def test_cache_key_different_inputs(self):
        """Different inputs produce different keys."""
        model1 = SimpleTestModel(name="test", value=42)
        model2 = SimpleTestModel(name="test", value=43)  # Different value

        key1 = cache_key("analysis", model1)
        key2 = cache_key("analysis", model2)

        assert key1 != key2

    def test_cache_key_format(self):
        """Key has expected format."""
        model = SimpleTestModel(name="test", value=42)
        key = cache_key("analysis", model)

        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "pipeline"
        assert parts[1] == "analysis"
        assert len(parts[2]) == 64  # SHA256 hex digest

    def test_cache_key_with_nested_model(self):
        """Works with nested Pydantic models."""
        model1 = NestedTestModel(
            id="123",
            items=["a", "b", "c"],
            metadata={"key": "value"},
        )
        model2 = NestedTestModel(
            id="123",
            items=["a", "b", "c"],
            metadata={"key": "value"},
        )

        key1 = cache_key("test", model1)
        key2 = cache_key("test", model2)

        assert key1 == key2

    def test_cache_key_with_real_analysis_result(self, sample_analysis_result):
        """Works with real AnalysisResult model."""
        key = cache_key("analysis", sample_analysis_result)

        assert key.startswith("pipeline:analysis:")
        assert len(key.split(":")[-1]) == 64


# ---------------------------------------------------------------------------
# TestPipelineCache
# ---------------------------------------------------------------------------


class TestPipelineCache:
    """Tests for PipelineCache class."""

    def test_get_returns_none_on_miss(self, cache: PipelineCache):
        """Get returns None when key not in cache."""
        result = cache.get("pipeline:analysis:nonexistent", SimpleTestModel)
        assert result is None

    def test_get_returns_model_on_hit(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Get returns deserialized model on cache hit."""
        model = SimpleTestModel(name="cached", value=123)
        key = "pipeline:test:abc123"

        # Store directly in Redis
        fake_redis.setex(key, 3600, model.model_dump_json())

        # Retrieve via cache
        result = cache.get(key, SimpleTestModel)

        assert result is not None
        assert result.name == "cached"
        assert result.value == 123

    def test_set_stores_with_ttl(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Set stores model with default TTL."""
        model = SimpleTestModel(name="test", value=42)
        key = "pipeline:test:xyz789"

        success = cache.set(key, model)

        assert success is True
        # Verify stored in Redis
        data = fake_redis.get(key)
        assert data is not None
        # Verify TTL was set
        ttl = fake_redis.ttl(key)
        assert ttl > 0
        assert ttl <= 3600

    def test_set_custom_ttl(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Set uses custom TTL when provided."""
        model = SimpleTestModel(name="test", value=42)
        key = "pipeline:test:custom"

        success = cache.set(key, model, ttl_seconds=1800)

        assert success is True
        ttl = fake_redis.ttl(key)
        assert ttl <= 1800

    def test_get_returns_none_on_deserialize_error(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Get returns None when cached data can't be deserialized."""
        key = "pipeline:test:corrupt"
        # Store corrupt data
        fake_redis.setex(key, 3600, b"not valid json")

        result = cache.get(key, SimpleTestModel)

        assert result is None

    def test_get_returns_none_on_wrong_model_type(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Get returns None when cached data doesn't match model."""
        key = "pipeline:test:wrongtype"
        # Store valid JSON but wrong model structure
        fake_redis.setex(key, 3600, b'{"different_field": "value"}')

        result = cache.get(key, SimpleTestModel)

        assert result is None

    def test_delete_removes_entry(
        self, cache: PipelineCache, fake_redis: fakeredis.FakeRedis
    ):
        """Delete removes entry from cache."""
        model = SimpleTestModel(name="to_delete", value=99)
        key = "pipeline:test:delete"

        # Store first
        cache.set(key, model)
        assert fake_redis.exists(key)

        # Delete
        result = cache.delete(key)

        assert result is True
        assert not fake_redis.exists(key)

    def test_delete_returns_true_for_nonexistent(self, cache: PipelineCache):
        """Delete returns True even for nonexistent keys."""
        result = cache.delete("pipeline:test:nonexistent")
        assert result is True

    def test_roundtrip_with_analysis_result(
        self, cache: PipelineCache, sample_analysis_result: AnalysisResult
    ):
        """Full roundtrip with real AnalysisResult model."""
        key = cache_key("analysis", sample_analysis_result)

        # Set
        success = cache.set(key, sample_analysis_result)
        assert success is True

        # Get
        result = cache.get(key, AnalysisResult)

        assert result is not None
        assert len(result.category_analyses) == 1
        assert result.category_analyses[0].category == "HVAC / Mechanical"
        assert result.confidence == "high"
        assert result.overall_delta_direction == "primary_higher"


# ---------------------------------------------------------------------------
# TestPipelineCacheEdgeCases
# ---------------------------------------------------------------------------


class TestPipelineCacheEdgeCases:
    """Edge case tests for PipelineCache."""

    def test_empty_list_in_model(self, cache: PipelineCache):
        """Handles models with empty lists."""
        model = AnalysisResult(
            category_analyses=[],
            scope_gaps=[],
            overall_delta_direction="similar",
            confidence="low",
        )
        key = "pipeline:test:empty"

        cache.set(key, model)
        result = cache.get(key, AnalysisResult)

        assert result is not None
        assert result.category_analyses == []
        assert result.scope_gaps == []

    def test_special_characters_in_data(self, cache: PipelineCache):
        """Handles special characters in model data."""
        model = SimpleTestModel(name="test with \"quotes\" and 'apostrophes'", value=42)
        key = "pipeline:test:special"

        cache.set(key, model)
        result = cache.get(key, SimpleTestModel)

        assert result is not None
        assert "quotes" in result.name

    def test_unicode_in_data(self, cache: PipelineCache):
        """Handles unicode characters in model data."""
        model = SimpleTestModel(name="unicode: \u2019 \u2013 \u00b2", value=42)
        key = "pipeline:test:unicode"

        cache.set(key, model)
        result = cache.get(key, SimpleTestModel)

        assert result is not None
        assert "\u2019" in result.name

    def test_large_model(self, cache: PipelineCache):
        """Handles large model data."""
        large_items = [f"item_{i}" for i in range(1000)]
        model = NestedTestModel(
            id="large",
            items=large_items,
            metadata={"size": "large"},
        )
        key = "pipeline:test:large"

        cache.set(key, model)
        result = cache.get(key, NestedTestModel)

        assert result is not None
        assert len(result.items) == 1000
