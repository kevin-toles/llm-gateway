# LLM Gateway API Reference

> **WBS 3.7.1.1**: Comprehensive API documentation with examples

**Version**: 1.0.0  
**Base URL**: `http://localhost:8080` (development) | `https://llm-gateway.example.com` (production)  
**OpenAPI Spec**: `/openapi.json` | `/docs` (Swagger UI) | `/redoc` (ReDoc)

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [Health](#health-endpoints)
  - [Chat Completions](#chat-completions)
  - [Sessions](#sessions)
  - [Tools](#tools)
- [Python Client Examples](#python-client-examples)
- [OpenAI SDK Compatibility](#openai-sdk-compatibility)

---

## Overview

The LLM Gateway provides a unified API for LLM interactions following the OpenAI-compatible format. It abstracts provider differences (Anthropic, OpenAI, Ollama), orchestrates tool-use, and manages conversation sessions.

### Key Features

- **OpenAI-Compatible**: Use existing OpenAI SDKs with minimal changes
- **Multi-Provider**: Route requests to Anthropic Claude, OpenAI GPT, or Ollama
- **Tool Execution**: Built-in semantic search and custom tool support
- **Session Management**: Persistent conversation history via Redis
- **Operational Controls**: Rate limiting, caching, cost tracking

---

## Authentication

> **WBS 3.7.1.1.4**: Document authentication (if applicable)

### API Key Authentication

The gateway supports optional API key authentication via the `Authorization` header:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Environment Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_GATEWAY_API_KEY_ENABLED` | Enable API key validation | `false` |
| `LLM_GATEWAY_API_KEYS` | Comma-separated valid keys | `""` |

When disabled (default for development), all requests are accepted without authentication.

---

## Rate Limiting

> **WBS 3.7.1.1.5**: Document rate limiting behavior

### Default Limits

| Limit Type | Value | Scope |
|------------|-------|-------|
| Requests per minute | 60 | Per client IP |
| Burst allowance | 10 | Immediate requests |
| Token limit per request | 128,000 | Per model capability |

### Rate Limit Headers

When rate limiting is enabled, responses include:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1699574400
```

### Handling Rate Limits

When rate limited, the API returns:

```json
{
  "detail": "Rate limit exceeded. Retry after 60 seconds.",
  "retry_after": 60
}
```

**HTTP Status**: `429 Too Many Requests`

### Configuration

```python
# Environment variables
LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE=60
LLM_GATEWAY_RATE_LIMIT_ENABLED=true
```

---

## Error Handling

> **WBS 3.7.1.1.3**: Document error codes and messages

### Error Response Format

All errors follow a consistent JSON structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "ERROR_TYPE",
  "request_id": "req_abc123"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Invalid JSON, missing required fields |
| `401` | Unauthorized | Missing or invalid API key |
| `403` | Forbidden | API key lacks required permissions |
| `404` | Not Found | Invalid endpoint or resource |
| `422` | Validation Error | Invalid parameter types or values |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Error | Server-side error |
| `502` | Bad Gateway | LLM provider unavailable |
| `503` | Service Unavailable | Dependencies not ready |
| `504` | Gateway Timeout | LLM provider timeout |

### Validation Errors (422)

```json
{
  "detail": [
    {
      "loc": ["body", "messages", 0, "content"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Provider Errors (502)

```json
{
  "detail": "LLM provider error: Rate limit exceeded",
  "provider": "anthropic",
  "error_code": "PROVIDER_RATE_LIMIT"
}
```

---

## Endpoints

### Health Endpoints

#### GET /health

Basic health check for liveness probes.

**curl Example:**
```bash
curl http://localhost:8080/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

#### GET /health/ready

Readiness check verifying all dependencies are available.

**curl Example:**
```bash
curl http://localhost:8080/health/ready
```

**Response (200 OK - All Ready):**
```json
{
  "status": "ready",
  "checks": {
    "redis": true,
    "semantic_search": true,
    "ai_agents": true
  }
}
```

**Response (503 Service Unavailable - Dependencies Down):**
```json
{
  "status": "not_ready",
  "checks": {
    "redis": true,
    "semantic_search": false,
    "ai_agents": false
  }
}
```

---

#### GET /metrics

Prometheus-compatible metrics endpoint.

**curl Example:**
```bash
curl http://localhost:8080/metrics
```

**Response:**
```
# HELP llm_gateway_requests_total Total requests
# TYPE llm_gateway_requests_total counter
llm_gateway_requests_total{method="POST",endpoint="/v1/chat/completions"} 1234
...
```

---

### Chat Completions

#### POST /v1/chat/completions

Create a chat completion using the specified model. OpenAI-compatible format.

**curl Example:**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet-20240229",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "temperature": 0.7,
    "max_tokens": 1024
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | Model identifier (e.g., `claude-3-sonnet-20240229`, `gpt-4`) |
| `messages` | array | Yes | Array of message objects |
| `temperature` | number | No | Sampling temperature (0-2). Default: 1.0 |
| `max_tokens` | integer | No | Maximum tokens to generate. Default: model-specific |
| `top_p` | number | No | Nucleus sampling parameter (0-1) |
| `n` | integer | No | Number of completions. Default: 1 |
| `stream` | boolean | No | Enable streaming. Default: false |
| `stop` | string/array | No | Stop sequences |
| `presence_penalty` | number | No | Presence penalty (-2 to 2) |
| `frequency_penalty` | number | No | Frequency penalty (-2 to 2) |
| `tools` | array | No | Tool definitions for function calling |
| `tool_choice` | string/object | No | Tool selection mode |
| `user` | string | No | User identifier for tracking |
| `seed` | integer | No | Random seed for reproducibility |
| `session_id` | string | No | Session ID for conversation history |

**Message Object:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | string | Yes | One of: `system`, `user`, `assistant`, `tool` |
| `content` | string | Conditional | Message content (required for user/system) |
| `name` | string | No | Name for multi-participant conversations |
| `tool_calls` | array | No | Tool calls made by assistant |
| `tool_call_id` | string | Conditional | ID of tool call being responded to |

**Response (200 OK):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1699574400,
  "model": "claude-3-sonnet-20240229",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 10,
    "total_tokens": 35
  }
}
```

---

**Example with Tools:**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet-20240229",
    "messages": [
      {"role": "user", "content": "Search for information about Python decorators"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "semantic_search",
          "description": "Search documents semantically",
          "parameters": {
            "type": "object",
            "properties": {
              "query": {"type": "string", "description": "Search query"},
              "top_k": {"type": "integer", "description": "Number of results"}
            },
            "required": ["query"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }'
```

**Response with Tool Call:**
```json
{
  "id": "chatcmpl-xyz789",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "semantic_search",
              "arguments": "{\"query\": \"Python decorators\", \"top_k\": 5}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

---

**Example with Session:**
```bash
# Create a session first
SESSION_ID=$(curl -s -X POST http://localhost:8080/v1/sessions | jq -r '.id')

# Use session for conversation continuity
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"claude-3-sonnet-20240229\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Remember my name is Alice\"}],
    \"session_id\": \"$SESSION_ID\"
  }"

# Continue conversation - session maintains context
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"claude-3-sonnet-20240229\",
    \"messages\": [{\"role\": \"user\", \"content\": \"What is my name?\"}],
    \"session_id\": \"$SESSION_ID\"
  }"
```

---

### Sessions

#### POST /v1/sessions

Create a new conversation session.

**curl Example:**
```bash
curl -X POST http://localhost:8080/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "ttl_seconds": 3600,
    "context": {"user_id": "user_123"}
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ttl_seconds` | integer | No | Session TTL in seconds. Default: 3600 |
| `context` | object | No | Custom context data |

**Response (200 OK):**
```json
{
  "id": "sess_abc123def456",
  "messages": [],
  "context": {"user_id": "user_123"},
  "created_at": "2024-11-09T12:00:00Z",
  "expires_at": "2024-11-09T13:00:00Z"
}
```

---

#### GET /v1/sessions/{session_id}

Retrieve session state and conversation history.

**curl Example:**
```bash
curl http://localhost:8080/v1/sessions/sess_abc123def456
```

**Response (200 OK):**
```json
{
  "id": "sess_abc123def456",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help you?"}
  ],
  "context": {"user_id": "user_123"},
  "created_at": "2024-11-09T12:00:00Z",
  "expires_at": "2024-11-09T13:00:00Z"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Session not found",
  "session_id": "sess_invalid"
}
```

---

#### DELETE /v1/sessions/{session_id}

Delete a session and its conversation history.

**curl Example:**
```bash
curl -X DELETE http://localhost:8080/v1/sessions/sess_abc123def456
```

**Response (200 OK):**
```json
{
  "status": "deleted",
  "session_id": "sess_abc123def456"
}
```

---

### Tools

#### GET /v1/tools

List all available tools.

**curl Example:**
```bash
curl http://localhost:8080/v1/tools
```

**Response (200 OK):**
```json
{
  "tools": [
    {
      "name": "semantic_search",
      "description": "Search documents using semantic similarity",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "Search query"},
          "top_k": {"type": "integer", "description": "Number of results", "default": 5}
        },
        "required": ["query"]
      }
    },
    {
      "name": "get_chunk",
      "description": "Retrieve a specific document chunk by ID",
      "parameters": {
        "type": "object",
        "properties": {
          "chunk_id": {"type": "string", "description": "Chunk identifier"}
        },
        "required": ["chunk_id"]
      }
    }
  ]
}
```

---

#### POST /v1/tools/execute

Execute a tool directly (without LLM orchestration).

**curl Example:**
```bash
curl -X POST http://localhost:8080/v1/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "name": "semantic_search",
    "arguments": {
      "query": "Python async programming",
      "top_k": 3
    }
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Tool name |
| `arguments` | object | No | Tool arguments as key-value pairs |

