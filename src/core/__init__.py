"""
Core module for LLM Gateway.

This module contains configuration, exceptions, and shared utilities.

WBS 2.1.2: Core Configuration Module
- 2.1.2.1: Settings Class Implementation
- 2.1.2.2: Settings Singleton
- 2.1.2.3: Custom Exceptions
"""

from src.core.config import Settings, get_settings
from src.core.exceptions import (
    ErrorCode,
    GatewayValidationError,
    LLMGatewayException,
    ProviderError,
    RateLimitError,
    SessionError,
    ToolExecutionError,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "ErrorCode",
    "LLMGatewayException",
    "ProviderError",
    "SessionError",
    "ToolExecutionError",
    "RateLimitError",
    "GatewayValidationError",
]

