# LLM Gateway Microservice

> **Version:** 2.0.0  
> **Updated:** 2026-02-01  
> **Status:** Active  
> **Git Reference:** Cross-referenced with codebase 2026-02-01

## Overview

The LLM Gateway is a **microservice** that provides a unified API for LLM interactions. It abstracts provider differences, orchestrates tool-use, manages sessions, and provides operational controls. Multiple applications consume this service over HTTP.

## Architecture Type

**Microservice** - Independently deployable, stateless (sessions in Redis), horizontally scalable.

---

## ⚠️ Gateway-First Communication Pattern

**CRITICAL RULE**: All external applications MUST route through the Gateway.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    SERVICE COMMUNICATION PATTERN                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EXTERNAL → PLATFORM: Via Gateway:8080 (REQUIRED)                           │
│  ─────────────────────────────────────────────────                          │
│  Applications outside the AI Platform must route through Gateway.           │
│                                                                              │
│  ✅ llm-document-enhancer → Gateway:8080 → ai-agents:8082                   │
│  ✅ VS Code Extension → Gateway:8080 → ai-agents:8082                       │
│  ❌ llm-document-enhancer → ai-agents:8082 (VIOLATION!)                     │
│                                                                              │
│  INTERNAL (Platform Services): Direct calls allowed                          │
│  ───────────────────────────────────────────────────                         │
│  Platform services (ai-agents, audit-service, Code-Orchestrator,            │
│  semantic-search) may call each other directly.                             │
│                                                                              │
│  ✅ ai-agents:8082 → audit-service:8084 (internal)                          │
│  ✅ ai-agents:8082 → Code-Orchestrator:8083 (internal)                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Platform Services (Internal Mesh)

| Service | Port | Direct Access From |
|---------|------|-------------------|
| `llm-gateway` | 8080 | External apps (entry point) |
| `ai-agents` | 8082 | Gateway, platform services |
| `semantic-search-service` | 8081 | Gateway, platform services |
| `Code-Orchestrator-Service` | 8083 | Platform services only |
| `audit-service` | 8084 | Platform services only |
| `inference-service` | 8085 | Gateway only (local LLM inference) |

---

## Kitchen Brigade Role: ROUTER (Pass-Through)

