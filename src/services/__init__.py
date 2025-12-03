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
- 2.6.2: Cost Tracker
- 2.6.3: Response Cache
"""

from src.services.cache import CacheError, ResponseCache
from src.services.chat import ChatService, ChatServiceError
from src.services.cost_tracker import CostTracker, CostTrackerError, UsageSummary

__all__ = [
    "CacheError",
    "ChatService",
    "ChatServiceError",
    "CostTracker",
    "CostTrackerError",
    "ResponseCache",
    "UsageSummary",
]
