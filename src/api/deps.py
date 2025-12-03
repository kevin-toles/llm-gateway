"""
API Dependencies - WBS 2.2.6.1

This module provides FastAPI dependency injection functions for the API layer.

Reference Documents:
- ARCHITECTURE.md line 31: deps.py - FastAPI dependencies
- GUIDELINES: Sinha pp. 89-91 (Dependency injection patterns)
- ANTI_PATTERN_ANALYSIS: §4.1 Extract to service class

WBS Items:
- 2.2.6.1.1: Create src/api/deps.py
- 2.2.6.1.2: Implement get_settings dependency
- 2.2.6.1.3: Implement get_redis dependency
- 2.2.6.1.4: Implement get_chat_service dependency
- 2.2.6.1.5: Implement get_session_manager dependency
- 2.2.6.1.6: Implement get_tool_executor dependency

Pattern: Centralized dependency injection following FastAPI best practices.
All dependencies are designed as factory functions that can be overridden
in tests using FastAPI's dependency_overrides mechanism.
"""

import logging
from typing import Optional, Any

from src.core.config import Settings, get_settings as _get_settings


# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# WBS 2.2.6.1.2: get_settings Dependency
# Pattern: Re-export from core.config for API layer
# =============================================================================


def get_settings() -> Settings:
    """
    Get application settings.

    WBS 2.2.6.1.2: Implement get_settings dependency.

    Pattern: Singleton with @lru_cache (from core.config)

    Returns:
        Settings: Application settings instance
    """
    return _get_settings()


# =============================================================================
# WBS 2.2.6.1.3: get_redis Dependency
# Pattern: Async factory for Redis connection
# =============================================================================


async def get_redis() -> Optional[Any]:
    """
    Get Redis client connection.

    WBS 2.2.6.1.3: Implement get_redis dependency.

    Pattern: Lazy initialization with graceful degradation

    Returns:
        Redis client or None if unavailable

    Note: This is a stub implementation. Full Redis integration
    will be implemented in WBS 2.3 (Sessions Module) with proper
    connection pooling and health checks.
    """
    settings = get_settings()

    try:
        # Attempt to import redis (optional dependency)
        import redis.asyncio as redis

        client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        # Test connection
        await client.ping()
        return client

    except ImportError:
        logger.warning("redis package not installed, Redis features disabled")
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        return None


# =============================================================================
# WBS 2.2.6.1.4: get_chat_service Dependency
# Pattern: Factory function for service layer
# =============================================================================


def get_chat_service():
    """
    Get ChatService instance.

    WBS 2.2.6.1.4: Implement get_chat_service dependency.

    Pattern: Factory function for DI (Sinha p. 90)

    Returns:
        ChatService: Chat service instance
    """
    from src.api.routes.chat import ChatService, get_chat_service as _get_chat_service

    return _get_chat_service()


# =============================================================================
# WBS 2.2.6.1.5: get_session_manager Dependency
# Pattern: Factory function for session management
# =============================================================================


def get_session_manager():
    """
    Get SessionService instance.

    WBS 2.2.6.1.5: Implement get_session_manager dependency.

    Pattern: Factory function for DI (Sinha p. 90)

    Returns:
        SessionService: Session service instance
    """
    from src.api.routes.sessions import SessionService, get_session_service

    return get_session_service()


# =============================================================================
# WBS 2.2.6.1.6: get_tool_executor Dependency
# Pattern: Factory function for tool execution
# =============================================================================


def get_tool_executor():
    """
    Get ToolExecutorService instance.

    WBS 2.2.6.1.6: Implement get_tool_executor dependency.

    Pattern: Factory function for DI (Sinha p. 90)

    Returns:
        ToolExecutorService: Tool executor service instance
    """
    from src.api.routes.tools import (
        ToolExecutorService,
        get_tool_executor as _get_tool_executor,
    )

    return _get_tool_executor()


# =============================================================================
# Convenience Re-exports
# =============================================================================

__all__ = [
    "get_settings",
    "get_redis",
    "get_chat_service",
    "get_session_manager",
    "get_tool_executor",
]
