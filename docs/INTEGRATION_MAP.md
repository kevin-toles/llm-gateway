# Integration Map - LLM Document Enhancement System

## Overview

This document maps the integration points between all four repositories in the LLM Document Enhancement system.

---

## System Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                    APPLICATIONS                                         │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                      llm-document-enhancer (Application)                         │   │
│  │                                                                                  │   │
│  │  Batch job that processes technical documents into cross-referenced guidelines   │   │
│  │                                                                                  │   │
│  └──────────────────────────────┬───────────────────────────────────────────────────┘   │
│                                 │                                                       │
│  ┌──────────────────────────────┼───────────────────────────────────────────────────┐   │
│  │        Future Apps           │           (e.g., chatbot, doc search, etc.)       │   │
│  └──────────────────────────────┼───────────────────────────────────────────────────┘   │
│                                 │                                                       │
└─────────────────────────────────┼───────────────────────────────────────────────────────┘
                                  │ HTTP/REST
                                  ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                    MICROSERVICES                                        │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌───────────────────────────────────────────────────────────────────────────────┐    │
│   │                          llm-gateway (Port 8080)                              │    │
│   │                                                                               │    │
│   │   Central gateway for all LLM operations. Routes to providers, manages       │    │
│   │   sessions, executes tools. Primary integration point for applications.      │    │
│   │                                                                               │    │
│   │   Endpoints:                                                                  │    │
│   │     POST /v1/chat/completions    - LLM completion with tool-use              │    │
│   │     GET  /v1/sessions/{id}       - Session state                             │    │
│   │     POST /v1/tools/execute       - Execute registered tool                   │    │
│   │                                                                               │    │
│   └─────────────────────┬────────────────────────────────────┬────────────────────┘    │
│                         │                                    │                          │
│           ┌─────────────┴──────────────┐      ┌──────────────┴─────────────┐           │
│           ▼                            ▼      ▼                            ▼           │
│   ┌───────────────────────┐    ┌─────────────────────────┐    ┌───────────────────────┐│
│   │ semantic-search       │    │ External LLM Providers  │    │ ai-agents             ││
│   │ (Port 8081)           │    │                         │    │ (Port 8082)           ││
│   │                       │    │ • Anthropic             │    │                       ││
│   │ • SBERT embeddings    │    │ • OpenAI                │    │ • Cross-Reference     ││
│   │ • Qdrant vector search│    │ • Ollama (local)        │    │ • Code Review Agent   ││
│   │ • Hybrid graph search │    │                         │    │ • Architecture Agent  ││
│   │                       │    │                         │    │ • Doc Generate Agent  ││
│   └──────────┬────────────┘    └─────────────────────────┘    └───────────┬───────────┘│
│              │                                                            │            │
│              └──────────────────────┬─────────────────────────────────────┘            │
│                                     ▼                                                  │
│                          ┌───────────────────────┐                                     │
│                          │       Neo4j           │                                     │
│                          │    (Port 7687)        │                                     │
│                          │                       │                                     │
│                          │ • Taxonomy graph      │                                     │
│                          │ • Tier relationships  │                                     │
│                          │ • Spider web traversal│                                     │
│                          └───────────────────────┘                                     │
│                                                                                         │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## LLM Interaction Architecture (Critical)

