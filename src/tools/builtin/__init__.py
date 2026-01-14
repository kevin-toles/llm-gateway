"""
Built-in Tools Package - WBS 2.4.3 Built-in Tools

This package provides built-in tools for the LLM Gateway, including
semantic search, chunk retrieval, and cross-reference tools that proxy
to the semantic-search-service and ai-agents service.

Reference Documents:
- ARCHITECTURE.md Lines 50-53: builtin/semantic_search.py, chunk_retrieval.py
- ARCHITECTURE.md Line 82: ai-agents-service dependency (ai_agents_url)
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391-1440: RAG patterns
- TIER_RELATIONSHIP_DIAGRAM.md: Spider Web Model taxonomy
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
from src.tools.builtin.cross_reference import (
    cross_reference,
    CROSS_REFERENCE_DEFINITION,
    CrossReferenceServiceError,
)
from src.tools.builtin.enrich_metadata import (
    enrich_metadata,
    ENRICH_METADATA_DEFINITION,
    EnrichMetadataServiceError,
)
from src.tools.builtin.hybrid_search import (
    hybrid_search,
    HYBRID_SEARCH_DEFINITION,
    HybridSearchServiceError,
)
from src.tools.builtin.code_orchestrator_tools import (
    compute_similarity,
    extract_keywords,
    generate_embeddings,
    COMPUTE_SIMILARITY_DEFINITION,
    EXTRACT_KEYWORDS_DEFINITION,
    GENERATE_EMBEDDINGS_DEFINITION,
    CodeOrchestratorServiceError,
)
from src.tools.builtin.embed import (
    embed,
    EMBED_DEFINITION,
    EmbedServiceError,
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
    # Register search_corpus (semantic-search-service proxy)
    registry.register(
        "search_corpus",
        RegisteredTool(definition=SEARCH_CORPUS_DEFINITION, handler=search_corpus),
    )

    # Register get_chunk (semantic-search-service proxy)
    registry.register(
        "get_chunk",
        RegisteredTool(definition=GET_CHUNK_DEFINITION, handler=get_chunk),
    )

    # Register cross_reference (ai-agents service proxy)
    # This enables the agentic workflow: LLM -> gateway -> ai-agents -> semantic-search
    registry.register(
        "cross_reference",
        RegisteredTool(definition=CROSS_REFERENCE_DEFINITION, handler=cross_reference),
    )

    # Register enrich_metadata (ai-agents MSEP service proxy)
    # Kitchen Brigade: External apps call Gateway, Gateway routes to ai-agents
    registry.register(
        "enrich_metadata",
        RegisteredTool(definition=ENRICH_METADATA_DEFINITION, handler=enrich_metadata),
    )

    # Register hybrid_search (semantic-search-service proxy)
    # WBS-CPA1: Gateway external tool exposure for MCP/external LLMs
    registry.register(
        "hybrid_search",
        RegisteredTool(definition=HYBRID_SEARCH_DEFINITION, handler=hybrid_search),
    )

    # =========================================================================
    # WBS-CPA2: Code-Orchestrator Tools for External Clients
    # =========================================================================
    
    # Register compute_similarity (Code-Orchestrator-Service proxy)
    registry.register(
        "compute_similarity",
        RegisteredTool(definition=COMPUTE_SIMILARITY_DEFINITION, handler=compute_similarity),
    )

    # Register extract_keywords (Code-Orchestrator-Service proxy)
    registry.register(
        "extract_keywords",
        RegisteredTool(definition=EXTRACT_KEYWORDS_DEFINITION, handler=extract_keywords),
    )

    # Register generate_embeddings (Code-Orchestrator-Service proxy)
    registry.register(
        "generate_embeddings",
        RegisteredTool(definition=GENERATE_EMBEDDINGS_DEFINITION, handler=generate_embeddings),
    )

    # =========================================================================
    # WBS-CPA6: Embed Tool for External Clients
    # Routes to semantic-search-service /v1/embeddings
    # =========================================================================
    
    # Register embed (semantic-search-service proxy)
    registry.register(
        "embed",
        RegisteredTool(definition=EMBED_DEFINITION, handler=embed),
    )


__all__ = [
    # Semantic Search
    "search_corpus",
    "SEARCH_CORPUS_DEFINITION",
    "SearchServiceError",
    # Hybrid Search (WBS-CPA1)
    "hybrid_search",
    "HYBRID_SEARCH_DEFINITION",
    "HybridSearchServiceError",
    # Chunk Retrieval
    "get_chunk",
    "GET_CHUNK_DEFINITION",
    "ChunkNotFoundError",
    "ChunkServiceError",
    # Cross Reference (ai-agents proxy)
    "cross_reference",
    "CROSS_REFERENCE_DEFINITION",
    "CrossReferenceServiceError",
    # Enrich Metadata (ai-agents MSEP proxy)
    "enrich_metadata",
    "ENRICH_METADATA_DEFINITION",
    "EnrichMetadataServiceError",
    # Code-Orchestrator Tools (WBS-CPA2)
    "compute_similarity",
    "extract_keywords",
    "generate_embeddings",
    "COMPUTE_SIMILARITY_DEFINITION",
    "EXTRACT_KEYWORDS_DEFINITION",
    "GENERATE_EMBEDDINGS_DEFINITION",
    "CodeOrchestratorServiceError",
    # Embed Tool (WBS-CPA6)
    "embed",
    "EMBED_DEFINITION",
    "EmbedServiceError",
    # Registration
    "register_builtin_tools",
]
