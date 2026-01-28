# Issue Write-Up: LLM Gateway Multi-Provider Routing

> **Version:** 1.0.0  
> **Date:** January 8, 2026  
> **Status:** RESOLVED  
> **Severity:** P1 - Critical Path Blocker  
> **References:** 
> - [TECHNICAL_CHANGE_LOG.md](TECHNICAL_CHANGE_LOG.md) - CL-035, CL-036
> - [Platform Documentation/UNIFIED_KITCHEN_BRIGADE_ARCHITECTURE.md](../../Platform%20Documentation/UNIFIED_KITCHEN_BRIGADE_ARCHITECTURE.md)
> - [ai-agents/docs/guides/MODEL_LIBRARY.md](../../ai-agents/docs/guides/MODEL_LIBRARY.md) - Brigade Tier System

---

## Executive Summary

The Kitchen Brigade protocol was failing when attempting to use multiple LLM providers (OpenAI GPT-5.2, Claude Opus 4.5, DeepSeek Reasoner, and local Qwen3). External models returned 400 errors, and the system couldn't properly route requests to different providers. The root cause was a single-provider endpoint design that assumed all requests should be sent to OpenAI's API, regardless of the requested model.

---

## 1. Complete Root Cause Analysis

### 1.1 Single-Provider Endpoint Design Problem

The LLM Gateway's `/v1/responses` endpoint was originally designed to only call OpenAI's Responses API. When Claude or DeepSeek models were requested, the endpoint still attempted to send them to OpenAI, resulting in 400 errors (invalid model).

**BEFORE: Only OpenAI Supported (Problematic)**

```python
# src/api/routes/responses.py - ORIGINAL (PROBLEMATIC)
class ResponsesService:
    """Responses API handler - OpenAI only."""
    
    async def create_response(self, request: ResponsesRequest) -> ResponsesResponse:
        # BUG: Always called OpenAI regardless of model
        api_key = settings.openai_api_key.get_secret_value()
        
        async with httpx.AsyncClient() as client:
            # WRONG: Sending claude-opus-4.5 to api.openai.com
            response = await client.post(
                "https://api.openai.com/v1/responses",
                json={"model": request.model, "input": request.input},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            # Returns 400: "claude-opus-4.5 is not a valid OpenAI model"
            return self._transform_response(response.json())
```

**Failure Scenario Timeline:**

```
[Kitchen Brigade Protocol - Roundtable Discussion]

1. User requests: "Analyze this architecture using Premium tier"
2. ai-agents executor calls llm-gateway with model="claude-opus-4.5" (Analyst role)
3. Gateway /v1/responses receives request
4. Gateway sends to https://api.openai.com/v1/responses
5. OpenAI returns 400: "Invalid model: claude-opus-4.5"
6. Protocol fails, no fallback attempted
```

### 1.2 Missing Provider Abstraction in Responses API

While the `/v1/chat/completions` endpoint had proper provider routing via `ProviderRouter`, the `/v1/responses` endpoint was implemented as a separate code path without leveraging the existing routing infrastructure.

**Problem Areas Identified:**

| Component | Issue | Impact |
|-----------|-------|--------|
| `responses.py` | No provider type detection | All models sent to OpenAI |
| `responses.py` | No API format translation | Anthropic/DeepSeek require different formats |
| `responses.py` | No error handling per provider | Generic errors, no retry logic |
| `router.py` | Not used by Responses endpoint | Routing logic duplicated/missing |

### 1.3 API Format Incompatibility

Each provider has a different API contract:

| Provider | Endpoint | Request Format | Auth Header |
|----------|----------|----------------|-------------|
| OpenAI | `/v1/responses` | `{model, input, instructions}` | `Authorization: Bearer` |
| Anthropic | `/v1/messages` | `{model, messages, system}` | `x-api-key` + `anthropic-version` |
| DeepSeek | `/chat/completions` | `{model, messages}` (OpenAI-compatible) | `Authorization: Bearer` |
| Google | `generateContent` | `{contents, generationConfig}` | `x-goog-api-key` |

---

## 2. Architecture Impact on Kitchen Brigade

### 2.1 Kitchen Brigade Protocol Dependency

