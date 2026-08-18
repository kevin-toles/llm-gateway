"""
Tests for Provider Base Interface - WBS 2.3.1.1 Abstract Provider Class

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Lines 38-44 - providers/ folder structure
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES p. 953: @abstractmethod decorator usage
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Test Categories:
- Abstract class instantiation behavior (2.3.1.1.9)
- Interface method signatures (2.3.1.1.4-7)
- Concrete implementation validation (2.3.1.1.10)
"""

import pytest
from abc import ABC
from typing import AsyncIterator

from src.models.requests import ChatCompletionRequest, Message
from src.models.responses import ChatCompletionResponse


# =============================================================================
# WBS 2.3.1.1.9: Test abstract class cannot be instantiated
# =============================================================================


class TestLLMProviderAbstractClass:
    """Tests for LLMProvider ABC instantiation behavior."""

    def test_llm_provider_cannot_be_instantiated_directly(self) -> None:
        """
        WBS 2.3.1.1.9: Abstract class cannot be instantiated.

        Pattern: ABC enforcement (GUIDELINES p. 953)
        """
        from src.providers.base import LLMProvider

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            LLMProvider()  # type: ignore[abstract]

    def test_llm_provider_is_abstract_base_class(self) -> None:
        """
        WBS 2.3.1.1.3: LLMProvider is an ABC.

        Pattern: ABC pattern (GUIDELINES pp. 793-795)
        """
        from src.providers.base import LLMProvider

        assert issubclass(LLMProvider, ABC)

    def test_llm_provider_has_complete_abstract_method(self) -> None:
        """
        WBS 2.3.1.1.4: Define async def complete().

        Pattern: @abstractmethod decorator (GUIDELINES p. 953)
        """
        from src.providers.base import LLMProvider

        assert hasattr(LLMProvider, "complete")
        assert getattr(LLMProvider.complete, "__isabstractmethod__", False)

    def test_llm_provider_has_stream_abstract_method(self) -> None:
        """
        WBS 2.3.1.1.5: Define async def stream().

        Pattern: Iterator protocol (GUIDELINES p. 2149)
        """
        from src.providers.base import LLMProvider

        assert hasattr(LLMProvider, "stream")
        assert getattr(LLMProvider.stream, "__isabstractmethod__", False)

    def test_llm_provider_has_supports_model_abstract_method(self) -> None:
        """
        WBS 2.3.1.1.6: Define supports_model().

        Pattern: Adapter pattern for provider routing
        """
        from src.providers.base import LLMProvider

        assert hasattr(LLMProvider, "supports_model")
        assert getattr(LLMProvider.supports_model, "__isabstractmethod__", False)

    def test_llm_provider_has_get_supported_models_abstract_method(self) -> None:
        """
        WBS 2.3.1.1.7: Define get_supported_models().

        Pattern: Adapter pattern for provider discovery
        """
        from src.providers.base import LLMProvider

        assert hasattr(LLMProvider, "get_supported_models")
        assert getattr(LLMProvider.get_supported_models, "__isabstractmethod__", False)


# =============================================================================
# WBS 2.3.1.1.10: Test concrete implementation behavior
# =============================================================================


class TestLLMProviderConcreteImplementation:
    """Tests for concrete LLMProvider implementations."""

    def test_incomplete_implementation_raises_type_error(self) -> None:
        """
        WBS 2.3.1.1.10: Incomplete implementation cannot be instantiated.

        Pattern: ABC enforcement ensures all abstract methods implemented.
        """
        from src.providers.base import LLMProvider

        class IncompleteProvider(LLMProvider):
            """Provider missing required implementations."""

            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()  # type: ignore[abstract]

    def test_partial_implementation_raises_type_error(self) -> None:
        """
        WBS 2.3.1.1.10: Partial implementation cannot be instantiated.

        Only implementing some methods should still raise TypeError.
        """
        from src.providers.base import LLMProvider

        class PartialProvider(LLMProvider):
            """Provider with only some methods implemented."""

            def supports_model(self, model: str) -> bool:
                return model == "test-model"

            def get_supported_models(self) -> list[str]:
                return ["test-model"]

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialProvider()  # type: ignore[abstract]

    def test_complete_implementation_can_be_instantiated(self) -> None:
        """
        WBS 2.3.1.1.10: Complete implementation can be instantiated.

        Pattern: Concrete adapter implements all ABC methods.
        """
        from src.providers.base import LLMProvider

        class CompleteProvider(LLMProvider):
            """Fully implemented provider for testing."""

            async def complete(
                self, request: ChatCompletionRequest
            ) -> ChatCompletionResponse:
                # Stub implementation
                from src.models.responses import (
                    ChatCompletionResponse,
                    Choice,
                    ChoiceMessage,
                    Usage,
                )
                import time

                return ChatCompletionResponse(
                    id="test-id",
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        Choice(
                            index=0,
                            message=ChoiceMessage(role="assistant", content="Test"),
                            finish_reason="stop",
                        )
                    ],
                    usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                )

            async def stream(
                self, request: ChatCompletionRequest
            ) -> AsyncIterator:
                # Stub implementation - yield nothing
                return
                yield  # Makes this a generator

            def supports_model(self, model: str) -> bool:
                return model == "test-model"

            def get_supported_models(self) -> list[str]:
                return ["test-model"]

        # Should not raise
        provider = CompleteProvider()
        assert provider is not None
        assert isinstance(provider, LLMProvider)