> ⚠️ **KEY DESIGN PRINCIPLE**: Only `llm-gateway` communicates directly with LLM providers (Anthropic, OpenAI, Ollama). All other services that need LLM capabilities MUST route through the gateway.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           LLM INTERACTION ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                        llm-document-enhancer                                 │   │
│   │                                                                              │   │
│   │   ❌ Does NOT call Anthropic/OpenAI directly                                │   │
│   │   ✅ Calls llm-gateway for all LLM operations                               │   │
│   │                                                                              │   │
│   └────────────────────────────────────┬────────────────────────────────────────┘   │
│                                        │                                            │
│                                        ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                           llm-gateway                                        │   │
│   │                           (Port 8080)                                        │   │
│   │                                                                              │   │
│   │   ✅ THE ONLY SERVICE WITH LLM PROVIDER CREDENTIALS                         │   │
│   │   ✅ Centralizes: rate limiting, caching, cost tracking, session mgmt       │   │
│   │                                                                              │   │
│   │                    │                     │                                   │   │
│   │          ┌─────────┴─────────┐   ┌──────┴──────┐                            │   │
│   │          ▼                   ▼   ▼            ▼                             │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────┐                       │   │
│   │   │   Anthropic   │  │    OpenAI     │  │  Ollama   │                       │   │
│   │   │ Claude Models │  │  GPT Models   │  │  (Local)  │                       │   │
│   │   └───────────────┘  └───────────────┘  └───────────┘                       │   │
│   │                                                                              │   │
│   └────────────────────────────────────┬────────────────────────────────────────┘   │
│                                        │                                            │
│                            Tool Calls  │  (HTTP to downstream)                      │
│                                        ▼                                            │
│   ┌──────────────────────────────────────────────────────────────────────────────┐  │
│   │                          TOOL SERVICES                                        │  │
│   │                                                                               │  │
│   │   ┌─────────────────────────────┐    ┌─────────────────────────────────┐     │  │
│   │   │   semantic-search-service   │    │         ai-agents               │     │  │
│   │   │        (Port 8081)          │    │        (Port 8082)              │     │  │
│   │   │                             │    │                                 │     │  │
│   │   │  • SBERT embeddings (local) │    │  • Cross-Reference Agent  │     │  │
│   │   │  • Qdrant vector search     │    │  • Code Review Agent      │     │  │
│   │   │  • Graph traversal (Neo4j)  │    │  • Architecture Agent     │     │  │
│   │   │                             │    │  • Doc Generate Agent     │     │  │
│   │   │  ❌ NO direct LLM calls     │    │                                 │     │  │
│   │   │     (SBERT ≠ LLM API)       │    │  ❌ NO direct LLM calls        │     │  │
│   │   │                             │    │  ✅ Calls BACK to llm-gateway  │     │  │
│   │   │                             │    │     if LLM reasoning needed    │     │  │
│   │   └─────────────────────────────┘    └─────────────────────────────────┘     │  │
│   │                                                                               │  │
│   └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

| Benefit | Description |
|---------|-------------|
| **Single credential store** | Only gateway needs API keys; reduces secret sprawl |
| **Centralized rate limiting** | Prevent overloading provider APIs across all services |
| **Unified cost tracking** | All token usage tracked in one place |
| **Consistent caching** | Response cache benefits all consumers |
| **Provider abstraction** | Switch providers without changing downstream services |
| **Session management** | Multi-turn conversations centralized |
| **Audit trail** | All LLM calls logged through single point |

---

## Repository Summary

| Repository | Type | Port | Purpose | Talks to LLMs? |
|------------|------|------|---------|----------------|
| `llm-gateway` | Microservice | 8080 | LLM provider abstraction, tool-use, sessions | ✅ **YES** (only one) |
| `semantic-search-service` | Microservice | 8081 | Embeddings, vector search, graph traversal | ❌ No (SBERT is local) |
| `ai-agents` | Microservice | 8082 | Specialized AI agents (cross-reference, code review, architecture) | ❌ No (calls gateway) |
| `llm-document-enhancer` | Application | N/A | Batch job consuming the above services | ❌ No (calls gateway) |
| `Neo4j` | Database | 7687 | Taxonomy graph, tier relationships, spider web traversal | ❌ No |

---

## Future Consumers (Unified Platform)

The microservice architecture is designed to support multiple consumers beyond the initial batch processing use case:

| Consumer | Type | Use Case |
|----------|------|----------|
| llm-document-enhancer | Batch | Process technical documents into cross-referenced guidelines |
| VS Code Copilot | Interactive | Real-time code assistance with taxonomy awareness |
| CI/CD Pipelines | Automated | Code review and architecture validation |
| IDE Extensions | Real-time | Context-aware suggestions and documentation |

---

## Integration Points

### 1. llm-document-enhancer → llm-gateway

**Purpose**: All LLM inference for the 3-step enhancement process

**Protocol**: HTTP/REST

**Endpoints Used**:
```
POST /v1/chat/completions
  Body: {
    model: "claude-3-sonnet-20240229",
    messages: [...],
    tools: [...],
    tool_choice: "auto"
  }
  Response: {
    choices: [...],
    usage: {...}
  }

GET /v1/sessions/{session_id}
  Response: {
    id: "...",
    messages: [...],
    context: {...}
  }
```

