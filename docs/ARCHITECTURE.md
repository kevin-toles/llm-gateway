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
├── deploy/
│   ├── docker/
│   │   ├── Dockerfile               # Production multi-stage Dockerfile
│   │   ├── Dockerfile.dev           # Development Dockerfile
│   │   ├── docker-compose.yml       # Full stack compose
│   │   ├── docker-compose.dev.yml   # Dev compose
│   │   └── .env.example             # Environment template
│   ├── kubernetes/
│   │   ├── base/                    # Kustomize base manifests
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── configmap.yaml
│   │   │   └── ...
│   │   └── overlays/
│   │       ├── dev/                 # Dev environment overlay
│   │       ├── staging/             # Staging environment overlay
│   │       └── prod/                # Production environment overlay
│   └── helm/
│       └── llm-gateway/             # Helm chart
│           ├── Chart.yaml
│           ├── values.yaml
│           ├── values-dev.yaml
│           ├── values-staging.yaml
│           ├── values-prod.yaml
│           ├── templates/           # Kubernetes templates
│           └── tests/               # Helm unit tests
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # CI pipeline
│       ├── cd-dev.yml               # Dev deployment
│       ├── cd-staging.yml           # Staging deployment
│       └── cd-prod.yml              # Production deployment
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

## Service Discovery Patterns

> **WBS 3.2.1.1.4**: Document service discovery patterns for microservice communication.

The LLM Gateway uses **DNS-based service discovery** for communication with dependent services. This pattern is consistent across local development (Docker Compose) and production (Kubernetes).

### Pattern: DNS Service Discovery

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Service Discovery Flow                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Environment Variable                     DNS Resolution                    │
│   ────────────────────                     ──────────────                    │
│                                                                              │
│   LLM_GATEWAY_SEMANTIC_SEARCH_URL          Docker Compose:                   │
│   ────────────────────────────────         service name → container IP       │
│   "http://semantic-search:8081"                                              │
│                                            Kubernetes:                       │
│                                            service.namespace.svc.cluster.local │
│                                                                              │
│   LLM_GATEWAY_REDIS_URL                    Both environments:                │
│   ─────────────────────                    DNS resolves to service endpoint  │
│   "redis://redis:6379"                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### URL Resolution by Environment

| Environment | Service | URL Pattern | Resolution |
|-------------|---------|-------------|------------|
| Local (direct) | semantic-search | `http://localhost:8081` | Localhost binding |
| Docker Compose | semantic-search | `http://semantic-search:8081` | Docker DNS |
| Kubernetes | semantic-search | `http://semantic-search:8081` | K8s Service DNS |
| Kubernetes (cross-namespace) | semantic-search | `http://semantic-search.default.svc.cluster.local:8081` | FQDN |

### Configuration Hierarchy

```python
# Priority (highest to lowest):
# 1. Environment variable: LLM_GATEWAY_SEMANTIC_SEARCH_URL
# 2. ConfigMap/Secret mount (Kubernetes)
# 3. Default in Settings class: "http://localhost:8081"
```

### Health Check Integration

The gateway's `/health/ready` endpoint verifies connectivity to dependent services:

```
GET /health/ready

Response (all healthy):
{
  "status": "ready",
  "checks": {
    "redis": true,
    "semantic_search": true
  }
}

Response (degraded - semantic-search down):
{
  "status": "degraded",
  "checks": {
    "redis": true,
    "semantic_search": false
  }
}
```

### Graceful Degradation

Following Newman's patterns (Building Microservices pp. 352-353):

1. **Service Unavailable**: Return `503` with `"status": "not_ready"` if critical dependencies down
2. **Degraded Mode**: Return `200` with `"status": "degraded"` if optional services unavailable
3. **Circuit Breaker**: Fast-fail after repeated failures (implemented in `src/clients/circuit_breaker.py`)
4. **Timeout Configuration**: 5-second health check timeout prevents cascading delays

### Docker Compose Example

```yaml
services:
  llm-gateway:
    environment:
      - LLM_GATEWAY_SEMANTIC_SEARCH_URL=http://semantic-search:8081
      - LLM_GATEWAY_REDIS_URL=redis://redis:6379
    depends_on:
      semantic-search:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - app-network

  semantic-search:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### Kubernetes ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-gateway-config
data:
  LLM_GATEWAY_SEMANTIC_SEARCH_URL: "http://semantic-search:8081"
  LLM_GATEWAY_REDIS_URL: "redis://redis-master:6379"
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
    
    # Microservice URLs (WBS 3.2.1.1: Service Discovery)
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
