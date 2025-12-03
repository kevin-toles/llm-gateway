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
- 2.3.3: OpenAI Provider (future)
- 2.3.4: Ollama Provider (future)
- 2.3.5: Provider Router (future)
"""

from src.providers.base import LLMProvider
from src.providers.anthropic import AnthropicToolHandler

__all__ = ["LLMProvider", "AnthropicToolHandler"]