**Response (200 OK):**
```json
{
  "name": "semantic_search",
  "result": {
    "chunks": [
      {
        "id": "chunk_001",
        "content": "Async programming in Python uses...",
        "score": 0.92,
        "metadata": {"source": "python_guide.pdf", "page": 42}
      }
    ]
  },
  "success": true,
  "error": null
}
```

**Response (Tool Execution Error):**
```json
{
  "name": "semantic_search",
  "result": null,
  "success": false,
  "error": "Semantic search service unavailable"
}
```

---

### Info Endpoints

#### GET /

Root endpoint with API information.

**curl Example:**
```bash
curl http://localhost:8080/
```

**Response (200 OK):**
```json
{
  "name": "LLM Gateway",
  "version": "1.0.0",
  "docs": "/docs",
  "openapi": "/openapi.json"
}
```

---

## Python Client Examples

> **WBS 3.7.1.1.7**: Add Python client examples

### Using requests

```python
import requests

BASE_URL = "http://localhost:8080"

# Simple chat completion
def chat_completion(message: str, model: str = "claude-3-sonnet-20240229") -> str:
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": message}]
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# With session management
class ChatSession:
    def __init__(self, ttl_seconds: int = 3600):
        response = requests.post(
            f"{BASE_URL}/v1/sessions",
            json={"ttl_seconds": ttl_seconds}
        )
        response.raise_for_status()
        self.session_id = response.json()["id"]
    
    def send(self, message: str, model: str = "claude-3-sonnet-20240229") -> str:
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": message}],
                "session_id": self.session_id
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def get_history(self) -> list:
        response = requests.get(f"{BASE_URL}/v1/sessions/{self.session_id}")
        response.raise_for_status()
        return response.json()["messages"]
    
    def close(self):
        requests.delete(f"{BASE_URL}/v1/sessions/{self.session_id}")

# Usage
session = ChatSession()
print(session.send("Hello, my name is Alice"))
print(session.send("What's my name?"))  # Session remembers context
session.close()
```