The Kitchen Brigade Protocol Executor relies on the LLM Gateway for all model invocations across three tiers:

```yaml
# Brigade Tier System (from ai-agents/docs/guides/MODEL_LIBRARY.md)

local_only:  # Zero cost
  analyst: deepseek-r1-7b       # inference-service
  critic: qwen3-8b              # inference-service
  synthesizer: phi-4            # inference-service
  validator: codellama-13b      # inference-service

balanced:    # Mixed local + external
  analyst: claude-sonnet-4.5    # Anthropic API (FAILED)
  critic: qwen3-8b              # inference-service (OK)
  synthesizer: gpt-5-mini       # OpenAI API (FAILED)
  validator: codellama-13b      # inference-service (OK)

premium:     # Maximum quality
  analyst: claude-opus-4.5      # Anthropic API (FAILED)
  critic: gpt-5.2-pro           # OpenAI API (OK)
  synthesizer: gemini-1.5-pro   # Google API (NOT IMPLEMENTED)
  validator: claude-sonnet-4.5  # Anthropic API (FAILED)
```

**Impact Summary:**
- ❌ `local_only` tier: **Partially broken** - DeepSeek cloud calls failed
- ❌ `balanced` tier: **Broken** - 50% of models unreachable
- ❌ `premium` tier: **Broken** - 75% of models unreachable

### 2.2 Tiered Fallback Failure

The Kitchen Brigade pattern implements tiered fallback (local → cloud → passthrough), but without proper provider routing, the fallback chain was effectively:

```
INTENDED:   local-model → cloud-model → gateway-passthrough
ACTUAL:     local-model → OpenAI-only → ERROR (no retry)
```

### 2.3 Service Discovery Impact

The Kitchen Brigade architecture relies on the Gateway as the single entry point:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ llm-document-   │     │  llm-gateway    │     │   inference-    │
│   enhancer      │────▶│    :8080        │────▶│   service:8085  │
│  (CUSTOMER)     │     │   (ROUTER)      │     │   (LINE COOK)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
     ┌──────────────┐   ┌───────────────┐   ┌───────────────┐
     │  OpenAI API  │   │ Anthropic API │   │ DeepSeek API  │
     │   (gpt-*)    │   │  (claude-*)   │   │ (deepseek-*)  │
     └──────────────┘   └───────────────┘   └───────────────┘
```

When the Router only knows OpenAI, the entire architecture collapses to a single provider.

---

## 3. Solution Design: Multi-Provider Routing Architecture

### 3.1 Provider Detection Strategy

Implement a `get_provider_type()` classifier that determines the target provider from the model name:

```python
# AFTER: Multi-provider routing in ResponsesService
class ResponsesService:
    """Service for handling Responses API requests.
    
    Routes requests to the appropriate provider:
    - OpenAI models (gpt-*) -> OpenAI Responses API
    - Anthropic models (claude-*) -> Anthropic Messages API (transformed)
    - DeepSeek models (deepseek-*) -> DeepSeek Chat API (transformed)
    - Google models (gemini-*) -> Google AI API (transformed)
    """
    
    @classmethod
    def get_provider_type(cls, model: str) -> str:
        """Determine which provider to use for a model.
        
        Priority order:
        1. Explicit provider prefix (anthropic/, deepseek-api/)
        2. Model name pattern matching
        3. Default to OpenAI for unknown models
        """
        model_lower = model.lower()
        
        # Check for explicit prefix
        if model_lower.startswith("anthropic/"):
            return "anthropic"
        if model_lower.startswith("deepseek-api/"):
            return "deepseek"
        if model_lower.startswith("google/"):
            return "google"
        
        # Pattern matching
        if model_lower.startswith("claude") or "claude" in model_lower:
            return "anthropic"
        if model_lower.startswith("deepseek") or "deepseek" in model_lower:
            return "deepseek"
        if model_lower.startswith("gemini"):
            return "google"
        
        return "openai"
