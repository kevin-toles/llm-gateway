"""
Unit tests for src/core/exceptions.py - Custom Exception Classes.

WBS 2.1.2.3: Custom Exceptions

TDD Approach: RED tests - all tests should fail initially.

Reference:
- ANTI_PATTERN_ANALYSIS.md: Exception handling patterns
- GUIDELINES: Specific exceptions, always capture with 'as e'
"""


# =============================================================================
# WBS 2.1.2.3.1: Exceptions Module
# =============================================================================


class TestExceptionsModuleExists:
    """Tests for WBS 2.1.2.3.1: Create src/core/exceptions.py."""

    def test_exceptions_module_exists(self):
        """
        WBS 2.1.2.3.1: Create src/core/exceptions.py.
        
        Verifies the exceptions module can be imported.
        """
        from src.core import exceptions

        assert exceptions is not None


# =============================================================================
# WBS 2.1.2.3.2: Base Exception
# =============================================================================


class TestLLMGatewayException:
    """Tests for WBS 2.1.2.3.2: LLMGatewayException base class."""

    def test_base_exception_exists(self):
        """
        WBS 2.1.2.3.2: Implement LLMGatewayException base class.
        """
        from src.core.exceptions import LLMGatewayException

        assert LLMGatewayException is not None

    def test_base_exception_inherits_from_exception(self):
        """
        LLMGatewayException should inherit from Exception.
        """
        from src.core.exceptions import LLMGatewayException

        assert issubclass(LLMGatewayException, Exception)

    def test_base_exception_has_message(self):
        """
        LLMGatewayException should accept a message.
        """
        from src.core.exceptions import LLMGatewayException

        exc = LLMGatewayException("test message")
        assert str(exc) == "test message"

    def test_base_exception_has_error_code(self):
        """
        LLMGatewayException should have an error_code attribute.
        """
        from src.core.exceptions import LLMGatewayException

        exc = LLMGatewayException("test", error_code="GATEWAY_ERROR")
        assert exc.error_code == "GATEWAY_ERROR"

    def test_base_exception_has_default_error_code(self):
        """
        LLMGatewayException should have a default error_code.
        """
        from src.core.exceptions import LLMGatewayException

        exc = LLMGatewayException("test")
        assert exc.error_code is not None


# =============================================================================
# WBS 2.1.2.3.3: ProviderError
# =============================================================================


class TestProviderError:
    """Tests for WBS 2.1.2.3.3: ProviderError for LLM provider issues."""

    def test_provider_error_exists(self):
        """
        WBS 2.1.2.3.3: Implement ProviderError.
        """
        from src.core.exceptions import ProviderError

        assert ProviderError is not None

    def test_provider_error_inherits_from_base(self):
        """
        ProviderError should inherit from LLMGatewayException.
        """
        from src.core.exceptions import LLMGatewayException, ProviderError

        assert issubclass(ProviderError, LLMGatewayException)

    def test_provider_error_has_provider_name(self):
        """
        ProviderError should have a provider attribute.
        """
        from src.core.exceptions import ProviderError

        exc = ProviderError("API error", provider="anthropic")
        assert exc.provider == "anthropic"

    def test_provider_error_has_status_code(self):
        """
        ProviderError should have an optional status_code.
        """
        from src.core.exceptions import ProviderError

        exc = ProviderError("Rate limited", provider="openai", status_code=429)
        assert exc.status_code == 429

    def test_provider_error_default_error_code(self):
        """
        ProviderError should have PROVIDER_ERROR as default code.
        """
        from src.core.exceptions import ProviderError

        exc = ProviderError("test", provider="test")
        assert exc.error_code == "PROVIDER_ERROR"


# =============================================================================
# WBS 2.1.2.3.4: SessionError
# =============================================================================


