"""
Tests for CostTracker - WBS 2.6.2 Cost Tracker Service

TDD RED Phase: These tests should fail until CostTracker is implemented.

Reference Documents:
- ARCHITECTURE.md: Line 63 - cost_tracker.py "Token/cost tracking"
- ARCHITECTURE.md: Line 223 - "Token/cost tracking per request"
- GUIDELINES pp. 2153: Redis for external state stores

WBS Items Covered:
- 2.6.2.1.1: Create src/services/cost_tracker.py
- 2.6.2.1.2: Implement CostTracker class
- 2.6.2.1.3: Define pricing per model (tokens per dollar)
- 2.6.2.1.4: Implement record_usage(model: str, usage: Usage)
- 2.6.2.1.5: Calculate cost from token counts
- 2.6.2.1.6: Store in Redis with daily aggregation
- 2.6.2.1.7: Implement get_daily_usage() -> UsageSummary
- 2.6.2.1.8: Implement get_usage_by_model() -> dict[str, UsageSummary]
- 2.6.2.1.9: RED test: record_usage stores data
- 2.6.2.1.10: RED test: cost calculation correct
- 2.6.2.1.11: RED test: daily aggregation works
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import fakeredis.aioredis

from src.models.responses import Usage


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def fake_redis():
    """Create a fake Redis client for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cost_tracker(fake_redis):
    """Create CostTracker with fake Redis."""
    from src.services.cost_tracker import CostTracker

    return CostTracker(redis_client=fake_redis)


@pytest.fixture
def sample_usage():
    """Create sample usage data."""
    return Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)


# =============================================================================
# WBS 2.6.2.1.2: CostTracker Class Tests
# =============================================================================


class TestCostTrackerClass:
    """Tests for CostTracker class structure."""

    def test_cost_tracker_can_be_instantiated(self, fake_redis) -> None:
        """
        WBS 2.6.2.1.2: CostTracker class exists and can be instantiated.
        """
        from src.services.cost_tracker import CostTracker

        tracker = CostTracker(redis_client=fake_redis)

        assert isinstance(tracker, CostTracker)

    def test_cost_tracker_requires_redis(self) -> None:
        """
        CostTracker requires Redis client dependency.
        """
        from src.services.cost_tracker import CostTracker

        with pytest.raises(TypeError):
            CostTracker()


# =============================================================================
# WBS 2.6.2.1.3: Model Pricing Tests
# =============================================================================