```

### 3.2 Provider-Specific API Methods

Each provider requires its own implementation method that handles:
- API endpoint URL
- Request format transformation
- Authentication headers
- Response format transformation back to OpenAI Responses API format

```python
async def create_response(self, request: ResponsesRequest) -> ResponsesResponse:
    """
    Create a response, routing to the appropriate provider.
    
    This is the main entry point that dispatches to provider-specific
    implementations based on the requested model.
    """
    provider_type = self.get_provider_type(request.model)
    
    match provider_type:
        case "anthropic":
            return await self._create_anthropic_response(request)
        case "deepseek":
            return await self._create_deepseek_response(request)
        case "google":
            return await self._create_google_response(request)
        case _:
            return await self._create_openai_response(request)
```

### 3.3 API Format Translation Layer

**Anthropic Messages API Translation:**

```python
async def _create_anthropic_response(self, request: ResponsesRequest) -> ResponsesResponse:
    """
    Create a response using the Anthropic Messages API.
    
    Transforms:
    - ResponsesRequest.input -> messages[] format
    - ResponsesRequest.instructions -> system parameter
    - ResponsesRequest.max_output_tokens -> max_tokens
    
    Returns: ResponsesResponse (unified format)
    """
    # Model alias mapping (handle variations)
    MODEL_ALIASES = {
        "claude-opus-4-5-20250514": "claude-opus-4-20250514",
        "claude-opus-4.5": "claude-opus-4-20250514",
        "claude-4-opus": "claude-opus-4-20250514",
        "claude-sonnet-4.5": "claude-sonnet-4-20250514",
    }
    model = MODEL_ALIASES.get(request.model, request.model)
    
    # Transform input to Anthropic messages format
    messages = self._convert_input_to_messages(request.input)
    
    # Build Anthropic-specific payload
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": request.max_output_tokens or 4096,
    }
    
    # Add system message from instructions
    if request.instructions:
        payload["system"] = request.instructions
    
    # Add optional parameters
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    
    # Call Anthropic API with correct headers
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
    
    # Transform response back to Responses API format
    return self._transform_anthropic_response(response.json(), model)
```

**DeepSeek Chat API Translation:**

```python
async def _create_deepseek_response(self, request: ResponsesRequest) -> ResponsesResponse:
    """
    Create a response using the DeepSeek Chat API.
    
    DeepSeek uses OpenAI-compatible /chat/completions format,
    so transformation is simpler.
    """
    MODEL_ALIASES = {
        "deepseek-api/deepseek-chat": "deepseek-chat",
        "deepseek": "deepseek-chat",
        "deepseek-api/deepseek-reasoner": "deepseek-reasoner",
    }
    model = MODEL_ALIASES.get(request.model, request.model)
    
    messages = []
    if request.instructions:
        messages.append({"role": "system", "content": request.instructions})
    
    # Convert input to messages
    messages.extend(self._convert_input_to_messages(request.input))
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": request.max_output_tokens or 4096,
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.deepseek.com/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
    
    return self._transform_deepseek_response(response.json(), model)
```

### 3.4 Unified Response Transformation

All provider responses must be transformed to a consistent `ResponsesResponse` format:

```python
def _transform_anthropic_response(self, data: dict[str, Any], model: str) -> ResponsesResponse:
    """Transform Anthropic Messages response to Responses API format."""
    # Extract text from content blocks
    text_content = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_content += block.get("text", "")
    
    # Build unified response
    return ResponsesResponse(
        id=data.get("id", f"resp_{uuid.uuid4().hex[:24]}"),
        object="response",
        created_at=int(time.time()),
        model=model,
        output=[
            OutputMessage(
                type="message",
                role="assistant",
                content=[
                    OutputTextContent(
                        type="output_text",
                        text=text_content,
                    )
                ],
            )
        ],
        usage=ResponseUsage(
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
            total_tokens=data.get("usage", {}).get("input_tokens", 0) 
                       + data.get("usage", {}).get("output_tokens", 0),
        ),
    )
```

---

## 4. Implementation Details: Provider Abstraction Layer

### 4.1 Provider Base Interface

The existing `LLMProvider` base class in [src/providers/base.py](../src/providers/base.py) defines the contract:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    All providers must implement these methods to participate
    in the provider routing system.
    """
    
    @abstractmethod
    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Generate a completion for the given request."""
        pass
    
    @abstractmethod
    async def stream_complete(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream a completion for the given request."""
        pass
    
    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """Return list of models this provider supports."""
        pass
```