class TestSessionError:
    """Tests for WBS 2.1.2.3.4: SessionError for session management issues."""

    def test_session_error_exists(self):
        """
        WBS 2.1.2.3.4: Implement SessionError.
        """
        from src.core.exceptions import SessionError

        assert SessionError is not None

    def test_session_error_inherits_from_base(self):
        """
        SessionError should inherit from LLMGatewayException.
        """
        from src.core.exceptions import LLMGatewayException, SessionError

        assert issubclass(SessionError, LLMGatewayException)

    def test_session_error_has_session_id(self):
        """
        SessionError should have a session_id attribute.
        """
        from src.core.exceptions import SessionError

        exc = SessionError("Session not found", session_id="sess_123")
        assert exc.session_id == "sess_123"

    def test_session_error_default_error_code(self):
        """
        SessionError should have SESSION_ERROR as default code.
        """
        from src.core.exceptions import SessionError

        exc = SessionError("test")
        assert exc.error_code == "SESSION_ERROR"


# =============================================================================
# WBS 2.1.2.3.5: ToolExecutionError
# =============================================================================


class TestToolExecutionError:
    """Tests for WBS 2.1.2.3.5: ToolExecutionError for tool failures."""

    def test_tool_execution_error_exists(self):
        """
        WBS 2.1.2.3.5: Implement ToolExecutionError.
        """
        from src.core.exceptions import ToolExecutionError

        assert ToolExecutionError is not None

    def test_tool_execution_error_inherits_from_base(self):
        """
        ToolExecutionError should inherit from LLMGatewayException.
        """
        from src.core.exceptions import LLMGatewayException, ToolExecutionError

        assert issubclass(ToolExecutionError, LLMGatewayException)

    def test_tool_execution_error_has_tool_name(self):
        """
        ToolExecutionError should have a tool_name attribute.
        """
        from src.core.exceptions import ToolExecutionError

        exc = ToolExecutionError("Tool failed", tool_name="search_corpus")
        assert exc.tool_name == "search_corpus"

    def test_tool_execution_error_has_tool_call_id(self):
        """
        ToolExecutionError should have a tool_call_id attribute.
        """
        from src.core.exceptions import ToolExecutionError

        exc = ToolExecutionError("Tool failed", tool_name="test", tool_call_id="call_123")
        assert exc.tool_call_id == "call_123"

    def test_tool_execution_error_default_error_code(self):
        """
        ToolExecutionError should have TOOL_EXECUTION_ERROR as default code.
        """
        from src.core.exceptions import ToolExecutionError

        exc = ToolExecutionError("test", tool_name="test")
        assert exc.error_code == "TOOL_EXECUTION_ERROR"


# =============================================================================
# WBS 2.1.2.3.6: RateLimitError
# =============================================================================


class TestRateLimitError:
    """Tests for WBS 2.1.2.3.6: RateLimitError for rate limiting."""

    def test_rate_limit_error_exists(self):
        """
        WBS 2.1.2.3.6: Implement RateLimitError.
        """
        from src.core.exceptions import RateLimitError

        assert RateLimitError is not None

    def test_rate_limit_error_inherits_from_base(self):
        """
        RateLimitError should inherit from LLMGatewayException.
        """
        from src.core.exceptions import LLMGatewayException, RateLimitError

        assert issubclass(RateLimitError, LLMGatewayException)

    def test_rate_limit_error_has_retry_after(self):
        """
        RateLimitError should have a retry_after attribute (seconds).
        """
        from src.core.exceptions import RateLimitError

        exc = RateLimitError("Too many requests", retry_after=60)
        assert exc.retry_after == 60

    def test_rate_limit_error_has_limit(self):
        """
        RateLimitError should have a limit attribute.
        """
        from src.core.exceptions import RateLimitError

        exc = RateLimitError("Too many requests", limit=100, retry_after=60)
        assert exc.limit == 100

    def test_rate_limit_error_default_error_code(self):
        """
        RateLimitError should have RATE_LIMIT_ERROR as default code.
        """
        from src.core.exceptions import RateLimitError

        exc = RateLimitError("test")
        assert exc.error_code == "RATE_LIMIT_ERROR"


# =============================================================================
# WBS 2.1.2.3.7: ValidationError
# =============================================================================


