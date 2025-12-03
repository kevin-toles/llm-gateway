"""API Package - FastAPI routes, middleware, and dependencies.

WBS 2.2: API Layer Implementation

Components:
- routes: API endpoint routers (health, chat, sessions, tools)
- middleware: Request/response middleware (logging, rate_limit)
- deps: FastAPI dependency injection functions

Note: Import routers directly from src.api.routes to avoid circular imports.
"""

__all__ = ["routes", "middleware", "deps"]