### 4.2 Provider Router Model Mapping

The `ProviderRouter` class manages model-to-provider mappings:

```python
class ProviderRouter:
    """Routes requests to appropriate LLM provider based on model name."""
    
    # Exact model matches for local inference-service
    LOCAL_MODELS = {
        "phi-4", "qwen2.5-7b", "qwen3-8b", "llama-3.2-3b", "gpt-oss-20b",
        "deepseek-r1-7b", "phi-3-medium-128k",
        "codellama-7b-instruct", "codellama-13b", "qwen2.5-coder-7b",
        "codegemma-7b", "deepseek-coder-v2-lite", "granite-8b-code-128k",
    }
    
    # External owned API mappings
    EXTERNAL_MODELS = {
        # Anthropic
        "claude-opus-4-5-20250514": "anthropic",
        "claude-sonnet-4-5-20250514": "anthropic",
        "claude-opus-4.5": "anthropic",
        "claude-sonnet-4.5": "anthropic",
        # OpenAI
        "gpt-5.2": "openai",
        "gpt-5.2-pro": "openai",
        "gpt-5-mini": "openai",
        # Google
        "gemini-2.0-flash": "google",
        "gemini-1.5-pro": "google",
    }
    
    # Prefix routing fallback
    MODEL_PREFIXES = {
        "claude-": "anthropic",
        "gpt-": "openai",
        "gemini-": "google",
        "deepseek-api/": "deepseek",
        "openrouter/": "openrouter",
    }
    
    # Provider alias defaults
    PROVIDER_DEFAULTS = {
        "openai": "gpt-5.2",
        "anthropic": "claude-opus-4-5-20250514",
        "claude": "claude-opus-4-5-20250514",
        "deepseek": "deepseek-api/deepseek-reasoner",
        "google": "gemini-1.5-pro",
    }
```

### 4.3 Provider Registration Factory

```python
def create_provider_router(settings: "Settings") -> ProviderRouter:
    """Create a provider router from settings.
    
    Registers providers based on available API keys.
    """
    providers: dict[str, LLMProvider] = {}

    # Register inference provider FIRST - default for local models
    _register_inference(settings, providers)
    
    # Cloud providers (each checks for API key availability)
    _register_openai(settings, providers)
    _register_anthropic(settings, providers)
    _register_deepseek(settings, providers)
    _register_gemini(settings, providers)
    _register_openrouter(settings, providers)
    
    logger.info(f"Provider router initialized: {list(providers.keys())}")
    
    return ProviderRouter(
        providers=providers,
        default_provider="inference",
    )
```

### 4.4 Error Handling Per Provider

Each provider has specific error patterns that require custom handling:

```python
class ProviderError(Exception):
    """Base exception for provider errors."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


# Provider-specific error handling
PROVIDER_ERROR_HANDLERS = {
    "anthropic": {
        400: ("Invalid request format", False),
        401: ("Invalid API key", False),
        429: ("Rate limit exceeded", True),
        500: ("Anthropic server error", True),
        529: ("Anthropic overloaded", True),
    },
    "openai": {
        400: ("Invalid model or parameters", False),
        401: ("Invalid API key", False),
        429: ("Rate limit or quota exceeded", True),
        500: ("OpenAI server error", True),
        503: ("OpenAI overloaded", True),
    },
    "deepseek": {
        400: ("Invalid request", False),
        401: ("Invalid API key", False),
        402: ("Insufficient balance", False),
        429: ("Rate limit exceeded", True),
    },
}


async def handle_provider_error(
    provider: str,
    status_code: int,
    response_body: dict,
) -> ProviderError:
    """Create appropriate ProviderError based on provider and status code."""
    handlers = PROVIDER_ERROR_HANDLERS.get(provider, {})
    message, retryable = handlers.get(
        status_code, 
        (f"Unknown error from {provider}", False)
    )
    
    # Extract detailed message from response
    if "error" in response_body:
        detail = response_body["error"].get("message", "")
        message = f"{message}: {detail}"
    
    return ProviderError(
        message=message,
        provider=provider,
        status_code=status_code,
        retryable=retryable,
    )
```

---

## 5. Testing Strategy

