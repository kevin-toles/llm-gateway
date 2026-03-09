# Environment Variables

This document describes all environment variables used by LLM Gateway.

## Application Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_GATEWAY_ENV` | No | `development` | Environment name (development, staging, production) |
| `LLM_GATEWAY_PORT` | No | `8080` | HTTP server port |
| `LLM_GATEWAY_LOG_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LLM_GATEWAY_WORKERS` | No | `4` | Number of Uvicorn worker processes |

## Redis Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_GATEWAY_REDIS_URL` | No | `` | Redis connection URL (e.g., `redis://localhost:6379`) |
| `LLM_GATEWAY_SESSION_TTL_SECONDS` | No | `3600` | Session time-to-live in seconds |

## LLM Provider Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_GATEWAY_DEFAULT_PROVIDER` | No | `anthropic` | Default LLM provider (anthropic, openai, ollama) |
| `LLM_GATEWAY_DEFAULT_MODEL` | No | `claude-3-sonnet-20240229` | Default model to use |

## API Keys (Secrets)

These should be stored securely and never committed to version control.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic Claude API key |
| `OPENAI_API_KEY` | Yes* | OpenAI API key |
| `OLLAMA_BASE_URL` | No | Ollama server URL (default: `http://localhost:11434`) |

*At least one provider API key is required for production use.

## Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | `60` | Rate limit per client per minute |
| `LLM_GATEWAY_RATE_LIMIT_TOKENS_PER_MINUTE` | No | `100000` | Token limit per client per minute |

## Service Discovery

For microservice deployments, these configure inter-service communication:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_GATEWAY_SEMANTIC_SEARCH_URL` | No | `` | Semantic search service URL |
| `LLM_GATEWAY_AI_AGENTS_URL` | No | `` | AI agents service URL |

## Observability

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | `` | OpenTelemetry collector endpoint |
| `OTEL_SERVICE_NAME` | No | `llm-gateway` | Service name for traces |
| `PROMETHEUS_MULTIPROC_DIR` | No | `/tmp` | Prometheus multiprocess directory |

## Example .env File

```bash
# Environment
LLM_GATEWAY_ENV=development
LLM_GATEWAY_PORT=8080
LLM_GATEWAY_LOG_LEVEL=DEBUG
LLM_GATEWAY_WORKERS=2

# Redis
LLM_GATEWAY_REDIS_URL=redis://localhost:6379
LLM_GATEWAY_SESSION_TTL_SECONDS=3600

# LLM Providers
LLM_GATEWAY_DEFAULT_PROVIDER=anthropic
LLM_GATEWAY_DEFAULT_MODEL=claude-3-sonnet-20240229
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-xxxxx

# Rate Limiting
LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Service Discovery (optional)
# LLM_GATEWAY_SEMANTIC_SEARCH_URL=http://semantic-search:8081
# LLM_GATEWAY_AI_AGENTS_URL=http://ai-agents:8082
```

## Kubernetes ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-gateway-config
data:
  LLM_GATEWAY_ENV: "production"
  LLM_GATEWAY_PORT: "8080"
  LLM_GATEWAY_LOG_LEVEL: "INFO"
  LLM_GATEWAY_WORKERS: "4"
  LLM_GATEWAY_REDIS_URL: "redis://redis:6379"
  LLM_GATEWAY_DEFAULT_PROVIDER: "anthropic"
  LLM_GATEWAY_DEFAULT_MODEL: "claude-3-sonnet-20240229"
  LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE: "60"
```

## Kubernetes Secret Example

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-gateway-secrets
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "sk-ant-api03-xxxxx"
  OPENAI_API_KEY: "sk-xxxxx"
```

## Environment-Specific Defaults

### Development
- `LLM_GATEWAY_ENV=development`
- `LLM_GATEWAY_LOG_LEVEL=DEBUG`
- `LLM_GATEWAY_WORKERS=2`
- OpenAPI docs enabled at `/docs`

### Staging
- `LLM_GATEWAY_ENV=staging`
- `LLM_GATEWAY_LOG_LEVEL=INFO`
- `LLM_GATEWAY_WORKERS=4`
- OpenAPI docs enabled

### Production
- `LLM_GATEWAY_ENV=production`
- `LLM_GATEWAY_LOG_LEVEL=WARNING`
- `LLM_GATEWAY_WORKERS=8`
- OpenAPI docs **disabled**
- Stricter rate limits

## Notes

1. **Never commit secrets** - Use `.env` files locally and Kubernetes Secrets in production
2. **Validate configuration** - The application validates required environment variables on startup
3. **Use secrets management** - Consider using HashiCorp Vault, AWS Secrets Manager, or GCP Secret Manager for production secrets