**Data Flow**:
1. Application prepares prompt with pre-computed matches
2. Application sends to gateway with tool definitions
3. Gateway routes to LLM provider
4. Gateway orchestrates tool calls if needed
5. Gateway returns final response to application

---

### 2. llm-document-enhancer → semantic-search-service

**Purpose**: Embedding generation, similarity search, topic assignment

**Protocol**: HTTP/REST

**Endpoints Used**:
```
POST /v1/embed
  Body: { texts: ["chunk 1", "chunk 2", ...] }
  Response: { embeddings: [[...], [...], ...] }

POST /v1/search
  Body: {
    query: "search text",
    collection: "corpus",
    top_k: 10,
    threshold: 0.7
  }
  Response: {
    results: [
      { id: "...", text: "...", score: 0.95, metadata: {...} },
      ...
    ]
  }

POST /v1/topics
  Body: { text: "...", num_topics: 5 }
  Response: { topics: ["topic1", "topic2", ...], scores: [...] }
```

**Data Flow**:
1. Ingestion: Application sends chunks to embed
2. Pre-compute: Application queries for similar chunks
3. Pre-compute: Application assigns topics to chunks
4. All results cached locally for enhancement step

---

### 3. llm-gateway → semantic-search-service

**Purpose**: LLM tools can retrieve context during inference

**Protocol**: HTTP/REST (internal service-to-service)

**Integration**:
When LLM calls a tool like `search_corpus`, the gateway executes it by calling semantic-search:

```python
# llm-gateway/src/tools/builtins.py
async def search_corpus(query: str, top_k: int = 5) -> list[dict]:
    """Tool exposed to LLM for searching the corpus."""
    response = await self.search_client.post(
        "/v1/search",
        json={"query": query, "collection": "corpus", "top_k": top_k}
    )
    return response.json()["results"]
```

---

### 4. llm-gateway → ai-agents

**Purpose**: LLM can delegate specialized tasks to AI agents

**Protocol**: HTTP/REST (internal service-to-service)

**Integration**:
The gateway can register tools that invoke ai-agents:

```python
# llm-gateway/src/tools/agent_tools.py
async def review_code(code: str, language: str) -> dict:
    """Tool exposed to LLM for code review."""
    response = await self.agents_client.post(
        "/v1/agents/code-review/run",
        json={"code": code, "language": language}
    )
    return response.json()
```

---

### 5. llm-document-enhancer → ai-agents (Optional)

**Purpose**: Direct agent invocation for code examples in documents

**Protocol**: HTTP/REST

**Endpoints Used**:
```
POST /v1/agents/code-review/run
  Body: { code: "...", language: "python" }
  Response: { findings: [...], suggestions: [...] }

POST /v1/agents/doc-generate/run
  Body: { code: "...", format: "markdown" }
  Response: { documentation: "..." }
```

---

## Communication Matrix

| From | To | Protocol | Purpose |
|------|----|----------|---------|
| llm-document-enhancer | llm-gateway | HTTP | LLM inference (3-step enhancement) |
| llm-document-enhancer | semantic-search | HTTP | Embed, search, hybrid search |
| llm-document-enhancer | ai-agents | HTTP | Cross-reference, code review |
| llm-gateway | semantic-search | HTTP | Tool execution (search_corpus) |
| llm-gateway | ai-agents | HTTP | Tool execution (cross_reference, review_code) |
| llm-gateway | Anthropic/OpenAI/Ollama | HTTP | LLM provider calls |
| semantic-search | Neo4j | Bolt | Graph queries, traversal |
| ai-agents | Neo4j | Bolt | Taxonomy traversal |
| ai-agents | llm-gateway | HTTP | LLM reasoning for agents |

---

## Data Models (Shared)

### Chunk
```python
@dataclass
class Chunk:
    id: str
    text: str
    source: str           # Document source path
    chapter: str | None
    section: str | None
    tier: str             # "tier1", "tier2", "tier3"
    metadata: dict
```

### Match
```python
@dataclass
class Match:
    chunk_id: str
    source_chunk_id: str
    score: float
    match_type: str       # "similar", "cross_reference", "conflict"
```

### ToolCall
```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
```

### ToolResult
```python
@dataclass
class ToolResult:
    tool_call_id: str
    content: str | dict
```

---

## Environment Variables