### 5.1 Unit Tests: Provider Detection

```python
# tests/unit/test_responses_routing.py
import pytest
from src.api.routes.responses import ResponsesService


class TestProviderDetection:
    """Test get_provider_type() correctly identifies providers."""
    
    @pytest.mark.parametrize("model,expected", [
        # Anthropic models
        ("claude-opus-4.5", "anthropic"),
        ("claude-sonnet-4-5-20250514", "anthropic"),
        ("claude-3-opus-20240229", "anthropic"),
        # OpenAI models
        ("gpt-5.2", "openai"),
        ("gpt-5.2-pro", "openai"),
        ("o3-mini", "openai"),
        # DeepSeek models
        ("deepseek-reasoner", "deepseek"),
        ("deepseek-api/deepseek-chat", "deepseek"),
        # Google models
        ("gemini-1.5-pro", "google"),
        ("gemini-2.0-flash", "google"),
        # Unknown defaults to OpenAI
        ("unknown-model", "openai"),
    ])
    def test_get_provider_type(self, model: str, expected: str):
        assert ResponsesService.get_provider_type(model) == expected


class TestModelAliasResolution:
    """Test model alias resolution works correctly."""
    
    @pytest.mark.parametrize("alias,expected", [
        ("openai", "gpt-5.2"),
        ("chatgpt", "gpt-5.2"),
        ("claude", "claude-opus-4-5-20250514"),
        ("anthropic", "claude-opus-4-5-20250514"),
        ("deepseek", "deepseek-api/deepseek-reasoner"),
    ])
    def test_alias_resolution(self, alias: str, expected: str):
        from src.providers.router import ProviderRouter
        assert ProviderRouter.PROVIDER_DEFAULTS.get(alias) == expected
```

### 5.2 Integration Tests: Provider Routing

```python
# tests/integration/test_multi_provider_routing.py
import pytest
from unittest.mock import AsyncMock, patch
from httpx import Response


class TestMultiProviderRouting:
    """Integration tests for multi-provider request routing."""
    
    @pytest.fixture
    def mock_settings(self):
        """Settings with all API keys configured."""
        return MockSettings(
            openai_api_key="sk-openai-test",
            anthropic_api_key="sk-anthropic-test",
            deepseek_api_key="sk-deepseek-test",
            gemini_api_key="sk-gemini-test",
        )
    
    @pytest.mark.asyncio
    async def test_anthropic_model_routes_to_anthropic_api(self, mock_settings):
        """Claude models should call Anthropic API, not OpenAI."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Response(
                200,
                json={
                    "id": "msg_123",
                    "content": [{"type": "text", "text": "Hello"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )
            
            service = ResponsesService()
            request = ResponsesRequest(
                model="claude-opus-4.5",
                input="Hello",
            )
            
            await service.create_response(request)
            
            # Verify Anthropic API was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "api.anthropic.com" in call_args.args[0]
            assert "x-api-key" in call_args.kwargs["headers"]
    
    @pytest.mark.asyncio
    async def test_openai_model_routes_to_openai_api(self, mock_settings):
        """GPT models should call OpenAI API."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Response(
                200,
                json={
                    "id": "resp_123",
                    "output": [{"type": "message", "content": [{"text": "Hi"}]}],
                },
            )
            
            service = ResponsesService()
            request = ResponsesRequest(
                model="gpt-5.2",
                input="Hello",
            )
            
            await service.create_response(request)
            
            # Verify OpenAI API was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "api.openai.com" in call_args.args[0]
```

### 5.3 E2E Tests: Kitchen Brigade Protocol

