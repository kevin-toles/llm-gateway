# LLM Gateway Integration Guide

> **WBS 3.7.1.2**: How to integrate applications with the LLM Gateway

This guide explains how to integrate your applications with the LLM Gateway microservice, including service discovery, tool registration, session management, and common integration patterns.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Service Discovery](#service-discovery)
- [Tool Registration](#tool-registration)
- [Session Management](#session-management)
- [Integration Patterns](#integration-patterns)
- [Best Practices](#best-practices)

---

## Quick Start

### 1. Verify Gateway is Running

```bash
# Check health
curl http://localhost:8080/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# Check readiness (all dependencies)
curl http://localhost:8080/health/ready
# Expected: {"status": "ready", "checks": {...}}
```

### 2. Make Your First Request

```python
import requests

response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
        "model": "claude-3-sonnet-20240229",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)
print(response.json()["choices"][0]["message"]["content"])
```

### 3. Configure Your Application

```python
# config.py
import os

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://localhost:8080")
LLM_GATEWAY_TIMEOUT = int(os.getenv("LLM_GATEWAY_TIMEOUT", "60"))
```

---

## Service Discovery

> **WBS 3.7.1.2.3**: Document service discovery configuration

### DNS-Based Discovery (Recommended)

The LLM Gateway uses DNS-based service discovery, which works consistently across Docker Compose and Kubernetes environments.

#### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  your-application:
    environment:
      - LLM_GATEWAY_URL=http://llm-gateway:8080
    depends_on:
      llm-gateway:
        condition: service_healthy
    networks:
      - app-network

  llm-gateway:
    image: llm-gateway:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

#### Kubernetes Configuration

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LLM_GATEWAY_URL: "http://llm-gateway.default.svc.cluster.local:8080"
```

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: your-application
spec:
  template:
    spec:
      containers:
        - name: app
          envFrom:
            - configMapRef:
                name: app-config
```

### URL Resolution by Environment

| Environment | URL Pattern | Notes |
|-------------|-------------|-------|
| Local Development | `http://localhost:8080` | Direct connection |
| Docker Compose | `http://llm-gateway:8080` | Docker DNS resolution |
| Kubernetes (same namespace) | `http://llm-gateway:8080` | K8s Service DNS |
| Kubernetes (cross-namespace) | `http://llm-gateway.namespace.svc.cluster.local:8080` | FQDN |

### Client Configuration Pattern

```python
# llm_client.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMGatewayConfig:
    """LLM Gateway connection configuration."""
    
    base_url: str = "http://localhost:8080"
    timeout_seconds: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    api_key: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "LLMGatewayConfig":
        """Load configuration from environment variables."""
        return cls(
            base_url=os.getenv("LLM_GATEWAY_URL", "http://localhost:8080"),
            timeout_seconds=int(os.getenv("LLM_GATEWAY_TIMEOUT", "60")),
            retry_attempts=int(os.getenv("LLM_GATEWAY_RETRIES", "3")),
            api_key=os.getenv("LLM_GATEWAY_API_KEY"),
        )
```

---

## Tool Registration

> **WBS 3.7.1.2.4**: Document tool registration process

### Understanding Tools

Tools enable the LLM to perform actions like searching documents, executing code, or calling external APIs. The gateway provides built-in tools and supports custom tool registration.

### Built-in Tools

| Tool | Description | Service |
|------|-------------|---------|
| `semantic_search` | Semantic document search | semantic-search-service |
| `get_chunk` | Retrieve document chunks | semantic-search-service |
| `analyze_architecture` | Analyze code architecture | ai-agents-service |
| `review_code` | Code review | ai-agents-service |
| `generate_docs` | Generate documentation | ai-agents-service |

### Using Tools in Chat Completions

```python
import requests

# Define tools to use
tools = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search documents using semantic similarity",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Request with tools
response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
        "model": "claude-3-sonnet-20240229",
        "messages": [
            {"role": "user", "content": "Find information about Python decorators"}
        ],
        "tools": tools,
        "tool_choice": "auto"
    }
)

result = response.json()

# Check if model wants to call a tool
if result["choices"][0]["message"].get("tool_calls"):
    tool_calls = result["choices"][0]["message"]["tool_calls"]
    for tool_call in tool_calls:
        print(f"Tool: {tool_call['function']['name']}")
        print(f"Arguments: {tool_call['function']['arguments']}")
```

### Handling Tool Calls (Full Loop)

```python
import json
import requests

def chat_with_tools(user_message: str, tools: list) -> str:
    """Complete chat with automatic tool execution."""
    
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        # Request completion
        response = requests.post(
            "http://localhost:8080/v1/chat/completions",
            json={
                "model": "claude-3-sonnet-20240229",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }
        )
        result = response.json()
        assistant_message = result["choices"][0]["message"]
        messages.append(assistant_message)
        
        # Check for tool calls
        if not assistant_message.get("tool_calls"):
            # No more tool calls, return final response
            return assistant_message.get("content", "")
        
        # Execute each tool call
        for tool_call in assistant_message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            # Execute tool via gateway
            tool_response = requests.post(
                "http://localhost:8080/v1/tools/execute",
                json={"name": tool_name, "arguments": tool_args}
            )
            tool_result = tool_response.json()
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(tool_result["result"])
            })
```

### Registering Custom Tools

Custom tools can be registered via configuration:

```json
// config/tools.json
{
  "tools": [
    {
      "name": "my_custom_tool",
      "description": "Description of what this tool does",
      "parameters": {
        "type": "object",
        "properties": {
          "param1": {"type": "string", "description": "First parameter"},
          "param2": {"type": "integer", "description": "Second parameter"}
        },
        "required": ["param1"]
      },
      "handler": {
        "type": "http",
        "url": "http://my-service:8000/execute",
        "method": "POST"
      }
    }
  ]
}
```

---

## Session Management

> **WBS 3.7.1.2.5**: Document session management best practices

### Why Use Sessions?

Sessions maintain conversation context across multiple requests:
- **Context Continuity**: LLM remembers previous messages
- **Efficient**: Reduces token usage by not resending history
- **State Management**: Store custom context data

### Session Lifecycle

```
┌─────────┐     ┌───────────────┐     ┌─────────────┐     ┌─────────┐
│ Create  │────▶│ Use (chat)    │────▶│ Extend TTL  │────▶│ Delete  │
└─────────┘     └───────────────┘     └─────────────┘     └─────────┘
                       │                     ▲
                       └─────────────────────┘
                         (auto-extends on use)
```

### Creating Sessions

```python
import requests
from datetime import datetime, timedelta

def create_session(ttl_seconds: int = 3600, context: dict = None) -> str:
    """Create a new conversation session."""
    response = requests.post(
        "http://localhost:8080/v1/sessions",
        json={
            "ttl_seconds": ttl_seconds,
            "context": context or {}
        }
    )
    response.raise_for_status()
    return response.json()["id"]

# Create session with 1-hour TTL
session_id = create_session(
    ttl_seconds=3600,
    context={"user_id": "user_123", "project": "documentation"}
)
```

### Using Sessions in Chat

```python
def chat_in_session(session_id: str, message: str) -> str:
    """Send message within a session context."""
    response = requests.post(
        "http://localhost:8080/v1/chat/completions",
        json={
            "model": "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": message}],
            "session_id": session_id
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Conversation with memory
session_id = create_session()
print(chat_in_session(session_id, "My name is Alice"))
print(chat_in_session(session_id, "What is my name?"))  # Remembers "Alice"
```

### Session Best Practices

1. **Set Appropriate TTL**
   ```python
   # Short-lived for quick tasks
   session_id = create_session(ttl_seconds=300)  # 5 minutes
   
   # Long-lived for extended conversations
   session_id = create_session(ttl_seconds=86400)  # 24 hours
   ```

2. **Store Context Data**
   ```python
   session_id = create_session(
       context={
           "user_id": "user_123",
           "preferences": {"language": "en", "format": "detailed"},
           "permissions": ["read", "write"]
       }
   )
   ```

3. **Clean Up Sessions**
   ```python
   def cleanup_session(session_id: str):
       """Delete session when done."""
       requests.delete(f"http://localhost:8080/v1/sessions/{session_id}")
   
   # Use context manager pattern
   from contextlib import contextmanager
   
   @contextmanager
   def session_scope(ttl_seconds: int = 3600):
       session_id = create_session(ttl_seconds)
       try:
           yield session_id
       finally:
           cleanup_session(session_id)
   
   with session_scope() as session_id:
       print(chat_in_session(session_id, "Hello!"))
   ```

4. **Handle Session Expiry**
   ```python
   def safe_chat(session_id: str, message: str) -> str:
       """Chat with automatic session recreation on expiry."""
       try:
           return chat_in_session(session_id, message)
       except requests.HTTPError as e:
           if e.response.status_code == 404:
               # Session expired, create new one
               new_session_id = create_session()
               return chat_in_session(new_session_id, message)
           raise
   ```

---

## Integration Patterns

> **WBS 3.7.1.2.6**: Add code examples for common patterns

### Pattern 1: Simple Request-Response

For stateless interactions without session management:

```python
class SimpleLLMClient:
    """Simple LLM client for stateless interactions."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
    
    def complete(
        self, 
        prompt: str, 
        model: str = "claude-3-sonnet-20240229",
        **kwargs
    ) -> str:
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

# Usage
client = SimpleLLMClient()
result = client.complete("Summarize the key points of Python decorators")
```

### Pattern 2: Conversational Agent

For multi-turn conversations with context:

```python
class ConversationalAgent:
    """Agent with conversation memory via sessions."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session_id = None
        self.model = "claude-3-sonnet-20240229"
    
    def start_conversation(self, system_prompt: str = None) -> None:
        """Start a new conversation."""
        response = requests.post(
            f"{self.base_url}/v1/sessions",
            json={"ttl_seconds": 3600}
        )
        self.session_id = response.json()["id"]
        
        if system_prompt:
            # Prime the conversation with system context
            self.send(f"[System Context]: {system_prompt}")
    
    def send(self, message: str) -> str:
        """Send message and get response."""
        if not self.session_id:
            self.start_conversation()
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": message}],
                "session_id": self.session_id
            }
        )
        return response.json()["choices"][0]["message"]["content"]
    
    def end_conversation(self) -> None:
        """Clean up conversation session."""
        if self.session_id:
            requests.delete(f"{self.base_url}/v1/sessions/{self.session_id}")
            self.session_id = None

# Usage
agent = ConversationalAgent()
agent.start_conversation("You are a helpful coding assistant.")
print(agent.send("How do I write a Python decorator?"))
print(agent.send("Can you give me an example?"))  # Remembers context
agent.end_conversation()
```

### Pattern 3: RAG (Retrieval-Augmented Generation)

Combine semantic search with LLM generation:

```python
class RAGClient:
    """Retrieval-Augmented Generation client."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
    
    def search(self, query: str, top_k: int = 5) -> list:
        """Search for relevant documents."""
        response = requests.post(
            f"{self.base_url}/v1/tools/execute",
            json={
                "name": "semantic_search",
                "arguments": {"query": query, "top_k": top_k}
            }
        )
        result = response.json()
        if result["success"]:
            return result["result"].get("chunks", [])
        return []
    
    def generate_with_context(self, query: str, context_chunks: list) -> str:
        """Generate response using retrieved context."""
        context = "\n\n".join([
            f"[Source: {c.get('metadata', {}).get('source', 'unknown')}]\n{c['content']}"
            for c in context_chunks
        ])
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": "claude-3-sonnet-20240229",
                "messages": [
                    {
                        "role": "system",
                        "content": f"Answer based on the following context:\n\n{context}"
                    },
                    {"role": "user", "content": query}
                ]
            }
        )
        return response.json()["choices"][0]["message"]["content"]
    
    def ask(self, question: str, top_k: int = 5) -> str:
        """Full RAG pipeline: search then generate."""
        chunks = self.search(question, top_k)
        if not chunks:
            return "No relevant information found."
        return self.generate_with_context(question, chunks)

# Usage
rag = RAGClient()
answer = rag.ask("How do I implement a circuit breaker pattern?")
```

### Pattern 4: Async Batch Processing

For high-throughput scenarios:

```python
import asyncio
import httpx

class AsyncLLMClient:
    """Async client for batch processing."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
    
    async def complete_async(
        self, 
        prompt: str, 
        client: httpx.AsyncClient
    ) -> str:
        response = await client.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": "claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60.0
        )
        return response.json()["choices"][0]["message"]["content"]
    
    async def batch_complete(
        self, 
        prompts: list[str], 
        concurrency: int = 5
    ) -> list[str]:
        """Process multiple prompts concurrently."""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_complete(prompt: str, client: httpx.AsyncClient):
            async with semaphore:
                return await self.complete_async(prompt, client)
        
        async with httpx.AsyncClient() as client:
            tasks = [limited_complete(p, client) for p in prompts]
            return await asyncio.gather(*tasks)

# Usage
async def main():
    client = AsyncLLMClient()
    prompts = [
        "Summarize Python decorators",
        "Explain async/await in Python",
        "What is a context manager?"
    ]
    results = await client.batch_complete(prompts, concurrency=3)
    for prompt, result in zip(prompts, results):
        print(f"Q: {prompt}\nA: {result[:100]}...\n")

asyncio.run(main())
```

---

## Best Practices

### Connection Management

```python
# Use connection pooling for production
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retry() -> requests.Session:
    """Create requests session with retry logic."""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session
```

### Error Handling

```python
from enum import Enum
from typing import Optional

class LLMError(Exception):
    """Base exception for LLM operations."""
    pass

class RateLimitError(LLMError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")

class ProviderError(LLMError):
    """LLM provider error."""
    pass

def handle_response(response: requests.Response) -> dict:
    """Handle API response with proper error mapping."""
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise RateLimitError(retry_after)
    elif response.status_code == 502:
        raise ProviderError(response.json().get("detail", "Provider unavailable"))
    else:
        response.raise_for_status()
```

### Health Checking

```python
def wait_for_gateway(
    base_url: str = "http://localhost:8080",
    timeout: int = 60,
    interval: int = 2
) -> bool:
    """Wait for gateway to become ready."""
    import time
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/health/ready", timeout=5)
            if response.status_code == 200:
                status = response.json()
                if status.get("status") == "ready":
                    return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    
    return False

# Use at application startup
if not wait_for_gateway():
    raise RuntimeError("LLM Gateway not available")
```

---

## See Also

- [API.md](./API.md) - Complete API reference
- [RUNBOOK.md](./RUNBOOK.md) - Operational procedures
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues and solutions
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