class TestCostTrackerPricing:
    """Tests for model pricing configuration."""

    def test_has_pricing_for_claude_models(self, cost_tracker) -> None:
        """
        WBS 2.6.2.1.3: Pricing defined for Claude models.
        """
        cost = cost_tracker.calculate_cost(
            "claude-3-5-sonnet-20241022",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        assert cost > 0

    def test_has_pricing_for_gpt_models(self, cost_tracker) -> None:
        """
        WBS 2.6.2.1.3: Pricing defined for GPT models.
        """
        cost = cost_tracker.calculate_cost(
            "gpt-4",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        assert cost > 0

    def test_unknown_model_uses_default_pricing(self, cost_tracker) -> None:
        """
        Unknown models use default pricing.
        """
        cost = cost_tracker.calculate_cost(
            "unknown-model",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        assert cost > 0


# =============================================================================
# WBS 2.6.2.1.4-5: Record Usage and Cost Calculation Tests
# =============================================================================


class TestCostTrackerRecordUsage:
    """Tests for record_usage method."""

    @pytest.mark.asyncio
    async def test_record_usage_stores_data(
        self, cost_tracker, fake_redis, sample_usage
    ) -> None:
        """
        WBS 2.6.2.1.4: record_usage stores data.
        WBS 2.6.2.1.9: RED test: record_usage stores data.
        """
        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)

        # Verify data was stored
        summary = await cost_tracker.get_daily_usage()
        assert summary.total_tokens > 0

    @pytest.mark.asyncio
    async def test_record_usage_calculates_cost(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        WBS 2.6.2.1.5: Calculate cost from token counts.
        WBS 2.6.2.1.10: RED test: cost calculation correct.
        """
        await cost_tracker.record_usage("gpt-4", sample_usage)

        summary = await cost_tracker.get_daily_usage()
        assert summary.total_cost > 0

    @pytest.mark.asyncio
    async def test_record_usage_aggregates_multiple_calls(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        WBS 2.6.2.1.6: Store with daily aggregation.
        WBS 2.6.2.1.11: RED test: daily aggregation works.
        """
        # Record multiple usages
        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)
        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)

        summary = await cost_tracker.get_daily_usage()
        # Should have 150 * 2 = 300 total tokens
        assert summary.total_tokens == 300

    @pytest.mark.asyncio
    async def test_record_usage_tracks_request_count(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        record_usage increments request count.
        """
        await cost_tracker.record_usage("gpt-4", sample_usage)
        await cost_tracker.record_usage("gpt-4", sample_usage)
        await cost_tracker.record_usage("gpt-4", sample_usage)

        summary = await cost_tracker.get_daily_usage()
        assert summary.request_count == 3


# =============================================================================
# WBS 2.6.2.1.7: Daily Usage Tests
# =============================================================================


class TestCostTrackerDailyUsage:
    """Tests for get_daily_usage method."""

    @pytest.mark.asyncio
    async def test_get_daily_usage_returns_summary(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        WBS 2.6.2.1.7: get_daily_usage returns UsageSummary.
        """
        from src.services.cost_tracker import UsageSummary

        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)

        summary = await cost_tracker.get_daily_usage()

        assert isinstance(summary, UsageSummary)
        assert summary.prompt_tokens == 100
        assert summary.completion_tokens == 50
        assert summary.total_tokens == 150

    @pytest.mark.asyncio
    async def test_get_daily_usage_empty_returns_zeros(
        self, cost_tracker
    ) -> None:
        """
        get_daily_usage returns zeros when no data recorded.
        """
        summary = await cost_tracker.get_daily_usage()

        assert summary.total_tokens == 0
        assert abs(summary.total_cost) < 0.001  # Float comparison
        assert summary.request_count == 0

    @pytest.mark.asyncio
    async def test_get_daily_usage_for_specific_date(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        get_daily_usage can query specific date.
        """
        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)

        # Query today's date
        today = date.today()
        summary = await cost_tracker.get_daily_usage(date=today)

        assert summary.total_tokens == 150


# =============================================================================
# WBS 2.6.2.1.8: Usage by Model Tests
# =============================================================================


class TestCostTrackerUsageByModel:
    """Tests for get_usage_by_model method."""

    @pytest.mark.asyncio
    async def test_get_usage_by_model_returns_dict(
        self, cost_tracker, sample_usage
    ) -> None:
        """
        WBS 2.6.2.1.8: get_usage_by_model returns dict[str, UsageSummary].
        """
        from src.services.cost_tracker import UsageSummary

        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", sample_usage)
        await cost_tracker.record_usage("gpt-4", sample_usage)

        usage_by_model = await cost_tracker.get_usage_by_model()

        assert isinstance(usage_by_model, dict)
        assert "claude-3-5-sonnet-20241022" in usage_by_model
        assert "gpt-4" in usage_by_model
        assert isinstance(usage_by_model["claude-3-5-sonnet-20241022"], UsageSummary)

    @pytest.mark.asyncio
    async def test_get_usage_by_model_separates_models(
        self, cost_tracker
    ) -> None:
        """
        get_usage_by_model tracks each model separately.
        """
        usage_claude = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage_gpt = Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

        await cost_tracker.record_usage("claude-3-5-sonnet-20241022", usage_claude)
        await cost_tracker.record_usage("gpt-4", usage_gpt)

        usage_by_model = await cost_tracker.get_usage_by_model()

        assert usage_by_model["claude-3-5-sonnet-20241022"].total_tokens == 150
        assert usage_by_model["gpt-4"].total_tokens == 300

    @pytest.mark.asyncio
    async def test_get_usage_by_model_empty_returns_empty_dict(
        self, cost_tracker
    ) -> None:
        """
        get_usage_by_model returns empty dict when no data.
        """
        usage_by_model = await cost_tracker.get_usage_by_model()

        assert usage_by_model == {}


# =============================================================================
# Cost Calculation Tests
# =============================================================================


class TestCostCalculation:
    """Tests for cost calculation accuracy."""

    def test_calculate_cost_claude_sonnet(self, cost_tracker) -> None:
        """
        Claude Sonnet pricing: $3/M input, $15/M output.
        """
        cost = cost_tracker.calculate_cost(
            "claude-3-5-sonnet-20241022",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        # $3 input + $15 output = $18
        assert abs(cost - 18.0) < 0.01

    def test_calculate_cost_gpt4(self, cost_tracker) -> None:
        """
        GPT-4 pricing: $30/M input, $60/M output.
        """
        cost = cost_tracker.calculate_cost(
            "gpt-4",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        # $30 input + $60 output = $90
        assert abs(cost - 90.0) < 0.01

    def test_calculate_cost_small_usage(self, cost_tracker) -> None:
        """
        Cost calculation for small token counts.
        """
        cost = cost_tracker.calculate_cost(
            "claude-3-5-sonnet-20241022",
            prompt_tokens=100,
            completion_tokens=50,
        )
        # 100 * $3/M + 50 * $15/M = $0.0003 + $0.00075 = $0.00105
        assert cost > 0
        assert cost < 0.01


# =============================================================================
# Import Tests
# =============================================================================


class TestCostTrackerImportable:
    """Tests for module importability."""

    def test_cost_tracker_importable_from_services(self) -> None:
        """CostTracker is importable from src.services."""
        from src.services import CostTracker

        assert callable(CostTracker)

    def test_usage_summary_importable(self) -> None:
        """UsageSummary is importable from src.services.cost_tracker."""
        from src.services.cost_tracker import UsageSummary

        assert callable(UsageSummary)