```python
# tests/e2e/test_kitchen_brigade_multi_provider.py
import pytest
import httpx


class TestKitchenBrigadeMultiProvider:
    """E2E tests for Kitchen Brigade with multiple providers."""
    
    @pytest.fixture
    def gateway_url(self):
        return "http://localhost:8080"
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_balanced_tier_all_providers(self, gateway_url):
        """
        Test balanced tier uses mixed providers successfully.
        
        balanced:
          analyst: claude-sonnet-4.5    -> Anthropic
          critic: qwen3-8b              -> Local
          synthesizer: gpt-5-mini       -> OpenAI
          validator: codellama-13b      -> Local
        """
        models_to_test = [
            ("claude-sonnet-4.5", "Anthropic"),
            ("qwen3-8b", "Local"),
            ("gpt-5-mini", "OpenAI"),
            ("codellama-13b", "Local"),
        ]
        
        async with httpx.AsyncClient() as client:
            for model, expected_provider in models_to_test:
                response = await client.post(
                    f"{gateway_url}/v1/responses",
                    json={
                        "model": model,
                        "input": "Test prompt",
                    },
                    timeout=60.0,
                )
                
                assert response.status_code == 200, (
                    f"{model} ({expected_provider}) failed: {response.text}"
                )
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_premium_tier_external_only(self, gateway_url):
        """
        Test premium tier routes to correct external providers.
        """
        async with httpx.AsyncClient() as client:
            # Test Anthropic routing
            response = await client.post(
                f"{gateway_url}/v1/responses",
                json={
                    "model": "claude-opus-4.5",
                    "input": "Analyze this code",
                    "instructions": "You are a senior architect.",
                },
                timeout=60.0,
            )
            assert response.status_code == 200
            
            # Test OpenAI routing  
            response = await client.post(
                f"{gateway_url}/v1/responses",
                json={
                    "model": "gpt-5.2-pro",
                    "input": "Review this analysis",
                },
                timeout=60.0,
            )
            assert response.status_code == 200
```

### 5.4 Contract Tests: Response Format Consistency

```python
# tests/contract/test_response_format.py
from pydantic import ValidationError


class TestResponseFormatConsistency:
    """Ensure all providers return consistent ResponsesResponse format."""
    
    @pytest.mark.parametrize("provider_method", [
        "_create_openai_response",
        "_create_anthropic_response",
        "_create_deepseek_response",
    ])
    @pytest.mark.asyncio
    async def test_response_matches_schema(self, provider_method, mock_request):
        """All providers must return valid ResponsesResponse."""
        service = ResponsesService()
        method = getattr(service, provider_method)
        
        # Mock the HTTP call
        with patch_http_for_provider(provider_method):
            response = await method(mock_request)
        
        # Validate response schema
        assert isinstance(response, ResponsesResponse)
        assert response.id is not None
        assert response.output is not None
        assert len(response.output) > 0
        assert response.usage is not None
        assert response.usage.total_tokens >= 0
```

---

## 6. Monitoring Considerations

### 6.1 Provider-Specific Metrics

The Gateway exports Prometheus metrics per provider:

```python
# src/api/routes/health.py - MetricsService

# Provider request counts
llm_gateway_provider_requests_total{provider="openai"} 1523
llm_gateway_provider_requests_total{provider="anthropic"} 847
llm_gateway_provider_requests_total{provider="inference"} 12456
llm_gateway_provider_requests_total{provider="deepseek"} 234

# Provider latency histograms
llm_gateway_provider_latency_seconds_bucket{provider="openai",le="1.0"} 1200
llm_gateway_provider_latency_seconds_bucket{provider="anthropic",le="1.0"} 650

# Provider error counts
llm_gateway_provider_errors_total{provider="openai",error_type="rate_limit"} 12
llm_gateway_provider_errors_total{provider="anthropic",error_type="auth"} 0
```

### 6.2 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Log provider routing decisions
logger.info(
    "request_routed",
    model=request.model,
    provider=provider_type,
    endpoint=endpoint_url,
    has_instructions=bool(request.instructions),
)

# Log provider responses
logger.info(
    "provider_response",
    provider=provider_type,
    model=model,
    status_code=response.status_code,
    latency_ms=latency_ms,
    input_tokens=usage.input_tokens,
    output_tokens=usage.output_tokens,
)