### Using httpx (async)

```python
import httpx
import asyncio

BASE_URL = "http://localhost:8080"

async def async_chat(message: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": "claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": message}]
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

# Run async
result = asyncio.run(async_chat("What is 2 + 2?"))
print(result)
```

### With Tool Execution

```python
import requests

BASE_URL = "http://localhost:8080"

def search_and_answer(query: str) -> str:
    """Use semantic search tool to find information, then answer."""
    
    # Execute search tool directly
    search_response = requests.post(
        f"{BASE_URL}/v1/tools/execute",
        json={
            "name": "semantic_search",
            "arguments": {"query": query, "top_k": 3}
        }
    )
    search_results = search_response.json()
    
    if not search_results["success"]:
        return f"Search failed: {search_results['error']}"
    
    # Build context from search results
    context = "\n".join([
        chunk["content"] 
        for chunk in search_results["result"]["chunks"]
    ])
    
    # Ask LLM to answer based on context
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "claude-3-sonnet-20240229",
            "messages": [
                {"role": "system", "content": f"Answer based on this context:\n{context}"},
                {"role": "user", "content": query}
            ]
        }
    )
    
    return response.json()["choices"][0]["message"]["content"]
```

---

## OpenAI SDK Compatibility

> **WBS 3.7.1.1.7**: OpenAI SDK compatibility examples

The LLM Gateway is designed to be compatible with the OpenAI Python SDK. Point the SDK to your gateway URL:

```python
from openai import OpenAI

# Point to LLM Gateway instead of OpenAI
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed-for-development"  # Or your actual key if auth enabled
)

# Use exactly like OpenAI SDK
response = client.chat.completions.create(
    model="claude-3-sonnet-20240229",  # Gateway routes to Anthropic
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

### With Tool Use

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="dev")

tools = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search documents semantically",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="claude-3-sonnet-20240229",
    messages=[{"role": "user", "content": "Find info about Python decorators"}],
    tools=tools,
    tool_choice="auto"
)

# Handle tool calls
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        print(f"Tool: {tool_call.function.name}")
        print(f"Args: {tool_call.function.arguments}")
```

---

## Supported Models

| Provider | Model ID | Description |
|----------|----------|-------------|
| Anthropic | `claude-3-opus-20240229` | Most capable Claude model |
| Anthropic | `claude-3-sonnet-20240229` | Balanced performance/cost |
| Anthropic | `claude-3-haiku-20240307` | Fastest Claude model |
| OpenAI | `gpt-4` | GPT-4 base model |
| OpenAI | `gpt-4-turbo` | GPT-4 Turbo with vision |
| OpenAI | `gpt-3.5-turbo` | Fast and economical |
| Ollama | `llama2` | Local Llama 2 |
| Ollama | `codellama` | Local Code Llama |
| Ollama | `mistral` | Local Mistral |

---

## Interactive Documentation

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

---

## See Also

- [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) - How to integrate with LLM Gateway
- [RUNBOOK.md](./RUNBOOK.md) - Operational procedures
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues and solutions
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
