"""
Cost Tracker Service - WBS 2.6.2.1

This module provides cost tracking functionality for LLM API usage.

Reference Documents:
- ARCHITECTURE.md: Service layer patterns
- GUIDELINES: Async patterns, dependency injection
- CODING_PATTERNS_ANALYSIS.md: Pydantic patterns, error handling

Pattern: Repository pattern with Redis storage
Anti-Pattern §1.3 Avoided: Uses Pydantic models for data structures
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field
from redis.asyncio import Redis

if TYPE_CHECKING:
    from src.models.responses import Usage


# =============================================================================
# Custom Exceptions - WBS 2.6.2.1.9
# =============================================================================


class CostTrackerError(Exception):
    """Base exception for cost tracker errors."""

    pass


# =============================================================================
# UsageSummary Model - WBS 2.6.2.1.10
# =============================================================================


class UsageSummary(BaseModel):
    """
    Summary of token usage and costs.

    Attributes:
        prompt_tokens: Total prompt tokens used
        completion_tokens: Total completion tokens used
        total_tokens: Total tokens used
        total_cost: Total cost in USD
        request_count: Number of requests made
    """

    prompt_tokens: int = Field(default=0, description="Total prompt tokens")
    completion_tokens: int = Field(default=0, description="Total completion tokens")
    total_tokens: int = Field(default=0, description="Total tokens")
    total_cost: float = Field(default=0.0, description="Total cost in USD")
    request_count: int = Field(default=0, description="Number of requests")


# =============================================================================
# Model Pricing Configuration - WBS 2.6.2.1.3
# Prices per 1M tokens (input/output)
# =============================================================================


DEFAULT_PRICING: dict[str, dict[str, Decimal]] = {
    # Claude models
    "claude-3-opus-20240229": {
        "input": Decimal("15.00"),
        "output": Decimal("75.00"),
    },
    "claude-3-sonnet-20240229": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "claude-3-5-sonnet-20241022": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "claude-3-haiku-20240307": {
        "input": Decimal("0.25"),
        "output": Decimal("1.25"),
    },
    # GPT models
    "gpt-4": {
        "input": Decimal("30.00"),
        "output": Decimal("60.00"),
    },
    "gpt-4-turbo": {
        "input": Decimal("10.00"),
        "output": Decimal("30.00"),
    },
    "gpt-4o": {
        "input": Decimal("2.50"),
        "output": Decimal("10.00"),
    },
    "gpt-4o-mini": {
        "input": Decimal("0.15"),
        "output": Decimal("0.60"),
    },
    "gpt-3.5-turbo": {
        "input": Decimal("0.50"),
        "output": Decimal("1.50"),
    },
    # Ollama models (free/local)
    "llama2": {
        "input": Decimal("0"),
        "output": Decimal("0"),
    },
    "llama3": {
        "input": Decimal("0"),
        "output": Decimal("0"),
    },
    "mistral": {
        "input": Decimal("0"),
        "output": Decimal("0"),
    },
    "codellama": {
        "input": Decimal("0"),
        "output": Decimal("0"),
    },
    # Default fallback
    "_default": {
        "input": Decimal("1.00"),
        "output": Decimal("2.00"),
    },
}


# =============================================================================
# CostTracker Service - WBS 2.6.2.1.2
# =============================================================================


class CostTracker:
    """
    Service for tracking LLM API usage and costs.

    Pattern: Repository pattern with Redis storage
    Reference: ARCHITECTURE.md service layer patterns

    Attributes:
        redis: Redis client for persistence
        pricing: Model pricing configuration
    """

    # Redis key prefixes
    KEY_PREFIX = "cost:"
    DAILY_KEY_PREFIX = "cost:daily:"
    MODEL_KEY_PREFIX = "cost:model:"

    def __init__(
        self,
        redis_client: Redis,
        pricing: Optional[dict[str, dict[str, Decimal]]] = None,
    ) -> None:
        """
        Initialize CostTracker.

        Args:
            redis_client: Redis client for persistence
            pricing: Optional custom pricing (defaults to DEFAULT_PRICING)
        """
        self._redis = redis_client
        self._pricing = pricing or DEFAULT_PRICING

    @property
    def pricing(self) -> dict[str, dict[str, Decimal]]:
        """Get pricing configuration."""
        return self._pricing

    def _get_model_pricing(self, model: str) -> dict[str, Decimal]:
        """
        Get pricing for a specific model.

        Args:
            model: Model name

        Returns:
            Pricing dict with input/output rates
        """
        # Try exact match first
        if model in self._pricing:
            return self._pricing[model]

        # Try prefix match (e.g., "gpt-4-0613" matches "gpt-4")
        for model_prefix in self._pricing:
            if model_prefix != "_default" and model.startswith(model_prefix):
                return self._pricing[model_prefix]

        # Fallback to default
        return self._pricing.get("_default", {"input": Decimal("1.00"), "output": Decimal("2.00")})

    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """
        Calculate cost for token usage.

        WBS 2.6.2.1.5: Cost calculation from token counts.

        Args:
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in USD as float
        """
        pricing = self._get_model_pricing(model)
        # Prices are per 1M tokens
        input_cost = (Decimal(prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(completion_tokens) / Decimal("1000000")) * pricing["output"]
        return float(input_cost + output_cost)

    def _get_daily_key(self, target_date: Optional[dt.date] = None) -> str:
        """Get Redis key for daily usage."""
        target = target_date or dt.date.today()
        return f"{self.DAILY_KEY_PREFIX}{target.isoformat()}"

    def _get_model_key(self, model: str, target_date: Optional[dt.date] = None) -> str:
        """Get Redis key for model-specific usage."""
        target = target_date or dt.date.today()
        return f"{self.MODEL_KEY_PREFIX}{target.isoformat()}:{model}"

    async def record_usage(
        self,
        model: str,
        usage: "Usage",
    ) -> UsageSummary:
        """
        Record usage for a request.

        WBS 2.6.2.1.4: record_usage method for storing usage data.
        WBS 2.6.2.1.6: Redis storage with daily aggregation.
        WBS 2.6.2.1.12: Uses atomic HINCRBY/HINCRBYFLOAT for thread safety.

        Args:
            model: Model name
            usage: Usage object with token counts

        Returns:
            Updated usage summary for today
        """
        try:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            cost = self.calculate_cost(model, prompt_tokens, completion_tokens)

            # Get keys
            daily_key = self._get_daily_key()
            model_key = self._get_model_key(model)

            # Use atomic HINCRBY/HINCRBYFLOAT operations on hash
            # This is thread-safe and prevents race conditions
            pipe = self._redis.pipeline()
            
            # Atomic increments for daily usage
            pipe.hincrby(daily_key, "prompt_tokens", prompt_tokens)
            pipe.hincrby(daily_key, "completion_tokens", completion_tokens)
            pipe.hincrby(daily_key, "total_tokens", total_tokens)
            pipe.hincrbyfloat(daily_key, "total_cost", cost)
            pipe.hincrby(daily_key, "request_count", 1)
            
            # Atomic increments for model-specific usage
            pipe.hincrby(model_key, "prompt_tokens", prompt_tokens)
            pipe.hincrby(model_key, "completion_tokens", completion_tokens)
            pipe.hincrby(model_key, "total_tokens", total_tokens)
            pipe.hincrbyfloat(model_key, "total_cost", cost)
            pipe.hincrby(model_key, "request_count", 1)
            
            # Execute pipeline atomically
            results = await pipe.execute()
            
            # Results are the new values after increment
            # [prompt, completion, total, cost, count] for daily
            return UsageSummary(
                prompt_tokens=int(results[0]),
                completion_tokens=int(results[1]),
                total_tokens=int(results[2]),
                total_cost=float(results[3]),
                request_count=int(results[4]),
            )

        except Exception as e:
            raise CostTrackerError(f"Failed to record usage: {e}") from e

    async def get_daily_usage(
        self,
        date: Optional[dt.date] = None,
    ) -> UsageSummary:
        """
        Get usage summary for a specific day.

        WBS 2.6.2.1.7: get_daily_usage method.
        WBS 2.6.2.1.12: Uses HGETALL to read from hash.

        Args:
            date: Date to get usage for (defaults to today)

        Returns:
            Usage summary for the day
        """
        try:
            daily_key = self._get_daily_key(date)
            data = await self._redis.hgetall(daily_key)

            if not data:
                return UsageSummary()

            return UsageSummary(
                prompt_tokens=int(data.get("prompt_tokens", 0)),
                completion_tokens=int(data.get("completion_tokens", 0)),
                total_tokens=int(data.get("total_tokens", 0)),
                total_cost=float(data.get("total_cost", 0)),
                request_count=int(data.get("request_count", 0)),
            )

        except Exception as e:
            raise CostTrackerError(f"Failed to get daily usage: {e}") from e

    async def get_usage_by_model(
        self,
        target_date: Optional[dt.date] = None,
    ) -> dict[str, UsageSummary]:
        """
        Get usage breakdown by model for a specific day.

        WBS 2.6.2.1.8: get_usage_by_model method.
        WBS 2.6.2.1.12: Uses HGETALL to read from hash.

        Args:
            target_date: Date to get usage for (defaults to today)

        Returns:
            Dict mapping model names to usage summaries
        """
        try:
            target = target_date or dt.date.today()
            pattern = f"{self.MODEL_KEY_PREFIX}{target.isoformat()}:*"

            result: dict[str, UsageSummary] = {}

            # Scan for matching keys
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # Extract model name from key
                    key_str = key.decode() if isinstance(key, bytes) else key
                    model = key_str.split(":")[-1]

                    # Read hash data instead of JSON
                    data = await self._redis.hgetall(key)
                    if data:
                        result[model] = UsageSummary(
                            prompt_tokens=int(data.get("prompt_tokens", 0)),
                            completion_tokens=int(data.get("completion_tokens", 0)),
                            total_tokens=int(data.get("total_tokens", 0)),
                            total_cost=float(data.get("total_cost", 0)),
                            request_count=int(data.get("request_count", 0)),
                        )

                if cursor == 0:
                    break

            return result

        except Exception as e:
            raise CostTrackerError(f"Failed to get usage by model: {e}") from e
