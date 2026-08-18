"""
Fake LLM Provider - Test Double Implementation

This module provides a FakeProvider that implements the real LLMProvider interface
without making network calls. This follows the FakeRepository pattern from
GUIDELINES p. 157.

Pattern: Test Doubles using duck typing (GUIDELINES pp. 157)
"Python's duck typing enables test doubles without complex mocking frameworks"

This is NOT mocking - it's a proper implementation of the interface for testing.
The FakeProvider can be used in production for:
- Local development without API keys
- Integration testing without network calls
- Demo/sandbox environments

Reference:
- GUIDELINES pp. 157: FakeRepository pattern
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
"""

import time
import uuid
from typing import AsyncIterator

from src.models.requests import ChatCompletionRequest
from src.models.responses import (
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    ChoiceMessage,
    Usage,
    ChunkChoice,
    ChunkDelta,
)
from src.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    """
    Fake LLM provider for testing and local development.
    
    Implements the full LLMProvider interface with deterministic responses.
    This is a proper test double, not a mock - it has real behavior.
    
    Pattern: FakeRepository (GUIDELINES p. 157)
    
    Attributes:
        name: Provider identifier
        supported_models: List of model names this provider claims to support
        response_content: Default content to return in completions
        error_on_complete: Optional exception to raise on complete() calls
        
    Example:
        >>> provider = FakeProvider()
        >>> response = await provider.complete(request)
        >>> assert response.choices[0].message.content == "Fake response for testing"
        
        # For error testing:
        >>> from src.core.exceptions import ProviderError
        >>> provider = FakeProvider(error_on_complete=ProviderError(...))
        >>> await provider.complete(request)  # Raises ProviderError
    """
    
    def __init__(
        self,
        name: str = "fake",
        supported_models: list[str] | None = None,
        response_content: str = "Fake response for testing",
        error_on_complete: Exception | None = None,
    ) -> None:
        """
        Initialize the fake provider.
        
        Args:
            name: Provider identifier (default: "fake")
            supported_models: Models to support (default: common test models)
            response_content: Content to return in responses
            error_on_complete: Exception to raise on complete() calls (for error testing)
        """
        self.name = name
        self.supported_models = supported_models or [
            "fake-model",
            "test-model",
            "gpt-4",  # Support common model names for testing
            "claude-3-sonnet",
            "claude-3-sonnet-20240229",
        ]
        self.response_content = response_content
        self.error_on_complete = error_on_complete
        
        # Track calls for test assertions
        self.complete_calls: list[ChatCompletionRequest] = []
        self.stream_calls: list[ChatCompletionRequest] = []
    
    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Generate a fake chat completion response.
        
        Returns a deterministic response structure matching the real API format.
        
        Args:
            request: The chat completion request
            
        Returns:
            ChatCompletionResponse with fake but valid content
            
        Raises:
            Exception: If error_on_complete was set during initialization
        """
        # Track the call
        self.complete_calls.append(request)
        
        # Raise configured error if set (for testing error handling)
        if self.error_on_complete is not None:
            raise self.error_on_complete
        
        # Generate response matching real format
        response_id = f"chatcmpl-fake-{uuid.uuid4().hex[:12]}"
        
        # Build response content based on input
        content = self._generate_response_content(request)
        
        # Estimate tokens (rough approximation)
        prompt_tokens = sum(
            len((msg.content or "").split()) for msg in request.messages
        ) * 2  # ~2 tokens per word
        completion_tokens = len(content.split()) * 2
        
        return ChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
    
    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Stream a fake chat completion as chunks.
        
        Yields chunks matching the real streaming API format.
        
        Args:
            request: The chat completion request
            
        Yields:
            ChatCompletionChunk for each token
        """
        # Track the call
        self.stream_calls.append(request)
        
        response_id = f"chatcmpl-fake-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        content = self._generate_response_content(request)
        tokens = content.split()
        
        # First chunk: role
        yield ChatCompletionChunk(
            id=response_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )
        
        # Content chunks
        for i, token in enumerate(tokens):
            token_content = f" {token}" if i > 0 else token
            yield ChatCompletionChunk(
                id=response_id,
                created=created,
                model=request.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=ChunkDelta(content=token_content),
                        finish_reason=None,
                    )
                ],
            )
        
        # Final chunk: finish_reason
        yield ChatCompletionChunk(
            id=response_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(),
                    finish_reason="stop",
                )
            ],
        )
    
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model."""
        return model in self.supported_models
    
    def get_supported_models(self) -> list[str]:
        """Return list of supported models."""
        return self.supported_models.copy()
    
    def _generate_response_content(self, request: ChatCompletionRequest) -> str:
        """
        Generate response content based on the request.
        
        Can be overridden in subclasses for custom behavior.
        """
        # Find last user message
        last_user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user" and msg.content:
                last_user_message = msg.content
                break
        
        if last_user_message:
            return f"{self.response_content}: {last_user_message[:50]}"
        return self.response_content