class TestGatewayValidationError:
    """Tests for WBS 2.1.2.3.7: ValidationError for request validation."""

    def test_validation_error_exists(self):
        """
        WBS 2.1.2.3.7: Implement ValidationError.
        
        Note: Named GatewayValidationError to avoid conflict with pydantic.
        """
        from src.core.exceptions import GatewayValidationError

        assert GatewayValidationError is not None

    def test_validation_error_inherits_from_base(self):
        """
        GatewayValidationError should inherit from LLMGatewayException.
        """
        from src.core.exceptions import GatewayValidationError, LLMGatewayException

        assert issubclass(GatewayValidationError, LLMGatewayException)

    def test_validation_error_has_field(self):
        """
        GatewayValidationError should have a field attribute.
        """
        from src.core.exceptions import GatewayValidationError

        exc = GatewayValidationError("Invalid model", field="model")
        assert exc.field == "model"

    def test_validation_error_has_value(self):
        """
        GatewayValidationError should have a value attribute.
        """
        from src.core.exceptions import GatewayValidationError

        exc = GatewayValidationError("Invalid model", field="model", value="unknown-model")
        assert exc.value == "unknown-model"

    def test_validation_error_default_error_code(self):
        """
        GatewayValidationError should have VALIDATION_ERROR as default code.
        """
        from src.core.exceptions import GatewayValidationError

        exc = GatewayValidationError("test")
        assert exc.error_code == "VALIDATION_ERROR"


# =============================================================================
# WBS 2.1.2.3.8: Error Codes Enum
# =============================================================================


class TestErrorCodes:
    """Tests for WBS 2.1.2.3.8: Error codes enum."""

    def test_error_codes_enum_exists(self):
        """
        WBS 2.1.2.3.8: Add error codes enum.
        """
        from src.core.exceptions import ErrorCode

        assert ErrorCode is not None

    def test_error_codes_has_gateway_error(self):
        """
        ErrorCode should have GATEWAY_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "GATEWAY_ERROR")

    def test_error_codes_has_provider_error(self):
        """
        ErrorCode should have PROVIDER_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "PROVIDER_ERROR")

    def test_error_codes_has_session_error(self):
        """
        ErrorCode should have SESSION_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "SESSION_ERROR")

    def test_error_codes_has_tool_execution_error(self):
        """
        ErrorCode should have TOOL_EXECUTION_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "TOOL_EXECUTION_ERROR")

    def test_error_codes_has_rate_limit_error(self):
        """
        ErrorCode should have RATE_LIMIT_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "RATE_LIMIT_ERROR")

    def test_error_codes_has_validation_error(self):
        """
        ErrorCode should have VALIDATION_ERROR.
        """
        from src.core.exceptions import ErrorCode

        assert hasattr(ErrorCode, "VALIDATION_ERROR")


# =============================================================================
# Exception Export Tests
# =============================================================================


class TestExceptionExports:
    """Tests for exception exports from src/core/__init__.py."""

    def test_llm_gateway_exception_exported(self):
        """Verify LLMGatewayException is exported from core."""
        from src.core import LLMGatewayException

        assert LLMGatewayException is not None

    def test_provider_error_exported(self):
        """Verify ProviderError is exported from core."""
        from src.core import ProviderError

        assert ProviderError is not None

    def test_session_error_exported(self):
        """Verify SessionError is exported from core."""
        from src.core import SessionError

        assert SessionError is not None

    def test_tool_execution_error_exported(self):
        """Verify ToolExecutionError is exported from core."""
        from src.core import ToolExecutionError

        assert ToolExecutionError is not None

    def test_rate_limit_error_exported(self):
        """Verify RateLimitError is exported from core."""
        from src.core import RateLimitError

        assert RateLimitError is not None

    def test_validation_error_exported(self):
        """Verify GatewayValidationError is exported from core."""
        from src.core import GatewayValidationError

        assert GatewayValidationError is not None

    def test_error_code_exported(self):
        """Verify ErrorCode is exported from core."""
        from src.core import ErrorCode

        assert ErrorCode is not None
