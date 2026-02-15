# llm-gateway: Technical Change Log

**Purpose**: Documents architectural decisions, API changes, and significant updates to the LLM Gateway service (cloud LLM routing, provider management).

---

## Changelog

### 2026-01-26: Chat and Responses Routes Enhancement (CL-009)

**Summary**: Refactored chat and responses route handlers with improved error handling and response formatting.

**Commit:** `52f8d58`

**Files Changed:**

| File | Changes |
|------|---------|
| `src/api/routes/chat.py` | +78 lines: Improved chat handling |
| `src/api/routes/responses.py` | +105 lines: Enhanced response formatting |
| `src/main.py` | +11 lines: Route registration updates |

---

### 2026-01-25: OBS-5 Resilience Metrics Export (CL-008)

**Summary**: Added Prometheus export for circuit breaker and resilience metrics, completing the observability integration.

**Commit:** `c7e0707`

**New Metrics:**

| Metric | Type | Purpose |
|--------|------|---------|
| `circuit_breaker_state` | Gauge | Current circuit state (open/closed/half-open) |
| `circuit_breaker_failures` | Counter | Failure count triggering circuit open |
| `retry_attempts_total` | Counter | Retry attempt count by operation |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/observability/__init__.py` | +12 lines: Resilience metrics export |

**Cross-References:**
- WBS-OBS-5: Resilience metrics work package
- CL-005: Resilience layer implementation

---

### 2026-01-18: WBS-OBS OpenTelemetry and Prometheus (CL-007)

**Summary**: Wired OpenTelemetry tracing and Prometheus metrics for full observability integration.

**New Metrics:**

| Metric | Type | Purpose |
|--------|------|---------|
| `llm_request_duration_seconds` | Histogram | Request latency |
| `llm_request_total` | Counter | Request count by provider |
| `llm_tokens_total` | Counter | Token usage |
| `llm_errors_total` | Counter | Error count by type |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/observability/metrics.py` | Prometheus metrics |
| `src/observability/tracing.py` | OpenTelemetry integration |
| `src/api/middleware.py` | Metrics middleware |

**Cross-References:**
- WBS-OBS: Observability work packages

---

### 2026-01-15: WBS-LOG0 Structured JSON Logging (CL-006)

**Summary**: Added structured JSON logging with correlation ID support for distributed tracing.

**Logging Features:**

| Feature | Purpose |
|---------|---------|
| JSON Format | Machine-readable logs |
| Correlation ID | Request tracing across services |
| Log Levels | Configurable per-module |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/core/logging.py` | Structured logging setup |
| `src/api/middleware.py` | Correlation ID propagation |

**Cross-References:**
- WBS-LOG0: Logging architecture

---

### 2026-01-12: Resilience Layer and Code Orchestrator Tools (CL-005)

**Summary**: Added resilience infrastructure and integration with Code Orchestrator service tools.

**Resilience Features:**

| Feature | Purpose |
|---------|---------|
| Circuit Breaker | Provider failure handling |
| Retry Policy | Automatic retries with backoff |
| Timeout Management | Configurable timeouts |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/resilience/` | New resilience module |
| `src/clients/code_orchestrator.py` | COS integration |

---

### 2026-01-10: CMS Integration WBS-CMS11 (CL-004)

**Summary**: Added Context Management Service integration for tier calculation and header propagation.

**CMS Integration:**

| Feature | Purpose |
|---------|---------|
| Tier Calculation | Compute CMS tier for requests |
| Header Propagation | Pass CMS headers to providers |
| CMS Client | HTTP client for CMS service |

**Note**: Gateway calculates tiers and adds headers but does NOT call CMS.process() for optimization - that's handled by services routing through CMS directly.

**Files Changed:**

| File | Changes |
|------|---------|
| `src/clients/cms_client.py` | CMS HTTP client |
| `src/api/routes/cms_routing.py` | Tier calculation |
| `src/api/routes/chat.py` | CMS header propagation |

**Cross-References:**
- WBS_CMS_DUAL_ROUTING_AND_LOGGING.md: CMS11 work package

---

### 2026-01-08: WBS-PS5 OOM Prevention (CL-003)

**Summary**: Added memory tracking and backpressure mechanisms to prevent out-of-memory conditions during high load.

**Features:**

| Feature | Purpose |
|---------|---------|
| Memory Tracking | Monitor heap usage |
| Backpressure | Reject requests when memory high |
| Graceful Degradation | Reduce batch sizes under load |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/core/memory.py` | Memory monitoring |
| `src/api/middleware.py` | Backpressure middleware |

**Cross-References:**
- WBS-PS5: Platform stability

---

### 2026-01-05: Multi-Provider Routing (CL-002)

**Summary**: Added support for multiple cloud LLM providers with intelligent routing.

**Supported Providers:**

| Provider | Models | Configuration |
|----------|--------|---------------|
| Anthropic | claude-3-*, claude-3.5-* | ANTHROPIC_API_KEY |
| OpenAI | gpt-4*, gpt-3.5*, o1*, o3* | OPENAI_API_KEY |
| Google | gemini-* | GEMINI_API_KEY |
| DeepSeek | deepseek-* | DEEPSEEK_API_KEY |
| OpenRouter | Any via router | OPENROUTER_API_KEY |

**Routing Logic:**

| Model Pattern | Provider |
|---------------|----------|
| `claude-*` | Anthropic |
| `gpt-*`, `o1*` | OpenAI |
| `gemini-*` | Google |
| `deepseek-*` | DeepSeek |
| Fallback | OpenRouter |

**Files Changed:**

| File | Changes |
|------|---------|
| `src/providers/` | Provider implementations |
| `src/routing/model_router.py` | Model→provider routing |
| `config/providers.yaml` | Provider configuration |

---

### 2026-01-01: Initial LLM Gateway (CL-001)

**Summary**: Initial LLM Gateway service with OpenAI-compatible API and provider abstraction.

**Core Components:**

| Component | Purpose |
|-----------|---------|
| `ChatRouter` | Route chat completions |
| `ProviderManager` | Manage provider clients |
| `RateLimiter` | Per-provider rate limiting |

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/v1/chat/completions` | POST | Chat completions (OpenAI-compatible) |
| `/v1/models` | GET | List available models |

**Configuration:**

| Setting | Default | Purpose |
|---------|---------|---------|
| `LLM_GATEWAY_PORT` | 8080 | Service port |
| `REDIS_URL` | `redis://localhost:6379` | Rate limit storage |

**Cross-References:**
- ARCHITECTURE.md: Full gateway architecture
