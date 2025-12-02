# Technical Change Log - LLM Gateway

This document tracks all implementation changes, their rationale, and git commit correlations.

---

## Change Log Format

| Field | Description |
|-------|-------------|
| **Date/Time** | When the change was made |
| **WBS Item** | Related WBS task number |
| **Change Type** | Feature, Fix, Refactor, Documentation |
| **Summary** | Brief description of the change |
| **Files Changed** | List of affected files |
| **Rationale** | Why the change was made |
| **Git Commit** | Commit hash (if committed) |

---

## 2025-12-02

### CL-001: WBS 2.1.1 Application Entry Point - Lifespan Pattern Update

| Field | Value |
|-------|-------|
| **Date/Time** | 2025-12-02 ~14:00 UTC |
| **WBS Item** | 2.1.1.1.3, 2.1.1.1.4, 2.1.1.2.1-2.1.1.2.8 |
| **Change Type** | Refactor |
| **Summary** | Replaced deprecated `@app.on_event` with `@asynccontextmanager` lifespan pattern |
| **Files Changed** | `src/main.py`, `tests/unit/test_main.py` |
| **Rationale** | FastAPI deprecation warning for `@app.on_event("startup")` and `@app.on_event("shutdown")`. Modern pattern uses `lifespan` context manager per Starlette/FastAPI best practices. Added tools_router that was missing. |
| **Git Commit** | `a39a7b1` |

**Details:**
- Replaced `@app.on_event("startup")` with `@asynccontextmanager async def lifespan(app)`
- Replaced `@app.on_event("shutdown")` with cleanup in lifespan's finally block
- Added `from src.api.routes.tools import router as tools_router`
- Added `app.include_router(tools_router)`
- Added `app.state.initialized` for tracking startup state
- Added 20 new tests in `tests/unit/test_main.py`

---

### CL-002: WBS 2.1.2 Core Configuration Module - New Implementation

| Field | Value |
|-------|-------|
| **Date/Time** | 2025-12-02 ~15:00 UTC |
| **WBS Item** | 2.1.2.1, 2.1.2.2, 2.1.2.3 |
| **Change Type** | Feature |
| **Summary** | Implemented core configuration module with Settings class and custom exceptions |
| **Files Changed** | `src/core/__init__.py`, `src/core/config.py`, `src/core/exceptions.py`, `tests/unit/core/test_config.py`, `tests/unit/core/test_exceptions.py` |
| **Rationale** | Per ARCHITECTURE.md specification for centralized configuration using Pydantic BaseSettings. Required for all downstream components that need configuration. |
| **Git Commit** | `a39a7b1` |

**Details:**
- Created `Settings` class extending `pydantic_settings.BaseSettings`
- Implemented `get_settings()` singleton with `@lru_cache`
- Added field validators for port, redis_url, environment
- Created custom exception hierarchy:
  - `LLMGatewayException` (base)
  - `ProviderError`
  - `SessionError`
  - `ToolExecutionError`
  - `RateLimitError`
  - `GatewayValidationError`
- Created `ErrorCode` enum for consistent error codes
- Added 74 tests (30 config + 44 exceptions)

**Configuration Fields Added:**
- Service: `service_name`, `port`, `environment`
- Redis: `redis_url`, `redis_pool_size`
- Microservices: `semantic_search_url`, `ai_agents_url`, `ollama_url`
- Providers: `anthropic_api_key`, `openai_api_key`, `default_provider`, `default_model`
- Rate Limiting: `rate_limit_requests_per_minute`, `rate_limit_burst`
- Session: `session_ttl_seconds`

---

### CL-003: __init__.py Export Updates - Acceptance Criteria Compliance

| Field | Value |
|-------|-------|
| **Date/Time** | 2025-12-02 ~16:00 UTC |
| **WBS Item** | Stage 2 Acceptance Criteria |
| **Change Type** | Refactor |
| **Summary** | Updated `__init__.py` files to properly export public interfaces while avoiding circular imports |
| **Files Changed** | `src/__init__.py`, `src/api/__init__.py`, `src/api/routes/__init__.py`, `src/models/__init__.py` |
| **Rationale** | Acceptance criteria requires: "All `__init__.py` files export public interfaces". Initial implementation caused circular import errors, requiring redesign. |
| **Git Commit** | `a39a7b1` |

**Details:**
- `src/__init__.py`: Exports `__all__ = ["main", "api", "core", "models"]` (no direct imports to avoid circular)
- `src/api/__init__.py`: Exports `__all__ = ["routes"]`
- `src/api/routes/__init__.py`: Exports `__all__ = ["health", "chat", "tools"]`
- `src/models/__init__.py`: Exports all Pydantic models (ChatCompletionRequest, Tool, ToolDefinition, etc.)
- `src/core/__init__.py`: Exports Settings, get_settings, and all custom exceptions

**Circular Import Resolution:**
- Removed direct imports in package `__init__.py` files that would cause import cycles
- Added documentation notes about importing from specific modules instead
- Models package can safely import all models since they don't import main.py

---

## Historical Commits (Pre-Change Log)

| Date | Commit | Summary |
|------|--------|---------|
| 2025-12-01 | 155e97c | feat(api): Implement WBS 2.2 API Layer - health, chat, streaming, tools endpoints |
| 2025-12-01 | 19fd5ed | docs: Complete WBS 1.7.1 documentation and validation |
| 2025-11-30 | 7a66532 | feat: Complete WBS 1.2-1.5 deployment infrastructure |
| 2025-11-30 | 8a0c243 | docs: Update INTEGRATION_MAP and DEPLOYMENT_IMPLEMENTATION_PLAN |
| 2025-11-29 | 2816056 | docs: Add microservice architecture documentation |

---

## Test Count Progression

| WBS | Date | Tests Added | Total Tests |
|-----|------|-------------|-------------|
| 2.2.1 Health | 2025-12-01 | 12 | 12 |
| 2.2.2 Chat | 2025-12-01 | 25 | 37 |
| 2.2.3 Streaming | 2025-12-01 | 18 | 55 |
| 2.2.4 Tools | 2025-12-01 | 32 | 87 |
| 2.1.1 Main | 2025-12-02 | 20 | 107 |
| 2.1.2 Core | 2025-12-02 | 74 | 181 |
