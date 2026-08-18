"""
Provider Base Interface - WBS 2.3.1.1 Abstract Provider Class

This module defines the abstract base class for all LLM provider adapters.
The LLMProvider ABC establishes a consistent interface for chat completions
across different providers (Anthropic, OpenAI, Ollama).

Reference Documents:
- ARCHITECTURE.md: Lines 38-44 - providers/base.py "Abstract provider interface"
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES p. 953: @abstractmethod decorator usage
- GUIDELINES p. 2149: Iterator protocol for streaming responses
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Design Pattern:
- Ports and Adapters (Hexagonal Architecture)
- LLMProvider serves as the "port" (interface)
- Concrete providers (anthropic.py, openai.py, ollama.py) serve as "adapters"

Reference: GUIDELINES pp. 793-795:
"The repository pattern's ports-and-adapters architecture maps naturally to
Python's protocol-oriented design, where AbstractRepository serves as the port
and SqlAlchemyRepository or FakeRepository serve as adapters."
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from src.models.requests import ChatCompletionRequest
from src.models.responses import ChatCompletionResponse, ChatCompletionChunk


class LLMProvider(ABC):
    """
    Abstract base class for LLM provider adapters.

    WBS 2.3.1.1.3: Define LLMProvider abstract base class.

    This ABC defines the contract that all LLM provider implementations must
    fulfill. It follows the Ports and Adapters (Hexagonal) architecture pattern,
    allowing the application to interact with different LLM providers through
    a consistent interface.

    Pattern: ABC for interface contracts (GUIDELINES pp. 793-795)
    Pattern: @abstractmethod for enforcement (GUIDELINES p. 953)

    Methods:
        complete: Synchronous (non-streaming) chat completion
        stream: Streaming chat completion using async generators
        supports_model: Check if provider supports a specific model
        get_supported_models: List all supported model identifiers

    Example:
        >>> class AnthropicProvider(LLMProvider):
        ...     async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        ...         # Implementation using Anthropic API
        ...         pass
        ...
        ...     async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        ...         # Streaming implementation
        ...         yield chunk
        ...
        ...     def supports_model(self, model: str) -> bool:
        ...         return model.startswith("claude-")
        ...
        ...     def get_supported_models(self) -> list[str]:
        ...         return ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]

    Reference:
        GUIDELINES p. 795: "Python's flexibility enables both rigorous architectural
        patterns (through ABCs and explicit interfaces) and pragmatic shortcuts
        (through duck typing and protocols)."
    """

    @abstractmethod
    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).

        WBS 2.3.1.1.4: Define async def complete().

        This method sends the chat completion request to the LLM provider
        and returns the complete response once generation is finished.

        Args:
            request: The chat completion request containing messages,
                model identifier, and optional parameters (temperature,
                max_tokens, tools, etc.)

        Returns:
            ChatCompletionResponse: The complete response including:
                - id: Unique response identifier
                - choices: List of completion choices with messages
                - usage: Token usage statistics
                - model: Model used for completion

        Raises:
            ProviderError: If the provider API returns an error
            RateLimitError: If rate limits are exceeded
            AuthenticationError: If API credentials are invalid

        Pattern: Request-Response with Pydantic models (Sinha pp. 193-195)

        Example:
            >>> response = await provider.complete(request)
            >>> print(response.choices[0].message.content)
        """
        ...

    @abstractmethod
    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.

        WBS 2.3.1.1.5: Define async def stream() -> AsyncIterator.

        This method sends the chat completion request to the LLM provider
        and yields response chunks as they are generated, enabling real-time
        streaming of responses to clients.

        Args:
            request: The chat completion request. Note: request.stream
                should be True, but implementations may ignore this field.

        Yields:
            ChatCompletionChunk: Incremental response chunks containing:
                - id: Same response ID across all chunks
                - choices: List with delta content
                - model: Model used for completion

        Raises:
            ProviderError: If the provider API returns an error
            RateLimitError: If rate limits are exceeded
            AuthenticationError: If API credentials are invalid

        Pattern: Iterator protocol with async generators (GUIDELINES p. 2149)
        Pattern: Observable patterns with async generators (Sinha)

        Reference: GUIDELINES p. 2149:
        "The iterator protocol and generator functions form the architectural
        foundation for processing large language model outputs efficiently,
        particularly when handling streaming responses."

        Example:
            >>> async for chunk in provider.stream(request):
            ...     if chunk.choices[0].delta.content:
            ...         print(chunk.choices[0].delta.content, end="")
        """
        ...

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.

        WBS 2.3.1.1.6: Define supports_model(model: str) -> bool.

        This method is used by the Provider Router to determine which
        provider should handle a given request based on the model identifier.

        Args:
            model: The model identifier (e.g., "claude-3-opus", "gpt-4", "llama2")

        Returns:
            bool: True if this provider can handle the specified model,
                False otherwise.

        Pattern: Strategy pattern for provider selection

        Example:
            >>> anthropic_provider.supports_model("claude-3-opus")
            True
            >>> anthropic_provider.supports_model("gpt-4")
            False
        """
        ...

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """
        Get the list of model identifiers supported by this provider.

        WBS 2.3.1.1.7: Define get_supported_models() -> list[str].

        This method returns all model identifiers that this provider
        can handle. Used for provider discovery and configuration validation.

        Returns:
            list[str]: List of supported model identifiers.
                Each identifier should be unique and match the format
                expected by the provider's API.

        Pattern: Provider discovery for routing and validation

        Example:
            >>> anthropic_provider.get_supported_models()
            ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']

            >>> openai_provider.get_supported_models()
            ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo']
        """
        ...