In the Kitchen Brigade architecture, **llm-gateway** is the **Router** - it directs requests but doesn't make content decisions:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         🚪 ROUTER - TRAFFIC DIRECTOR                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WHAT IT DOES:                                                               │
│  ─────────────                                                               │
│  ✓ Routes LLM requests to appropriate providers (Anthropic, OpenAI, Ollama) │
│  ✓ Manages chat sessions (in Redis)                                         │
│  ✓ Registers and executes tools                                             │
│  ✓ Handles rate limiting, auth, logging                                     │
│  ✓ Proxies tool calls to other services                                     │
│                                                                              │
│  WHAT IT DOES NOT DO:                                                        │
│  ────────────────────                                                        │
│  ✗ Make decisions about content                                              │
│  ✗ Extract keywords or validate terms                                        │
│  ✗ Host HuggingFace models (that's Code-Orchestrator-Service)               │
│  ✗ Filter or rank search results                                             │
│                                                                              │
│  TOOL EXECUTION:                                                             │
│  ───────────────                                                             │
│  When an LLM requests a tool like `cross_reference`, the gateway:           │
│  1. Receives the tool request from the LLM                                  │
│  2. Proxies to the appropriate service (ai-agents or Code-Orchestrator)     │
│  3. Returns the result to the LLM                                            │
│  The gateway is a pass-through - it doesn't interpret the tool's output.    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Tool Proxy Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                        LLM Gateway                              │
│                                                                 │
│  Tool Registry:                                                 │
│  ├── cross_reference → POST to ai-agents /v1/agents/cross-ref  │
│  ├── semantic_search → POST to semantic-search /v1/search      │
│  ├── extract_terms   → POST to Code-Orchestrator /api/v1/extract│
│  └── ...                                                        │
│                                                                 │
│  The gateway PROXIES these calls - it doesn't execute logic.   │
│  Intelligence lives in the destination services.                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
llm-gateway/
├── src/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry point
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                  # FastAPI dependencies
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py              # POST /v1/chat/completions
│   │   │   ├── cms_routing.py       # CMS proxy routes
│   │   │   ├── health.py            # /health, /health/detailed, /health/ready
│   │   │   ├── models.py            # /v1/models, /v1/providers
│   │   │   ├── responses.py         # POST /v1/responses (OpenAI Responses API)
│   │   │   ├── sessions.py          # /v1/sessions/*
│   │   │   └── tools.py             # /v1/tools/*
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── logging.py           # Request/response logging
│   │       ├── memory.py            # Memory monitoring
│   │       └── rate_limit.py        # Request rate limiting
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic settings
│   │   ├── exceptions.py            # Custom exceptions
│   │   └── logging.py               # Structured logging
│   │
│   ├── providers/                   # LLM Provider Adapters
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract provider interface
│   │   ├── anthropic.py             # Anthropic Claude
│   │   ├── deepseek.py              # DeepSeek API
│   │   ├── fake.py                  # Test/mock provider
│   │   ├── gemini.py                # Google Gemini
│   │   ├── inference.py             # Local inference-service
│   │   ├── llamacpp.py              # LlamaCpp/GGUF models
│   │   ├── ollama.py                # Ollama local
│   │   ├── openai.py                # OpenAI GPT
│   │   ├── openrouter.py            # OpenRouter (multi-provider)
│   │   └── router.py                # Provider routing logic
│   │
│   ├── clients/                     # Service Clients
│   │   ├── __init__.py
│   │   ├── ai_agents.py             # ai-agents service client
│   │   ├── circuit_breaker.py       # Circuit breaker pattern
│   │   ├── cms_client.py            # Context Management Service client
│   │   ├── http.py                  # Base HTTP client
│   │   └── semantic_search.py       # semantic-search client
│   │
│   ├── tools/                       # Tool Execution
│   │   ├── __init__.py
│   │   ├── registry.py              # Tool registration
│   │   ├── executor.py              # Tool execution orchestration
│   │   └── builtin/
│   │       ├── __init__.py
│   │       ├── architecture.py      # Architecture tools
│   │       ├── chunk_retrieval.py   # Document chunk retrieval
│   │       ├── code_orchestrator_tools.py  # Code-Orchestrator proxy
│   │       ├── code_review.py       # Code review tools
│   │       ├── cross_reference.py   # Cross-reference search
│   │       ├── doc_generate.py      # Documentation generation
│   │       ├── embed.py             # Embedding tools
│   │       ├── enrich_metadata.py   # Metadata enrichment
│   │       ├── hybrid_search.py     # Hybrid search proxy
│   │       └── semantic_search.py   # Semantic search proxy
│   │
│   ├── sessions/
│   │   ├── __init__.py
│   │   ├── manager.py               # Session lifecycle
│   │   └── store.py                 # Redis session storage
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cache.py                 # Response caching
│   │   ├── chat.py                  # Chat completion business logic
│   │   └── cost_tracker.py          # Token/cost tracking
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── domain.py                # Domain models (Message, Tool, etc.)
│   │   ├── requests.py              # Pydantic request models
│   │   ├── responses.py             # Pydantic response models
│   │   └── tools.py                 # Tool-related models
│   │
│   ├── observability/               # Monitoring & Tracing
│   │   ├── __init__.py
│   │   ├── logging.py               # Structured logging
│   │   ├── metrics.py               # Prometheus metrics
│   │   └── tracing.py               # OpenTelemetry tracing
│   │
│   └── resilience/                  # Fault Tolerance
│       ├── __init__.py
│       ├── circuit_breaker_state_machine.py
│       ├── fallback_chain.py        # Provider fallback
│       └── metrics.py               # Resilience metrics
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
├── docs/
│   ├── ARCHITECTURE.md              # This file
│   ├── TECHNICAL_CHANGE_LOG.md
│   └── guides/
│
├── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.hybrid.yml
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
│  │ • LlamaCpp   │  │ • Taxonomy   │  │  │ • Taxonomy   │  │              │   │
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
| POST | `/v1/responses` | OpenAI Responses API compatible endpoint |
| GET | `/v1/models` | List available models |
| GET | `/v1/models/{model_id}` | Get specific model info |
| GET | `/v1/providers` | List available providers |
| POST | `/v1/sessions` | Create new session |
| GET | `/v1/sessions/{id}` | Get session state |
| DELETE | `/v1/sessions/{id}` | Delete session |
| POST | `/v1/tools/execute` | Execute a registered tool |
| GET | `/health` | Health check |
| GET | `/health/detailed` | Detailed health with dependency status |
| GET | `/health/ready` | Readiness check |

---

## Taxonomy-Aware Tool Routing

The LLM Gateway supports taxonomy-aware tool execution. When users specify a taxonomy in their prompt, the gateway passes this to downstream services.

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  User Prompt: "Search for rate limiting patterns, use AI-ML taxonomy"       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. LLM Gateway receives chat request                                        │
│  2. LLM decides to call semantic_search tool                                │
│  3. Gateway extracts taxonomy from user context/prompt                       │
│  4. Gateway proxies to semantic-search-service WITH taxonomy parameter:      │
│                                                                              │
│     POST http://semantic-search-service:8081/v1/search/hybrid               │
│     {                                                                        │
│       "query": "rate limiting patterns",                                    │
│       "taxonomy": "AI-ML_taxonomy",    ← Passed from user context           │
│       "tier_filter": [1, 2]            ← Optional tier filter               │
│     }                                                                        │
│                                                                              │
│  5. Results returned with tier/priority from specified taxonomy              │
│  6. LLM uses tier info to prioritize references in response                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Session Taxonomy Context

Sessions can store a default taxonomy that applies to all tool calls:

```json
POST /v1/sessions
{
  "context": {
    "taxonomy": "AI-ML_taxonomy",
    "tier_filter": [1, 2, 3]
  }
}
```

This enables users to say "use the Security taxonomy" once, and all subsequent searches in that session use it automatically.

---

## Enrichment Scalability - Gateway Role

The LLM Gateway is a **transparent pass-through** for enriched data. The "compute once, filter at query-time" pattern is fully implemented in semantic-search-service.

### Gateway Does NOT:

| Aspect | Gateway Role |
|--------|--------------|
| Filter `similar_chapters` | ❌ Proxied to semantic-search-service |
| Cache enriched data | ❌ Semantic-search handles caching |
| Apply taxonomy to results | ❌ Done by downstream service |
| Trigger enrichment updates | ❌ CI/CD handles in ai-platform-data |

### Gateway DOES:

| Aspect | Gateway Role |
|--------|--------------|
| Pass `taxonomy` parameter | ✅ Extracted from user prompt/session |
| Pass `tier_filter` parameter | ✅ From session context |
| Proxy to semantic-search | ✅ Transparent routing |
| Return results unchanged | ✅ No interpretation |

### Architecture Compliance

```
User: "Get similar chapters for arch_patterns_ch4, use AI-ML taxonomy"
    ↓
LLM Gateway (Router) - EXTRACTS taxonomy, PROXIES request
    ↓
POST http://semantic-search:8081/v1/search/similar-chapters
{
    "chapter_id": "arch_patterns_ch4",
    "taxonomy": "AI-ML_taxonomy"
}
    ↓
Semantic Search Service - FILTERS similar_chapters by taxonomy
    ↓
{
    "similar_chapters": [...filtered results with tier info...]
}
    ↓
LLM Gateway - RETURNS results unchanged to user
```

The gateway requires **no code changes** to support enrichment scalability. All filtering logic is in semantic-search-service.

---

## Components

### Provider Router
Routes requests to the appropriate LLM provider based on model name or configuration.

### Tool-Use Orchestrator
- Registers available tools
- Parses LLM tool_call responses
- Executes tools (local or proxied to other microservices)
- Returns results to LLM for continuation
- **Passes taxonomy context to downstream services**

### Session Manager
- Creates sessions with TTL
- Stores conversation history
- **Stores taxonomy context per session**
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
| ai-agents | Microservice | Cross-reference, agent functions |
| Code-Orchestrator | Microservice | Code analysis tools |
| context-management-service | Microservice | Context/session management |
| inference-service | Microservice | Local LLM inference (llamacpp provider) |
| Anthropic API | External | LLM provider (cloud) |
| OpenAI API | External | LLM provider (cloud) |
| Google Gemini API | External | LLM provider (cloud) |
| DeepSeek API | External | LLM provider (cloud) |
| OpenRouter API | External | Multi-provider routing |

---

## Provider Routing

The gateway routes LLM requests to the appropriate provider based on the `model` parameter:

### Supported Providers (11 Total)

| Provider | Models | Target |
|----------|--------|--------|
| `anthropic` | `claude-*` | Anthropic API |
| `openai` | `gpt-*` | OpenAI API |
| `gemini` | `gemini-*` | Google Gemini API |
| `deepseek` | `deepseek-*` | DeepSeek API |
| `openrouter` | Various | OpenRouter (multi-provider) |
| `ollama` | `ollama/*` | Local Ollama server |
| `llamacpp` | `local/*`, GGUF | inference-service:8085 |
| `inference` | Via CMS | inference-service (managed) |
| `fake` | `fake/*` | Test/mock responses |

### Provider Resolution

| Model Pattern | Provider | Target |
|---------------|----------|--------|
| `claude-*`, `anthropic/*` | Anthropic | Anthropic API |
| `gpt-*`, `openai/*` | OpenAI | OpenAI API |
| `ollama/*` | Ollama | Local Ollama server |
| `local/*`, GGUF models | LlamaCpp | inference-service:8085 |

### LlamaCpp Provider (Local Inference)

The `llamacpp` provider routes requests to `inference-service:8085` for local GGUF model inference:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LlamaCpp Provider → Inference Service                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Gateway receives:                                                           │
│  POST /v1/chat/completions                                                  │
│  { "model": "local/phi-4", "messages": [...] }                              │
│                                                                              │
│  Provider Router identifies: model prefix "local/" → LlamaCppProvider       │
│                                                                              │
│  LlamaCppProvider proxies to:                                               │
│  POST http://inference-service:8085/v1/chat/completions                     │
│  { "model": "phi-4", "messages": [...] }                                    │
│                                                                              │
│  Supported models (via inference-service):                                  │
│  - phi-4 (8.4GB)              - deepseek-r1-7b (4.7GB)                      │
│  - qwen2.5-7b (4.5GB)         - llama-3.2-3b (2.0GB)                        │
│  - phi-3-medium-128k (8.6GB)  - granite-8b-code-128k (4.5GB)                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

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