### llm-document-enhancer
```bash
DOC_ENHANCER_LLM_GATEWAY_URL=http://localhost:8080
DOC_ENHANCER_SEMANTIC_SEARCH_URL=http://localhost:8081
DOC_ENHANCER_AI_AGENTS_URL=http://localhost:8082
```

### llm-gateway
```bash
LLM_GATEWAY_PORT=8080
LLM_GATEWAY_SEMANTIC_SEARCH_URL=http://semantic-search:8081
LLM_GATEWAY_AI_AGENTS_URL=http://ai-agents:8082
LLM_GATEWAY_ANTHROPIC_API_KEY=...
LLM_GATEWAY_OPENAI_API_KEY=...
LLM_GATEWAY_OLLAMA_URL=http://localhost:11434
```

### semantic-search-service
```bash
SEMANTIC_SEARCH_PORT=8081
SEMANTIC_SEARCH_MODEL=all-MiniLM-L6-v2
SEMANTIC_SEARCH_QDRANT_URL=http://localhost:6333
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
```

### ai-agents
```bash
AI_AGENTS_PORT=8082
# Agents call BACK to llm-gateway when they need LLM reasoning
AI_AGENTS_LLM_GATEWAY_URL=http://llm-gateway:8080
AI_AGENTS_SEMANTIC_SEARCH_URL=http://semantic-search:8081
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
```

---

## Docker Compose (Full Stack)

```yaml
version: "3.9"

services:
  # Infrastructure
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # Browser UI
      - "7687:7687"  # Bolt protocol
    volumes:
      - neo4j-data:/data
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}

  # Microservices
  semantic-search:
    build: ../semantic-search-service
    ports:
      - "8081:8081"
    environment:
      - SEMANTIC_SEARCH_PORT=8081
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    volumes:
      - semantic-data:/data
    depends_on:
      - neo4j

  llm-gateway:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_GATEWAY_PORT=8080
      - LLM_GATEWAY_SEMANTIC_SEARCH_URL=http://semantic-search:8081
      - LLM_GATEWAY_AI_AGENTS_URL=http://ai-agents:8082
      - LLM_GATEWAY_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - semantic-search
      - redis

  ai-agents:
    build: ../ai-agents
    ports:
      - "8082:8082"
    environment:
      - AI_AGENTS_PORT=8082
      - AI_AGENTS_LLM_GATEWAY_URL=http://llm-gateway:8080
      - AI_AGENTS_SEMANTIC_SEARCH_URL=http://semantic-search:8081
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    depends_on:
      - llm-gateway
      - neo4j

volumes:
  semantic-data:
  neo4j-data:
```

---

## Deployment Patterns

### Local Development
```
                   ┌─────────────────────────────────┐
                   │  Developer Machine              │
                   │                                 │
                   │  docker-compose up              │
                   │    • redis                      │
                   │    • semantic-search (:8081)    │
                   │    • llm-gateway (:8080)        │
                   │    • ai-agents (:8082)          │
                   │                                 │
                   │  python -m doc_enhancer ...     │
                   └─────────────────────────────────┘
```

### Kubernetes
```
                   ┌─────────────────────────────────────────────────────────┐
                   │  Kubernetes Cluster                                     │
                   │                                                         │
                   │  Deployments (always running):                          │
                   │    • llm-gateway (replicas: 2)                          │
                   │    • semantic-search (replicas: 2)                      │
                   │    • ai-agents (replicas: 1)                            │
                   │                                                         │
                   │  Jobs (on-demand):                                      │
                   │    • doc-enhancer-job                                   │
                   │                                                         │
                   │  Services:                                              │
                   │    • llm-gateway-svc (ClusterIP)                        │
                   │    • semantic-search-svc (ClusterIP)                    │
                   │    • ai-agents-svc (ClusterIP)                          │
                   └─────────────────────────────────────────────────────────┘
```

---

## API Versioning

All microservices use `/v1/` prefix. Breaking changes will increment to `/v2/`.

---

## Health Checks

Each microservice exposes:
```
GET /health
  Response: { status: "healthy", version: "1.0.0" }

GET /health/ready
  Response: { status: "ready" }  # For K8s readiness probe
```

---

## Observability

All services emit:
- **Logs**: Structured JSON to stdout
- **Metrics**: Prometheus format at `/metrics`
- **Traces**: OpenTelemetry compatible

The observability platform in `llm-document-enhancer/observability_platform/` collects and visualizes.
