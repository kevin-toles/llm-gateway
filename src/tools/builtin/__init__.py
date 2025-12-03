"""
Built-in Tools Package - WBS 2.4.3 Built-in Tools

This package provides built-in tools for the LLM Gateway, including
semantic search and chunk retrieval tools that proxy to the
semantic-search-service.

Reference Documents:
- ARCHITECTURE.md Lines 50-53: builtin/semantic_search.py, chunk_retrieval.py
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391-1440: RAG patterns
"""

from src.tools.builtin.semantic_search import (
    search_corpus,
    SEARCH_CORPUS_DEFINITION,
    SearchServiceError,
)
from src.tools.builtin.chunk_retrieval import (
    get_chunk,
    GET_CHUNK_DEFINITION,
    ChunkNotFoundError,
    ChunkServiceError,
)
from src.tools.registry import ToolRegistry
from src.models.domain import RegisteredTool


def register_builtin_tools(registry: ToolRegistry) -> None:
    """
    Register all built-in tools with the given registry.

    WBS 2.4.3.3.4: Register built-in tools on application startup.

    Args:
        registry: The ToolRegistry to register tools with.
    """
    # Register search_corpus
    registry.register(
        "search_corpus",
        RegisteredTool(definition=SEARCH_CORPUS_DEFINITION, handler=search_corpus),
    )

    # Register get_chunk
    registry.register(
        "get_chunk",
        RegisteredTool(definition=GET_CHUNK_DEFINITION, handler=get_chunk),
    )


__all__ = [
    # Semantic Search
    "search_corpus",
    "SEARCH_CORPUS_DEFINITION",
    "SearchServiceError",
    # Chunk Retrieval
    "get_chunk",
    "GET_CHUNK_DEFINITION",
    "ChunkNotFoundError",
    "ChunkServiceError",
    # Registration
    "register_builtin_tools",
]
