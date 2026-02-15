# LLM Gateway

[![CI](https://github.com/kevin-toles/llm-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/kevin-toles/llm-gateway/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A unified gateway microservice providing access to multiple LLM providers (Anthropic Claude, OpenAI GPT, Ollama) with built-in rate limiting, caching, session management, and observability.

## Features

- 🔄 **Multi-Provider Support**: Anthropic Claude, OpenAI GPT, Ollama (local)
- ⚡ **High Performance**: Async Python with FastAPI, Redis caching
- 🔒 **Security**: Non-root containers, network policies, secrets management
- 📊 **Observability**: Structured logging, Prometheus metrics, OpenTelemetry tracing
- 🚀 **Production Ready**: Kubernetes, Helm charts, CI/CD pipelines

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- (Optional) Kubernetes cluster + Helm 3.x

### Local Development with Docker

```bash
# Clone the repository
git clone https://github.com/kevin-toles/llm-gateway.git
cd llm-gateway

# Copy environment file and add your API keys
cp deploy/docker/.env.example .env
# Edit .env with your ANTHROPIC_API_KEY and/or OPENAI_API_KEY

# Start all services
docker-compose up -d

# Check health
curl http://localhost:8080/health

# View logs
docker-compose logs -f llm-gateway

# Stop services
docker-compose down
```

### Local Development with Python

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Start Redis (required for session storage)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Set environment variables
export LLM_GATEWAY_ENV=development
export LLM_GATEWAY_REDIS_URL=redis://localhost:6379

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Run tests
pytest tests/ -v
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component status |
| `/ready` | GET | Readiness check for Kubernetes |
| `/live` | GET | Liveness check for Kubernetes |
| `/docs` | GET | OpenAPI documentation (dev only) |

## Gateway Tools

The LLM Gateway exposes the following tools for external clients (MCP, external LLMs, llm-document-enhancer):

### Search Tools

| Tool | Backend Service | Description |
|------|-----------------|-------------|
| `search_corpus` | semantic-search-service | Semantic similarity search in document corpus |
| `hybrid_search` | semantic-search-service | Combined semantic + keyword search (WBS-CPA1) |
| `get_chunk` | semantic-search-service | Retrieve specific document chunks by ID |
| `cross_reference` | ai-agents | Multi-source cross-reference search |

### Embedding Tools

| Tool | Backend Service | Description |
|------|-----------------|-------------|
| `embed` | semantic-search-service | Generate embedding vectors for texts (WBS-CPA6) |
| `generate_embeddings` | Code-Orchestrator | Batch embedding generation via SBERT (WBS-CPA2) |

### Analysis Tools

| Tool | Backend Service | Description |
|------|-----------------|-------------|
| `compute_similarity` | Code-Orchestrator | Compute cosine similarity between texts (WBS-CPA2) |
| `extract_keywords` | Code-Orchestrator | Extract TF-IDF keywords from corpus (WBS-CPA2) |

### Metadata Tools

| Tool | Backend Service | Description |
|------|-----------------|-------------|
| `enrich_metadata` | ai-agents | MSEP metadata enrichment pipeline |

### Tool Usage Example

```bash
# Call embed tool via Gateway
curl -X POST http://localhost:8080/v1/tools/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Machine learning is powerful", "Deep learning is a subset"]}'

# Call hybrid_search tool
curl -X POST http://localhost:8080/v1/tools/hybrid_search \
  -H "Content-Type: application/json" \
  -d '{"query": "circuit breaker patterns", "top_k": 5}'

# Call compute_similarity tool
curl -X POST http://localhost:8080/v1/tools/compute_similarity \
  -H "Content-Type: application/json" \
  -d '{"text1": "Hello world", "text2": "Hi there world"}'
```

### Service URLs Configuration

Backend service URLs can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_SEMANTIC_SEARCH_URL` | `http://semantic-search:8081` | Semantic search service URL |
| `LLM_GATEWAY_AI_AGENTS_URL` | `http://ai-agents:8082` | AI agents service URL |
| `LLM_GATEWAY_CODE_ORCHESTRATOR_URL` | `http://code-orchestrator:8083` | Code orchestrator service URL |

## Project Structure

```
llm-gateway/
├── src/                    # Application source code
│   └── main.py            # FastAPI application entry point
├── config/                 # Configuration files
├── deploy/
│   ├── docker/            # Dockerfiles and docker-compose
│   ├── kubernetes/        # Kustomize base and overlays
│   └── helm/              # Helm chart
├── .github/
│   └── workflows/         # CI/CD pipelines
├── tests/                 # Test suites
├── docs/                  # Documentation
├── requirements.txt       # Production dependencies
└── requirements-dev.txt   # Development dependencies
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_GATEWAY_ENV` | `development` | Environment (development/staging/production) |
| `LLM_GATEWAY_PORT` | `8080` | Server port |
| `LLM_GATEWAY_LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `LLM_GATEWAY_WORKERS` | `4` | Number of Uvicorn workers |
| `LLM_GATEWAY_REDIS_URL` | `` | Redis connection URL |
| `LLM_GATEWAY_DEFAULT_PROVIDER` | `anthropic` | Default LLM provider |
| `LLM_GATEWAY_DEFAULT_MODEL` | `claude-3-sonnet-20240229` | Default model |
| `LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Rate limit |
| `LLM_GATEWAY_SESSION_TTL_SECONDS` | `3600` | Session TTL |

### API Keys (Secrets)

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |

## Deployment

### Kubernetes with Kustomize

```bash
# Deploy to dev
kubectl apply -k deploy/kubernetes/overlays/dev

# Deploy to staging
kubectl apply -k deploy/kubernetes/overlays/staging

# Deploy to production
kubectl apply -k deploy/kubernetes/overlays/prod
```

### Kubernetes with Helm

```bash
# Install/upgrade
helm upgrade --install llm-gateway deploy/helm/llm-gateway \
  --namespace llm-services \
  --create-namespace \
  -f deploy/helm/llm-gateway/values-prod.yaml \
  --set secrets.anthropicApiKey=$ANTHROPIC_API_KEY

# Check status
helm status llm-gateway -n llm-services

# Uninstall
helm uninstall llm-gateway -n llm-services
```

## Development

### Docker Compose Development Workflow (WBS 3.4.2.1)

The project includes multiple Docker Compose configurations for different scenarios:

#### Hot-Reload Development (Recommended)

```bash
# Start with hot-reload enabled (code changes reflected without rebuild)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Verify hot-reload is working:
# 1. Edit any file in src/
# 2. Watch the logs - uvicorn will auto-reload
# 3. Test with: curl http://localhost:8080/health
```

#### Selective Service Profiles (WBS 3.4.2.2)

```bash
# Full stack - all services (default)
docker-compose --profile full-stack up -d

# Gateway only - just gateway + Redis (no downstream services)
docker-compose --profile gateway-only up -d

# Integration tests - all services + test runner
docker-compose --profile integration-test up

# Check service status
docker-compose ps

# View logs
docker-compose logs -f llm-gateway
```

| Profile | Services | Use Case |
|---------|----------|----------|
| `full-stack` | redis, semantic-search, ai-agents, llm-gateway | Full integration testing |
| `gateway-only` | redis, llm-gateway-standalone | Gateway development without downstream services |
| `integration-test` | All services + test-runner | Automated integration testing |

#### Health Verification

```bash
# Check all services are healthy
curl http://localhost:8080/health        # llm-gateway
curl http://localhost:8080/health/ready  # llm-gateway readiness
curl http://localhost:8081/health        # semantic-search
curl http://localhost:8082/health        # ai-agents
docker exec llm-gateway-redis redis-cli ping  # Redis
```

### Running Tests

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires Redis)
pytest tests/integration -v

# All tests with coverage
pytest tests/ -v --cov=src --cov-report=html
```

### Linting & Type Checking

```bash
# Lint with Ruff
ruff check src/

# Format with Ruff
ruff format src/

# Type check with MyPy
mypy src/
```

### Helm Chart Testing

```bash
# Lint chart
helm lint deploy/helm/llm-gateway

# Run unit tests
helm unittest deploy/helm/llm-gateway

# Validate templates
helm template test deploy/helm/llm-gateway | kubeconform -summary -strict
```

## CI/CD

The project includes GitHub Actions workflows for:

- **CI** (`ci.yml`): Lint, test, security scan, build on push/PR
- **CD-Dev** (`cd-dev.yml`): Deploy to dev on push to `develop`
- **CD-Staging** (`cd-staging.yml`): Deploy to staging on push to `main`
- **CD-Production** (`cd-prod.yml`): Deploy to production on release

### Required Secrets (Quick Reference)

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Required For | How to Obtain |
|--------|--------------|---------------|
| `ANTHROPIC_API_KEY` | CI tests, CD deployments | [Anthropic Console](https://console.anthropic.com/) |
| `OPENAI_API_KEY` | CI tests, CD deployments | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `KUBE_CONFIG_DEV` | CD-Dev | `cat ~/.kube/config \| base64` |
| `KUBE_CONFIG_STAGING` | CD-Staging | `cat ~/.kube/config \| base64` |
| `KUBE_CONFIG_PROD` | CD-Production | `cat ~/.kube/config \| base64` |
| `SONAR_TOKEN` | CI security scan | [SonarCloud](https://sonarcloud.io/account/security) or SonarQube |
| `SONAR_HOST_URL` | CI security scan | Your SonarQube server URL (not needed for SonarCloud) |
| `CODECOV_TOKEN` | CI coverage upload | [Codecov Dashboard](https://codecov.io/) |
| `SLACK_WEBHOOK` | CD notifications | [Slack Apps](https://api.slack.com/messaging/webhooks) |

**Quick setup with GitHub CLI:**
```bash
# Set API keys from environment
gh secret set ANTHROPIC_API_KEY --body "$ANTHROPIC_API_KEY"
gh secret set OPENAI_API_KEY --body "$OPENAI_API_KEY"

# Set base64-encoded kubeconfig
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG_STAGING
```

See [.github/SECRETS.md](.github/SECRETS.md) for detailed setup instructions and security best practices.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
