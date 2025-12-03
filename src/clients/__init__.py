"""
Clients Package - WBS 2.7.1 HTTP Client Setup

This package provides HTTP client factories and service clients for
communicating with downstream microservices.

Reference Documents:
- ARCHITECTURE.md: Lines 232 - semantic-search-service dependency
- ARCHITECTURE.md: Lines 277 - semantic_search_url configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service
- GUIDELINES pp. 2145: Graceful degradation, circuit breaker patterns

WBS Items:
- 2.7.1.1: HTTP Client Factory
- 2.7.1.2: Semantic Search Client
- 2.7.1.3: AI Agents Client
"""

from src.clients.http import (
    HTTPClientError,
    create_http_client,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT_SECONDS,
)
from src.clients.semantic_search import (
    Chunk,
    ChunkNotFoundError,
    SearchResult,
    SearchResults,
    SemanticSearchClient,
    SemanticSearchError,
)
from src.clients.ai_agents import (
    AIAgentsClient,
    AIAgentsError,
    ToolDefinition,
    ToolNotFoundError,
    ToolResult,
    ToolSchema,
)

__all__ = [
    # HTTP Client Factory
    "HTTPClientError",
    "create_http_client",
    "DEFAULT_MAX_CONNECTIONS",
    "DEFAULT_MAX_KEEPALIVE",
    "DEFAULT_RETRY_COUNT",
    "DEFAULT_TIMEOUT_SECONDS",
    # Semantic Search Client
    "Chunk",
    "ChunkNotFoundError",
    "SearchResult",
    "SearchResults",
    "SemanticSearchClient",
    "SemanticSearchError",
    # AI Agents Client
    "AIAgentsClient",
    "AIAgentsError",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolResult",
    "ToolSchema",
]
