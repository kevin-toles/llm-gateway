"""
Tests for Issue 27 Resolution - Real ChatService Wiring

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- Comp_Static_Analysis_Report_20251203.md: Issue 27 "Duplicate ChatService Stub"
- ARCHITECTURE.md: Lines 61-65 - services/chat.py integration
- CODING_PATTERNS_ANALYSIS.md: Dependency injection patterns
- GUIDELINES pp. 89-91: FastAPI dependency injection (Sinha)
- GUIDELINES pp. 157: FakeRepository pattern for test doubles

WBS Context:
- Issue 27 Resolution: Wire get_chat_service() to real ChatService
- Requires: ProviderRouter, ToolExecutor dependencies
- Goal: Replace stub responses with actual LLM provider routing

Anti-Patterns Being Fixed:
- Issue 27: Duplicate ChatService stub in routes vs services
- Violation of DRY principle (two ChatService implementations)
- Stub breaks real LLM integration in POC

Test Strategy:
- Verify get_chat_service() returns real ChatService from src/services/chat.py
- Verify real ChatService has provider routing capability
- Verify integration through dependency injection
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# Issue 27 RED Phase Tests: Real ChatService Wiring
# =============================================================================


class TestIssue27RealChatServiceWiring:
    """
    Tests for Issue 27: Replace stub ChatService with real implementation.
    
    Reference: Comp_Static_Analysis_Report_20251203.md
    - Issue 27: "Duplicate ChatService Stub"
    - Status: OPEN - requires proper resolution via TDD
    
    Acceptance Criteria:
    1. get_chat_service() must return instance of src/services/chat.ChatService
    2. Real ChatService must receive ProviderRouter dependency
    3. Real ChatService must receive ToolExecutor dependency
    4. Provider routing must work based on model prefix
    """

    def test_get_chat_service_returns_real_service_type(self) -> None:
        """
        Issue 27: get_chat_service() must return real ChatService.
        
        The real ChatService is in src/services/chat.py, not the stub
        in src/api/routes/chat.py.
        
        Pattern: Dependency injection factory (Sinha p. 90)
        """
        from src.api.routes.chat import get_chat_service
        from src.services.chat import ChatService as RealChatService
        
        # Reset any cached service
        import src.api.routes.chat as chat_module
        chat_module._chat_service = None
        
        service = get_chat_service()
        
        assert isinstance(service, RealChatService), (
            f"get_chat_service() should return src/services/chat.ChatService, "
            f"not {type(service).__module__}.{type(service).__name__}"
        )

    def test_real_chat_service_has_provider_router(self) -> None:
        """
        Issue 27: Real ChatService must have ProviderRouter.
        
        The ProviderRouter enables model-based provider selection.
        
        Reference: ARCHITECTURE.md - Provider routing
        """
        from src.api.routes.chat import get_chat_service
        from src.providers.router import ProviderRouter
        
        # Reset any cached service
        import src.api.routes.chat as chat_module
        chat_module._chat_service = None
        
        service = get_chat_service()
        
        assert hasattr(service, '_router'), (
            "Real ChatService must have _router attribute"
        )
        assert isinstance(service._router, ProviderRouter), (
            f"_router must be ProviderRouter, not {type(service._router)}"
        )

    def test_real_chat_service_has_tool_executor(self) -> None:
        """
        Issue 27: Real ChatService must have ToolExecutor.
        
        The ToolExecutor enables function/tool calling capability.
        
        Reference: GUIDELINES pp. 1463-1587 - Tool/function calling
        """
        from src.api.routes.chat import get_chat_service
        from src.tools.executor import ToolExecutor
        
        # Reset any cached service
        import src.api.routes.chat as chat_module
        chat_module._chat_service = None
        
        service = get_chat_service()
        
        assert hasattr(service, '_executor'), (
            "Real ChatService must have _executor attribute"
        )
        assert isinstance(service._executor, ToolExecutor), (
            f"_executor must be ToolExecutor, not {type(service._executor)}"
        )

    def test_real_chat_service_complete_method_exists(self) -> None:
        """
        Issue 27: Real ChatService must have complete() method.
        
        Note: Real ChatService uses complete(), not create_completion().
        This is the correct method name per src/services/chat.py.
        
        Reference: src/services/chat.py - ChatService.complete()
        """
        from src.api.routes.chat import get_chat_service
        
        # Reset any cached service
        import src.api.routes.chat as chat_module
        chat_module._chat_service = None
        
        service = get_chat_service()
        
        assert hasattr(service, 'complete'), (
            "Real ChatService must have complete() method"
        )
        assert callable(service.complete), (
            "complete must be callable"
        )


class TestIssue27ProviderRouting:
    """
    Tests for provider routing through real ChatService.
    
    Validates that the wiring enables actual LLM provider selection.
    """

    @pytest.mark.asyncio
    async def test_complete_routes_to_provider(
        self, mock_provider_router: MagicMock, mock_tool_executor: MagicMock
    ) -> None:
        """
        Issue 27: complete() must route to appropriate provider.
        
        Pattern: Provider routing (ARCHITECTURE.md)
        """
        from src.services.chat import ChatService
        from src.models.requests import ChatCompletionRequest, Message
        from src.models.responses import (
            ChatCompletionResponse, Choice, ChoiceMessage, Usage
        )
        
        # Setup mock provider response
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=ChatCompletionResponse(
            id="chatcmpl-test",
            object="chat.completion",
            created=1234567890,
            model="claude-3-sonnet",
            choices=[Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Real response"),
                finish_reason="stop"
            )],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        ))
        mock_provider_router.get_provider.return_value = mock_provider
        
        service = ChatService(
            router=mock_provider_router,
            executor=mock_tool_executor,
        )
        
        request = ChatCompletionRequest(
            model="claude-3-sonnet",
            messages=[Message(role="user", content="Hello")]
        )
        
        response = await service.complete(request)
        
        # Verify provider was looked up
        mock_provider_router.get_provider.assert_called_once_with("claude-3-sonnet")
        
        # Verify provider.complete was called
        mock_provider.complete.assert_called_once()
        
        # Verify response is from provider, not stub
        assert response.choices[0].message.content == "Real response"
        assert "stub" not in response.choices[0].message.content.lower()


class TestIssue27BackwardsCompatibility:
    """
    Tests ensuring backwards compatibility during migration.
    
    The endpoint contract must remain unchanged.
    """

    def test_endpoint_still_returns_valid_response(
        self, client: TestClient, mock_provider_router: MagicMock, mock_tool_executor: MagicMock
    ) -> None:
        """
        Issue 27: Endpoint must still return OpenAI-compatible response.
        
        Pattern: OpenAI API compatibility (ARCHITECTURE.md)
        """
        from src.models.responses import (
            ChatCompletionResponse, Choice, ChoiceMessage, Usage
        )
        
        # Setup mock provider
        mock_provider = AsyncMock()
        mock_response = ChatCompletionResponse(
            id="chatcmpl-real",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            choices=[Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Real GPT-4 response"),
                finish_reason="stop"
            )],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        mock_provider.complete = AsyncMock(return_value=mock_response)
        mock_provider_router.get_provider.return_value = mock_provider
        
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        
        response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # OpenAI-compatible response structure
        assert "id" in data
        assert data["object"] == "chat.completion"
        assert "choices" in data
        assert "usage" in data


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_provider_router():
    """
    Mock ProviderRouter for testing Issue 27 wiring.
    
    Pattern: FakeRepository (GUIDELINES p. 157)
    """
    from src.providers.router import ProviderRouter
    
    router = MagicMock(spec=ProviderRouter)
    router.get_provider = MagicMock()
    router.list_available_models = MagicMock(return_value=[])
    return router


@pytest.fixture
def mock_tool_executor():
    """
    Mock ToolExecutor for testing Issue 27 wiring.
    
    Pattern: FakeRepository (GUIDELINES p. 157)
    """
    from src.tools.executor import ToolExecutor
    
    executor = MagicMock(spec=ToolExecutor)
    executor.execute = AsyncMock()
    executor.execute_batch = AsyncMock()
    return executor


@pytest.fixture
def client(mock_provider_router, mock_tool_executor):
    """
    Test client with real ChatService wiring (mocked dependencies).
    
    Pattern: Test isolation with dependency injection
    """
    from fastapi import FastAPI
    from src.api.routes.chat import router as chat_router, get_chat_service
    from src.services.chat import ChatService
    
    # Create real ChatService with mocked dependencies
    real_service = ChatService(
        router=mock_provider_router,
        executor=mock_tool_executor,
    )
    
    # Override the dependency
    def override_get_chat_service():
        return real_service
    
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_chat_service] = override_get_chat_service
    
    return TestClient(app)