# Log provider errors with context
logger.error(
    "provider_error",
    provider=provider_type,
    model=model,
    status_code=status_code,
    error_message=error_msg,
    retryable=error.retryable,
)
```

### 6.3 Alerting Rules

```yaml
# prometheus/alerts/llm_gateway.yml
groups:
  - name: llm_gateway_provider_health
    rules:
      # Alert if any provider has >5% error rate
      - alert: ProviderHighErrorRate
        expr: |
          sum(rate(llm_gateway_provider_errors_total[5m])) by (provider)
          / sum(rate(llm_gateway_provider_requests_total[5m])) by (provider)
          > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate for {{ $labels.provider }}"
          description: "Provider {{ $labels.provider }} has >5% error rate"
      
      # Alert if provider latency P95 exceeds threshold
      - alert: ProviderHighLatency
        expr: |
          histogram_quantile(0.95, 
            rate(llm_gateway_provider_latency_seconds_bucket[5m])
          ) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High latency for {{ $labels.provider }}"
      
      # Alert if no requests to a provider for 1 hour (potential config issue)
      - alert: ProviderNoTraffic
        expr: |
          sum(increase(llm_gateway_provider_requests_total[1h])) by (provider) == 0
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "No traffic to {{ $labels.provider }}"
```

### 6.4 Distributed Tracing

```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer(__name__)

async def create_response(self, request: ResponsesRequest) -> ResponsesResponse:
    provider_type = self.get_provider_type(request.model)
    
    with tracer.start_as_current_span(
        "llm_gateway.create_response",
        kind=SpanKind.SERVER,
        attributes={
            "llm.model": request.model,
            "llm.provider": provider_type,
            "llm.max_tokens": request.max_output_tokens or 4096,
        },
    ) as span:
        try:
            response = await self._dispatch_to_provider(provider_type, request)
            span.set_attribute("llm.usage.total_tokens", response.usage.total_tokens)
            return response
        except ProviderError as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

---

## 7. Recommendations

### 7.1 Immediate Actions (Completed)

- ✅ Implemented `get_provider_type()` for model-to-provider routing
- ✅ Added `_create_anthropic_response()` with API format translation
- ✅ Added `_create_deepseek_response()` with API format translation
- ✅ Unified response transformation to `ResponsesResponse`
- ✅ Provider-specific error handling

### 7.2 Future Enhancements

| Enhancement | Priority | Rationale |
|-------------|----------|-----------|
| Add Google Gemini support | P1 | Complete premium tier support |
| Implement retry with exponential backoff | P2 | Handle transient failures gracefully |
| Add circuit breaker per provider | P2 | Prevent cascade failures |
| Implement request caching | P3 | Reduce costs for repeated queries |
| Add model capability discovery | P3 | Dynamic model selection based on features |

### 7.3 Configuration Best Practices

```bash
# .env configuration for multi-provider support
# ============================================

# Required: At least one provider must be configured
OPENAI_API_KEY=sk-...          # OpenAI GPT-5.x models
ANTHROPIC_API_KEY=sk-ant-...   # Claude Opus/Sonnet models
DEEPSEEK_API_KEY=sk-...        # DeepSeek Reasoner
GEMINI_API_KEY=...             # Google Gemini models

# Optional: Aggregator (explicit prefix required)
OPENROUTER_API_KEY=sk-or-...   # Use with "openrouter/model-name"

# Local inference (default for unknown models)
INFERENCE_SERVICE_URL=http://localhost:8085
```

---

## 8. Conclusion

The multi-provider routing issue was resolved by:

1. **Adding provider detection** - `get_provider_type()` classifies models by provider
2. **Implementing API translators** - Each provider has a dedicated method handling its unique API contract
3. **Unifying responses** - All providers return consistent `ResponsesResponse` format
4. **Updating the router** - `ProviderRouter` maps models to providers correctly

The Kitchen Brigade protocol can now successfully use mixed provider tiers (local + cloud), enabling the full range of model selection for different task requirements.

**Files Changed:**
- [src/api/routes/responses.py](../src/api/routes/responses.py) - Multi-provider routing
- [src/providers/router.py](../src/providers/router.py) - Model-to-provider mappings
- [src/providers/deepseek.py](../src/providers/deepseek.py) - DeepSeek provider adapter

**Related Documentation:**
- [CL-035: GPT-5.2, Claude Opus 4, OpenRouter Providers](TECHNICAL_CHANGE_LOG.md)
- [CL-036: DeepSeek Provider](TECHNICAL_CHANGE_LOG.md)
- [Kitchen Brigade Model Library](../../ai-agents/docs/guides/MODEL_LIBRARY.md)
