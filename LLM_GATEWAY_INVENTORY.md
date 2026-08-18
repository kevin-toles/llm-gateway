# LLM Gateway Service - Comprehensive Inventory

**Service Location:** `/Users/kevintoles/POC/llm-gateway`  
**Generated:** 2026-01-27  
**Port:** 8080

---

## 1. Module Inventory

### 1.1 Core Structure

```
src/
├── main.py                          # FastAPI application entry point
├── api/
│   ├── deps.py                      # Dependency injection utilities
│   ├── middleware/
│   │   ├── logging.py               # Request/response logging
│   │   ├── memory.py                # Memory tracking & backpressure (WBS-PS5)
│   │   └── rate_limit.py            # Rate limiting middleware
│   └── routes/
│       ├── chat.py                  # /v1/chat/* endpoints
│       ├── cms_routing.py           # CMS tier routing logic
│       ├── health.py                # Health check endpoints
│       ├── models.py                # /v1/models endpoint
│       ├── responses.py             # /v1/responses endpoint (GPT-5.2/o3)
│       ├── sessions.py              # /v1/sessions/* endpoints
│       └── tools.py                 # /v1/tools/* endpoints
├── clients/
│   ├── ai_agents.py                 # AI Agents service client
│   ├── circuit_breaker.py           # Circuit breaker for HTTP clients
│   ├── cms_client.py                # Context Management Service client
│   ├── http.py                      # HTTP client factory with pooling
│   └── semantic_search.py           # Semantic Search service client
├── core/
│   ├── config.py                    # Pydantic Settings configuration
│   ├── exceptions.py                # Custom exception hierarchy
│   └── logging.py                   # Logging configuration
├── models/
│   ├── domain.py                    # Domain models (Message, ToolCall)
│   ├── requests.py                  # Pydantic request models
│   ├── responses.py                 # Pydantic response models
│   └── tools.py                     # Tool-related models
├── observability/
│   ├── logging.py                   # Structured logging
│   ├── metrics.py                   # Prometheus metrics
│   └── tracing.py                   # OpenTelemetry tracing
├── providers/
│   ├── base.py                      # LLMProvider ABC (interface)
│   ├── anthropic.py                 # Anthropic Claude adapter
│   ├── deepseek.py                  # DeepSeek adapter
│   ├── fake.py                      # Fake provider for testing
│   ├── gemini.py                    # Google Gemini adapter
│   ├── inference.py                 # Local inference-service adapter
│   ├── llamacpp.py                  # LlamaCpp GGUF adapter
│   ├── ollama.py                    # Ollama adapter
│   ├── openai.py                    # OpenAI GPT adapter
│   ├── openrouter.py                # OpenRouter aggregator adapter
│   └── router.py                    # Provider routing logic
├── resilience/
│   ├── circuit_breaker_state_machine.py  # Circuit breaker FSM
│   ├── fallback_chain.py            # Fallback provider chain
│   └── metrics.py                   # Resilience metrics
├── services/
│   ├── cache.py                     # Response caching service
│   ├── chat.py                      # Chat completion orchestration
│   └── cost_tracker.py              # Cost tracking service
├── sessions/
│   ├── manager.py                   # Session lifecycle manager
│   └── store.py                     # Session storage interface
└── tools/
    ├── executor.py                  # Tool execution engine
    ├── registry.py                  # Tool registry
    └── builtin/
        ├── architecture.py          # analyze_architecture tool
        ├── chunk_retrieval.py       # get_chunk tool
        ├── code_orchestrator_tools.py  # Code orchestrator tools
        ├── code_review.py           # review_code tool
        ├── cross_reference.py       # cross_reference tool
        ├── doc_generate.py          # generate_documentation tool
        ├── embed.py                 # Embedding tool
        ├── enrich_metadata.py       # MSEP metadata enrichment
        ├── hybrid_search.py         # Hybrid search tool
        └── semantic_search.py       # search_corpus tool
```

