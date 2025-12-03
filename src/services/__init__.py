"""
Services Package - WBS 2.6 Service Layer

This package provides business logic services for the LLM Gateway,
including chat completion orchestration, cost tracking, and caching.

Reference Documents:
- ARCHITECTURE.md: Lines 61-65 - services/ directory structure
- GUIDELINES pp. 211: Service layers for orchestrating foundation models
- GUIDELINES pp. 1440: Service Layer abstractions for RAG systems
- GUIDELINES pp. 1544: Agent tool orchestration patterns

WBS Items:
- 2.6.1: Chat Service Implementation
- 2.6.2: Cost Tracker (future)
- 2.6.3: Response Cache (future)
"""

from src.services.chat import ChatService, ChatServiceError

__all__ = ["ChatService", "ChatServiceError"]
