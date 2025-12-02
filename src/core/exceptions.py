"""
Custom exceptions for LLM Gateway.

WBS 2.1.2.3: Custom Exceptions

This module provides a hierarchy of custom exceptions for the LLM Gateway service.
All exceptions inherit from LLMGatewayException and include error codes for 
consistent error handling and API responses.

Reference:
- ANTI_PATTERN_ANALYSIS.md: Exception handling patterns
- GUIDELINES: Specific exceptions, always capture with 'as e'
"""

from enum import Enum
from typing import Any


# =============================================================================
# WBS 2.1.2.3.8: Error Codes Enum
# =============================================================================


class ErrorCode(str, Enum):
    """
    Error codes for LLM Gateway exceptions.
    
    WBS 2.1.2.3.8: Add error codes enum.
    
    These codes provide a consistent way to identify error types
    across the API and in logging.
    """

    GATEWAY_ERROR = "GATEWAY_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    SESSION_ERROR = "SESSION_ERROR"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


# =============================================================================
# WBS 2.1.2.3.2: Base Exception
# =============================================================================


class LLMGatewayException(Exception):
    """
    Base exception for all LLM Gateway errors.
    
    WBS 2.1.2.3.2: Implement LLMGatewayException base class.
    
    All custom exceptions in the gateway inherit from this class,
    providing consistent error handling and structured error information.
    
    Attributes:
        message: Human-readable error message.
        error_code: Machine-readable error code from ErrorCode enum.
    """

    def __init__(
        self,
        message: str,
        error_code: str = ErrorCode.GATEWAY_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message.
            error_code: Machine-readable error code.
            **kwargs: Additional attributes to set on the exception.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        
        # Set any additional attributes from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


# =============================================================================
# WBS 2.1.2.3.3: ProviderError
# =============================================================================


class ProviderError(LLMGatewayException):
    """
    Exception for LLM provider issues.
    
    WBS 2.1.2.3.3: Implement ProviderError for LLM provider issues.
    
    Raised when communication with an LLM provider fails,
    including API errors, timeouts, and authentication issues.
    
    Attributes:
        provider: Name of the provider (e.g., "anthropic", "openai").
        status_code: HTTP status code from the provider API (if applicable).
    """

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        error_code: str = ErrorCode.PROVIDER_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the provider error.
        
        Args:
            message: Human-readable error message.
            provider: Name of the LLM provider.
            status_code: HTTP status code from provider (optional).
            error_code: Machine-readable error code.
            **kwargs: Additional attributes.
        """
        super().__init__(message, error_code, **kwargs)
        self.provider = provider
        self.status_code = status_code


# =============================================================================
# WBS 2.1.2.3.4: SessionError
# =============================================================================


class SessionError(LLMGatewayException):
    """
    Exception for session management issues.
    
    WBS 2.1.2.3.4: Implement SessionError for session management issues.
    
    Raised when session operations fail, including session not found,
    session expired, or Redis connection issues.
    
    Attributes:
        session_id: ID of the affected session (if known).
    """

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        error_code: str = ErrorCode.SESSION_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the session error.
        
        Args:
            message: Human-readable error message.
            session_id: ID of the affected session (optional).
            error_code: Machine-readable error code.
            **kwargs: Additional attributes.
        """
        super().__init__(message, error_code, **kwargs)
        self.session_id = session_id


# =============================================================================
# WBS 2.1.2.3.5: ToolExecutionError
# =============================================================================


class ToolExecutionError(LLMGatewayException):
    """
    Exception for tool execution failures.
    
    WBS 2.1.2.3.5: Implement ToolExecutionError for tool failures.
    
    Raised when a tool fails to execute, including timeout,
    invalid arguments, or downstream service errors.
    
    Attributes:
        tool_name: Name of the tool that failed.
        tool_call_id: ID of the tool call (for correlation).
    """

    def __init__(
        self,
        message: str,
        tool_name: str,
        tool_call_id: str | None = None,
        error_code: str = ErrorCode.TOOL_EXECUTION_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the tool execution error.
        
        Args:
            message: Human-readable error message.
            tool_name: Name of the tool that failed.
            tool_call_id: ID of the tool call (optional).
            error_code: Machine-readable error code.
            **kwargs: Additional attributes.
        """
        super().__init__(message, error_code, **kwargs)
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id


# =============================================================================
# WBS 2.1.2.3.6: RateLimitError
# =============================================================================


class RateLimitError(LLMGatewayException):
    """
    Exception for rate limiting.
    
    WBS 2.1.2.3.6: Implement RateLimitError for rate limiting.
    
    Raised when a client exceeds their rate limit.
    Includes retry information for clients.
    
    Attributes:
        retry_after: Seconds until the rate limit resets.
        limit: The rate limit that was exceeded.
    """

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        limit: int | None = None,
        error_code: str = ErrorCode.RATE_LIMIT_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the rate limit error.
        
        Args:
            message: Human-readable error message.
            retry_after: Seconds until rate limit resets (optional).
            limit: The rate limit that was exceeded (optional).
            error_code: Machine-readable error code.
            **kwargs: Additional attributes.
        """
        super().__init__(message, error_code, **kwargs)
        self.retry_after = retry_after
        self.limit = limit


# =============================================================================
# WBS 2.1.2.3.7: ValidationError
# =============================================================================


class GatewayValidationError(LLMGatewayException):
    """
    Exception for request validation errors.
    
    WBS 2.1.2.3.7: Implement ValidationError for request validation.
    
    Raised when request validation fails beyond Pydantic's built-in
    validation, such as business rule violations.
    
    Note: Named GatewayValidationError to avoid conflict with
    pydantic.ValidationError.
    
    Attributes:
        field: Name of the field that failed validation.
        value: The invalid value (if safe to include).
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        error_code: str = ErrorCode.VALIDATION_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the validation error.
        
        Args:
            message: Human-readable error message.
            field: Name of the invalid field (optional).
            value: The invalid value (optional).
            error_code: Machine-readable error code.
            **kwargs: Additional attributes.
        """
        super().__init__(message, error_code, **kwargs)
        self.field = field
        self.value = value