---

## 2. API Surface

### 2.1 Health Endpoints

| Method | Path | Request | Response | Status Codes | Location |
|--------|------|---------|----------|--------------|----------|
| `GET` | `/health` | None | `HealthResponse` | 200 | [health.py#L351](src/api/routes/health.py#L351) |
| `GET` | `/health/detailed` | None | `DetailedHealthResponse` | 200, 503 | [health.py#L369](src/api/routes/health.py#L369) |
| `GET` | `/health/ready` | None | `ReadinessResponse` | 200, 503 | [health.py#L418](src/api/routes/health.py#L418) |

**Response Models:**
```python
class HealthResponse(BaseModel):
    status: str                    # "healthy"
    version: str                   # "1.0.0"
    models_available: int          # 0 (use /detailed for actual count)
    inference_service: str         # "unchecked"

class DetailedHealthResponse(BaseModel):
    status: str                    # "healthy" | "degraded"
    version: str
    models_available: int
    inference_service: str         # "up" | "up_no_models" | "down"
    memory: dict | None            # Memory metrics (WBS-PS5)
    backpressure: dict | None      # Backpressure status

class ReadinessResponse(BaseModel):
    status: str                    # "ready" | "degraded" | "not_ready"
    checks: dict[str, bool]        # redis, semantic_search, ai_agents, inference_service
    models_available: int
```

---

### 2.2 Chat Completions

| Method | Path | Request | Response | Streaming | Location |
|--------|------|---------|----------|-----------|----------|
| `POST` | `/v1/chat/completions` | `ChatCompletionRequest` | `ChatCompletionResponse` or SSE | Yes (SSE) | [chat.py#L378](src/api/routes/chat.py#L378) |

**Request Model (`ChatCompletionRequest`):**
```python
class ChatCompletionRequest(BaseModel):
    model: str                                    # Required: e.g., "gpt-5.2", "claude-opus-4.5"
    messages: list[Message]                       # Required: conversation history
    temperature: Optional[float] = None           # 0.0-2.0
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    n: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[list[str] | str] = None
    presence_penalty: Optional[float] = None      # -2.0 to 2.0
    frequency_penalty: Optional[float] = None     # -2.0 to 2.0
    tools: Optional[list[Tool]] = None            # Function calling
    tool_choice: Optional[str | dict] = None
    user: Optional[str] = None
    seed: Optional[int] = None
    session_id: Optional[str] = None              # Session continuity
```

**Custom Headers (CMS Integration):**
| Header | Direction | Values | Description |
|--------|-----------|--------|-------------|
| `X-CMS-Mode` | Request | `none`, `validate`, `optimize`, `plan`, `auto` | Control CMS behavior |
| `X-CMS-Routed` | Response | `true`, `false` | Whether request was routed to CMS |
| `X-CMS-Tier` | Response | `1`, `2`, `3`, `4` | Token utilization tier |
| `X-Token-Count` | Response | integer | Estimated token count |
| `X-Token-Limit` | Response | integer | Model's context limit |

**Streaming Behavior:**
- When `stream=true`: Returns `StreamingResponse` with `media_type="text/event-stream"`
- SSE format: `data: {chunk_json}\n\n`
- End marker: `data: [DONE]\n\n`

**Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Success (non-streaming) |
| 404 | Model requires Responses API (gpt-5.2-pro, o3, etc.) |
| 422 | Request validation failed |
| 502 | Provider error (upstream failure) |
| 503 | CMS unavailable for Tier 3+ requests |

---

### 2.3 Responses API (OpenAI Responses API Compatibility)

| Method | Path | Request | Response | Location |
|--------|------|---------|----------|----------|
| `POST` | `/v1/responses` | `ResponsesRequest` | `ResponsesResponse` | [responses.py#L683](src/api/routes/responses.py#L683) |

**Supported Models:**
- `gpt-5.2-pro`, `gpt-5.1-pro`, `gpt-5-pro`
- `o3`, `o3-mini`, `o1`, `o1-mini`, `o1-preview`

**Request Model:**
```python
class ResponsesRequest(BaseModel):
    model: str                                    # Required
    input: str | list[dict]                       # Text/image inputs
    instructions: Optional[str] = None            # System message
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None           # 0.0-2.0
    top_p: Optional[float] = None                 # 0.0-1.0
    stream: Optional[bool] = False
    tools: Optional[list[dict]] = None
    tool_choice: Optional[str | dict] = None
    previous_response_id: Optional[str] = None    # Multi-turn
    store: Optional[bool] = True
    metadata: Optional[dict[str, str]] = None
    reasoning: Optional[dict] = None              # For o-series/gpt-5 models
```

**Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Success |
| 502 | Provider error |
| 500 | Internal error |

---

### 2.4 Models Discovery

| Method | Path | Request | Response | Location |
|--------|------|---------|----------|----------|
| `GET` | `/v1/models` | None | `{"object": "list", "data": [...]}` | [models.py#L46](src/api/routes/models.py#L46) |
| `GET` | `/v1/models/{model_id}` | `model_id` path param | Model object or error | [models.py#L92](src/api/routes/models.py#L92) |
| `GET` | `/v1/providers` | None | Provider-to-models mapping | [models.py#L125](src/api/routes/models.py#L125) |

---

### 2.5 Sessions

| Method | Path | Request | Response | Status Codes | Location |
|--------|------|---------|----------|--------------|----------|
| `POST` | `/v1/sessions` | `SessionCreateRequest` | `SessionResponse` | 201 | [sessions.py#L175](src/api/routes/sessions.py#L175) |
| `GET` | `/v1/sessions/{session_id}` | None | `SessionResponse` | 200, 404 | [sessions.py#L211](src/api/routes/sessions.py#L211) |
| `DELETE` | `/v1/sessions/{session_id}` | None | Empty | 204, 404 | [sessions.py#L256](src/api/routes/sessions.py#L256) |

**Request/Response Models:**
```python
class SessionCreateRequest(BaseModel):
    ttl_seconds: Optional[int] = None     # Session TTL (min: 60)
    context: Optional[dict] = None        # Initial context

class SessionResponse(BaseModel):
    id: str
    messages: list[dict]
    context: dict
    created_at: str                       # ISO 8601
    expires_at: str                       # ISO 8601
```

---

### 2.6 Tools Execution

| Method | Path | Request | Response | Location |
|--------|------|---------|----------|----------|
| `GET` | `/v1/tools` | None | `list[ToolDefinition]` | [tools.py#L858](src/api/routes/tools.py#L858) |
| `POST` | `/v1/tools/execute` | `ToolExecuteRequest` | `ToolExecuteResponse` | [tools.py#L871](src/api/routes/tools.py#L871) |

**Available Tools:**
| Tool Name | Description | Service Proxy |
|-----------|-------------|---------------|
| `echo` | Echo input message | Local |
| `calculator` | Basic arithmetic | Local |
| `search_corpus` | Semantic search | semantic-search-service |
| `get_chunk` | Retrieve chunk by ID | semantic-search-service |
| `review_code` | Code review | ai-agents |
| `analyze_architecture` | Architecture analysis | ai-agents |
| `generate_documentation` | Doc generation | ai-agents |
| `cross_reference` | Cross-reference agent | ai-agents |
| `enrich_metadata` | MSEP enrichment | ai-agents |

**Request/Response Models:**
```python
class ToolExecuteRequest(BaseModel):
    name: str                              # Tool name
    arguments: dict[str, Any]              # Tool arguments

class ToolExecuteResponse(BaseModel):
    name: str
    result: dict[str, Any] | None
    success: bool
    error: str | None
```

**Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Success |
| 404 | Tool not found |
| 422 | Invalid arguments |

---

## 3. Interactions (What it Calls)

### 3.1 External HTTP Calls

| Service | Client Module | Base URL | Purpose |
|---------|---------------|----------|---------|
| **semantic-search-service** | `clients/semantic_search.py` | `http://localhost:8081` | Search, embeddings, chunk retrieval |
| **ai-agents** | `clients/ai_agents.py` | `http://localhost:8082` | Tool execution, code review, architecture analysis |
| **inference-service** | `providers/inference.py` | `http://localhost:8085` | Local GGUF model inference |
| **context-management-service** | `clients/cms_client.py` | `http://localhost:8086` | Token optimization, chunking |
| **code-orchestrator** | (tools) | `http://localhost:8083` | Code analysis tools |

### 3.2 External Provider APIs

| Provider | Module | API Endpoint |
|----------|--------|--------------|
| **OpenAI** | `providers/openai.py` | `https://api.openai.com/v1/chat/completions` |
| **OpenAI Responses** | `providers/openai.py` | `https://api.openai.com/v1/responses` |
| **Anthropic** | `providers/anthropic.py` | `https://api.anthropic.com/v1/messages` |
| **Google Gemini** | `providers/gemini.py` | `https://generativelanguage.googleapis.com/v1beta` |
| **DeepSeek** | `providers/deepseek.py` | `https://api.deepseek.com/chat/completions` |
| **OpenRouter** | `providers/openrouter.py` | `https://openrouter.ai/api/v1` |
| **Ollama** | `providers/ollama.py` | `http://localhost:11434` |

### 3.3 Database Connections

| Database | Usage | Environment Variable |
|----------|-------|----------------------|
| **Redis** | Session storage, caching | `LLM_GATEWAY_REDIS_URL` (default: `redis://localhost:6379`) |

**Note:** Neo4j and Qdrant are accessed via semantic-search-service and ai-agents, not directly.

### 3.4 Environment Variables

**Service Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_PORT` | 8080 | Service port |
| `LLM_GATEWAY_ENV` | development | Environment |
| `LLM_GATEWAY_LOG_LEVEL` | INFO | Log level |
| `LLM_GATEWAY_VERSION` | 1.0.0 | Service version |
| `LLM_GATEWAY_CORS_ORIGINS` | (empty) | CORS origins (comma-separated) |

**Provider API Keys:**
| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_GATEWAY_OPENAI_API_KEY` | For OpenAI | OpenAI API key |
| `LLM_GATEWAY_ANTHROPIC_API_KEY` | For Anthropic | Anthropic API key |
| `LLM_GATEWAY_DEEPSEEK_API_KEY` | For DeepSeek | DeepSeek API key |
| `LLM_GATEWAY_GOOGLE_API_KEY` | For Gemini | Google AI API key |
| `LLM_GATEWAY_OPENROUTER_API_KEY` | For OpenRouter | OpenRouter API key |

**Microservice URLs:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `LLM_GATEWAY_SEMANTIC_SEARCH_URL` | `http://localhost:8081` | Semantic search service |
| `LLM_GATEWAY_AI_AGENTS_URL` | `http://localhost:8082` | AI agents service |
| `INFERENCE_SERVICE_URL` | `http://localhost:8085` | Inference service |
| `CMS_URL` | `http://localhost:8086` | Context management service |
| `CODE_ORCHESTRATOR_URL` | `http://localhost:8083` | Code orchestrator |

**Resilience Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | Failures before open |
| `LLM_GATEWAY_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` | 30.0 | Recovery wait time |
| `LLM_GATEWAY_SEMANTIC_SEARCH_TIMEOUT_SECONDS` | 30.0 | Service timeout |

**Memory/Backpressure (WBS-PS5):**
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_MEMORY_THRESHOLD_MB` | 1024 | Memory limit (MB) |
| `LLM_GATEWAY_MEMORY_SOFT_LIMIT_PERCENT` | 0.8 | Soft limit ratio |
| `LLM_GATEWAY_MAX_CONCURRENT_REQUESTS` | 50 | Max concurrent requests |
| `LLM_GATEWAY_QUEUE_WARNING_THRESHOLD` | 30 | Queue warning level |

---

## 4. Reverse References (Who Imports What)

### 4.1 Provider Router Usage

```
src/providers/router.py::ProviderRouter
├── src/api/routes/chat.py (get_chat_service → create_provider_router)
├── src/api/routes/models.py (get_provider_router)
├── src/api/routes/responses.py (used for model resolution)
└── src/services/chat.py (injected dependency)
```

### 4.2 Tool Registry Usage

```
src/tools/registry.py::get_tool_registry
└── src/api/routes/chat.py (get_chat_service → ToolExecutor)

src/api/routes/tools.py::BUILTIN_TOOLS
└── Used directly by ToolExecutorService
```

### 4.3 Client Usage

```
src/clients/semantic_search.py::SemanticSearchClient
├── src/api/routes/health.py (check_semantic_search_health)
└── src/tools/builtin/semantic_search.py (search_corpus)

src/clients/ai_agents.py::AIAgentsClient
├── src/api/routes/health.py (check_ai_agents_health)
└── src/tools/builtin/*.py (tool proxies)

src/clients/cms_client.py::CMSClient
└── src/api/routes/cms_routing.py (CMS integration)
```

### 4.4 Exception Usage

```
src/core/exceptions.py
├── ProviderError → src/api/routes/chat.py, responses.py
├── SessionError → src/api/routes/sessions.py
├── AuthenticationError → src/providers/*.py
└── RateLimitError → src/providers/*.py
```

---

## 5. Issues/Observations

### 5.1 Missing Tests

| Module | Status | Notes |
|--------|--------|-------|
| `src/api/routes/responses.py` | ⚠️ Partial | No dedicated test file found |
| `src/providers/gemini.py` | ⚠️ Partial | Limited test coverage |
| `src/api/routes/cms_routing.py` | ✅ | Has `test_cms_routing.py` |
| `src/services/cache.py` | ❓ Unknown | Not verified |
| `src/services/cost_tracker.py` | ❓ Unknown | Not verified |

### 5.2 Unclear Contracts

1. **Stub ChatService vs Real ChatService** ([chat.py#L85-94](src/api/routes/chat.py#L85))
   - Route file contains a stub `ChatService` class
   - Real implementation in `src/services/chat.py`
   - Comment indicates migration in progress (Issue 27)
   
2. **CMS Tier Thresholds** ([cms_routing.py](src/api/routes/cms_routing.py))
   - Tier boundaries (25%, 50%, 75%) are hardcoded
   - No configuration option for custom thresholds

3. **Tool Execution Timeout**
   - `AIAgentsClient` has 60s timeout
   - Other tools inherit from HTTP client factory (30s default)
   - No per-tool timeout configuration

### 5.3 Hardcoded Values

| Location | Value | Recommendation |
|----------|-------|----------------|
| [chat.py#L61](src/api/routes/chat.py#L61) | `DEFAULT_MODEL = "gpt-4"` | Move to config |
| [cms_routing.py#L44-51](src/api/routes/cms_routing.py#L44) | `MODEL_CONTEXT_LIMITS` | Load from config/database |
| [router.py#L60-80](src/providers/router.py#L60) | `LOCAL_MODELS`, `EXTERNAL_MODELS` | Dynamic discovery |
| [responses.py#L175-183](src/api/routes/responses.py#L175) | `OPENAI_RESPONSES_MODELS` | Should sync with router |

### 5.4 Error Handling Gaps

1. **Missing Circuit Breaker on CMS Client**
   - `cms_client.py` doesn't use circuit breaker
   - Other clients (semantic_search, ai_agents) have circuit breakers
   
2. **Responses API Error Handling**
   - Catches generic `Exception` as catch-all
   - Could mask specific error types

3. **Session TTL Enforcement**
   - In-memory session store doesn't enforce TTL expiration
   - Comment indicates Redis integration pending

### 5.5 Deprecated/Legacy Code

1. **LlamaCpp Provider** ([providers/llamacpp.py](src/providers/llamacpp.py))
   - Superseded by `inference-service` provider
   - Still present but rarely used (marked for legacy support)

2. **Ollama Provider** ([providers/ollama.py](src/providers/ollama.py))
   - Requires explicit `ollama/` prefix
   - Not auto-routed

3. **Old Metrics Endpoint** (Removed - WBS-OBS13)
   - Comment in [health.py#L506](src/api/routes/health.py#L506) explains removal
   - Replaced by `prometheus_client` implementation

### 5.6 Potential Improvements

1. **Model Registry Consolidation**
   - Model lists duplicated across `router.py`, `responses.py`, `cms_routing.py`
   - Should be centralized in config or shared module

2. **Health Check Parallelization**
   - `/health/ready` calls services sequentially
   - Could use `asyncio.gather` for parallel checks

3. **Tool Registration API**
   - Currently tools are hardcoded in `BUILTIN_TOOLS`
   - No dynamic tool registration endpoint

4. **Session Cleanup**
   - No background task for expired session cleanup
   - Relies on external cleanup (Redis TTL when implemented)

---

## 6. Provider Routing Summary

### 6.1 Routing Priority

1. **Provider aliases** (`openai` → `gpt-5.2`, `claude` → `claude-opus-4-5-20250514`)
2. **Explicit prefix** (`openrouter/`, `ollama/`, `deepseek-api/`)
3. **Local model match** (exact match in `LOCAL_MODELS` → inference-service)
4. **External model match** (exact match in `EXTERNAL_MODELS` → specific provider)
5. **Prefix match** (`claude-` → anthropic, `gpt-` → openai, etc.)
6. **Default** (unknown models → inference-service)

### 6.2 Local Models (inference-service)

```
phi-4, qwen2.5-7b, qwen3-8b, llama-3.2-3b, gpt-oss-20b,
deepseek-r1-7b, phi-3-medium-128k,
codellama-7b-instruct, codellama-13b, qwen2.5-coder-7b,
qwen3-coder-30b, starcoder2-7b, codegemma-7b,
deepseek-coder-v2-lite, granite-8b-code-128k, granite-20b-code
```

### 6.3 Cloud Provider Prefixes

| Prefix | Provider |
|--------|----------|
| `claude-` | anthropic |
| `gpt-` | openai |
| `gemini-` | google |
| `deepseek-` | deepseek |
| `openrouter/` | openrouter (explicit only) |
| `ollama/` | ollama (explicit only) |

---

## 7. Test Coverage Overview

```
tests/
├── unit/
│   ├── api/            # Route tests
│   ├── clients/        # Client tests
│   ├── core/           # Config/exception tests
│   ├── models/         # Model validation tests
│   ├── observability/  # Metrics/tracing tests
│   ├── providers/      # Provider adapter tests
│   ├── resilience/     # Circuit breaker tests
│   ├── services/       # Service layer tests
│   ├── sessions/       # Session manager tests
│   └── tools/          # Tool executor tests
├── integration/
│   ├── test_health.py
│   ├── test_chat_integration.py
│   ├── test_sessions.py
│   ├── test_tools_execution.py
│   ├── test_ai_agents_integration.py
│   ├── test_fallback_chain.py
│   └── test_resilience.py
└── contract/           # Contract tests (if any)
```

---

## 8. Quick Reference

### Starting the Service

```bash
cd /Users/kevintoles/POC/llm-gateway
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

### Testing Chat Completion

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-8b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Health Check

```bash
curl http://localhost:8080/health/ready
```

### List Available Models

```bash
curl http://localhost:8080/v1/models
```

---

*End of Inventory*
