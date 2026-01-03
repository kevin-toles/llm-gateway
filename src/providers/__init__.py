"""
Providers Package - LLM Provider Adapters

This package contains the abstract provider interface and concrete
implementations for various LLM providers (Anthropic, OpenAI, Ollama).

Reference Documents:
- ARCHITECTURE.md: Lines 38-44 - providers/ folder structure
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES p. 953: @abstractmethod decorator usage

WBS Coverage:
- 2.3.1: Provider Base Interface
- 2.3.2: Anthropic Provider
- 2.3.3: OpenAI Provider
- 2.3.4: Ollama Provider
- 2.3.5: Provider Router
"""

from src.providers.base import LLMProvider
from src.providers.anthropic import AnthropicToolHandler
from src.providers.openai import (
    OpenAIProvider,
    OpenAIToolHandler,
)
from src.providers.openrouter import OpenRouterProvider
from src.core.exceptions import (
    ProviderError,
    RateLimitError,
    AuthenticationError,
)
from src.providers.ollama import (
    OllamaProvider,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from src.providers.router import (
    ProviderRouter,
    NoProviderError,
    create_provider_router,
)

__all__ = [
    "LLMProvider",
    "AnthropicToolHandler",
    "OpenAIProvider",
    "OpenAIToolHandler",
    "OpenRouterProvider",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "OllamaProvider",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "ProviderRouter",
    "NoProviderError",
    "create_provider_router",
]