# =============================================================================
# Interface Contract Tests
# =============================================================================


class TestLLMProviderInterfaceContract:
    """Tests for LLMProvider interface contract."""

    def test_complete_method_signature_accepts_chat_request(self) -> None:
        """
        WBS 2.3.1.1.4: complete() accepts ChatCompletionRequest.

        Pattern: Type-safe interface (Pydantic models from requests.py)
        """
        from src.providers.base import LLMProvider
        import inspect

        sig = inspect.signature(LLMProvider.complete)
        params = list(sig.parameters.keys())

        # Should have 'self' and 'request' parameters
        assert "self" in params
        assert "request" in params

    def test_stream_method_signature_accepts_chat_request(self) -> None:
        """
        WBS 2.3.1.1.5: stream() accepts ChatCompletionRequest.

        Pattern: Iterator protocol (GUIDELINES p. 2149)
        """
        from src.providers.base import LLMProvider
        import inspect

        sig = inspect.signature(LLMProvider.stream)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "request" in params

    def test_supports_model_signature_accepts_string(self) -> None:
        """
        WBS 2.3.1.1.6: supports_model() accepts model string.

        Pattern: Simple predicate for provider routing.
        """
        from src.providers.base import LLMProvider
        import inspect

        sig = inspect.signature(LLMProvider.supports_model)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "model" in params

    def test_get_supported_models_returns_list(self) -> None:
        """
        WBS 2.3.1.1.7: get_supported_models() returns list[str].

        Pattern: Provider discovery for routing.
        """
        from src.providers.base import LLMProvider
        import inspect

        # Get the type hints
        hints = getattr(LLMProvider.get_supported_models, "__annotations__", {})
        # The return annotation should be present
        assert "return" in hints or hasattr(
            LLMProvider.get_supported_models, "__wrapped__"
        )


# =============================================================================
# Documentation Tests
# =============================================================================


class TestLLMProviderDocumentation:
    """Tests for LLMProvider documentation (WBS 2.3.1.1.8)."""

    def test_llm_provider_has_docstring(self) -> None:
        """
        WBS 2.3.1.1.8: Write interface documentation.

        Pattern: Docstrings as living documentation.
        """
        from src.providers.base import LLMProvider

        assert LLMProvider.__doc__ is not None
        assert len(LLMProvider.__doc__) > 50  # Non-trivial docstring

    def test_complete_method_has_docstring(self) -> None:
        """
        WBS 2.3.1.1.8: complete() has documentation.
        """
        from src.providers.base import LLMProvider

        assert LLMProvider.complete.__doc__ is not None

    def test_stream_method_has_docstring(self) -> None:
        """
        WBS 2.3.1.1.8: stream() has documentation.
        """
        from src.providers.base import LLMProvider

        assert LLMProvider.stream.__doc__ is not None

    def test_supports_model_method_has_docstring(self) -> None:
        """
        WBS 2.3.1.1.8: supports_model() has documentation.
        """
        from src.providers.base import LLMProvider

        assert LLMProvider.supports_model.__doc__ is not None

    def test_get_supported_models_method_has_docstring(self) -> None:
        """
        WBS 2.3.1.1.8: get_supported_models() has documentation.
        """
        from src.providers.base import LLMProvider

        assert LLMProvider.get_supported_models.__doc__ is not None

