# LLM Gateway Microservice

## Overview

The LLM Gateway is a **microservice** that provides a unified API for LLM interactions. It abstracts provider differences, orchestrates tool-use, manages sessions, and provides operational controls. Multiple applications consume this service over HTTP.

## Architecture Type

**Microservice** - Independently deployable, stateless (sessions in Redis), horizontally scalable.

---

## Folder Structure

```
llm-gateway/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py              # POST /v1/chat/completions
│   │   │   ├── sessions.py          # /v1/sessions/*
│   │   │   ├── tools.py             # /v1/tools/*
│   │   │   └── health.py            # /health, /ready
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # API key validation
│   │   │   ├── rate_limit.py        # Request rate limiting
│   │   │   └── logging.py           # Request/response logging
│   │   └── deps.py                  # FastAPI dependencies
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic settings
│   │   └── exceptions.py            # Custom exceptions
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract provider interface
│   │   ├── anthropic.py             # Anthropic Claude adapter
│   │   ├── openai.py                # OpenAI GPT adapter
│   │   ├── ollama.py                # Ollama local adapter
│   │   └── router.py                # Provider routing logic
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py              # Tool registration
│   │   ├── executor.py              # Tool execution orchestration
│   │   └── builtin/
│   │       ├── __init__.py
│   │       ├── semantic_search.py   # Proxy to semantic-search-service
│   │       └── chunk_retrieval.py   # Document chunk retrieval
│   │
│   ├── sessions/
│   │   ├── __init__.py
│   │   ├── manager.py               # Session lifecycle
│   │   └── store.py                 # Redis session storage
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat.py                  # Chat completion business logic
│   │   ├── cost_tracker.py          # Token/cost tracking
│   │   └── cache.py                 # Response caching
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py              # Pydantic request models
│   │   ├── responses.py             # Pydantic response models
│   │   └── domain.py                # Domain models (Message, Tool, etc.)
│   │
│   └── main.py                      # FastAPI app entry point
│
├── tests/
│   ├── unit/
│   │   ├── test_providers/
│   │   ├── test_tools/
│   │   └── test_sessions/
│   ├── integration/
│   │   ├── test_chat_api.py
│   │   └── test_tool_execution.py
│   └── conftest.py
│
├── config/
│   ├── tools.json                   # Tool definitions
│   └── providers.json               # Provider configurations
│
├── docs/
│   ├── ARCHITECTURE.md              # This file
│   ├── API.md                       # API documentation
│   └── DEPLOYMENT.md                # Deployment guide
│
├── scripts/
│   ├── start.sh
│   └── healthcheck.sh
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## System Context

```
                          ┌─────────────────────────────────────────┐
                          │            CONSUMERS                     │
                          │                                          │
                          │  ┌────────────┐  ┌────────────────────┐ │
                          │  │ llm-doc-   │  │ ai-agents          │ │
                          │  │ enhancer   │  │ microservice       │ │
                          │  └─────┬──────┘  └─────────┬──────────┘ │
                          │        │                   │            │
                          │        │   ┌───────────────┘            │
                          │        │   │  ┌────────────────────┐   │
                          │        │   │  │ Future Apps        │   │
                          │        │   │  └─────────┬──────────┘   │
                          └────────┼───┼────────────┼──────────────┘
                                   │   │            │
                                   ▼   ▼            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          LLM GATEWAY MICROSERVICE                             │
│                              (Port 8080)                                      │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                           API Layer (FastAPI)                            │ │
│  │  POST /v1/chat/completions  │  POST /v1/sessions  │  GET /health        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│  ┌──────────────┐  ┌──────────────┐  │  ┌──────────────┐  ┌──────────────┐   │
│  │   Provider   │  │   Tool-Use   │  │  │   Session    │  │  Operational │   │
│  │   Router     │  │  Orchestrator│  │  │   Manager    │  │   Controls   │   │
│  │              │  │              │  │  │              │  │              │   │
│  │ • Anthropic  │  │ • Registry   │  │  │ • Create     │  │ • Rate Limit │   │
│  │ • OpenAI     │  │ • Execution  │  │  │ • Retrieve   │  │ • Caching    │   │
│  │ • Ollama     │  │ • Routing    │  │  │ • Delete     │  │ • Cost Track │   │
│  └──────┬───────┘  └──────┬───────┘  │  └──────┬───────┘  └──────────────┘   │
│         │                 │          │         │                              │
└─────────┼─────────────────┼──────────┼─────────┼──────────────────────────────┘
          │                 │          │         │
          ▼                 ▼          │         ▼
┌──────────────────┐ ┌─────────────────┐│  ┌─────────────────┐
│ LLM Providers    │ │ semantic-search ││  │     Redis       │
│                  │ │ microservice    ││  │  (Sessions)     │
│ • Anthropic API  │ │ (Port 8081)     ││  │                 │
│ • OpenAI API     │ │                 ││  │                 │
│ • Ollama (local) │ │                 ││  │                 │
└──────────────────┘ └─────────────────┘│  └─────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/chat/completions` | LLM inference with optional tool-use |
| POST | `/v1/sessions` | Create new session |
| GET | `/v1/sessions/{id}` | Get session state |
| DELETE | `/v1/sessions/{id}` | Delete session |
| POST | `/v1/tools/execute` | Execute a registered tool |
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |

---

## Components

### Provider Router
Routes requests to the appropriate LLM provider based on model name or configuration.

### Tool-Use Orchestrator
- Registers available tools
- Parses LLM tool_call responses
- Executes tools (local or proxied to other microservices)
- Returns results to LLM for continuation

### Session Manager
- Creates sessions with TTL
- Stores conversation history
- Uses Redis for distributed session storage

### Operational Controls
- Rate limiting per client
- Response caching
- Token/cost tracking per request

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| Redis | Infrastructure | Session storage, caching |
| semantic-search-service | Microservice | Tool execution for search |
| Anthropic API | External | LLM provider |
| OpenAI API | External | LLM provider |

---

## Deployment

```yaml
# docker-compose.yml
services:
  llm-gateway:
    build: .
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://redis:6379
      - SEMANTIC_SEARCH_URL=http://semantic-search:8081
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
      - semantic-search

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

---

## Configuration

```python
# src/core/config.py
class Settings(BaseSettings):
    # Service
    service_name: str = "llm-gateway"
    port: int = 8080
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Microservice URLs
    semantic_search_url: str = "http://localhost:8081"
    
    # Providers
    anthropic_api_key: str
    openai_api_key: str
    default_provider: str = "anthropic"
    default_model: str = "claude-3-sonnet-20240229"
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    
    class Config:
        env_prefix = "LLM_GATEWAY_"
```
