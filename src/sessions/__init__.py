"""
Sessions Package - WBS 2.5.1 Session Store

This package provides session management for the LLM Gateway, including
session storage with Redis and session lifecycle management.

Reference Documents:
- ARCHITECTURE.md: Session Manager - "Creates sessions with TTL, Stores conversation history"
- GUIDELINES pp. 2153: "production systems often require external state stores (Redis)"
- GUIDELINES pp. 949: Repository pattern for data access abstraction

WBS Items:
- 2.5.1.1: Redis Store Implementation (SessionStore class)
- 2.5.1.2: Session Model (in src/models/domain.py)
"""

from src.sessions.store import SessionStore, SessionStoreError

__all__ = ["SessionStore", "SessionStoreError"]
