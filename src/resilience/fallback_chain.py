"""
Fallback Chain - WBS-CPA3

This module implements the fallback chain pattern for resilient backend access.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3, AC-CPA3.3
- Building Microservices (Newman): Cascading failure prevention
- Microservices Patterns (Richardson): Fallback patterns

Fallback Chain:
    Gateway → semantic-search → Code-Orchestrator → local cache

Each backend has its own circuit breaker. When a backend fails or its
circuit is open, the chain automatically tries the next backend.

Anti-Pattern Compliance:
- AP-1: Constants for configuration keys
- AP-2: Methods <15 CC
- AP-5: Exception uses FallbackChainError prefix
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from src.resilience.circuit_breaker_state_machine import (
    CircuitBreakerError,
    CircuitBreakerState,
    CircuitBreakerStateMachine,
)
from src.resilience.metrics import record_fallback_attempt, record_fallback_success

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (AP-1 Compliance: No duplicated string literals)
# =============================================================================

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30.0

BACKEND_SEMANTIC_SEARCH = "semantic-search"
BACKEND_CODE_ORCHESTRATOR = "code-orchestrator"

CONFIG_KEY_NAME = "name"
CONFIG_KEY_BACKENDS = "backends"
CONFIG_KEY_ENABLE_CACHE = "enable_local_cache"
CONFIG_KEY_URL = "url"
CONFIG_KEY_TIMEOUT = "timeout"


# =============================================================================
# Exception Class (AP-5 Compliance: FallbackChainError prefix)
# =============================================================================


class FallbackChainError(Exception):
    """
    Exception raised when all backends in a fallback chain fail.

    AP-5 Compliance: Uses {Service}Error prefix pattern.

    Attributes:
        chain_name: Name of the fallback chain
        message: Additional context message
        backend_errors: Errors from each backend attempt
    """

    def __init__(
        self,
        chain_name: str,
        message: str = "All backends failed",
        backend_errors: Optional[Dict[str, str]] = None,
    ) -> None:
        self.chain_name = chain_name
        self.message = message
        self.backend_errors = backend_errors or {}
        super().__init__(f"FallbackChainError[{chain_name}]: {message}")


# =============================================================================
# Backend Configuration
# =============================================================================


@dataclass
class FallbackBackend:
    """
    Configuration for a fallback chain backend.

    Attributes:
        name: Backend identifier (e.g., "semantic-search")
        url: Base URL for the backend
        timeout: Request timeout in seconds
        failure_threshold: Circuit breaker failure threshold
        reset_timeout_seconds: Circuit breaker reset timeout
    """

    name: str
    url: str
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS


# =============================================================================
# Fallback Chain
# =============================================================================


class FallbackChain:
    """
    Fallback chain for resilient backend access.

    AC-CPA3.3: Implements fallback chain:
        Gateway → semantic-search → Code-Orchestrator → local cache

    Each backend has its own circuit breaker. When a backend fails or its
    circuit is open, the chain automatically tries the next backend.

    Thread Safety:
        Circuit breakers use asyncio.Lock() internally for state protection.

    Example:
        >>> chain = FallbackChain.create_search_chain()
        >>> result = await chain.execute("search", {"query": "test"})

    Attributes:
        name: Identifier for this fallback chain
        backends: Ordered list of backends to try
        enable_local_cache: Whether to use local cache as final fallback
    """

    def __init__(
        self,
        name: str,
        backends: List[FallbackBackend],
        enable_local_cache: bool = True,
    ) -> None:
        """
        Initialize FallbackChain.

        Args:
            name: Name for identification and metrics
            backends: Ordered list of backends to try
            enable_local_cache: Whether to use local cache as final fallback
        """
        self._name = name
        self._backends = backends
        self._enable_local_cache = enable_local_cache

        # Create circuit breaker per backend
        self._circuit_breakers: Dict[str, CircuitBreakerStateMachine] = {}
        for backend in backends:
            self._circuit_breakers[backend.name] = CircuitBreakerStateMachine(
                name=f"{name}-{backend.name}",
                failure_threshold=backend.failure_threshold,
                reset_timeout_seconds=backend.reset_timeout_seconds,
            )

        # Local cache for final fallback
        self._local_cache: Dict[str, Any] = {}

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "FallbackChain":
        """
        Create FallbackChain from configuration dictionary.

        Args:
            config: Configuration dict with name, backends, enable_local_cache

        Returns:
            Configured FallbackChain instance
        """
        name = config.get(CONFIG_KEY_NAME, "fallback-chain")
        enable_cache = config.get(CONFIG_KEY_ENABLE_CACHE, True)

        backends = []
        for backend_config in config.get(CONFIG_KEY_BACKENDS, []):
            backends.append(
                FallbackBackend(
                    name=backend_config.get(CONFIG_KEY_NAME, "unknown"),
                    url=backend_config.get(CONFIG_KEY_URL, "http://localhost"),
                    timeout=backend_config.get(CONFIG_KEY_TIMEOUT, DEFAULT_TIMEOUT_SECONDS),
                    failure_threshold=backend_config.get(
                        "failure_threshold", DEFAULT_FAILURE_THRESHOLD
                    ),
                    reset_timeout_seconds=backend_config.get(
                        "reset_timeout_seconds", DEFAULT_RESET_TIMEOUT_SECONDS
                    ),
                )
            )

        return cls(name=name, backends=backends, enable_local_cache=enable_cache)

    @classmethod
    def create_search_chain(
        cls,
        semantic_search_url: str = "http://localhost:8081",
        code_orchestrator_url: str = "http://localhost:8083",
    ) -> "FallbackChain":
        """
        Create pre-configured search fallback chain.

        AC-CPA3.3: Gateway → semantic-search → Code-Orchestrator → cache

        Args:
            semantic_search_url: URL for semantic-search service
            code_orchestrator_url: URL for Code-Orchestrator service

        Returns:
            Search fallback chain with standard configuration
        """
        backends = [
            FallbackBackend(
                name=BACKEND_SEMANTIC_SEARCH,
                url=semantic_search_url,
            ),
            FallbackBackend(
                name=BACKEND_CODE_ORCHESTRATOR,
                url=code_orchestrator_url,
            ),
        ]

        return cls(
            name="search-fallback",
            backends=backends,
            enable_local_cache=True,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Name of this fallback chain."""
        return self._name

    @property
    def backends(self) -> List[FallbackBackend]:
        """Ordered list of backends."""
        return self._backends

    @property
    def enable_local_cache(self) -> bool:
        """Whether local cache is enabled as final fallback."""
        return self._enable_local_cache

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute(
        self,
        operation: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute operation through the fallback chain.

        Tries each backend in order until one succeeds. If all backends
        fail and local cache is enabled, returns cached result if available.

        Args:
            operation: Operation name (search, embed, etc.)
            payload: Request payload

        Returns:
            Result from successful backend or cache

        Raises:
            FallbackChainError: If all backends fail and no cache available
        """
        backend_errors: Dict[str, str] = {}

        for backend in self._backends:
            cb = self._circuit_breakers[backend.name]

            # Check if circuit is open
            current_state = await cb.get_state()
            if current_state == CircuitBreakerState.OPEN:
                logger.debug(
                    f"Skipping {backend.name} - circuit open",
                    extra={"chain": self._name, "backend": backend.name},
                )
                backend_errors[backend.name] = "Circuit breaker open"
                continue

            # Record attempt metric
            record_fallback_attempt(self._name, backend.name, operation)

            try:
                result = await self._call_backend(backend, operation, payload)

                # Record success
                await cb.record_success()
                record_fallback_success(self._name, backend.name)

                # Update cache
                if self._enable_local_cache:
                    cache_key = self._get_cache_key(operation, payload)
                    self._local_cache[cache_key] = result

                return result

            except Exception as e:
                logger.warning(
                    f"Backend {backend.name} failed: {e}",
                    extra={"chain": self._name, "backend": backend.name},
                )
                await cb.record_failure()
                backend_errors[backend.name] = str(e)

        # All backends failed - try cache
        if self._enable_local_cache:
            cache_key = self._get_cache_key(operation, payload)
            cached_result = self._local_cache.get(cache_key)
            if cached_result is not None:
                logger.info(
                    f"Using cached result for {operation}",
                    extra={"chain": self._name, "cache_key": cache_key},
                )
                return cached_result

        # All backends and cache failed
        raise FallbackChainError(
            chain_name=self._name,
            message=f"All backends failed for operation '{operation}'",
            backend_errors=backend_errors,
        )

    async def _call_backend(
        self,
        backend: FallbackBackend,
        operation: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Make HTTP request to backend.

        Args:
            backend: Backend configuration
            operation: Operation name (maps to endpoint)
            payload: Request payload

        Returns:
            JSON response from backend

        Raises:
            httpx.HTTPError: On network or HTTP errors
        """
        endpoint = self._get_endpoint(backend, operation)

        async with httpx.AsyncClient(timeout=backend.timeout) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()

    def _get_endpoint(self, backend: FallbackBackend, operation: str) -> str:
        """
        Get endpoint URL for operation.

        Args:
            backend: Backend configuration
            operation: Operation name

        Returns:
            Full endpoint URL
        """
        # Map operation to endpoint path
        operation_paths = {
            "search": "/v1/search",
            "hybrid_search": "/v1/hybrid",
            "embed": "/v1/embeddings",
            "similarity": "/v1/similarity",
            "keywords": "/v1/keywords",
        }

        path = operation_paths.get(operation, f"/v1/{operation}")
        return f"{backend.url.rstrip('/')}{path}"

    def _get_cache_key(self, operation: str, payload: Dict[str, Any]) -> str:
        """
        Generate deterministic cache key for operation and payload.

        Args:
            operation: Operation name
            payload: Request payload

        Returns:
            Cache key string
        """
        # Sort payload keys for deterministic serialization
        payload_str = json.dumps(payload, sort_keys=True)
        combined = f"{operation}:{payload_str}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
