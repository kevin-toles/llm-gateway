# Deployment Implementation Plan

## Overview

This document provides a comprehensive implementation plan for Docker, Kubernetes, and CI/CD infrastructure for the **llm-gateway** microservice. It addresses all identified gaps and aligns with the existing [ARCHITECTURE.md](./ARCHITECTURE.md) and [INTEGRATION_MAP.md](./INTEGRATION_MAP.md).

---

## LLM Interaction Architecture (Critical Design Principle)

> ⚠️ **The llm-gateway is the ONLY service that communicates directly with LLM providers (Anthropic, OpenAI, Ollama).** All other services route through the gateway.

```
                    ┌───────────────────────────────────────┐
                    │      llm-document-enhancer            │
                    │      (Application)                    │
                    │                                       │
                    │   ❌ NO direct LLM provider calls     │
                    │   ✅ Calls llm-gateway                │
                    └─────────────────┬─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          llm-gateway (Port 8080)                         │
│                                                                          │
│   ✅ THE ONLY SERVICE WITH LLM API CREDENTIALS                          │
│   • Provider abstraction    • Rate limiting     • Cost tracking         │
│   • Session management      • Response caching  • Tool orchestration    │
│                                                                          │
│                         │                │                               │
│              ┌──────────┴────────┐   ┌───┴───────────────┐              │
│              ▼                   ▼   ▼                   ▼              │
│       ┌───────────┐      ┌───────────┐      ┌───────────────┐           │
│       │ Anthropic │      │  OpenAI   │      │    Ollama     │           │
│       │  Claude   │      │   GPT     │      │   (Local)     │           │
│       └───────────┘      └───────────┘      └───────────────┘           │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    Tool Calls  │  (HTTP to downstream services)
                                ▼
          ┌─────────────────────────────────────────────────────┐
          │                  TOOL SERVICES                       │
          │                                                      │
          │  ┌─────────────────────┐  ┌────────────────────────┐│
          │  │ semantic-search     │  │      ai-agents         ││
          │  │ (Port 8081)         │  │     (Port 8082)        ││
          │  │                     │  │                        ││
          │  │ • SBERT embeddings  │  │ • Code Review Agent    ││
          │  │ • FAISS search      │  │ • Architecture Agent   ││
          │  │ • Topic modeling    │  │ • Doc Generate Agent   ││
          │  │                     │  │                        ││
          │  │ ❌ NO LLM calls     │  │ ❌ NO direct LLM calls ││
          │  │ (SBERT is local,    │  │ ✅ Calls BACK to       ││
          │  │  not an LLM API)    │  │    llm-gateway if      ││
          │  │                     │  │    LLM reasoning needed││
          │  └─────────────────────┘  └────────────────────────┘│
          └─────────────────────────────────────────────────────┘
```

**Why?**
- Single credential store (only gateway needs API keys)
- Centralized rate limiting, caching, cost tracking
- Provider abstraction (swap providers without downstream changes)
- Complete audit trail of all LLM usage

---

## Document Cross-References

| Document | Purpose | Relationship |
|----------|---------|--------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Service architecture, folder structure | Source of truth for service design |
| [INTEGRATION_MAP.md](./INTEGRATION_MAP.md) | Multi-service orchestration | Defines service dependencies |
| This Document | Infrastructure & deployment | Implementation details for DevOps |

---

## Gap Analysis Summary

| Gap | Status | Implementation Section |
|-----|--------|----------------------|
| Dockerfile | 🔴 Missing | [Section 1](#1-dockerfile-implementation) |
| Kubernetes manifests | 🔴 Missing | [Section 2](#2-kubernetes-manifests) |
| Helm charts | 🔴 Missing | [Section 3](#3-helm-charts) |
| CI/CD pipeline | 🔴 Missing | [Section 4](#4-cicd-pipeline) |
| Container registry | 🔴 Missing | [Section 5](#5-container-registry-strategy) |
| Resource limits | 🔴 Missing | [Section 6](#6-resource-limits) |
| Ingress/Load Balancer | 🔴 Missing | [Section 7](#7-ingress-configuration) |
| Secret management | 🔴 Missing | [Section 8](#8-secret-management) |
| Network policies | 🔴 Missing | [Section 9](#9-network-policies) |

---

## Folder Structure (Updated)

```
llm-gateway/
├── src/                           # Application source (per ARCHITECTURE.md)
├── tests/                         # Tests (per ARCHITECTURE.md)
├── config/                        # Runtime configuration
├── docs/
│   ├── ARCHITECTURE.md
│   ├── INTEGRATION_MAP.md
│   ├── DEPLOYMENT_IMPLEMENTATION_PLAN.md   # This document
│   └── API.md
├── scripts/
│   ├── start.sh
│   ├── healthcheck.sh
│   └── entrypoint.sh              # NEW: Container entrypoint
│
├── deploy/                        # NEW: Deployment infrastructure
│   ├── docker/
│   │   ├── Dockerfile             # Multi-stage production build
│   │   ├── Dockerfile.dev         # Development build with hot-reload
│   │   ├── docker-compose.yml     # Full stack local development
│   │   ├── docker-compose.dev.yml # Development overrides
│   │   └── docker-compose.test.yml# Integration test environment
│   │
│   ├── kubernetes/
│   │   ├── base/                  # Kustomize base
│   │   │   ├── kustomization.yaml
│   │   │   ├── namespace.yaml
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── hpa.yaml           # HorizontalPodAutoscaler
│   │   │   ├── pdb.yaml           # PodDisruptionBudget
│   │   │   └── networkpolicy.yaml
│   │   │
│   │   └── overlays/
│   │       ├── dev/
│   │       │   ├── kustomization.yaml
│   │       │   ├── replica-patch.yaml
│   │       │   └── resource-patch.yaml
│   │       ├── staging/
│   │       │   ├── kustomization.yaml
│   │       │   ├── replica-patch.yaml
│   │       │   └── ingress.yaml
│   │       └── prod/
│   │           ├── kustomization.yaml
│   │           ├── replica-patch.yaml
│   │           ├── resource-patch.yaml
│   │           ├── ingress.yaml
│   │           └── hpa-patch.yaml
│   │
│   └── helm/
│       └── llm-gateway/
│           ├── Chart.yaml
│           ├── values.yaml
│           ├── values-dev.yaml
│           ├── values-staging.yaml
│           ├── values-prod.yaml
│           └── templates/
│               ├── _helpers.tpl
│               ├── deployment.yaml
│               ├── service.yaml
│               ├── configmap.yaml
│               ├── secret.yaml
│               ├── hpa.yaml
│               ├── pdb.yaml
│               ├── ingress.yaml
│               ├── networkpolicy.yaml
│               └── serviceaccount.yaml
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Continuous Integration
│       ├── cd-dev.yml             # Deploy to dev
│       ├── cd-staging.yml         # Deploy to staging
│       └── cd-prod.yml            # Deploy to production
│
├── Dockerfile                     # Symlink to deploy/docker/Dockerfile
├── docker-compose.yml             # Symlink to deploy/docker/docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 1. Dockerfile Implementation

### 1.1 Production Dockerfile (Multi-Stage)

**File**: `deploy/docker/Dockerfile`

```dockerfile
# ==============================================================================
# Stage 1: Builder
# ==============================================================================
FROM python:3.11-slim-bookworm AS builder

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ==============================================================================
# Stage 2: Production Runtime
# ==============================================================================
FROM python:3.11-slim-bookworm AS production

# Labels (OCI standard)
LABEL org.opencontainers.image.title="llm-gateway" \
      org.opencontainers.image.description="LLM Gateway Microservice" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="kevin-toles" \
      org.opencontainers.image.source="https://github.com/kevin-toles/llm-gateway"

# Security: Run as non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH" \
    # Application defaults (override via Kubernetes ConfigMap)
    LLM_GATEWAY_PORT=8080 \
    LLM_GATEWAY_LOG_LEVEL=INFO \
    LLM_GATEWAY_WORKERS=4

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup scripts/ ./scripts/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${LLM_GATEWAY_PORT}/health || exit 1

# Expose port (documentation)
EXPOSE 8080

# Entrypoint
ENTRYPOINT ["scripts/entrypoint.sh"]

# Default command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

### 1.2 Development Dockerfile

**File**: `deploy/docker/Dockerfile.dev`

```dockerfile
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Install dev dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with dev extras
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -r requirements-dev.txt

# Copy application (mounted as volume in dev)
COPY . .

EXPOSE 8080

# Hot-reload enabled
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
```

### 1.3 Entrypoint Script

**File**: `scripts/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Run pre-flight checks
echo "Starting llm-gateway..."
echo "Environment: ${LLM_GATEWAY_ENV:-production}"
echo "Port: ${LLM_GATEWAY_PORT:-8080}"

# Wait for dependencies if required
if [ -n "$LLM_GATEWAY_REDIS_URL" ]; then
    echo "Waiting for Redis..."
    # Add redis health check here if needed
fi

# Execute the main command
exec "$@"
```

---

## 2. Kubernetes Manifests

### 2.1 Namespace

**File**: `deploy/kubernetes/base/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: llm-services
  labels:
    app.kubernetes.io/part-of: llm-document-enhancement
    istio-injection: enabled  # Optional: if using Istio
```

### 2.2 Deployment

**File**: `deploy/kubernetes/base/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-gateway
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
    app.kubernetes.io/component: gateway
    app.kubernetes.io/part-of: llm-document-enhancement
    app.kubernetes.io/version: "1.0.0"
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: llm-gateway
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: llm-gateway
        app.kubernetes.io/component: gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: llm-gateway
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      
      containers:
        - name: llm-gateway
          image: ghcr.io/kevin-toles/llm-gateway:latest
          imagePullPolicy: Always
          
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          
          envFrom:
            - configMapRef:
                name: llm-gateway-config
            - secretRef:
                name: llm-gateway-secrets
          
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "2Gi"
          
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
          
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /app/.cache
      
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir: {}
      
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app.kubernetes.io/name: llm-gateway
                topologyKey: kubernetes.io/hostname
      
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: llm-gateway
```

### 2.3 Service

**File**: `deploy/kubernetes/base/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: llm-gateway
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
    app.kubernetes.io/component: gateway
spec:
  type: ClusterIP
  ports:
    - name: http
      port: 8080
      targetPort: http
      protocol: TCP
  selector:
    app.kubernetes.io/name: llm-gateway
```

### 2.4 ConfigMap

**File**: `deploy/kubernetes/base/configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-gateway-config
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
data:
  # Service Configuration
  LLM_GATEWAY_PORT: "8080"
  LLM_GATEWAY_ENV: "production"
  LLM_GATEWAY_LOG_LEVEL: "INFO"
  LLM_GATEWAY_LOG_FORMAT: "json"
  LLM_GATEWAY_WORKERS: "4"
  
  # Service Discovery (per INTEGRATION_MAP.md)
  LLM_GATEWAY_SEMANTIC_SEARCH_URL: "http://semantic-search.llm-services.svc.cluster.local:8081"
  LLM_GATEWAY_AI_AGENTS_URL: "http://ai-agents.llm-services.svc.cluster.local:8082"
  
  # Redis Configuration
  LLM_GATEWAY_REDIS_URL: "redis://redis.llm-services.svc.cluster.local:6379"
  
  # Provider Configuration
  LLM_GATEWAY_DEFAULT_PROVIDER: "anthropic"
  LLM_GATEWAY_DEFAULT_MODEL: "claude-3-sonnet-20240229"
  
  # Rate Limiting
  LLM_GATEWAY_RATE_LIMIT_REQUESTS_PER_MINUTE: "60"
  
  # Session Configuration
  LLM_GATEWAY_SESSION_TTL_SECONDS: "3600"
  
  # CORS (if needed)
  LLM_GATEWAY_CORS_ORIGINS: "*"
```

### 2.5 Secret (Template)

**File**: `deploy/kubernetes/base/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-gateway-secrets
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
type: Opaque
stringData:
  # These should be populated via external-secrets or sealed-secrets
  # DO NOT commit actual values to git
  LLM_GATEWAY_ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"
  LLM_GATEWAY_OPENAI_API_KEY: "${OPENAI_API_KEY}"
```

### 2.6 HorizontalPodAutoscaler

**File**: `deploy/kubernetes/base/hpa.yaml`

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-gateway
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 4
          periodSeconds: 15
      selectPolicy: Max
```

### 2.7 PodDisruptionBudget

**File**: `deploy/kubernetes/base/pdb.yaml`

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: llm-gateway
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: llm-gateway
```

### 2.8 ServiceAccount

**File**: `deploy/kubernetes/base/serviceaccount.yaml`

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: llm-gateway
  namespace: llm-services
  labels:
    app.kubernetes.io/name: llm-gateway
```

### 2.9 Kustomization (Base)

**File**: `deploy/kubernetes/base/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: llm-services

resources:
  - namespace.yaml
  - serviceaccount.yaml
  - configmap.yaml
  - secret.yaml
  - deployment.yaml
  - service.yaml
  - hpa.yaml
  - pdb.yaml
  - networkpolicy.yaml

commonLabels:
  app.kubernetes.io/managed-by: kustomize

images:
  - name: ghcr.io/kevin-toles/llm-gateway
    newTag: latest
```

---

## 3. Helm Charts

### 3.1 Chart.yaml

**File**: `deploy/helm/llm-gateway/Chart.yaml`

```yaml
apiVersion: v2
name: llm-gateway
description: LLM Gateway Microservice - Unified API for LLM interactions
type: application
version: 0.1.0
appVersion: "1.0.0"

keywords:
  - llm
  - gateway
  - ai
  - microservice
  - fastapi

home: https://github.com/kevin-toles/llm-gateway
sources:
  - https://github.com/kevin-toles/llm-gateway

maintainers:
  - name: Kevin Toles
    email: kevin@example.com

dependencies:
  - name: redis
    version: "17.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
```

### 3.2 values.yaml (Default)

**File**: `deploy/helm/llm-gateway/values.yaml`

```yaml
# Default values for llm-gateway

replicaCount: 2

image:
  repository: ghcr.io/kevin-toles/llm-gateway
  pullPolicy: IfNotPresent
  tag: ""  # Defaults to Chart.appVersion

imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  annotations: {}
  name: ""

podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL

service:
  type: ClusterIP
  port: 8080

ingress:
  enabled: false
  className: "nginx"
  annotations: {}
  hosts:
    - host: llm-gateway.local
      paths:
        - path: /
          pathType: Prefix
  tls: []

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

nodeSelector: {}
tolerations: []
affinity: {}

# Pod disruption budget
podDisruptionBudget:
  enabled: true
  minAvailable: 1

# Application Configuration
config:
  port: 8080
  environment: production
  logLevel: INFO
  logFormat: json
  workers: 4
  
  # Service Discovery (per INTEGRATION_MAP.md)
  semanticSearchUrl: "http://semantic-search:8081"
  aiAgentsUrl: "http://ai-agents:8082"
  
  # Redis
  redisUrl: "redis://redis:6379"
  
  # Provider defaults
  defaultProvider: anthropic
  defaultModel: claude-3-sonnet-20240229
  
  # Rate limiting
  rateLimitRequestsPerMinute: 60
  
  # Session
  sessionTtlSeconds: 3600

# Secrets (use external-secrets in production)
secrets:
  anthropicApiKey: ""
  openaiApiKey: ""

# Network policy
networkPolicy:
  enabled: true
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: llm-services
        - podSelector:
            matchLabels:
              app.kubernetes.io/part-of: llm-document-enhancement

# Redis subchart configuration
redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: false
  master:
    persistence:
      enabled: false
```

### 3.3 values-prod.yaml (Production Overrides)

**File**: `deploy/helm/llm-gateway/values-prod.yaml`

```yaml
# Production values for llm-gateway

replicaCount: 3

image:
  pullPolicy: Always

resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 60

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
  hosts:
    - host: llm-gateway.prod.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: llm-gateway-tls
      hosts:
        - llm-gateway.prod.example.com

config:
  environment: production
  logLevel: INFO
  workers: 8
  rateLimitRequestsPerMinute: 120

redis:
  enabled: true
  architecture: replication
  auth:
    enabled: true
  master:
    persistence:
      enabled: true
      size: 8Gi
  replica:
    replicaCount: 2
    persistence:
      enabled: true
      size: 8Gi
```

---

## 4. CI/CD Pipeline

### 4.1 Continuous Integration

**File**: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install ruff mypy
          pip install -r requirements.txt
      
      - name: Run Ruff (linting)
        run: ruff check src/
      
      - name: Run Ruff (formatting)
        run: ruff format --check src/
      
      - name: Run MyPy (type checking)
        run: mypy src/

  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration -v
        env:
          LLM_GATEWAY_REDIS_URL: redis://localhost:6379
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'

  build:
    needs: [lint, test, security]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=sha,prefix=
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: deploy/docker/Dockerfile
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

### 4.2 Continuous Deployment - Dev

**File**: `.github/workflows/cd-dev.yml`

```yaml
name: CD - Dev

on:
  push:
    branches: [develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  KUBE_NAMESPACE: llm-services-dev

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: development
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Kubectl
        uses: azure/setup-kubectl@v3
      
      - name: Configure Kubeconfig
        run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBE_CONFIG_DEV }}" | base64 -d > ~/.kube/config
      
      - name: Deploy with Kustomize
        run: |
          cd deploy/kubernetes/overlays/dev
          kustomize edit set image ghcr.io/kevin-toles/llm-gateway=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          kubectl apply -k .
      
      - name: Verify deployment
        run: |
          kubectl rollout status deployment/llm-gateway -n ${{ env.KUBE_NAMESPACE }} --timeout=300s
      
      - name: Run smoke tests
        run: |
          POD=$(kubectl get pods -n ${{ env.KUBE_NAMESPACE }} -l app.kubernetes.io/name=llm-gateway -o jsonpath='{.items[0].metadata.name}')
          kubectl exec -n ${{ env.KUBE_NAMESPACE }} $POD -- curl -f http://localhost:8080/health
```

### 4.3 Continuous Deployment - Production

**File**: `.github/workflows/cd-prod.yml`

```yaml
name: CD - Production

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to deploy'
        required: true
        type: string

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  KUBE_NAMESPACE: llm-services

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set version
        id: version
        run: |
          if [ "${{ github.event_name }}" == "release" ]; then
            echo "version=${{ github.event.release.tag_name }}" >> $GITHUB_OUTPUT
          else
            echo "version=${{ github.event.inputs.version }}" >> $GITHUB_OUTPUT
          fi
      
      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: 'v3.13.0'
      
      - name: Configure Kubeconfig
        run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBE_CONFIG_PROD }}" | base64 -d > ~/.kube/config
      
      - name: Deploy with Helm
        run: |
          helm upgrade --install llm-gateway deploy/helm/llm-gateway \
            --namespace ${{ env.KUBE_NAMESPACE }} \
            --create-namespace \
            --values deploy/helm/llm-gateway/values-prod.yaml \
            --set image.tag=${{ steps.version.outputs.version }} \
            --set secrets.anthropicApiKey=${{ secrets.ANTHROPIC_API_KEY }} \
            --set secrets.openaiApiKey=${{ secrets.OPENAI_API_KEY }} \
            --wait \
            --timeout 10m
      
      - name: Verify deployment
        run: |
          kubectl rollout status deployment/llm-gateway -n ${{ env.KUBE_NAMESPACE }} --timeout=300s
      
      - name: Notify on success
        if: success()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "✅ llm-gateway ${{ steps.version.outputs.version }} deployed to production"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 5. Container Registry Strategy

### Registry Selection

| Environment | Registry | Rationale |
|-------------|----------|-----------|
| Open Source | GitHub Container Registry (ghcr.io) | Native GitHub integration, free for public repos |
| Enterprise | AWS ECR / GCP Artifact Registry | Cloud-native, IAM integration |
| Air-gapped | Harbor | Self-hosted, enterprise features |

### Image Naming Convention

```
ghcr.io/kevin-toles/llm-gateway:<tag>

Tags:
  - latest          # Latest main branch build
  - v1.0.0          # Semantic version (releases)
  - sha-abc123      # Git SHA (immutable)
  - develop         # Develop branch builds
  - pr-123          # Pull request builds
```

### Image Signing (Cosign)

```yaml
# Add to CI workflow
- name: Sign image with Cosign
  uses: sigstore/cosign-installer@v3
  
- name: Sign the image
  run: |
    cosign sign --yes ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
  env:
    COSIGN_EXPERIMENTAL: 1
```

---

## 6. Resource Limits

### Resource Tiers

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit | Replicas |
|-------------|-------------|-----------|----------------|--------------|----------|
| Dev | 100m | 500m | 256Mi | 512Mi | 1 |
| Staging | 250m | 1000m | 512Mi | 2Gi | 2 |
| Production | 500m | 2000m | 1Gi | 4Gi | 3-20 |

### Resource Calculations

Based on FastAPI + Uvicorn with 4 workers:

```
Base memory: ~200MB
Per worker: ~100MB
Safety margin: 50%

Minimum = 200 + (4 * 100) = 600MB
With margin = 600 * 1.5 = 900MB → round to 1Gi request, 2Gi limit
```

### LimitRange (Namespace Defaults)

**File**: `deploy/kubernetes/base/limitrange.yaml`

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: llm-services
spec:
  limits:
    - default:
        cpu: "1000m"
        memory: "2Gi"
      defaultRequest:
        cpu: "250m"
        memory: "512Mi"
      type: Container
```

---

## 7. Ingress Configuration

### NGINX Ingress

**File**: `deploy/kubernetes/overlays/prod/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-gateway
  namespace: llm-services
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/use-regex: "true"
    # Security headers
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "X-Frame-Options: DENY";
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-XSS-Protection: 1; mode=block";
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - llm-gateway.example.com
      secretName: llm-gateway-tls
  rules:
    - host: llm-gateway.example.com
      http:
        paths:
          - path: /v1/
            pathType: Prefix
            backend:
              service:
                name: llm-gateway
                port:
                  number: 8080
          - path: /health
            pathType: Exact
            backend:
              service:
                name: llm-gateway
                port:
                  number: 8080
```

### Internal Service Mesh (Optional)

For service-to-service communication within the cluster, consider Istio:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: llm-gateway
  namespace: llm-services
spec:
  hosts:
    - llm-gateway
  http:
    - match:
        - uri:
            prefix: /v1/
      route:
        - destination:
            host: llm-gateway
            port:
              number: 8080
      timeout: 30s
      retries:
        attempts: 3
        perTryTimeout: 10s
```

---

## 8. Secret Management

### Option A: External Secrets Operator (Recommended)

**File**: `deploy/kubernetes/base/external-secret.yaml`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: llm-gateway-secrets
  namespace: llm-services
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: llm-gateway-secrets
    creationPolicy: Owner
  data:
    - secretKey: LLM_GATEWAY_ANTHROPIC_API_KEY
      remoteRef:
        key: llm-gateway/anthropic-api-key
    - secretKey: LLM_GATEWAY_OPENAI_API_KEY
      remoteRef:
        key: llm-gateway/openai-api-key
```

### Option B: Sealed Secrets (GitOps)

```bash
# Create sealed secret
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# The sealed secret can be committed to git
```

### Option C: HashiCorp Vault

```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "llm-gateway"
    vault.hashicorp.com/agent-inject-secret-anthropic: "secret/data/llm-gateway/anthropic"
spec:
  serviceAccountName: llm-gateway
  containers:
    - name: llm-gateway
      env:
        - name: LLM_GATEWAY_ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: vault-injected
              key: anthropic-api-key
```

### Secret Rotation Strategy

| Provider | Rotation Method | Frequency |
|----------|-----------------|-----------|
| Anthropic | Generate new key → Update secret → Revoke old | 90 days |
| OpenAI | Generate new key → Update secret → Revoke old | 90 days |
| Redis | Password rotation via Kubernetes operator | 30 days |

---

## 9. Network Policies

### Default Deny

**File**: `deploy/kubernetes/base/networkpolicy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: llm-services
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: llm-gateway-policy
  namespace: llm-services
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: llm-gateway
  policyTypes:
    - Ingress
    - Egress
  
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
    
    # Allow from llm-document-enhancer jobs
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: doc-enhancer
      ports:
        - protocol: TCP
          port: 8080
    
    # Allow from ai-agents (for callback when agents need LLM reasoning)
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: ai-agents
      ports:
        - protocol: TCP
          port: 8080
    
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 8080
  
  egress:
    # Allow to semantic-search-service (per INTEGRATION_MAP.md)
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: semantic-search
      ports:
        - protocol: TCP
          port: 8081
    
    # Allow to ai-agents (per INTEGRATION_MAP.md)
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: ai-agents
      ports:
        - protocol: TCP
          port: 8082
    
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: redis
      ports:
        - protocol: TCP
          port: 6379
    
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
    
    # Allow external HTTPS (for LLM providers: Anthropic, OpenAI)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
```

### Network Policy Diagram

```
                                    INGRESS
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  ▼                  │
                    │    ┌─────────────────────────┐      │
                    │    │      llm-gateway        │      │
  ingress-nginx ────┼───►│        :8080            │      │
  doc-enhancer ─────┼───►│                         │      │
  ai-agents ────────┼───►│                         │      │
  prometheus ───────┼───►│                         │      │
                    │    └──────────┬──────────────┘      │
                    │               │                     │
                    │    EGRESS     │                     │
                    │               ▼                     │
                    │    ┌──────────────────┐             │
                    │    │ semantic-search  │◄────────────┤
                    │    │     :8081        │             │
                    │    └──────────────────┘             │
                    │    ┌──────────────────┐             │
                    │    │    ai-agents     │◄────────────┤
                    │    │     :8082        │             │
                    │    └──────────────────┘             │
                    │    ┌──────────────────┐             │
                    │    │      Redis       │◄────────────┤
                    │    │     :6379        │             │
                    │    └──────────────────┘             │
                    │    ┌──────────────────┐             │
                    │    │  External HTTPS  │◄────────────┘
                    │    │ (Anthropic/OpenAI)│
                    │    └──────────────────┘
                    │
                    └────────────────────────────────────
                              llm-services namespace
```

---

## 10. Work Breakdown Structure (WBS)

This section provides a comprehensive 5-level WBS organized into 4 stages. Each Level 1 item includes acceptance criteria that are satisfied when all child tasks are completed.

### WBS Numbering Convention
```
Stage.Category.Component.Task.Subtask
  1      1         1       1      1
```

---

## Stage 1: Scaffolding and Infrastructure Setup

> **Stage 1 Acceptance Criteria**: The llm-gateway repository has a complete `deploy/` folder structure with all Docker, Kubernetes, Helm, and CI/CD scaffolding in place. All configuration files pass linting/validation. Local development environment starts successfully with `docker-compose up`.

---

### 1.1 Project Structure Scaffolding

> **Acceptance Criteria**: All directories exist per ARCHITECTURE.md. All `__init__.py` files created. Symlinks functional. `tree deploy/` shows complete structure matching specification.

#### 1.1.1 Deploy Folder Hierarchy Creation

##### 1.1.1.1 Create Root Deploy Structure
- 1.1.1.1.1 Create `deploy/` directory at repository root
- 1.1.1.1.2 Create `deploy/docker/` subdirectory
- 1.1.1.1.3 Create `deploy/kubernetes/` subdirectory
- 1.1.1.1.4 Create `deploy/helm/` subdirectory
- 1.1.1.1.5 Verify structure with `tree deploy/ -L 2`

##### 1.1.1.2 Create Docker Folder Structure
- 1.1.1.2.1 Create `deploy/docker/` directory (if not exists)
- 1.1.1.2.2 Create placeholder `deploy/docker/Dockerfile`
- 1.1.1.2.3 Create placeholder `deploy/docker/Dockerfile.dev`
- 1.1.1.2.4 Create placeholder `deploy/docker/docker-compose.yml`
- 1.1.1.2.5 Create placeholder `deploy/docker/docker-compose.dev.yml`
- 1.1.1.2.6 Create placeholder `deploy/docker/docker-compose.test.yml`

##### 1.1.1.3 Create Kubernetes Folder Structure
- 1.1.1.3.1 Create `deploy/kubernetes/base/` directory
- 1.1.1.3.2 Create `deploy/kubernetes/overlays/` directory
- 1.1.1.3.3 Create `deploy/kubernetes/overlays/dev/` directory
- 1.1.1.3.4 Create `deploy/kubernetes/overlays/staging/` directory
- 1.1.1.3.5 Create `deploy/kubernetes/overlays/prod/` directory
- 1.1.1.3.6 Verify structure with `tree deploy/kubernetes/ -L 3`

##### 1.1.1.4 Create Helm Chart Folder Structure
- 1.1.1.4.1 Create `deploy/helm/llm-gateway/` directory
- 1.1.1.4.2 Create `deploy/helm/llm-gateway/templates/` directory
- 1.1.1.4.3 Create placeholder `deploy/helm/llm-gateway/Chart.yaml`
- 1.1.1.4.4 Create placeholder `deploy/helm/llm-gateway/values.yaml`
- 1.1.1.4.5 Verify structure with `tree deploy/helm/ -L 3`

#### 1.1.2 GitHub Workflows Scaffolding

##### 1.1.2.1 Create Workflows Directory
- 1.1.2.1.1 Create `.github/` directory at repository root
- 1.1.2.1.2 Create `.github/workflows/` subdirectory
- 1.1.2.1.3 Create placeholder `.github/workflows/ci.yml`
- 1.1.2.1.4 Create placeholder `.github/workflows/cd-dev.yml`
- 1.1.2.1.5 Create placeholder `.github/workflows/cd-staging.yml`
- 1.1.2.1.6 Create placeholder `.github/workflows/cd-prod.yml`

##### 1.1.2.2 Create Root Symlinks
- 1.1.2.2.1 Create symlink `Dockerfile` → `deploy/docker/Dockerfile`
- 1.1.2.2.2 Create symlink `docker-compose.yml` → `deploy/docker/docker-compose.yml`
- 1.1.2.2.3 Verify symlinks with `ls -la Dockerfile docker-compose.yml`
- 1.1.2.2.4 Test symlink resolution with `cat Dockerfile`

#### 1.1.3 Scripts Directory Setup

##### 1.1.3.1 Create Operational Scripts
- 1.1.3.1.1 Create `scripts/` directory (if not exists)
- 1.1.3.1.2 Create `scripts/entrypoint.sh` with shebang and base structure
- 1.1.3.1.3 Create `scripts/healthcheck.sh` placeholder
- 1.1.3.1.4 Create `scripts/start.sh` placeholder
- 1.1.3.1.5 Set executable permissions: `chmod +x scripts/*.sh`
- 1.1.3.1.6 Verify permissions: `ls -la scripts/`

---

### 1.2 Docker Infrastructure

> **Acceptance Criteria**: `docker build -t llm-gateway .` succeeds. Container runs and responds to `/health` endpoint. Non-root user verified. Image size < 500MB. All docker-compose variants start without errors.

#### 1.2.1 Production Dockerfile Implementation

##### 1.2.1.1 Builder Stage
- 1.2.1.1.1 Add `FROM python:3.11-slim-bookworm AS builder` base image
- 1.2.1.1.2 Configure environment variables (PYTHONDONTWRITEBYTECODE, PYTHONUNBUFFERED, PIP_NO_CACHE_DIR)
- 1.2.1.1.3 Install build dependencies (build-essential, curl)
- 1.2.1.1.4 Create virtual environment at `/opt/venv`
- 1.2.1.1.5 Copy and install `requirements.txt` dependencies
- 1.2.1.1.6 Verify builder stage: `docker build --target builder -t llm-gateway-builder .`

##### 1.2.1.2 Production Runtime Stage
- 1.2.1.2.1 Add `FROM python:3.11-slim-bookworm AS production` base image
- 1.2.1.2.2 Add OCI labels (title, description, version, vendor, source)
- 1.2.1.2.3 Create non-root user `appuser` with UID/GID 1000
- 1.2.1.2.4 Configure runtime environment variables
- 1.2.1.2.5 Install runtime-only dependencies (curl, ca-certificates)
- 1.2.1.2.6 Copy virtual environment from builder stage

##### 1.2.1.3 Application Setup
- 1.2.1.3.1 Set `WORKDIR /app`
- 1.2.1.3.2 Copy `src/` directory with correct ownership
- 1.2.1.3.3 Copy `config/` directory with correct ownership
- 1.2.1.3.4 Copy `scripts/` directory with correct ownership
- 1.2.1.3.5 Set executable permissions on scripts
- 1.2.1.3.6 Switch to non-root user with `USER appuser`

##### 1.2.1.4 Container Configuration
- 1.2.1.4.1 Add HEALTHCHECK instruction (interval=30s, timeout=10s, retries=3)
- 1.2.1.4.2 Add EXPOSE 8080 documentation
- 1.2.1.4.3 Set ENTRYPOINT to `scripts/entrypoint.sh`
- 1.2.1.4.4 Set CMD for uvicorn with 4 workers
- 1.2.1.4.5 Build and verify: `docker build -t llm-gateway:test .`
- 1.2.1.4.6 Verify non-root: `docker run --rm llm-gateway:test whoami` → expect `appuser`

##### 1.2.1.5 Dockerfile Testing (TDD)
- 1.2.1.5.1 RED: Write test script to verify image builds successfully
- 1.2.1.5.2 RED: Write test to verify `/health` endpoint responds
- 1.2.1.5.3 RED: Write test to verify non-root user
- 1.2.1.5.4 RED: Write test to verify image size < 500MB
- 1.2.1.5.5 GREEN: Fix any failing tests
- 1.2.1.5.6 REFACTOR: Optimize Dockerfile layers for caching

#### 1.2.2 Development Dockerfile Implementation

##### 1.2.2.1 Dev Dockerfile Setup
- 1.2.2.1.1 Create `deploy/docker/Dockerfile.dev` with Python 3.11 base
- 1.2.2.1.2 Install development dependencies (git, build-essential)
- 1.2.2.1.3 Copy and install `requirements.txt` and `requirements-dev.txt`
- 1.2.2.1.4 Configure for hot-reload with `--reload` flag
- 1.2.2.1.5 Test build: `docker build -f deploy/docker/Dockerfile.dev -t llm-gateway:dev .`
- 1.2.2.1.6 Verify hot-reload: modify source file, observe auto-restart

#### 1.2.3 Entrypoint Script Implementation

##### 1.2.3.1 Entrypoint Logic
- 1.2.3.1.1 Add bash shebang and `set -e` for error handling
- 1.2.3.1.2 Add startup logging (environment, port)
- 1.2.3.1.3 Add Redis dependency wait logic (if `LLM_GATEWAY_REDIS_URL` set)
- 1.2.3.1.4 Add `exec "$@"` for proper signal handling
- 1.2.3.1.5 Test entrypoint: `docker run --rm llm-gateway:test echo "test"`
- 1.2.3.1.6 Verify logs show startup messages

#### 1.2.4 Docker Compose Configuration

##### 1.2.4.1 Main Docker Compose (Full Stack)
- 1.2.4.1.1 Create `deploy/docker/docker-compose.yml` with version 3.9
- 1.2.4.1.2 Add `redis` service (redis:7-alpine, port 6379)
- 1.2.4.1.3 Add `llm-gateway` service with build context
- 1.2.4.1.4 Configure environment variables per INTEGRATION_MAP.md
- 1.2.4.1.5 Add `depends_on` for redis
- 1.2.4.1.6 Add health check configuration
- 1.2.4.1.7 Test: `docker-compose -f deploy/docker/docker-compose.yml config`

##### 1.2.4.2 Development Docker Compose Override
- 1.2.4.2.1 Create `deploy/docker/docker-compose.dev.yml`
- 1.2.4.2.2 Override build to use `Dockerfile.dev`
- 1.2.4.2.3 Add volume mount for source code hot-reload
- 1.2.4.2.4 Add volume mount for logs
- 1.2.4.2.5 Set DEBUG environment variables
- 1.2.4.2.6 Test: `docker-compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.dev.yml up`

##### 1.2.4.3 Test Docker Compose Environment
- 1.2.4.3.1 Create `deploy/docker/docker-compose.test.yml`
- 1.2.4.3.2 Add isolated network for test environment
- 1.2.4.3.3 Add test database/redis containers
- 1.2.4.3.4 Configure for CI/CD usage (no TTY, exit codes)
- 1.2.4.3.5 Add test runner service
- 1.2.4.3.6 Test: `docker-compose -f deploy/docker/docker-compose.test.yml run --rm tests`

##### 1.2.4.4 Docker Compose Validation
- 1.2.4.4.1 Validate all compose files: `docker-compose config` for each
- 1.2.4.4.2 Test full stack startup: `docker-compose up -d`
- 1.2.4.4.3 Verify health endpoint: `curl http://localhost:8080/health`
- 1.2.4.4.4 Verify Redis connectivity from gateway container
- 1.2.4.4.5 Test graceful shutdown: `docker-compose down`
- 1.2.4.4.6 Document any issues in troubleshooting section

---

### 1.3 Kubernetes Manifests Scaffolding

> **Acceptance Criteria**: `kubectl kustomize deploy/kubernetes/base` produces valid YAML. `kubectl kustomize deploy/kubernetes/overlays/dev` produces valid YAML with dev overrides. All manifests pass `kubeval` or `kubeconform` validation.

#### 1.3.1 Kustomize Base Manifests

##### 1.3.1.1 Namespace Configuration
- 1.3.1.1.1 Create `deploy/kubernetes/base/namespace.yaml`
- 1.3.1.1.2 Set namespace name to `llm-services`
- 1.3.1.1.3 Add labels: `app.kubernetes.io/part-of: llm-document-enhancement`
- 1.3.1.1.4 Add optional Istio injection label
- 1.3.1.1.5 Validate YAML syntax: `kubectl apply --dry-run=client -f namespace.yaml`

##### 1.3.1.2 ServiceAccount Configuration
- 1.3.1.2.1 Create `deploy/kubernetes/base/serviceaccount.yaml`
- 1.3.1.2.2 Set name to `llm-gateway`
- 1.3.1.2.3 Add namespace reference
- 1.3.1.2.4 Add standard Kubernetes labels
- 1.3.1.2.5 Validate: `kubectl apply --dry-run=client -f serviceaccount.yaml`

##### 1.3.1.3 ConfigMap Configuration
- 1.3.1.3.1 Create `deploy/kubernetes/base/configmap.yaml`
- 1.3.1.3.2 Add service configuration (port, environment, log level)
- 1.3.1.3.3 Add service discovery URLs per INTEGRATION_MAP.md
- 1.3.1.3.4 Add Redis URL configuration
- 1.3.1.3.5 Add provider configuration (default provider, model)
- 1.3.1.3.6 Add rate limiting and session configuration
- 1.3.1.3.7 Validate: `kubectl apply --dry-run=client -f configmap.yaml`

##### 1.3.1.4 Secret Template
- 1.3.1.4.1 Create `deploy/kubernetes/base/secret.yaml` (template only)
- 1.3.1.4.2 Add placeholder for `LLM_GATEWAY_ANTHROPIC_API_KEY`
- 1.3.1.4.3 Add placeholder for `LLM_GATEWAY_OPENAI_API_KEY`
- 1.3.1.4.4 Add comment: "DO NOT commit actual values"
- 1.3.1.4.5 Document external-secrets/sealed-secrets integration
- 1.3.1.4.6 Validate structure (not values)

##### 1.3.1.5 Deployment Configuration
- 1.3.1.5.1 Create `deploy/kubernetes/base/deployment.yaml`
- 1.3.1.5.2 Configure metadata (name, namespace, labels)
- 1.3.1.5.3 Set replicas to 2, rolling update strategy
- 1.3.1.5.4 Add pod template with security context (runAsNonRoot, UID 1000)
- 1.3.1.5.5 Configure container spec (image, ports, envFrom)
- 1.3.1.5.6 Add resource requests/limits (250m/1000m CPU, 512Mi/2Gi memory)
- 1.3.1.5.7 Add liveness probe (/health, 30s interval)
- 1.3.1.5.8 Add readiness probe (/health/ready, 10s interval)
- 1.3.1.5.9 Add container security context (no privilege escalation, read-only FS)
- 1.3.1.5.10 Add volume mounts for tmp and cache
- 1.3.1.5.11 Add pod anti-affinity for HA
- 1.3.1.5.12 Add topology spread constraints
- 1.3.1.5.13 Validate: `kubectl apply --dry-run=client -f deployment.yaml`

##### 1.3.1.6 Service Configuration
- 1.3.1.6.1 Create `deploy/kubernetes/base/service.yaml`
- 1.3.1.6.2 Set type to ClusterIP
- 1.3.1.6.3 Configure port 8080 targeting container port
- 1.3.1.6.4 Add selector matching deployment labels
- 1.3.1.6.5 Validate: `kubectl apply --dry-run=client -f service.yaml`

##### 1.3.1.7 HorizontalPodAutoscaler Configuration
- 1.3.1.7.1 Create `deploy/kubernetes/base/hpa.yaml`
- 1.3.1.7.2 Reference deployment as scale target
- 1.3.1.7.3 Set minReplicas=2, maxReplicas=10
- 1.3.1.7.4 Add CPU metric (70% utilization target)
- 1.3.1.7.5 Add memory metric (80% utilization target)
- 1.3.1.7.6 Configure scale down behavior (300s stabilization)
- 1.3.1.7.7 Configure scale up behavior (0s stabilization, aggressive)
- 1.3.1.7.8 Validate: `kubectl apply --dry-run=client -f hpa.yaml`

##### 1.3.1.8 PodDisruptionBudget Configuration
- 1.3.1.8.1 Create `deploy/kubernetes/base/pdb.yaml`
- 1.3.1.8.2 Set minAvailable to 1
- 1.3.1.8.3 Add selector matching deployment labels
- 1.3.1.8.4 Validate: `kubectl apply --dry-run=client -f pdb.yaml`

##### 1.3.1.9 NetworkPolicy Configuration
- 1.3.1.9.1 Create `deploy/kubernetes/base/networkpolicy.yaml`
- 1.3.1.9.2 Add default-deny-all policy for namespace
- 1.3.1.9.3 Add llm-gateway-policy with ingress rules
- 1.3.1.9.4 Allow ingress from ingress-nginx namespace
- 1.3.1.9.5 Allow ingress from doc-enhancer pods
- 1.3.1.9.6 Allow ingress from ai-agents pods
- 1.3.1.9.7 Allow ingress from monitoring namespace (Prometheus)
- 1.3.1.9.8 Add egress rules for semantic-search (port 8081)
- 1.3.1.9.9 Add egress rules for ai-agents (port 8082)
- 1.3.1.9.10 Add egress rules for Redis (port 6379)
- 1.3.1.9.11 Add egress rules for DNS (UDP 53)
- 1.3.1.9.12 Add egress rules for external HTTPS (Anthropic, OpenAI)
- 1.3.1.9.13 Validate: `kubectl apply --dry-run=client -f networkpolicy.yaml`

##### 1.3.1.10 Kustomization File
- 1.3.1.10.1 Create `deploy/kubernetes/base/kustomization.yaml`
- 1.3.1.10.2 Set namespace to `llm-services`
- 1.3.1.10.3 List all resources in correct order
- 1.3.1.10.4 Add commonLabels for management
- 1.3.1.10.5 Add images section with placeholder tag
- 1.3.1.10.6 Validate: `kubectl kustomize deploy/kubernetes/base`

#### 1.3.2 Kustomize Overlay: Dev

##### 1.3.2.1 Dev Overlay Setup
- 1.3.2.1.1 Create `deploy/kubernetes/overlays/dev/kustomization.yaml`
- 1.3.2.1.2 Reference base with relative path
- 1.3.2.1.3 Set namespace suffix or prefix for dev
- 1.3.2.1.4 Add dev-specific labels

##### 1.3.2.2 Dev Resource Patches
- 1.3.2.2.1 Create `deploy/kubernetes/overlays/dev/replica-patch.yaml`
- 1.3.2.2.2 Set replicas to 1 for dev
- 1.3.2.2.3 Create `deploy/kubernetes/overlays/dev/resource-patch.yaml`
- 1.3.2.2.4 Reduce CPU/memory limits for dev
- 1.3.2.2.5 Add patches to kustomization.yaml
- 1.3.2.2.6 Validate: `kubectl kustomize deploy/kubernetes/overlays/dev`

#### 1.3.3 Kustomize Overlay: Staging

##### 1.3.3.1 Staging Overlay Setup
- 1.3.3.1.1 Create `deploy/kubernetes/overlays/staging/kustomization.yaml`
- 1.3.3.1.2 Reference base with relative path
- 1.3.3.1.3 Create `deploy/kubernetes/overlays/staging/replica-patch.yaml` (2 replicas)
- 1.3.3.1.4 Create `deploy/kubernetes/overlays/staging/ingress.yaml` for staging domain
- 1.3.3.1.5 Add patches and resources to kustomization
- 1.3.3.1.6 Validate: `kubectl kustomize deploy/kubernetes/overlays/staging`

#### 1.3.4 Kustomize Overlay: Prod

##### 1.3.4.1 Prod Overlay Setup
- 1.3.4.1.1 Create `deploy/kubernetes/overlays/prod/kustomization.yaml`
- 1.3.4.1.2 Reference base with relative path
- 1.3.4.1.3 Create `deploy/kubernetes/overlays/prod/replica-patch.yaml` (3 replicas)
- 1.3.4.1.4 Create `deploy/kubernetes/overlays/prod/resource-patch.yaml` (higher limits)
- 1.3.4.1.5 Create `deploy/kubernetes/overlays/prod/hpa-patch.yaml` (higher max replicas)
- 1.3.4.1.6 Create `deploy/kubernetes/overlays/prod/ingress.yaml` for prod domain with TLS
- 1.3.4.1.7 Add all patches and resources to kustomization
- 1.3.4.1.8 Validate: `kubectl kustomize deploy/kubernetes/overlays/prod`

#### 1.3.5 Kubernetes Manifest Validation

##### 1.3.5.1 Static Validation
- 1.3.5.1.1 Install `kubeconform` or `kubeval` tool
- 1.3.5.1.2 Validate base: `kubeconform deploy/kubernetes/base/*.yaml`
- 1.3.5.1.3 Validate dev overlay output
- 1.3.5.1.4 Validate staging overlay output
- 1.3.5.1.5 Validate prod overlay output
- 1.3.5.1.6 Document any validation warnings/errors

---

### 1.4 Helm Chart Scaffolding

> **Acceptance Criteria**: `helm lint deploy/helm/llm-gateway` passes with 0 errors. `helm template llm-gateway deploy/helm/llm-gateway` produces valid YAML. `helm template` with each values file (dev, staging, prod) produces correct environment-specific configuration.

#### 1.4.1 Helm Chart Structure

##### 1.4.1.1 Chart Metadata
- 1.4.1.1.1 Create `deploy/helm/llm-gateway/Chart.yaml`
- 1.4.1.1.2 Set apiVersion to v2
- 1.4.1.1.3 Set name, description, type (application)
- 1.4.1.1.4 Set version (0.1.0) and appVersion (1.0.0)
- 1.4.1.1.5 Add keywords, home, sources
- 1.4.1.1.6 Add maintainers section
- 1.4.1.1.7 Add Redis dependency (conditional)
- 1.4.1.1.8 Validate: `helm lint deploy/helm/llm-gateway`

##### 1.4.1.2 Default Values
- 1.4.1.2.1 Create `deploy/helm/llm-gateway/values.yaml`
- 1.4.1.2.2 Add image configuration (repository, pullPolicy, tag)
- 1.4.1.2.3 Add replicaCount default (2)
- 1.4.1.2.4 Add serviceAccount configuration
- 1.4.1.2.5 Add podAnnotations (Prometheus scrape)
- 1.4.1.2.6 Add security contexts (pod and container)
- 1.4.1.2.7 Add service configuration (type, port)
- 1.4.1.2.8 Add ingress configuration (disabled by default)
- 1.4.1.2.9 Add resources (requests/limits)
- 1.4.1.2.10 Add autoscaling configuration
- 1.4.1.2.11 Add application config section
- 1.4.1.2.12 Add secrets placeholders
- 1.4.1.2.13 Add networkPolicy configuration
- 1.4.1.2.14 Add Redis subchart configuration

##### 1.4.1.3 Environment-Specific Values
- 1.4.1.3.1 Create `deploy/helm/llm-gateway/values-dev.yaml`
- 1.4.1.3.2 Set dev-specific replicas (1), resources (low)
- 1.4.1.3.3 Create `deploy/helm/llm-gateway/values-staging.yaml`
- 1.4.1.3.4 Set staging ingress with staging domain
- 1.4.1.3.5 Create `deploy/helm/llm-gateway/values-prod.yaml`
- 1.4.1.3.6 Set prod replicas (3), resources (high), autoscaling (aggressive)
- 1.4.1.3.7 Set prod ingress with TLS configuration
- 1.4.1.3.8 Set prod Redis replication mode

#### 1.4.2 Helm Templates

##### 1.4.2.1 Helper Templates
- 1.4.2.1.1 Create `deploy/helm/llm-gateway/templates/_helpers.tpl`
- 1.4.2.1.2 Add `llm-gateway.name` helper
- 1.4.2.1.3 Add `llm-gateway.fullname` helper
- 1.4.2.1.4 Add `llm-gateway.chart` helper
- 1.4.2.1.5 Add `llm-gateway.labels` helper
- 1.4.2.1.6 Add `llm-gateway.selectorLabels` helper
- 1.4.2.1.7 Add `llm-gateway.serviceAccountName` helper

##### 1.4.2.2 Core Templates
- 1.4.2.2.1 Create `deploy/helm/llm-gateway/templates/deployment.yaml`
- 1.4.2.2.2 Use helpers for labels and selectors
- 1.4.2.2.3 Template replicas, image, resources from values
- 1.4.2.2.4 Template security contexts from values
- 1.4.2.2.5 Template probes from values
- 1.4.2.2.6 Create `deploy/helm/llm-gateway/templates/service.yaml`
- 1.4.2.2.7 Create `deploy/helm/llm-gateway/templates/serviceaccount.yaml`
- 1.4.2.2.8 Add conditional creation based on values

##### 1.4.2.3 Configuration Templates
- 1.4.2.3.1 Create `deploy/helm/llm-gateway/templates/configmap.yaml`
- 1.4.2.3.2 Template all config values from `.Values.config`
- 1.4.2.3.3 Create `deploy/helm/llm-gateway/templates/secret.yaml`
- 1.4.2.3.4 Template secrets with base64 encoding
- 1.4.2.3.5 Add conditional creation for external secrets

##### 1.4.2.4 Scaling Templates
- 1.4.2.4.1 Create `deploy/helm/llm-gateway/templates/hpa.yaml`
- 1.4.2.4.2 Add conditional based on `.Values.autoscaling.enabled`
- 1.4.2.4.3 Template min/max replicas, metrics
- 1.4.2.4.4 Create `deploy/helm/llm-gateway/templates/pdb.yaml`
- 1.4.2.4.5 Add conditional based on `.Values.podDisruptionBudget.enabled`

##### 1.4.2.5 Network Templates
- 1.4.2.5.1 Create `deploy/helm/llm-gateway/templates/ingress.yaml`
- 1.4.2.5.2 Add conditional based on `.Values.ingress.enabled`
- 1.4.2.5.3 Template hosts, paths, TLS from values
- 1.4.2.5.4 Create `deploy/helm/llm-gateway/templates/networkpolicy.yaml`
- 1.4.2.5.5 Add conditional based on `.Values.networkPolicy.enabled`
- 1.4.2.5.6 Template ingress/egress rules from values

#### 1.4.3 Helm Chart Validation

##### 1.4.3.1 Lint and Template Tests
- 1.4.3.1.1 Run `helm lint deploy/helm/llm-gateway`
- 1.4.3.1.2 Fix any linting errors
- 1.4.3.1.3 Run `helm template llm-gateway deploy/helm/llm-gateway`
- 1.4.3.1.4 Run `helm template` with `values-dev.yaml`
- 1.4.3.1.5 Run `helm template` with `values-staging.yaml`
- 1.4.3.1.6 Run `helm template` with `values-prod.yaml`
- 1.4.3.1.7 Verify all templates render correctly
- 1.4.3.1.8 Pipe template output through `kubeconform` for validation

---

### 1.5 CI/CD Pipeline Scaffolding

> **Acceptance Criteria**: All GitHub Actions workflow files pass YAML validation. Workflows can be triggered manually (workflow_dispatch). CI workflow runs lint, test, security, and build jobs successfully on push to develop branch.

#### 1.5.1 Continuous Integration Workflow

##### 1.5.1.1 CI Workflow Structure
- 1.5.1.1.1 Create `.github/workflows/ci.yml`
- 1.5.1.1.2 Configure triggers (push to main/develop, pull_request to main)
- 1.5.1.1.3 Define environment variables (REGISTRY, IMAGE_NAME)
- 1.5.1.1.4 Define job dependencies (build needs lint, test, security)

##### 1.5.1.2 Lint Job
- 1.5.1.2.1 Add lint job with ubuntu-latest runner
- 1.5.1.2.2 Add checkout step
- 1.5.1.2.3 Add Python setup step (3.11)
- 1.5.1.2.4 Add dependency installation (ruff, mypy)
- 1.5.1.2.5 Add Ruff check step
- 1.5.1.2.6 Add Ruff format check step
- 1.5.1.2.7 Add MyPy type checking step

##### 1.5.1.3 Test Job
- 1.5.1.3.1 Add test job with ubuntu-latest runner
- 1.5.1.3.2 Add Redis service container
- 1.5.1.3.3 Add checkout and Python setup steps
- 1.5.1.3.4 Add dependency installation (requirements + dev)
- 1.5.1.3.5 Add unit test step with coverage
- 1.5.1.3.6 Add integration test step
- 1.5.1.3.7 Add coverage upload step (Codecov)

##### 1.5.1.4 Security Job
- 1.5.1.4.1 Add security job with ubuntu-latest runner
- 1.5.1.4.2 Add checkout step
- 1.5.1.4.3 Add Trivy vulnerability scanner step
- 1.5.1.4.4 Configure severity threshold (CRITICAL, HIGH)
- 1.5.1.4.5 Add SARIF output for GitHub Security tab (optional)

##### 1.5.1.5 Build Job
- 1.5.1.5.1 Add build job with dependencies on lint, test, security
- 1.5.1.5.2 Configure permissions (contents: read, packages: write)
- 1.5.1.5.3 Add Docker Buildx setup step
- 1.5.1.5.4 Add container registry login step
- 1.5.1.5.5 Add metadata extraction step (tags, labels)
- 1.5.1.5.6 Add build and push step
- 1.5.1.5.7 Configure multi-platform build (amd64, arm64)
- 1.5.1.5.8 Configure build caching (GitHub Actions cache)

#### 1.5.2 Continuous Deployment Workflows

##### 1.5.2.1 Dev Deployment Workflow
- 1.5.2.1.1 Create `.github/workflows/cd-dev.yml`
- 1.5.2.1.2 Configure trigger (push to develop)
- 1.5.2.1.3 Define environment (development)
- 1.5.2.1.4 Add checkout step
- 1.5.2.1.5 Add kubectl setup step
- 1.5.2.1.6 Add kubeconfig configuration step (from secret)
- 1.5.2.1.7 Add Kustomize deploy step
- 1.5.2.1.8 Add rollout status verification step
- 1.5.2.1.9 Add smoke test step

##### 1.5.2.2 Staging Deployment Workflow
- 1.5.2.2.1 Create `.github/workflows/cd-staging.yml`
- 1.5.2.2.2 Configure trigger (push to main)
- 1.5.2.2.3 Define environment (staging) with protection rules
- 1.5.2.2.4 Add deployment steps (similar to dev)
- 1.5.2.2.5 Add integration test step post-deployment
- 1.5.2.2.6 Add notification step (Slack/email)

##### 1.5.2.3 Production Deployment Workflow
- 1.5.2.3.1 Create `.github/workflows/cd-prod.yml`
- 1.5.2.3.2 Configure triggers (release published, workflow_dispatch)
- 1.5.2.3.3 Define environment (production) with approval requirement
- 1.5.2.3.4 Add version extraction step
- 1.5.2.3.5 Add Helm setup step
- 1.5.2.3.6 Add kubeconfig configuration step
- 1.5.2.3.7 Add Helm deploy step with values-prod.yaml
- 1.5.2.3.8 Add rollout status verification step
- 1.5.2.3.9 Add success/failure notification steps

#### 1.5.3 Workflow Validation

##### 1.5.3.1 Workflow Testing
- 1.5.3.1.1 Validate YAML syntax for all workflow files
- 1.5.3.1.2 Use `actionlint` to validate GitHub Actions syntax
- 1.5.3.1.3 Commit workflows to feature branch
- 1.5.3.1.4 Trigger CI workflow via push
- 1.5.3.1.5 Verify all jobs pass
- 1.5.3.1.6 Test workflow_dispatch trigger manually
- 1.5.3.1.7 Document required repository secrets

---

### 1.6 Requirements and Dependencies

> **Acceptance Criteria**: `requirements.txt` and `requirements-dev.txt` are complete and installable. `pip install -r requirements.txt -r requirements-dev.txt` succeeds. All linting tools run without import errors.

#### 1.6.1 Production Requirements

##### 1.6.1.1 Core Dependencies
- 1.6.1.1.1 Add FastAPI with version pin
- 1.6.1.1.2 Add Uvicorn with standard extras
- 1.6.1.1.3 Add Pydantic with version >= 2.0
- 1.6.1.1.4 Add httpx for async HTTP client
- 1.6.1.1.5 Add redis for session storage
- 1.6.1.1.6 Add anthropic SDK
- 1.6.1.1.7 Add openai SDK

##### 1.6.1.2 Observability Dependencies
- 1.6.1.2.1 Add structlog for structured logging
- 1.6.1.2.2 Add prometheus-client for metrics
- 1.6.1.2.3 Add opentelemetry-api
- 1.6.1.2.4 Add opentelemetry-sdk
- 1.6.1.2.5 Add opentelemetry-instrumentation-fastapi

#### 1.6.2 Development Requirements

##### 1.6.2.1 Testing Dependencies
- 1.6.2.1.1 Create `requirements-dev.txt`
- 1.6.2.1.2 Add pytest with version pin
- 1.6.2.1.3 Add pytest-asyncio for async tests
- 1.6.2.1.4 Add pytest-cov for coverage
- 1.6.2.1.5 Add httpx for test client
- 1.6.2.1.6 Add fakeredis for Redis mocking

##### 1.6.2.2 Linting Dependencies
- 1.6.2.2.1 Add ruff for linting and formatting
- 1.6.2.2.2 Add mypy for type checking
- 1.6.2.2.3 Add types-redis for Redis type stubs
- 1.6.2.2.4 Add pre-commit for git hooks

#### 1.6.3 Dependency Validation

##### 1.6.3.1 Installation Testing
- 1.6.3.1.1 Create fresh virtual environment
- 1.6.3.1.2 Install production requirements
- 1.6.3.1.3 Install development requirements
- 1.6.3.1.4 Verify no version conflicts
- 1.6.3.1.5 Run `pip check` for dependency issues
- 1.6.3.1.6 Generate `requirements.lock` (optional)

---

### 1.7 Stage 1 Validation and Sign-off

> **Acceptance Criteria**: All Stage 1 tasks completed. All validation commands pass. Documentation updated. Ready for Stage 2 (Implementation).

#### 1.7.1 Final Validation Checklist

##### 1.7.1.1 Docker Validation
- 1.7.1.1.1 `docker build -t llm-gateway .` exits 0
- 1.7.1.1.2 `docker run --rm llm-gateway whoami` returns `appuser`
- 1.7.1.1.3 `docker-compose up -d` starts all services
- 1.7.1.1.4 `curl http://localhost:8080/health` returns 200
- 1.7.1.1.5 `docker-compose down` exits cleanly
- 1.7.1.1.6 Image size < 500MB verified

##### 1.7.1.2 Kubernetes Validation
- 1.7.1.2.1 `kubectl kustomize deploy/kubernetes/base` produces valid YAML
- 1.7.1.2.2 `kubectl kustomize deploy/kubernetes/overlays/dev` valid
- 1.7.1.2.3 `kubectl kustomize deploy/kubernetes/overlays/staging` valid
- 1.7.1.2.4 `kubectl kustomize deploy/kubernetes/overlays/prod` valid
- 1.7.1.2.5 All manifests pass `kubeconform` validation

##### 1.7.1.3 Helm Validation
- 1.7.1.3.1 `helm lint deploy/helm/llm-gateway` passes
- 1.7.1.3.2 `helm template llm-gateway deploy/helm/llm-gateway` valid
- 1.7.1.3.3 Template with values-dev.yaml renders correctly
- 1.7.1.3.4 Template with values-staging.yaml renders correctly
- 1.7.1.3.5 Template with values-prod.yaml renders correctly

##### 1.7.1.4 CI/CD Validation
- 1.7.1.4.1 All workflow files pass YAML lint
- 1.7.1.4.2 All workflow files pass `actionlint`
- 1.7.1.4.3 CI workflow triggers and passes on push
- 1.7.1.4.4 Required secrets documented

##### 1.7.1.5 Documentation
- 1.7.1.5.1 Update README.md with local development instructions
- 1.7.1.5.2 Update ARCHITECTURE.md if structure changed
- 1.7.1.5.3 Create CONTRIBUTING.md with setup instructions
- 1.7.1.5.4 Document all environment variables
- 1.7.1.5.5 Document all required secrets

---

## Stage 2: Implementation

> **Stage 2 Acceptance Criteria**: All core application modules implemented per ARCHITECTURE.md. All unit tests pass with ≥80% coverage. All integration tests pass. API endpoints respond correctly. Provider routing functional with Anthropic/OpenAI/Ollama. Session management operational with Redis. Tool execution framework complete.

---

### 2.1 Core Application Structure

> **Acceptance Criteria**: `src/` directory structure matches ARCHITECTURE.md. All `__init__.py` files export public interfaces. `python -c "from src.main import app"` succeeds without errors.

#### 2.1.1 Application Entry Point

##### 2.1.1.1 FastAPI Application Setup
- 2.1.1.1.1 Create `src/main.py` with FastAPI app instantiation
- 2.1.1.1.2 Configure app metadata (title, description, version)
- 2.1.1.1.3 Add lifespan context manager for startup/shutdown
- 2.1.1.1.4 Import and include all routers
- 2.1.1.1.5 Add middleware registration
- 2.1.1.1.6 Add exception handlers
- 2.1.1.1.7 Write RED test: app instantiates without error
- 2.1.1.1.8 GREEN: verify test passes
- 2.1.1.1.9 REFACTOR: ensure clean imports

##### 2.1.1.2 Application Lifespan Events
- 2.1.1.2.1 Implement startup event handler
- 2.1.1.2.2 Initialize Redis connection pool on startup
- 2.1.1.2.3 Initialize provider clients on startup
- 2.1.1.2.4 Implement shutdown event handler
- 2.1.1.2.5 Close Redis connections on shutdown
- 2.1.1.2.6 Close HTTP clients on shutdown
- 2.1.1.2.7 Write RED test: startup initializes dependencies
- 2.1.1.2.8 Write RED test: shutdown cleans up resources
- 2.1.1.2.9 GREEN: implement and pass tests

#### 2.1.2 Core Configuration Module

##### 2.1.2.1 Settings Class Implementation
- 2.1.2.1.1 Create `src/core/__init__.py`
- 2.1.2.1.2 Create `src/core/config.py`
- 2.1.2.1.3 Implement `Settings` class extending `BaseSettings`
- 2.1.2.1.4 Add service configuration (name, port, environment)
- 2.1.2.1.5 Add Redis configuration (url, pool_size)
- 2.1.2.1.6 Add microservice URLs per INTEGRATION_MAP.md
- 2.1.2.1.7 Add provider API keys (anthropic, openai)
- 2.1.2.1.8 Add provider defaults (default_provider, default_model)
- 2.1.2.1.9 Add rate limiting configuration
- 2.1.2.1.10 Add session configuration (TTL)
- 2.1.2.1.11 Configure `env_prefix = "LLM_GATEWAY_"`
- 2.1.2.1.12 Write RED test: settings loads from environment
- 2.1.2.1.13 Write RED test: settings validates required fields
- 2.1.2.1.14 GREEN: implement and pass tests
- 2.1.2.1.15 REFACTOR: add field validators where needed

##### 2.1.2.2 Settings Singleton
- 2.1.2.2.1 Implement `get_settings()` function with caching
- 2.1.2.2.2 Add `@lru_cache` decorator for singleton pattern
- 2.1.2.2.3 Write RED test: get_settings returns same instance
- 2.1.2.2.4 GREEN: verify singleton behavior
- 2.1.2.2.5 Export from `src/core/__init__.py`

##### 2.1.2.3 Custom Exceptions
- 2.1.2.3.1 Create `src/core/exceptions.py`
- 2.1.2.3.2 Implement `LLMGatewayException` base class
- 2.1.2.3.3 Implement `ProviderError` for LLM provider issues
- 2.1.2.3.4 Implement `SessionError` for session management issues
- 2.1.2.3.5 Implement `ToolExecutionError` for tool failures
- 2.1.2.3.6 Implement `RateLimitError` for rate limiting
- 2.1.2.3.7 Implement `ValidationError` for request validation
- 2.1.2.3.8 Add error codes enum
- 2.1.2.3.9 Write RED tests for each exception type
- 2.1.2.3.10 GREEN: implement and pass tests

---

### 2.2 API Layer Implementation

> **Acceptance Criteria**: All endpoints defined in ARCHITECTURE.md respond correctly. OpenAPI schema generated. Request validation works. Error responses follow consistent format. Health endpoints return correct status.

#### 2.2.1 Health Endpoints

##### 2.2.1.1 Health Router Setup
- 2.2.1.1.1 Create `src/api/__init__.py`
- 2.2.1.1.2 Create `src/api/routes/__init__.py`
- 2.2.1.1.3 Create `src/api/routes/health.py`
- 2.2.1.1.4 Create FastAPI router instance
- 2.2.1.1.5 Implement `GET /health` endpoint
- 2.2.1.1.6 Return `{"status": "healthy", "version": "1.0.0"}`
- 2.2.1.1.7 Write RED test: /health returns 200
- 2.2.1.1.8 GREEN: implement and pass test

##### 2.2.1.2 Readiness Endpoint
- 2.2.1.2.1 Implement `GET /health/ready` endpoint
- 2.2.1.2.2 Check Redis connectivity
- 2.2.1.2.3 Check provider availability (optional)
- 2.2.1.2.4 Return `{"status": "ready"}` if all checks pass
- 2.2.1.2.5 Return 503 if dependencies unavailable
- 2.2.1.2.6 Write RED test: /health/ready returns 200 when Redis up
- 2.2.1.2.7 Write RED test: /health/ready returns 503 when Redis down
- 2.2.1.2.8 GREEN: implement and pass tests
- 2.2.1.2.9 REFACTOR: extract dependency checks to separate functions

##### 2.2.1.3 Metrics Endpoint
- 2.2.1.3.1 Implement `GET /metrics` endpoint
- 2.2.1.3.2 Expose Prometheus metrics format
- 2.2.1.3.3 Include request count, latency, error rate
- 2.2.1.3.4 Include provider-specific metrics
- 2.2.1.3.5 Write RED test: /metrics returns valid Prometheus format
- 2.2.1.3.6 GREEN: implement and pass test

#### 2.2.2 Chat Completions Endpoint

##### 2.2.2.1 Chat Router Setup
- 2.2.2.1.1 Create `src/api/routes/chat.py`
- 2.2.2.1.2 Create FastAPI router instance
- 2.2.2.1.3 Define route prefix `/v1/chat`

##### 2.2.2.2 Request/Response Models
- 2.2.2.2.1 Create `src/models/__init__.py`
- 2.2.2.2.2 Create `src/models/requests.py`
- 2.2.2.2.3 Implement `ChatCompletionRequest` Pydantic model
- 2.2.2.2.4 Add `model` field with validation
- 2.2.2.2.5 Add `messages` field (list of Message)
- 2.2.2.2.6 Add `tools` field (optional list of Tool)
- 2.2.2.2.7 Add `tool_choice` field (optional)
- 2.2.2.2.8 Add `temperature`, `max_tokens` fields
- 2.2.2.2.9 Add `session_id` field (optional)
- 2.2.2.2.10 Create `src/models/responses.py`
- 2.2.2.2.11 Implement `ChatCompletionResponse` model
- 2.2.2.2.12 Add `id`, `choices`, `usage` fields
- 2.2.2.2.13 Implement `Choice` model with `message`, `finish_reason`
- 2.2.2.2.14 Implement `Usage` model with token counts
- 2.2.2.2.15 Write RED tests for request validation
- 2.2.2.2.16 Write RED tests for response serialization
- 2.2.2.2.17 GREEN: implement and pass tests

##### 2.2.2.3 Chat Completions Handler
- 2.2.2.3.1 Implement `POST /v1/chat/completions` endpoint
- 2.2.2.3.2 Inject dependencies (settings, chat_service)
- 2.2.2.3.3 Validate request body
- 2.2.2.3.4 Call chat service for completion
- 2.2.2.3.5 Handle tool calls if present in response
- 2.2.2.3.6 Return ChatCompletionResponse
- 2.2.2.3.7 Write RED test: completion returns valid response
- 2.2.2.3.8 Write RED test: invalid request returns 422
- 2.2.2.3.9 Write RED test: provider error returns 502
- 2.2.2.3.10 GREEN: implement and pass tests
- 2.2.2.3.11 REFACTOR: extract business logic to service layer

#### 2.2.3 Sessions Endpoints

##### 2.2.3.1 Sessions Router Setup
- 2.2.3.1.1 Create `src/api/routes/sessions.py`
- 2.2.3.1.2 Create FastAPI router with prefix `/v1/sessions`

##### 2.2.3.2 Session Models
- 2.2.3.2.1 Add `SessionCreateRequest` model to requests.py
- 2.2.3.2.2 Add `SessionResponse` model to responses.py
- 2.2.3.2.3 Include `id`, `messages`, `context`, `created_at`, `expires_at`
- 2.2.3.2.4 Write RED tests for session models
- 2.2.3.2.5 GREEN: implement and pass tests

##### 2.2.3.3 Session CRUD Endpoints
- 2.2.3.3.1 Implement `POST /v1/sessions` - create session
- 2.2.3.3.2 Implement `GET /v1/sessions/{id}` - get session
- 2.2.3.3.3 Implement `DELETE /v1/sessions/{id}` - delete session
- 2.2.3.3.4 Implement `PUT /v1/sessions/{id}` - update session (optional)
- 2.2.3.3.5 Write RED test: create session returns 201 with id
- 2.2.3.3.6 Write RED test: get session returns session data
- 2.2.3.3.7 Write RED test: get nonexistent session returns 404
- 2.2.3.3.8 Write RED test: delete session returns 204
- 2.2.3.3.9 GREEN: implement and pass all tests
- 2.2.3.3.10 REFACTOR: ensure proper error handling

#### 2.2.4 Tools Endpoints

##### 2.2.4.1 Tools Router Setup
- 2.2.4.1.1 Create `src/api/routes/tools.py`
- 2.2.4.1.2 Create FastAPI router with prefix `/v1/tools`

##### 2.2.4.2 Tool Models
- 2.2.4.2.1 Add `ToolExecuteRequest` model
- 2.2.4.2.2 Add `ToolExecuteResponse` model
- 2.2.4.2.3 Add `ToolDefinition` model for registry
- 2.2.4.2.4 Write RED tests for tool models
- 2.2.4.2.5 GREEN: implement and pass tests

##### 2.2.4.3 Tool Execution Endpoint
- 2.2.4.3.1 Implement `POST /v1/tools/execute` endpoint
- 2.2.4.3.2 Validate tool name exists in registry
- 2.2.4.3.3 Validate tool arguments against schema
- 2.2.4.3.4 Execute tool via executor service
- 2.2.4.3.5 Return tool result or error
- 2.2.4.3.6 Write RED test: execute valid tool returns result
- 2.2.4.3.7 Write RED test: execute unknown tool returns 404
- 2.2.4.3.8 Write RED test: invalid arguments returns 422
- 2.2.4.3.9 GREEN: implement and pass tests

##### 2.2.4.4 Tool Listing Endpoint
- 2.2.4.4.1 Implement `GET /v1/tools` - list available tools
- 2.2.4.4.2 Return tool definitions with schemas
- 2.2.4.4.3 Write RED test: list tools returns all registered tools
- 2.2.4.4.4 GREEN: implement and pass test

#### 2.2.5 API Middleware

##### 2.2.5.1 Request Logging Middleware
- 2.2.5.1.1 Create `src/api/middleware/__init__.py`
- 2.2.5.1.2 Create `src/api/middleware/logging.py`
- 2.2.5.1.3 Implement request/response logging middleware
- 2.2.5.1.4 Log request method, path, duration
- 2.2.5.1.5 Log response status code
- 2.2.5.1.6 Redact sensitive headers (Authorization, API keys)
- 2.2.5.1.7 Write RED test: middleware logs requests
- 2.2.5.1.8 GREEN: implement and pass test

##### 2.2.5.2 Rate Limiting Middleware
- 2.2.5.2.1 Create `src/api/middleware/rate_limit.py`
- 2.2.5.2.2 Implement token bucket or sliding window algorithm
- 2.2.5.2.3 Use Redis for distributed rate limiting
- 2.2.5.2.4 Configure limits from settings
- 2.2.5.2.5 Return 429 when limit exceeded
- 2.2.5.2.6 Add `X-RateLimit-*` headers to responses
- 2.2.5.2.7 Write RED test: requests within limit succeed
- 2.2.5.2.8 Write RED test: requests exceeding limit return 429
- 2.2.5.2.9 GREEN: implement and pass tests
- 2.2.5.2.10 REFACTOR: make algorithm configurable

##### 2.2.5.3 Authentication Middleware (Optional)
- 2.2.5.3.1 Create `src/api/middleware/auth.py`
- 2.2.5.3.2 Implement API key validation
- 2.2.5.3.3 Check `X-API-Key` or `Authorization` header
- 2.2.5.3.4 Return 401 if missing or invalid
- 2.2.5.3.5 Write RED tests for auth scenarios
- 2.2.5.3.6 GREEN: implement and pass tests

#### 2.2.6 API Dependencies

##### 2.2.6.1 Dependency Injection Setup
- 2.2.6.1.1 Create `src/api/deps.py`
- 2.2.6.1.2 Implement `get_settings` dependency
- 2.2.6.1.3 Implement `get_redis` dependency
- 2.2.6.1.4 Implement `get_chat_service` dependency
- 2.2.6.1.5 Implement `get_session_manager` dependency
- 2.2.6.1.6 Implement `get_tool_executor` dependency
- 2.2.6.1.7 Write RED tests for dependency injection
- 2.2.6.1.8 GREEN: implement and pass tests

---

### 2.3 Provider Layer Implementation

> **Acceptance Criteria**: Provider abstraction allows swapping providers without code changes. Anthropic, OpenAI, and Ollama adapters functional. Provider router correctly routes based on model name. All provider tests pass with mocked API responses.

#### 2.3.1 Provider Base Interface

##### 2.3.1.1 Abstract Provider Class
- 2.3.1.1.1 Create `src/providers/__init__.py`
- 2.3.1.1.2 Create `src/providers/base.py`
- 2.3.1.1.3 Define `LLMProvider` abstract base class
- 2.3.1.1.4 Define `async def complete(request: ChatCompletionRequest) -> ChatCompletionResponse`
- 2.3.1.1.5 Define `async def stream(request: ChatCompletionRequest) -> AsyncIterator`
- 2.3.1.1.6 Define `def supports_model(model: str) -> bool`
- 2.3.1.1.7 Define `def get_supported_models() -> list[str]`
- 2.3.1.1.8 Write interface documentation
- 2.3.1.1.9 Write RED test: abstract class cannot be instantiated
- 2.3.1.1.10 GREEN: verify ABC behavior

#### 2.3.2 Anthropic Provider

##### 2.3.2.1 Anthropic Adapter Implementation
- 2.3.2.1.1 Create `src/providers/anthropic.py`
- 2.3.2.1.2 Implement `AnthropicProvider` extending `LLMProvider`
- 2.3.2.1.3 Initialize Anthropic client in constructor
- 2.3.2.1.4 Implement `complete()` method
- 2.3.2.1.5 Transform request to Anthropic format
- 2.3.2.1.6 Call Anthropic API
- 2.3.2.1.7 Transform response to internal format
- 2.3.2.1.8 Handle tool_use in response
- 2.3.2.1.9 Implement `stream()` method
- 2.3.2.1.10 Implement `supports_model()` for claude-* models
- 2.3.2.1.11 Add retry logic with exponential backoff
- 2.3.2.1.12 Write RED test: complete returns valid response (mocked)
- 2.3.2.1.13 Write RED test: handles API errors gracefully
- 2.3.2.1.14 Write RED test: supports_model returns correct values
- 2.3.2.1.15 GREEN: implement and pass all tests
- 2.3.2.1.16 REFACTOR: extract transformation logic

##### 2.3.2.2 Anthropic Tool Handling
- 2.3.2.2.1 Implement tool definition transformation to Anthropic format
- 2.3.2.2.2 Implement tool_use response parsing
- 2.3.2.2.3 Implement tool_result message formatting
- 2.3.2.2.4 Write RED test: tools transformed correctly
- 2.3.2.2.5 Write RED test: tool_use parsed correctly
- 2.3.2.2.6 GREEN: implement and pass tests

#### 2.3.3 OpenAI Provider

##### 2.3.3.1 OpenAI Adapter Implementation
- 2.3.3.1.1 Create `src/providers/openai.py`
- 2.3.3.1.2 Implement `OpenAIProvider` extending `LLMProvider`
- 2.3.3.1.3 Initialize OpenAI client in constructor
- 2.3.3.1.4 Implement `complete()` method
- 2.3.3.1.5 Transform request to OpenAI format
- 2.3.3.1.6 Call OpenAI API
- 2.3.3.1.7 Transform response to internal format
- 2.3.3.1.8 Handle function_call/tool_calls in response
- 2.3.3.1.9 Implement `stream()` method
- 2.3.3.1.10 Implement `supports_model()` for gpt-* models
- 2.3.3.1.11 Add retry logic with exponential backoff
- 2.3.3.1.12 Write RED test: complete returns valid response (mocked)
- 2.3.3.1.13 Write RED test: handles API errors gracefully
- 2.3.3.1.14 GREEN: implement and pass all tests

##### 2.3.3.2 OpenAI Tool Handling
- 2.3.3.2.1 Implement tool definition transformation to OpenAI format
- 2.3.3.2.2 Implement tool_calls response parsing
- 2.3.3.2.3 Implement tool message formatting
- 2.3.3.2.4 Write RED tests for tool handling
- 2.3.3.2.5 GREEN: implement and pass tests

#### 2.3.4 Ollama Provider

##### 2.3.4.1 Ollama Adapter Implementation
- 2.3.4.1.1 Create `src/providers/ollama.py`
- 2.3.4.1.2 Implement `OllamaProvider` extending `LLMProvider`
- 2.3.4.1.3 Initialize HTTP client for Ollama API
- 2.3.4.1.4 Implement `complete()` method
- 2.3.4.1.5 Transform request to Ollama format
- 2.3.4.1.6 Call Ollama API (local endpoint)
- 2.3.4.1.7 Transform response to internal format
- 2.3.4.1.8 Implement `stream()` method
- 2.3.4.1.9 Implement `supports_model()` dynamically from available models
- 2.3.4.1.10 Implement `list_available_models()` method
- 2.3.4.1.11 Write RED test: complete returns valid response (mocked)
- 2.3.4.1.12 Write RED test: handles connection errors gracefully
- 2.3.4.1.13 GREEN: implement and pass all tests

#### 2.3.5 Provider Router

##### 2.3.5.1 Router Implementation
- 2.3.5.1.1 Create `src/providers/router.py`
- 2.3.5.1.2 Implement `ProviderRouter` class
- 2.3.5.1.3 Register providers in constructor
- 2.3.5.1.4 Implement `get_provider(model: str) -> LLMProvider`
- 2.3.5.1.5 Route based on model name prefix (claude-*, gpt-*, etc.)
- 2.3.5.1.6 Fall back to default provider if no match
- 2.3.5.1.7 Implement `list_available_models()` aggregating all providers
- 2.3.5.1.8 Write RED test: router returns correct provider for model
- 2.3.5.1.9 Write RED test: router falls back to default
- 2.3.5.1.10 Write RED test: unknown model raises error
- 2.3.5.1.11 GREEN: implement and pass all tests
- 2.3.5.1.12 REFACTOR: make provider registration configurable

##### 2.3.5.2 Provider Factory
- 2.3.5.2.1 Implement `create_provider_router()` factory function
- 2.3.5.2.2 Initialize providers from settings
- 2.3.5.2.3 Skip providers without API keys configured
- 2.3.5.2.4 Log available providers on startup
- 2.3.5.2.5 Write RED test: factory creates router with configured providers
- 2.3.5.2.6 GREEN: implement and pass test

---

### 2.4 Tool System Implementation

> **Acceptance Criteria**: Tool registry loads tools from configuration. Tools can be executed by name with validated arguments. Built-in tools (semantic_search, chunk_retrieval) proxy to appropriate services. Custom tools can be registered dynamically.

#### 2.4.1 Tool Registry

##### 2.4.1.1 Registry Implementation
- 2.4.1.1.1 Create `src/tools/__init__.py`
- 2.4.1.1.2 Create `src/tools/registry.py`
- 2.4.1.1.3 Implement `ToolRegistry` class
- 2.4.1.1.4 Implement `register(name: str, tool: Tool)` method
- 2.4.1.1.5 Implement `get(name: str) -> Tool` method
- 2.4.1.1.6 Implement `list() -> list[ToolDefinition]` method
- 2.4.1.1.7 Implement `has(name: str) -> bool` method
- 2.4.1.1.8 Load tools from `config/tools.json` on init
- 2.4.1.1.9 Write RED test: register and retrieve tool
- 2.4.1.1.10 Write RED test: get unknown tool raises error
- 2.4.1.1.11 Write RED test: list returns all tools
- 2.4.1.1.12 GREEN: implement and pass all tests

##### 2.4.1.2 Tool Definition Schema
- 2.4.1.2.1 Create `src/models/domain.py`
- 2.4.1.2.2 Implement `Tool` dataclass/Pydantic model
- 2.4.1.2.3 Add `name`, `description`, `parameters` (JSON Schema)
- 2.4.1.2.4 Add `handler` callable reference
- 2.4.1.2.5 Implement `ToolCall` model
- 2.4.1.2.6 Implement `ToolResult` model
- 2.4.1.2.7 Write RED tests for domain models
- 2.4.1.2.8 GREEN: implement and pass tests

#### 2.4.2 Tool Executor

##### 2.4.2.1 Executor Implementation
- 2.4.2.1.1 Create `src/tools/executor.py`
- 2.4.2.1.2 Implement `ToolExecutor` class
- 2.4.2.1.3 Inject `ToolRegistry` dependency
- 2.4.2.1.4 Implement `async execute(tool_call: ToolCall) -> ToolResult`
- 2.4.2.1.5 Validate tool exists in registry
- 2.4.2.1.6 Validate arguments against tool schema
- 2.4.2.1.7 Execute tool handler
- 2.4.2.1.8 Wrap result in ToolResult
- 2.4.2.1.9 Handle execution errors gracefully
- 2.4.2.1.10 Add execution timeout
- 2.4.2.1.11 Write RED test: execute valid tool returns result
- 2.4.2.1.12 Write RED test: execute with invalid args raises error
- 2.4.2.1.13 Write RED test: execution timeout handled
- 2.4.2.1.14 GREEN: implement and pass all tests
- 2.4.2.1.15 REFACTOR: add retry logic for transient failures

##### 2.4.2.2 Batch Execution
- 2.4.2.2.1 Implement `async execute_batch(tool_calls: list[ToolCall]) -> list[ToolResult]`
- 2.4.2.2.2 Execute tools concurrently with asyncio.gather
- 2.4.2.2.3 Preserve order of results
- 2.4.2.2.4 Handle partial failures
- 2.4.2.2.5 Write RED test: batch execution concurrent
- 2.4.2.2.6 Write RED test: batch handles partial failure
- 2.4.2.2.7 GREEN: implement and pass tests

#### 2.4.3 Built-in Tools

##### 2.4.3.1 Semantic Search Tool
- 2.4.3.1.1 Create `src/tools/builtin/__init__.py`
- 2.4.3.1.2 Create `src/tools/builtin/semantic_search.py`
- 2.4.3.1.3 Implement `search_corpus` tool function
- 2.4.3.1.4 Accept `query: str`, `top_k: int`, `collection: str` parameters
- 2.4.3.1.5 Call semantic-search-service `/v1/search` endpoint
- 2.4.3.1.6 Return search results as structured data
- 2.4.3.1.7 Handle service unavailable errors
- 2.4.3.1.8 Write RED test: search returns results (mocked service)
- 2.4.3.1.9 Write RED test: handles service errors
- 2.4.3.1.10 GREEN: implement and pass tests

##### 2.4.3.2 Chunk Retrieval Tool
- 2.4.3.2.1 Create `src/tools/builtin/chunk_retrieval.py`
- 2.4.3.2.2 Implement `get_chunk` tool function
- 2.4.3.2.3 Accept `chunk_id: str` parameter
- 2.4.3.2.4 Call semantic-search-service to retrieve chunk
- 2.4.3.2.5 Return chunk text and metadata
- 2.4.3.2.6 Handle not found errors
- 2.4.3.2.7 Write RED test: retrieval returns chunk
- 2.4.3.2.8 Write RED test: not found returns error
- 2.4.3.2.9 GREEN: implement and pass tests

##### 2.4.3.3 Tool Registration
- 2.4.3.3.1 Create tool definitions in `config/tools.json`
- 2.4.3.3.2 Define `search_corpus` with JSON schema
- 2.4.3.3.3 Define `get_chunk` with JSON schema
- 2.4.3.3.4 Register built-in tools on application startup
- 2.4.3.3.5 Write RED test: built-in tools registered
- 2.4.3.3.6 GREEN: verify registration on startup

---

### 2.5 Session Management Implementation

> **Acceptance Criteria**: Sessions created with unique IDs and TTL. Session data persisted in Redis. Conversation history maintained across requests. Sessions expire after configured TTL. Session retrieval and deletion work correctly.

#### 2.5.1 Session Store

##### 2.5.1.1 Redis Store Implementation
- 2.5.1.1.1 Create `src/sessions/__init__.py`
- 2.5.1.1.2 Create `src/sessions/store.py`
- 2.5.1.1.3 Implement `SessionStore` class
- 2.5.1.1.4 Inject Redis client dependency
- 2.5.1.1.5 Implement `async save(session: Session)` method
- 2.5.1.1.6 Serialize session to JSON
- 2.5.1.1.7 Store with TTL from settings
- 2.5.1.1.8 Implement `async get(session_id: str) -> Session | None`
- 2.5.1.1.9 Implement `async delete(session_id: str) -> bool`
- 2.5.1.1.10 Implement `async exists(session_id: str) -> bool`
- 2.5.1.1.11 Write RED test: save and retrieve session
- 2.5.1.1.12 Write RED test: session expires after TTL
- 2.5.1.1.13 Write RED test: delete removes session
- 2.5.1.1.14 Write RED test: get nonexistent returns None
- 2.5.1.1.15 GREEN: implement and pass all tests (use fakeredis)
- 2.5.1.1.16 REFACTOR: add connection error handling

##### 2.5.1.2 Session Model
- 2.5.1.2.1 Add `Session` model to `src/models/domain.py`
- 2.5.1.2.2 Add `id: str` (UUID)
- 2.5.1.2.3 Add `messages: list[Message]` for conversation history
- 2.5.1.2.4 Add `context: dict` for additional metadata
- 2.5.1.2.5 Add `created_at: datetime`
- 2.5.1.2.6 Add `expires_at: datetime`
- 2.5.1.2.7 Add `Message` model (role, content, tool_calls, tool_results)
- 2.5.1.2.8 Write RED tests for session model serialization
- 2.5.1.2.9 GREEN: implement and pass tests

#### 2.5.2 Session Manager

##### 2.5.2.1 Manager Implementation
- 2.5.2.1.1 Create `src/sessions/manager.py`
- 2.5.2.1.2 Implement `SessionManager` class
- 2.5.2.1.3 Inject `SessionStore` dependency
- 2.5.2.1.4 Implement `async create() -> Session`
- 2.5.2.1.5 Generate UUID for session ID
- 2.5.2.1.6 Set created_at and expires_at
- 2.5.2.1.7 Save to store and return
- 2.5.2.1.8 Implement `async get(session_id: str) -> Session`
- 2.5.2.1.9 Raise SessionError if not found
- 2.5.2.1.10 Implement `async delete(session_id: str)`
- 2.5.2.1.11 Implement `async add_message(session_id: str, message: Message)`
- 2.5.2.1.12 Load session, append message, save
- 2.5.2.1.13 Write RED test: create returns new session
- 2.5.2.1.14 Write RED test: add_message updates history
- 2.5.2.1.15 Write RED test: get nonexistent raises error
- 2.5.2.1.16 GREEN: implement and pass all tests

##### 2.5.2.2 Session Context Management
- 2.5.2.2.1 Implement `async update_context(session_id: str, context: dict)`
- 2.5.2.2.2 Implement `async get_history(session_id: str) -> list[Message]`
- 2.5.2.2.3 Implement `async clear_history(session_id: str)`
- 2.5.2.2.4 Write RED tests for context operations
- 2.5.2.2.5 GREEN: implement and pass tests

---

### 2.6 Service Layer Implementation

> **Acceptance Criteria**: Chat service orchestrates provider calls and tool execution. Cost tracker records token usage per request. Response caching reduces redundant API calls. All services properly inject dependencies.

#### 2.6.1 Chat Service

##### 2.6.1.1 Service Implementation
- 2.6.1.1.1 Create `src/services/__init__.py`
- 2.6.1.1.2 Create `src/services/chat.py`
- 2.6.1.1.3 Implement `ChatService` class
- 2.6.1.1.4 Inject `ProviderRouter`, `ToolExecutor`, `SessionManager`
- 2.6.1.1.5 Implement `async complete(request: ChatCompletionRequest) -> ChatCompletionResponse`
- 2.6.1.1.6 Get provider from router based on model
- 2.6.1.1.7 Load session history if session_id provided
- 2.6.1.1.8 Append history to messages
- 2.6.1.1.9 Call provider.complete()
- 2.6.1.1.10 Handle tool_calls in response
- 2.6.1.1.11 Execute tools via executor
- 2.6.1.1.12 Continue conversation if tools executed
- 2.6.1.1.13 Save messages to session if session_id provided
- 2.6.1.1.14 Return final response
- 2.6.1.1.15 Write RED test: complete without tools returns response
- 2.6.1.1.16 Write RED test: complete with tools executes and continues
- 2.6.1.1.17 Write RED test: session history included in request
- 2.6.1.1.18 GREEN: implement and pass all tests
- 2.6.1.1.19 REFACTOR: extract tool loop to separate method

##### 2.6.1.2 Tool Call Loop
- 2.6.1.2.1 Implement `async _handle_tool_calls(response, request) -> ChatCompletionResponse`
- 2.6.1.2.2 Extract tool_calls from response
- 2.6.1.2.3 Execute all tools via executor
- 2.6.1.2.4 Build tool result messages
- 2.6.1.2.5 Append to conversation
- 2.6.1.2.6 Call provider again with tool results
- 2.6.1.2.7 Repeat until no more tool_calls or max iterations
- 2.6.1.2.8 Write RED test: tool loop handles multiple iterations
- 2.6.1.2.9 Write RED test: tool loop respects max iterations
- 2.6.1.2.10 GREEN: implement and pass tests

#### 2.6.2 Cost Tracker Service

##### 2.6.2.1 Tracker Implementation
- 2.6.2.1.1 Create `src/services/cost_tracker.py`
- 2.6.2.1.2 Implement `CostTracker` class
- 2.6.2.1.3 Define pricing per model (tokens per dollar)
- 2.6.2.1.4 Implement `record_usage(model: str, usage: Usage)`
- 2.6.2.1.5 Calculate cost from token counts
- 2.6.2.1.6 Store in Redis with daily aggregation
- 2.6.2.1.7 Implement `get_daily_usage() -> UsageSummary`
- 2.6.2.1.8 Implement `get_usage_by_model() -> dict[str, UsageSummary]`
- 2.6.2.1.9 Write RED test: record_usage stores data
- 2.6.2.1.10 Write RED test: cost calculation correct
- 2.6.2.1.11 Write RED test: daily aggregation works
- 2.6.2.1.12 GREEN: implement and pass all tests

#### 2.6.3 Response Cache Service

##### 2.6.3.1 Cache Implementation
- 2.6.3.1.1 Create `src/services/cache.py`
- 2.6.3.1.2 Implement `ResponseCache` class
- 2.6.3.1.3 Inject Redis client
- 2.6.3.1.4 Implement cache key generation from request hash
- 2.6.3.1.5 Implement `async get(request: ChatCompletionRequest) -> ChatCompletionResponse | None`
- 2.6.3.1.6 Implement `async set(request: ChatCompletionRequest, response: ChatCompletionResponse)`
- 2.6.3.1.7 Configure TTL from settings
- 2.6.3.1.8 Skip caching for tool_use requests
- 2.6.3.1.9 Write RED test: cache hit returns response
- 2.6.3.1.10 Write RED test: cache miss returns None
- 2.6.3.1.11 Write RED test: cache expires after TTL
- 2.6.3.1.12 GREEN: implement and pass all tests

---

### 2.7 Integration with External Services

> **Acceptance Criteria**: HTTP clients configured for semantic-search-service and ai-agents. Connection pooling enabled. Timeouts and retries configured. Circuit breaker pattern implemented for resilience.

#### 2.7.1 HTTP Client Setup

##### 2.7.1.1 Client Factory
- 2.7.1.1.1 Create `src/clients/__init__.py`
- 2.7.1.1.2 Create `src/clients/http.py`
- 2.7.1.1.3 Implement `create_http_client()` factory
- 2.7.1.1.4 Configure connection pooling
- 2.7.1.1.5 Set default timeouts
- 2.7.1.1.6 Add retry middleware
- 2.7.1.1.7 Write RED test: client created with config
- 2.7.1.1.8 GREEN: implement and pass test

##### 2.7.1.2 Semantic Search Client
- 2.7.1.2.1 Create `src/clients/semantic_search.py`
- 2.7.1.2.2 Implement `SemanticSearchClient` class
- 2.7.1.2.3 Implement `async search(query: str, ...) -> SearchResults`
- 2.7.1.2.4 Implement `async embed(texts: list[str]) -> list[list[float]]`
- 2.7.1.2.5 Implement `async get_chunk(chunk_id: str) -> Chunk`
- 2.7.1.2.6 Add error handling for service unavailable
- 2.7.1.2.7 Write RED tests with mocked responses
- 2.7.1.2.8 GREEN: implement and pass tests

##### 2.7.1.3 AI Agents Client
- 2.7.1.3.1 Create `src/clients/ai_agents.py`
- 2.7.1.3.2 Implement `AIAgentsClient` class
- 2.7.1.3.3 Implement `async run_agent(agent: str, input: dict) -> AgentResult`
- 2.7.1.3.4 Support code-review, architecture, doc-generate agents
- 2.7.1.3.5 Add error handling
- 2.7.1.3.6 Write RED tests with mocked responses
- 2.7.1.3.7 GREEN: implement and pass tests

#### 2.7.2 Resilience Patterns

##### 2.7.2.1 Circuit Breaker
- 2.7.2.1.1 Implement circuit breaker pattern
- 2.7.2.1.2 Configure failure threshold
- 2.7.2.1.3 Configure recovery timeout
- 2.7.2.1.4 Track failure rate per service
- 2.7.2.1.5 Open circuit when threshold exceeded
- 2.7.2.1.6 Half-open for recovery testing
- 2.7.2.1.7 Write RED test: circuit opens after failures
- 2.7.2.1.8 Write RED test: circuit recovers after timeout
- 2.7.2.1.9 GREEN: implement and pass tests

---

### 2.8 Observability Implementation

> **Acceptance Criteria**: Structured JSON logging throughout application. Prometheus metrics exposed at /metrics. OpenTelemetry traces generated for requests. Correlation IDs propagated across services.

#### 2.8.1 Structured Logging

##### 2.8.1.1 Logger Configuration
- 2.8.1.1.1 Create `src/observability/__init__.py`
- 2.8.1.1.2 Create `src/observability/logging.py`
- 2.8.1.1.3 Configure structlog with JSON formatter
- 2.8.1.1.4 Add timestamp, level, logger name processors
- 2.8.1.1.5 Add correlation ID processor
- 2.8.1.1.6 Configure based on LOG_LEVEL setting
- 2.8.1.1.7 Export `get_logger()` function
- 2.8.1.1.8 Write RED test: logger outputs JSON
- 2.8.1.1.9 GREEN: implement and pass test

##### 2.8.1.2 Request Logging
- 2.8.1.2.1 Log request received with path, method
- 2.8.1.2.2 Log request completed with status, duration
- 2.8.1.2.3 Log provider calls with model, tokens
- 2.8.1.2.4 Log tool executions with name, duration
- 2.8.1.2.5 Redact sensitive data (API keys, auth tokens)
- 2.8.1.2.6 Write RED tests for log output
- 2.8.1.2.7 GREEN: implement and pass tests

#### 2.8.2 Metrics

##### 2.8.2.1 Prometheus Metrics
- 2.8.2.1.1 Create `src/observability/metrics.py`
- 2.8.2.1.2 Define `request_count` Counter
- 2.8.2.1.3 Define `request_latency` Histogram
- 2.8.2.1.4 Define `provider_request_count` Counter (by provider)
- 2.8.2.1.5 Define `provider_latency` Histogram (by provider)
- 2.8.2.1.6 Define `tool_execution_count` Counter (by tool)
- 2.8.2.1.7 Define `token_usage` Counter (by model)
- 2.8.2.1.8 Define `active_sessions` Gauge
- 2.8.2.1.9 Instrument request middleware
- 2.8.2.1.10 Write RED test: metrics incremented on request
- 2.8.2.1.11 GREEN: implement and pass test

#### 2.8.3 Tracing

##### 2.8.3.1 OpenTelemetry Setup
- 2.8.3.1.1 Create `src/observability/tracing.py`
- 2.8.3.1.2 Configure OpenTelemetry tracer provider
- 2.8.3.1.3 Add FastAPI instrumentation
- 2.8.3.1.4 Add httpx instrumentation for outbound calls
- 2.8.3.1.5 Add Redis instrumentation
- 2.8.3.1.6 Configure exporter (OTLP/Jaeger)
- 2.8.3.1.7 Write RED test: spans created for requests
- 2.8.3.1.8 GREEN: implement and pass test

---

### 2.9 Unit Testing Coverage

> **Acceptance Criteria**: All modules have corresponding test files. Unit test coverage ≥80%. All tests pass. Tests use mocks/fakes for external dependencies.

#### 2.9.1 Test Structure

##### 2.9.1.1 Test Directory Setup
- 2.9.1.1.1 Create `tests/unit/` directory structure
- 2.9.1.1.2 Create `tests/unit/test_providers/`
- 2.9.1.1.3 Create `tests/unit/test_tools/`
- 2.9.1.1.4 Create `tests/unit/test_sessions/`
- 2.9.1.1.5 Create `tests/unit/test_services/`
- 2.9.1.1.6 Create `tests/unit/test_api/`
- 2.9.1.1.7 Create `tests/conftest.py` with fixtures

##### 2.9.1.2 Test Fixtures
- 2.9.1.2.1 Create `FakeRedis` fixture
- 2.9.1.2.2 Create `MockProviderRouter` fixture
- 2.9.1.2.3 Create `MockSemanticSearchClient` fixture
- 2.9.1.2.4 Create `test_settings` fixture
- 2.9.1.2.5 Create `test_client` fixture (TestClient)
- 2.9.1.2.6 Create sample request/response fixtures

#### 2.9.2 Coverage Targets

##### 2.9.2.1 Coverage Verification
- 2.9.2.1.1 Run `pytest --cov=src --cov-report=term-missing`
- 2.9.2.1.2 Verify coverage ≥80% overall
- 2.9.2.1.3 Identify uncovered lines
- 2.9.2.1.4 Add tests for critical uncovered paths
- 2.9.2.1.5 Generate HTML coverage report
- 2.9.2.1.6 Document coverage in README

---

### 2.10 Stage 2 Validation and Sign-off

> **Acceptance Criteria**: All Stage 2 tasks completed. All unit tests pass. Coverage ≥80%. API endpoints respond correctly. Application runs locally and handles requests.

#### 2.10.1 Final Validation

##### 2.10.1.1 Test Suite Validation
- 2.10.1.1.1 Run full unit test suite: `pytest tests/unit -v`
- 2.10.1.1.2 Verify all tests pass
- 2.10.1.1.3 Run coverage report: `pytest --cov=src`
- 2.10.1.1.4 Verify coverage ≥80%
- 2.10.1.1.5 Run type checking: `mypy src/`
- 2.10.1.1.6 Run linting: `ruff check src/`

##### 2.10.1.2 API Validation
- 2.10.1.2.1 Start application locally
- 2.10.1.2.2 Verify `/health` returns 200
- 2.10.1.2.3 Verify `/health/ready` returns 200 (with Redis)
- 2.10.1.2.4 Test `/v1/chat/completions` with mock provider
- 2.10.1.2.5 Test session CRUD operations
- 2.10.1.2.6 Test tool execution
- 2.10.1.2.7 Verify OpenAPI schema at `/docs`

##### 2.10.1.3 Docker Validation
- 2.10.1.3.1 Build Docker image with implemented code
- 2.10.1.3.2 Run container and verify endpoints
- 2.10.1.3.3 Verify logs in JSON format
- 2.10.1.3.4 Test with docker-compose full stack

##### 2.10.1.4 Documentation
- 2.10.1.4.1 Update API.md with endpoint documentation
- 2.10.1.4.2 Document configuration options
- 2.10.1.4.3 Add code examples for API usage
- 2.10.1.4.4 Update ARCHITECTURE.md if design changed

---

## Stage 3: Integration

> **Stage 3 Acceptance Criteria**: LLM Gateway fully integrated with llm-document-enhancer application. Integration tests pass for all service-to-service communication. Mock services replaced with real service calls. Semantic-search-service and ai-agents integration points documented and tested. Full docker-compose stack runs end-to-end.

---

### 3.1 LLM Document Enhancer Integration

> **Acceptance Criteria**: llm-document-enhancer can call llm-gateway for all LLM operations. 3-step enhancement process works through gateway. Tool-use for corpus search functional. Session management maintains conversation context across enhancement steps.

#### 3.1.1 Gateway Client in Document Enhancer

##### 3.1.1.1 Client Module Setup
- 3.1.1.1.1 Navigate to `llm-document-enhancer` repository
- 3.1.1.1.2 Create `src/clients/` directory (if not exists)
- 3.1.1.1.3 Create `src/clients/__init__.py`
- 3.1.1.1.4 Create `src/clients/llm_gateway.py`
- 3.1.1.1.5 Implement `LLMGatewayClient` class
- 3.1.1.1.6 Configure base URL from `DOC_ENHANCER_LLM_GATEWAY_URL` env var
- 3.1.1.1.7 Add httpx async client with connection pooling
- 3.1.1.1.8 Add request timeout configuration
- 3.1.1.1.9 Write RED test: client instantiates with config
- 3.1.1.1.10 GREEN: implement and pass test

##### 3.1.1.2 Chat Completion Method
- 3.1.1.2.1 Implement `async chat_completion(messages, model, tools, session_id)`
- 3.1.1.2.2 Build request body per llm-gateway API spec
- 3.1.1.2.3 POST to `/v1/chat/completions`
- 3.1.1.2.4 Parse response into internal models
- 3.1.1.2.5 Handle error responses (4xx, 5xx)
- 3.1.1.2.6 Add retry logic for transient failures
- 3.1.1.2.7 Write RED test: successful completion returns response
- 3.1.1.2.8 Write RED test: error response raises exception
- 3.1.1.2.9 Write RED test: retry on 503
- 3.1.1.2.10 GREEN: implement and pass all tests

##### 3.1.1.3 Session Management Methods
- 3.1.1.3.1 Implement `async create_session() -> str`
- 3.1.1.3.2 POST to `/v1/sessions`
- 3.1.1.3.3 Return session ID
- 3.1.1.3.4 Implement `async get_session(session_id) -> Session`
- 3.1.1.3.5 GET from `/v1/sessions/{id}`
- 3.1.1.3.6 Implement `async delete_session(session_id)`
- 3.1.1.3.7 DELETE to `/v1/sessions/{id}`
- 3.1.1.3.8 Write RED tests for each method
- 3.1.1.3.9 GREEN: implement and pass tests

##### 3.1.1.4 Tool Execution Method
- 3.1.1.4.1 Implement `async execute_tool(tool_name, arguments) -> ToolResult`
- 3.1.1.4.2 POST to `/v1/tools/execute`
- 3.1.1.4.3 Handle tool execution errors
- 3.1.1.4.4 Write RED test: tool execution returns result
- 3.1.1.4.5 GREEN: implement and pass test

#### 3.1.2 Enhancement Pipeline Integration

##### 3.1.2.1 Replace Direct LLM Calls
- 3.1.2.1.1 Identify all direct Anthropic/OpenAI calls in document enhancer
- 3.1.2.1.2 Map each call to equivalent gateway API call
- 3.1.2.1.3 Create adapter layer if request/response formats differ
- 3.1.2.1.4 Update Step 1 (Context Gathering) to use gateway
- 3.1.2.1.5 Update Step 2 (Enhancement) to use gateway
- 3.1.2.1.6 Update Step 3 (Validation) to use gateway
- 3.1.2.1.7 Write integration test: Step 1 works through gateway
- 3.1.2.1.8 Write integration test: Step 2 works through gateway
- 3.1.2.1.9 Write integration test: Step 3 works through gateway
- 3.1.2.1.10 GREEN: all steps work through gateway

##### 3.1.2.2 Tool-Use Integration
- 3.1.2.2.1 Define tool schemas for enhancement process
- 3.1.2.2.2 Register `search_corpus` tool usage in prompts
- 3.1.2.2.3 Register `get_chunk` tool usage in prompts
- 3.1.2.2.4 Update prompt templates to include tool definitions
- 3.1.2.2.5 Handle tool_calls in enhancement response
- 3.1.2.2.6 Process tool results and continue conversation
- 3.1.2.2.7 Write integration test: enhancement uses search_corpus tool
- 3.1.2.2.8 Write integration test: tool results incorporated in response
- 3.1.2.2.9 GREEN: tool-use working end-to-end

##### 3.1.2.3 Session-Based Enhancement
- 3.1.2.3.1 Create session at start of document processing
- 3.1.2.3.2 Pass session_id to all enhancement steps
- 3.1.2.3.3 Maintain context across multi-turn enhancement
- 3.1.2.3.4 Delete session after document processing complete
- 3.1.2.3.5 Handle session expiry gracefully
- 3.1.2.3.6 Write integration test: session maintains context
- 3.1.2.3.7 Write integration test: session cleanup after processing
- 3.1.2.3.8 GREEN: session management working

#### 3.1.3 Configuration Updates

##### 3.1.3.1 Environment Configuration
- 3.1.3.1.1 Add `DOC_ENHANCER_LLM_GATEWAY_URL` to .env.example
- 3.1.3.1.2 Add `DOC_ENHANCER_LLM_GATEWAY_TIMEOUT` configuration
- 3.1.3.1.3 Add `DOC_ENHANCER_USE_GATEWAY` feature flag (for gradual rollout)
- 3.1.3.1.4 Update settings.py to load gateway configuration
- 3.1.3.1.5 Document configuration in README
- 3.1.3.1.6 Write test: settings loads gateway config
- 3.1.3.1.7 GREEN: configuration working

##### 3.1.3.2 Docker Compose Updates
- 3.1.3.2.1 Update llm-document-enhancer docker-compose.yml
- 3.1.3.2.2 Add llm-gateway service dependency
- 3.1.3.2.3 Add environment variable for gateway URL
- 3.1.3.2.4 Configure network for service discovery
- 3.1.3.2.5 Test docker-compose up starts all services
- 3.1.3.2.6 Verify document enhancer can reach gateway

---

### 3.2 Semantic Search Service Integration

> **Acceptance Criteria**: LLM Gateway can call semantic-search-service for embedding and search operations. Tool execution for `search_corpus` and `get_chunk` functional. Error handling for service unavailability implemented.

#### 3.2.1 Service Discovery Configuration

##### 3.2.1.1 Gateway Configuration for Semantic Search
- 3.2.1.1.1 Verify `LLM_GATEWAY_SEMANTIC_SEARCH_URL` in ConfigMap
- 3.2.1.1.2 Test URL resolution in local docker-compose
- 3.2.1.1.3 Test URL resolution in Kubernetes (service DNS)
- 3.2.1.1.4 Document service discovery patterns
- 3.2.1.1.5 Write integration test: gateway resolves semantic-search URL

##### 3.2.1.2 Health Check Integration
- 3.2.1.2.1 Add semantic-search health check to gateway readiness
- 3.2.1.2.2 Implement `check_semantic_search_health()` function
- 3.2.1.2.3 Call semantic-search `/health` endpoint
- 3.2.1.2.4 Report degraded status if semantic-search unavailable
- 3.2.1.2.5 Write integration test: readiness reflects semantic-search status
- 3.2.1.2.6 GREEN: health check working

#### 3.2.2 Search Tool Integration

##### 3.2.2.1 Search Corpus Tool Testing
- 3.2.2.1.1 Start semantic-search-service locally
- 3.2.2.1.2 Index sample documents for testing
- 3.2.2.1.3 Call `search_corpus` tool through gateway
- 3.2.2.1.4 Verify search results returned correctly
- 3.2.2.1.5 Test with various query types
- 3.2.2.1.6 Test with different top_k values
- 3.2.2.1.7 Write integration test: search returns relevant results
- 3.2.2.1.8 Write integration test: empty results handled
- 3.2.2.1.9 GREEN: search tool working

##### 3.2.2.2 Chunk Retrieval Tool Testing
- 3.2.2.2.1 Call `get_chunk` tool through gateway
- 3.2.2.2.2 Verify chunk text and metadata returned
- 3.2.2.2.3 Test with valid chunk IDs
- 3.2.2.2.4 Test with invalid chunk IDs (404 handling)
- 3.2.2.2.5 Write integration test: chunk retrieval works
- 3.2.2.2.6 Write integration test: not found handled gracefully
- 3.2.2.2.7 GREEN: chunk retrieval working

##### 3.2.2.3 Embedding Integration (Optional)
- 3.2.2.3.1 Implement `embed_text` tool if needed
- 3.2.2.3.2 Call semantic-search `/v1/embed` endpoint
- 3.2.2.3.3 Return embeddings for use in prompts
- 3.2.2.3.4 Write integration test: embedding returns vectors
- 3.2.2.3.5 GREEN: embedding working

#### 3.2.3 Error Handling and Resilience

##### 3.2.3.1 Service Unavailable Handling
- 3.2.3.1.1 Test gateway behavior when semantic-search is down
- 3.2.3.1.2 Verify circuit breaker opens after failures
- 3.2.3.1.3 Verify graceful degradation (tools return error, not crash)
- 3.2.3.1.4 Test recovery when service comes back
- 3.2.3.1.5 Write integration test: circuit breaker behavior
- 3.2.3.1.6 GREEN: resilience working

##### 3.2.3.2 Timeout Handling
- 3.2.3.2.1 Configure appropriate timeouts for search operations
- 3.2.3.2.2 Test behavior on slow responses
- 3.2.3.2.3 Verify timeout errors returned to caller
- 3.2.3.2.4 Write integration test: timeout handled
- 3.2.3.2.5 GREEN: timeout handling working

---

### 3.3 AI Agents Service Integration

> **Acceptance Criteria**: LLM Gateway can invoke AI agents through ai-agents service. Agent tools registered and executable. Code review, architecture, and doc-generate agents accessible. **Note**: ai-agents does NOT directly call LLM providers - if agents need LLM reasoning, they call BACK to llm-gateway. Error handling for agent failures implemented.

#### 3.3.1 Service Discovery Configuration

##### 3.3.1.1 Gateway Configuration for AI Agents
- 3.3.1.1.1 Verify `LLM_GATEWAY_AI_AGENTS_URL` in ConfigMap
- 3.3.1.1.2 Test URL resolution in local docker-compose
- 3.3.1.1.3 Test URL resolution in Kubernetes
- 3.3.1.1.4 Document service discovery patterns
- 3.3.1.1.5 Write integration test: gateway resolves ai-agents URL

##### 3.3.1.2 Health Check Integration
- 3.3.1.2.1 Add ai-agents health check to gateway readiness (optional)
- 3.3.1.2.2 Implement `check_ai_agents_health()` function
- 3.3.1.2.3 Report status but don't fail readiness (agents optional)
- 3.3.1.2.4 Write integration test: health check includes agents status
- 3.3.1.2.5 GREEN: health check working

#### 3.3.2 Agent Tool Registration

##### 3.3.2.1 Code Review Agent Tool
- 3.3.2.1.1 Create `src/tools/builtin/code_review.py` in gateway
- 3.3.2.1.2 Implement `review_code` tool function
- 3.3.2.1.3 Accept `code: str`, `language: str` parameters
- 3.3.2.1.4 Call ai-agents `/v1/agents/code-review/run` endpoint
- 3.3.2.1.5 Return review findings and suggestions
- 3.3.2.1.6 Add tool definition to `config/tools.json`
- 3.3.2.1.7 Write integration test: code review returns findings
- 3.3.2.1.8 GREEN: code review tool working

##### 3.3.2.2 Architecture Agent Tool
- 3.3.2.2.1 Create `src/tools/builtin/architecture.py` in gateway
- 3.3.2.2.2 Implement `analyze_architecture` tool function
- 3.3.2.2.3 Accept `code: str`, `context: str` parameters
- 3.3.2.2.4 Call ai-agents `/v1/agents/architecture/run` endpoint
- 3.3.2.2.5 Return architecture analysis
- 3.3.2.2.6 Add tool definition to `config/tools.json`
- 3.3.2.2.7 Write integration test: architecture analysis works
- 3.3.2.2.8 GREEN: architecture tool working

##### 3.3.2.3 Doc Generate Agent Tool
- 3.3.2.3.1 Create `src/tools/builtin/doc_generate.py` in gateway
- 3.3.2.3.2 Implement `generate_documentation` tool function
- 3.3.2.3.3 Accept `code: str`, `format: str` parameters
- 3.3.2.3.4 Call ai-agents `/v1/agents/doc-generate/run` endpoint
- 3.3.2.3.5 Return generated documentation
- 3.3.2.3.6 Add tool definition to `config/tools.json`
- 3.3.2.3.7 Write integration test: doc generation works
- 3.3.2.3.8 GREEN: doc generate tool working

#### 3.3.3 Agent Integration Testing

##### 3.3.3.1 Full Agent Flow Testing
- 3.3.3.1.1 Start ai-agents service locally
- 3.3.3.1.2 Test code review through gateway chat completion
- 3.3.3.1.3 Verify LLM can request code review tool
- 3.3.3.1.4 Verify tool results returned to LLM
- 3.3.3.1.5 Test multi-agent workflow (review → fix → review)
- 3.3.3.1.6 Write integration test: agent workflow end-to-end
- 3.3.3.1.7 GREEN: agent integration working

##### 3.3.3.2 Error Handling
- 3.3.3.2.1 Test behavior when ai-agents service unavailable
- 3.3.3.2.2 Test behavior on agent execution timeout
- 3.3.3.2.3 Test behavior on invalid agent response
- 3.3.3.2.4 Verify errors returned gracefully to LLM
- 3.3.3.2.5 Write integration test: error scenarios handled
- 3.3.3.2.6 GREEN: error handling working

---

### 3.4 Docker Compose Full Stack Integration

> **Acceptance Criteria**: Single `docker-compose up` starts entire system. All services can communicate. Health checks pass for all services. Logs aggregated and accessible.

#### 3.4.1 Multi-Service Docker Compose

##### 3.4.1.1 Full Stack Compose File
- 3.4.1.1.1 Create/update `docker-compose.yml` in llm-gateway
- 3.4.1.1.2 Add redis service
- 3.4.1.1.3 Add semantic-search service (build from ../semantic-search-service)
- 3.4.1.1.4 Add ai-agents service (build from ../ai-agents)
- 3.4.1.1.5 Add llm-gateway service
- 3.4.1.1.6 Configure shared network `llm-network`
- 3.4.1.1.7 Configure environment variables for service discovery
- 3.4.1.1.8 Add volume mounts for data persistence
- 3.4.1.1.9 Configure health checks for all services
- 3.4.1.1.10 Add depends_on with health conditions
- 3.4.1.1.11 Test: `docker-compose config` validates
- 3.4.1.1.12 Test: `docker-compose up` starts all services

##### 3.4.1.2 Service Health Verification
- 3.4.1.2.1 Wait for all services to be healthy
- 3.4.1.2.2 Verify redis: `redis-cli ping`
- 3.4.1.2.3 Verify semantic-search: `curl localhost:8081/health`
- 3.4.1.2.4 Verify ai-agents: `curl localhost:8082/health`
- 3.4.1.2.5 Verify llm-gateway: `curl localhost:8080/health`
- 3.4.1.2.6 Verify llm-gateway readiness: `curl localhost:8080/health/ready`
- 3.4.1.2.7 Document startup sequence and timing

##### 3.4.1.3 Service Communication Verification
- 3.4.1.3.1 From gateway container, curl semantic-search
- 3.4.1.3.2 From gateway container, curl ai-agents
- 3.4.1.3.3 From gateway container, verify Redis connection
- 3.4.1.3.4 Test tool execution calls downstream services
- 3.4.1.3.5 Test chat completion with tool_use
- 3.4.1.3.6 Document any networking issues and resolutions

#### 3.4.2 Development Workflow

##### 3.4.2.1 Local Development Setup
- 3.4.2.1.1 Create `docker-compose.dev.yml` for hot-reload
- 3.4.2.1.2 Mount source code as volumes
- 3.4.2.1.3 Enable debug logging
- 3.4.2.1.4 Expose additional ports for debugging
- 3.4.2.1.5 Document development workflow in README
- 3.4.2.1.6 Test code changes reflected without rebuild

##### 3.4.2.2 Selective Service Startup
- 3.4.2.2.1 Document how to start only specific services
- 3.4.2.2.2 Create profiles for different scenarios
- 3.4.2.2.3 Profile: `gateway-only` (gateway + redis)
- 3.4.2.2.4 Profile: `full-stack` (all services)
- 3.4.2.2.5 Profile: `integration-test` (all services + test runner)
- 3.4.2.2.6 Test each profile starts correctly

---

### 3.5 Integration Test Suite

> **Acceptance Criteria**: Comprehensive integration test suite covering all service interactions. Tests run against real services (not mocks). CI pipeline runs integration tests. All tests pass consistently.

#### 3.5.1 Integration Test Structure

##### 3.5.1.1 Test Directory Setup
- 3.5.1.1.1 Create `tests/integration/` directory in llm-gateway
- 3.5.1.1.2 Create `tests/integration/conftest.py`
- 3.5.1.1.3 Add fixtures for service URLs
- 3.5.1.1.4 Add fixtures for test data
- 3.5.1.1.5 Add setup/teardown for test isolation
- 3.5.1.1.6 Configure pytest markers for integration tests

##### 3.5.1.2 Service Fixtures
- 3.5.1.2.1 Create `wait_for_service()` helper function
- 3.5.1.2.2 Create `gateway_client` fixture
- 3.5.1.2.3 Create `semantic_search_client` fixture
- 3.5.1.2.4 Create `ai_agents_client` fixture
- 3.5.1.2.5 Create `redis_client` fixture for test data
- 3.5.1.2.6 Add cleanup fixtures to reset state between tests

#### 3.5.2 Gateway Integration Tests

##### 3.5.2.1 Health Endpoint Tests
- 3.5.2.1.1 Create `tests/integration/test_health.py`
- 3.5.2.1.2 Test `/health` returns 200
- 3.5.2.1.3 Test `/health/ready` returns 200 when all deps up
- 3.5.2.1.4 Test `/health/ready` returns 503 when Redis down
- 3.5.2.1.5 Test `/metrics` returns Prometheus format

##### 3.5.2.2 Chat Completion Tests
- 3.5.2.2.1 Create `tests/integration/test_chat.py`
- 3.5.2.2.2 Test simple completion (no tools)
- 3.5.2.2.3 Test completion with session
- 3.5.2.2.4 Test completion with tool_use
- 3.5.2.2.5 Test completion with multiple tool calls
- 3.5.2.2.6 Test provider routing (different models)
- 3.5.2.2.7 Test error handling (invalid model)
- 3.5.2.2.8 Test rate limiting behavior

##### 3.5.2.3 Session Tests
- 3.5.2.3.1 Create `tests/integration/test_sessions.py`
- 3.5.2.3.2 Test create session
- 3.5.2.3.3 Test get session
- 3.5.2.3.4 Test session persists messages
- 3.5.2.3.5 Test delete session
- 3.5.2.3.6 Test session expiry
- 3.5.2.3.7 Test get nonexistent session (404)

##### 3.5.2.4 Tool Execution Tests
- 3.5.2.4.1 Create `tests/integration/test_tools.py`
- 3.5.2.4.2 Test list available tools
- 3.5.2.4.3 Test execute search_corpus tool
- 3.5.2.4.4 Test execute get_chunk tool
- 3.5.2.4.5 Test execute unknown tool (404)
- 3.5.2.4.6 Test execute with invalid arguments (422)

#### 3.5.3 Cross-Service Integration Tests

##### 3.5.3.1 Gateway → Semantic Search Tests
- 3.5.3.1.1 Create `tests/integration/test_semantic_search_integration.py`
- 3.5.3.1.2 Test search_corpus returns results from semantic-search
- 3.5.3.1.3 Test get_chunk returns chunk from semantic-search
- 3.5.3.1.4 Test behavior when semantic-search unavailable
- 3.5.3.1.5 Test timeout handling

##### 3.5.3.2 Gateway → AI Agents Tests
- 3.5.3.2.1 Create `tests/integration/test_ai_agents_integration.py`
- 3.5.3.2.2 Test code_review tool calls ai-agents
- 3.5.3.2.3 Test architecture tool calls ai-agents
- 3.5.3.2.4 Test doc_generate tool calls ai-agents
- 3.5.3.2.5 Test behavior when ai-agents unavailable

##### 3.5.3.3 End-to-End Flow Tests
- 3.5.3.3.1 Create `tests/integration/test_e2e_flows.py`
- 3.5.3.3.2 Test: chat completion → tool_call → semantic-search → continue
- 3.5.3.3.3 Test: session-based multi-turn conversation
- 3.5.3.3.4 Test: enhancement workflow simulation
- 3.5.3.3.5 Test: full tool chain (search → retrieve → analyze)

#### 3.5.4 CI Integration Test Setup

##### 3.5.4.1 Docker Compose for CI
- 3.5.4.1.1 Create `docker-compose.test.yml` for CI environment
- 3.5.4.1.2 Configure services without volumes (ephemeral)
- 3.5.4.1.3 Add test runner service
- 3.5.4.1.4 Configure exit codes for CI
- 3.5.4.1.5 Add health check waits before tests run

##### 3.5.4.2 GitHub Actions Integration Tests
- 3.5.4.2.1 Update `.github/workflows/ci.yml`
- 3.5.4.2.2 Add integration test job
- 3.5.4.2.3 Start services with docker-compose
- 3.5.4.2.4 Wait for services to be healthy
- 3.5.4.2.5 Run integration tests
- 3.5.4.2.6 Collect and upload test results
- 3.5.4.2.7 Tear down services
- 3.5.4.2.8 Test: CI pipeline runs integration tests successfully

---

### 3.6 API Contract Testing

> **Acceptance Criteria**: API contracts documented and validated. Breaking changes detected automatically. Consumer-driven contracts for downstream services. OpenAPI spec validated against implementation.

#### 3.6.1 OpenAPI Specification

##### 3.6.1.1 OpenAPI Generation
- 3.6.1.1.1 Verify FastAPI generates OpenAPI spec at `/openapi.json`
- 3.6.1.1.2 Export spec to `docs/openapi.yaml`
- 3.6.1.1.3 Validate spec with `openapi-spec-validator`
- 3.6.1.1.4 Add spec export to CI pipeline
- 3.6.1.1.5 Version the API spec

##### 3.6.1.2 Contract Validation
- 3.6.1.2.1 Install `schemathesis` for contract testing
- 3.6.1.2.2 Run schemathesis against running gateway
- 3.6.1.2.3 Fix any contract violations
- 3.6.1.2.4 Add contract tests to CI
- 3.6.1.2.5 Document API versioning strategy

#### 3.6.2 Consumer Contract Tests

##### 3.6.2.1 Document Enhancer Contract
- 3.6.2.1.1 Define expected API behavior for document enhancer
- 3.6.2.1.2 Create contract tests in llm-document-enhancer repo
- 3.6.2.1.3 Test contract against gateway stub
- 3.6.2.1.4 Test contract against real gateway
- 3.6.2.1.5 Detect breaking changes early

---

### 3.7 Documentation Updates

> **Acceptance Criteria**: All integration points documented. API documentation complete. Runbook for common operations. Troubleshooting guide for integration issues.

#### 3.7.1 API Documentation

##### 3.7.1.1 Update API.md
- 3.7.1.1.1 Document all endpoints with examples
- 3.7.1.1.2 Document request/response formats
- 3.7.1.1.3 Document error codes and messages
- 3.7.1.1.4 Document authentication (if applicable)
- 3.7.1.1.5 Document rate limiting behavior
- 3.7.1.1.6 Add curl examples for each endpoint
- 3.7.1.1.7 Add Python client examples

##### 3.7.1.2 Integration Guide
- 3.7.1.2.1 Create `docs/INTEGRATION_GUIDE.md`
- 3.7.1.2.2 Document how to integrate with llm-gateway
- 3.7.1.2.3 Document service discovery configuration
- 3.7.1.2.4 Document tool registration process
- 3.7.1.2.5 Document session management best practices
- 3.7.1.2.6 Add code examples for common patterns

#### 3.7.2 Operations Documentation

##### 3.7.2.1 Runbook
- 3.7.2.1.1 Create `docs/RUNBOOK.md`
- 3.7.2.1.2 Document how to start/stop services
- 3.7.2.1.3 Document how to check service health
- 3.7.2.1.4 Document how to view logs
- 3.7.2.1.5 Document how to scale services
- 3.7.2.1.6 Document backup/restore procedures

##### 3.7.2.2 Troubleshooting Guide
- 3.7.2.2.1 Create `docs/TROUBLESHOOTING.md`
- 3.7.2.2.2 Document common integration issues
- 3.7.2.2.3 Document debugging steps
- 3.7.2.2.4 Document how to check connectivity
- 3.7.2.2.5 Document log analysis for errors
- 3.7.2.2.6 Add FAQ section

---

### 3.8 Stage 3 Validation and Sign-off

> **Acceptance Criteria**: All Stage 3 tasks completed. Integration tests pass. Full stack runs successfully. Documentation complete.

#### 3.8.1 Final Integration Validation

##### 3.8.1.1 Full Stack Validation
- 3.8.1.1.1 Start full stack: `docker-compose up -d`
- 3.8.1.1.2 Verify all services healthy
- 3.8.1.1.3 Run integration test suite
- 3.8.1.1.4 Verify all tests pass
- 3.8.1.1.5 Test document enhancement workflow end-to-end
- 3.8.1.1.6 Verify logs show cross-service calls
- 3.8.1.1.7 Verify metrics include service interactions

##### 3.8.1.2 CI/CD Validation
- 3.8.1.2.1 Verify CI pipeline includes integration tests
- 3.8.1.2.2 Trigger CI and verify integration tests run
- 3.8.1.2.3 Verify integration test results reported
- 3.8.1.2.4 Document CI integration test requirements

##### 3.8.1.3 Documentation Validation
- 3.8.1.3.1 Review all documentation for accuracy
- 3.8.1.3.2 Test all code examples in documentation
- 3.8.1.3.3 Verify API documentation matches implementation
- 3.8.1.3.4 Get team review/approval on documentation

---

## Stage 4: End-to-End Testing

> **Stage 4 Acceptance Criteria**: Complete end-to-end test suite validates the full document enhancement workflow. Performance benchmarks established. Load testing confirms system handles expected throughput. Security testing completed. Production readiness checklist satisfied. System deployed to staging and validated before production release.

---

### 4.1 End-to-End Test Framework

> **Acceptance Criteria**: E2E test framework set up and configured. Test data fixtures created. Tests can run against local docker-compose and staging environments. Test reports generated with pass/fail status and timing.

#### 4.1.1 E2E Test Infrastructure

##### 4.1.1.1 Test Framework Setup
- 4.1.1.1.1 Create `tests/e2e/` directory in llm-gateway
- 4.1.1.1.2 Create `tests/e2e/__init__.py`
- 4.1.1.1.3 Create `tests/e2e/conftest.py` with E2E fixtures
- 4.1.1.1.4 Install pytest-asyncio for async E2E tests
- 4.1.1.1.5 Install pytest-timeout for test timeouts
- 4.1.1.1.6 Install pytest-html for HTML reports
- 4.1.1.1.7 Configure pytest markers: `@pytest.mark.e2e`
- 4.1.1.1.8 Add E2E test configuration to `pyproject.toml`

##### 4.1.1.2 Environment Configuration
- 4.1.1.2.1 Create `tests/e2e/config.py` for test environment settings
- 4.1.1.2.2 Support local environment (docker-compose)
- 4.1.1.2.3 Support staging environment (Kubernetes)
- 4.1.1.2.4 Support production-like environment (optional)
- 4.1.1.2.5 Configure via environment variables
- 4.1.1.2.6 Add timeout configurations per environment
- 4.1.1.2.7 Document environment setup in README

##### 4.1.1.3 Test Data Management
- 4.1.1.3.1 Create `tests/e2e/fixtures/` directory
- 4.1.1.3.2 Create sample documents for enhancement testing
- 4.1.1.3.3 Create sample corpus chunks for search testing
- 4.1.1.3.4 Create sample code snippets for agent testing
- 4.1.1.3.5 Create expected output fixtures for validation
- 4.1.1.3.6 Add fixture loading utilities
- 4.1.1.3.7 Document fixture creation process

##### 4.1.1.4 Test Utilities
- 4.1.1.4.1 Create `tests/e2e/utils.py`
- 4.1.1.4.2 Implement `wait_for_services()` utility
- 4.1.1.4.3 Implement `seed_test_data()` utility
- 4.1.1.4.4 Implement `cleanup_test_data()` utility
- 4.1.1.4.5 Implement `capture_logs()` utility for debugging
- 4.1.1.4.6 Implement `measure_latency()` utility
- 4.1.1.4.7 Implement `assert_within_time()` utility

---

### 4.2 Document Enhancement E2E Tests

> **Acceptance Criteria**: Full 3-step document enhancement workflow tested end-to-end. Tests validate enhancement quality. Tests measure processing time. All enhancement scenarios covered.

#### 4.2.1 Enhancement Workflow Tests

##### 4.2.1.1 Single Document Enhancement
- 4.2.1.1.1 Create `tests/e2e/test_document_enhancement.py`
- 4.2.1.1.2 Test: Load sample document from fixtures
- 4.2.1.1.3 Test: Submit document to enhancement pipeline
- 4.2.1.1.4 Test: Step 1 (Context Gathering) completes successfully
- 4.2.1.1.5 Test: Step 2 (Enhancement) completes successfully
- 4.2.1.1.6 Test: Step 3 (Validation) completes successfully
- 4.2.1.1.7 Test: Enhanced document contains expected cross-references
- 4.2.1.1.8 Test: Enhanced document contains expected citations
- 4.2.1.1.9 Test: Enhancement metadata recorded correctly
- 4.2.1.1.10 Test: Total processing time within acceptable range
- 4.2.1.1.11 Verify: LLM gateway logs show all API calls
- 4.2.1.1.12 Verify: Tool calls to semantic-search logged

##### 4.2.1.2 Batch Document Enhancement
- 4.2.1.2.1 Test: Load multiple documents from fixtures
- 4.2.1.2.2 Test: Submit batch for enhancement
- 4.2.1.2.3 Test: All documents enhanced successfully
- 4.2.1.2.4 Test: Batch processing time reasonable
- 4.2.1.2.5 Test: No cross-contamination between documents
- 4.2.1.2.6 Test: Session isolation verified
- 4.2.1.2.7 Test: Error in one document doesn't fail batch

##### 4.2.1.3 Enhancement with Tool-Use
- 4.2.1.3.1 Test: Enhancement requests corpus search
- 4.2.1.3.2 Test: search_corpus tool executes via gateway
- 4.2.1.3.3 Test: Search results incorporated in enhancement
- 4.2.1.3.4 Test: get_chunk tool retrieves specific chunks
- 4.2.1.3.5 Test: Multiple tool calls in single enhancement
- 4.2.1.3.6 Test: Tool call results visible in final output
- 4.2.1.3.7 Verify: Tool execution metrics recorded

##### 4.2.1.4 Enhancement with Sessions
- 4.2.1.4.1 Test: Session created at enhancement start
- 4.2.1.4.2 Test: Multi-turn conversation within session
- 4.2.1.4.3 Test: Context maintained across turns
- 4.2.1.4.4 Test: Session cleaned up after enhancement
- 4.2.1.4.5 Test: Session expiry handled gracefully
- 4.2.1.4.6 Verify: Session data in Redis during processing

#### 4.2.2 Enhancement Quality Validation

##### 4.2.2.1 Output Quality Tests
- 4.2.2.1.1 Test: Enhanced document is valid Markdown
- 4.2.2.1.2 Test: Cross-references are valid links
- 4.2.2.1.3 Test: Citations reference real sources
- 4.2.2.1.4 Test: No hallucinated references
- 4.2.2.1.5 Test: Footnotes properly formatted
- 4.2.2.1.6 Test: Section structure preserved
- 4.2.2.1.7 Test: No content loss from original

##### 4.2.2.2 Comparison Tests
- 4.2.2.2.1 Compare enhanced output to golden files
- 4.2.2.2.2 Calculate similarity score
- 4.2.2.2.3 Flag significant deviations for review
- 4.2.2.2.4 Track quality metrics over time
- 4.2.2.2.5 Generate quality report

---

### 4.3 LLM Gateway E2E Tests

> **Acceptance Criteria**: All gateway functionality tested end-to-end. Provider routing tested with real providers. Tool execution tested with real downstream services. Session persistence tested with real Redis.

#### 4.3.1 Provider E2E Tests

> **Note**: Only llm-gateway communicates with LLM providers. All other services route through the gateway.

##### 4.3.1.1 Anthropic Provider Tests
- 4.3.1.1.1 Create `tests/e2e/test_providers.py`
- 4.3.1.1.2 Test: Chat completion with Claude model
- 4.3.1.1.3 Test: Streaming completion with Claude
- 4.3.1.1.4 Test: Tool-use with Claude
- 4.3.1.1.5 Test: Long context handling
- 4.3.1.1.6 Test: Rate limit handling
- 4.3.1.1.7 Test: API error handling
- 4.3.1.1.8 Verify: Token usage recorded correctly
- 4.3.1.1.9 Verify: Cost tracking accurate

##### 4.3.1.2 OpenAI Provider Tests
- 4.3.1.2.1 Test: Chat completion with GPT model
- 4.3.1.2.2 Test: Streaming completion with GPT
- 4.3.1.2.3 Test: Function calling with GPT
- 4.3.1.2.4 Test: Long context handling
- 4.3.1.2.5 Test: Rate limit handling
- 4.3.1.2.6 Test: API error handling
- 4.3.1.2.7 Verify: Token usage recorded correctly

##### 4.3.1.3 Ollama Provider Tests (Local)
- 4.3.1.3.1 Test: Chat completion with local model
- 4.3.1.3.2 Test: Model availability detection
- 4.3.1.3.3 Test: Fallback when Ollama unavailable
- 4.3.1.3.4 Test: Performance comparison with cloud providers

##### 4.3.1.4 Provider Routing Tests
- 4.3.1.4.1 Test: claude-* models route to Anthropic
- 4.3.1.4.2 Test: gpt-* models route to OpenAI
- 4.3.1.4.3 Test: Local models route to Ollama
- 4.3.1.4.4 Test: Default provider fallback
- 4.3.1.4.5 Test: Unknown model error handling

#### 4.3.2 Tool Execution E2E Tests

##### 4.3.2.1 Semantic Search Tools
- 4.3.2.1.1 Create `tests/e2e/test_tool_execution.py`
- 4.3.2.1.2 Test: search_corpus returns real results
- 4.3.2.1.3 Test: Search relevance reasonable
- 4.3.2.1.4 Test: get_chunk returns correct chunk
- 4.3.2.1.5 Test: Chunk metadata included
- 4.3.2.1.6 Test: Search with no results handled
- 4.3.2.1.7 Test: Invalid chunk ID handled
- 4.3.2.1.8 Verify: Latency within acceptable range

##### 4.3.2.2 AI Agent Tools
- 4.3.2.2.1 Test: code_review returns analysis
- 4.3.2.2.2 Test: Review findings are actionable
- 4.3.2.2.3 Test: architecture analysis returns insights
- 4.3.2.2.4 Test: doc_generate creates documentation
- 4.3.2.2.5 Test: Agent timeout handling
- 4.3.2.2.6 Test: Agent error handling
- 4.3.2.2.7 Verify: Agent execution metrics recorded

##### 4.3.2.3 Tool Chain Tests
- 4.3.2.3.1 Test: LLM requests tool → tool executes → LLM continues
- 4.3.2.3.2 Test: Multiple sequential tool calls
- 4.3.2.3.3 Test: Parallel tool call execution
- 4.3.2.3.4 Test: Tool result incorporated in final response
- 4.3.2.3.5 Test: Max tool iterations respected
- 4.3.2.3.6 Verify: Complete trace of tool chain

#### 4.3.3 Session E2E Tests

##### 4.3.3.1 Session Lifecycle Tests
- 4.3.3.1.1 Create `tests/e2e/test_sessions.py`
- 4.3.3.1.2 Test: Create session via API
- 4.3.3.1.3 Test: Session persisted in Redis
- 4.3.3.1.4 Test: Retrieve session via API
- 4.3.3.1.5 Test: Session data matches expected
- 4.3.3.1.6 Test: Update session with messages
- 4.3.3.1.7 Test: Delete session removes from Redis
- 4.3.3.1.8 Test: Session TTL enforced

##### 4.3.3.2 Session Context Tests
- 4.3.3.2.1 Test: Multi-turn conversation maintains context
- 4.3.3.2.2 Test: Previous messages included in request
- 4.3.3.2.3 Test: Context window management
- 4.3.3.2.4 Test: Large conversation history handled
- 4.3.3.2.5 Test: Session isolation (no cross-talk)

---

### 4.4 Performance Testing

> **Acceptance Criteria**: Performance benchmarks established for all critical paths. Latency targets met (P50, P95, P99). Throughput targets met (requests/second). Resource utilization within limits.

#### 4.4.1 Latency Benchmarks

##### 4.4.1.1 Gateway Latency Tests
- 4.4.1.1.1 Create `tests/performance/test_latency.py`
- 4.4.1.1.2 Benchmark: Health endpoint latency (<10ms P99)
- 4.4.1.1.3 Benchmark: Session create latency (<50ms P99)
- 4.4.1.1.4 Benchmark: Session get latency (<20ms P99)
- 4.4.1.1.5 Benchmark: Tool list latency (<20ms P99)
- 4.4.1.1.6 Record P50, P95, P99 for each endpoint
- 4.4.1.1.7 Compare against baseline

##### 4.4.1.2 LLM Call Latency Tests
- 4.4.1.2.1 Benchmark: Simple completion (no tools) latency
- 4.4.1.2.2 Benchmark: Completion with tool-use latency
- 4.4.1.2.3 Benchmark: Streaming first-token latency
- 4.4.1.2.4 Track provider-specific latencies
- 4.4.1.2.5 Identify latency bottlenecks
- 4.4.1.2.6 Document acceptable latency ranges

##### 4.4.1.3 Tool Execution Latency Tests
- 4.4.1.3.1 Benchmark: search_corpus latency
- 4.4.1.3.2 Benchmark: get_chunk latency
- 4.4.1.3.3 Benchmark: Agent tool latency
- 4.4.1.3.4 Identify slow tools
- 4.4.1.3.5 Document latency SLOs

#### 4.4.2 Load Testing

##### 4.4.2.1 Load Test Setup
- 4.4.2.1.1 Install load testing tool (locust or k6)
- 4.4.2.1.2 Create `tests/performance/locustfile.py`
- 4.4.2.1.3 Define user scenarios (enhancement workflow)
- 4.4.2.1.4 Configure ramp-up patterns
- 4.4.2.1.5 Configure test duration
- 4.4.2.1.6 Set up metrics collection

##### 4.4.2.2 Concurrent User Tests
- 4.4.2.2.1 Test: 10 concurrent users
- 4.4.2.2.2 Test: 50 concurrent users
- 4.4.2.2.3 Test: 100 concurrent users
- 4.4.2.2.4 Measure response times under load
- 4.4.2.2.5 Measure error rates under load
- 4.4.2.2.6 Identify breaking point
- 4.4.2.2.7 Document capacity limits

##### 4.4.2.3 Sustained Load Tests
- 4.4.2.3.1 Test: Sustained load for 30 minutes
- 4.4.2.3.2 Monitor memory usage over time
- 4.4.2.3.3 Monitor CPU usage over time
- 4.4.2.3.4 Monitor Redis memory over time
- 4.4.2.3.5 Check for memory leaks
- 4.4.2.3.6 Check for connection leaks
- 4.4.2.3.7 Verify graceful degradation

##### 4.4.2.4 Spike Tests
- 4.4.2.4.1 Test: Sudden spike from 10 to 100 users
- 4.4.2.4.2 Measure recovery time
- 4.4.2.4.3 Verify no data loss during spike
- 4.4.2.4.4 Verify error handling during spike
- 4.4.2.4.5 Test auto-scaling behavior (if enabled)

#### 4.4.3 Resource Utilization

##### 4.4.3.1 Resource Monitoring
- 4.4.3.1.1 Monitor CPU usage during tests
- 4.4.3.1.2 Monitor memory usage during tests
- 4.4.3.1.3 Monitor network I/O during tests
- 4.4.3.1.4 Monitor disk I/O during tests
- 4.4.3.1.5 Monitor Redis memory and connections
- 4.4.3.1.6 Generate resource utilization report

##### 4.4.3.2 Resource Limits Validation
- 4.4.3.2.1 Verify container CPU limits respected
- 4.4.3.2.2 Verify container memory limits respected
- 4.4.3.2.3 Test behavior at resource limits
- 4.4.3.2.4 Verify OOM handling graceful
- 4.4.3.2.5 Recommend resource allocations

---

### 4.5 Security Testing

> **Acceptance Criteria**: Security vulnerabilities identified and mitigated. API authentication tested. Input validation tested. No sensitive data leaked in logs or responses. Dependencies scanned for vulnerabilities.

#### 4.5.1 API Security Tests

##### 4.5.1.1 Authentication Tests
- 4.5.1.1.1 Create `tests/security/test_auth.py`
- 4.5.1.1.2 Test: Unauthenticated request rejected (if auth enabled)
- 4.5.1.1.3 Test: Invalid API key rejected
- 4.5.1.1.4 Test: Expired token rejected
- 4.5.1.1.5 Test: Valid authentication succeeds
- 4.5.1.1.6 Test: Rate limiting per API key

##### 4.5.1.2 Authorization Tests
- 4.5.1.2.1 Test: User can only access own sessions
- 4.5.1.2.2 Test: Cannot access other user's data
- 4.5.1.2.3 Test: Admin endpoints protected
- 4.5.1.2.4 Test: CORS configuration correct

##### 4.5.1.3 Input Validation Tests
- 4.5.1.3.1 Create `tests/security/test_input_validation.py`
- 4.5.1.3.2 Test: SQL injection attempts blocked
- 4.5.1.3.3 Test: XSS attempts blocked
- 4.5.1.3.4 Test: Command injection attempts blocked
- 4.5.1.3.5 Test: Oversized payloads rejected
- 4.5.1.3.6 Test: Malformed JSON rejected
- 4.5.1.3.7 Test: Invalid model names rejected
- 4.5.1.3.8 Test: Path traversal attempts blocked

#### 4.5.2 Data Security Tests

##### 4.5.2.1 Sensitive Data Handling
- 4.5.2.1.1 Test: API keys not logged
- 4.5.2.1.2 Test: API keys not in error responses
- 4.5.2.1.3 Test: Session data encrypted at rest (if applicable)
- 4.5.2.1.4 Test: PII redacted from logs
- 4.5.2.1.5 Test: Conversation content not leaked
- 4.5.2.1.6 Audit log content for sensitive data

##### 4.5.2.2 Secret Management Tests
- 4.5.2.2.1 Verify secrets not in container image
- 4.5.2.2.2 Verify secrets not in environment dump
- 4.5.2.2.3 Verify secrets loaded from secure source
- 4.5.2.2.4 Test secret rotation handling
- 4.5.2.2.5 Verify no hardcoded secrets in code

#### 4.5.3 Dependency Security

##### 4.5.3.1 Vulnerability Scanning
- 4.5.3.1.1 Run `pip-audit` on dependencies
- 4.5.3.1.2 Run `trivy` on container image
- 4.5.3.1.3 Run `snyk` scan (optional)
- 4.5.3.1.4 Document all findings
- 4.5.3.1.5 Prioritize and remediate critical vulnerabilities
- 4.5.3.1.6 Create exceptions for accepted risks
- 4.5.3.1.7 Add security scanning to CI pipeline

##### 4.5.3.2 Container Security
- 4.5.3.2.1 Verify running as non-root user
- 4.5.3.2.2 Verify read-only filesystem
- 4.5.3.2.3 Verify no unnecessary capabilities
- 4.5.3.2.4 Verify no privileged containers
- 4.5.3.2.5 Scan base image for vulnerabilities

---

### 4.6 Failure Mode Testing

> **Acceptance Criteria**: System behaves gracefully under failure conditions. Circuit breakers activate correctly. Fallbacks work as expected. Recovery is automatic when possible. Failures are logged and alerted.

#### 4.6.1 Dependency Failure Tests

##### 4.6.1.1 Redis Failure Tests
- 4.6.1.1.1 Create `tests/e2e/test_failure_modes.py`
- 4.6.1.1.2 Test: Gateway behavior when Redis unavailable
- 4.6.1.1.3 Test: Health endpoint reports degraded
- 4.6.1.1.4 Test: Session operations fail gracefully
- 4.6.1.1.5 Test: Chat completions without session still work
- 4.6.1.1.6 Test: Recovery when Redis comes back
- 4.6.1.1.7 Test: No data corruption on Redis restart

##### 4.6.1.2 Semantic Search Failure Tests
- 4.6.1.2.1 Test: Gateway behavior when semantic-search down
- 4.6.1.2.2 Test: search_corpus tool returns error
- 4.6.1.2.3 Test: Error propagated to LLM appropriately
- 4.6.1.2.4 Test: Circuit breaker opens after failures
- 4.6.1.2.5 Test: Circuit breaker recovery
- 4.6.1.2.6 Test: Chat without search tools still works

##### 4.6.1.3 AI Agents Failure Tests
- 4.6.1.3.1 Test: Gateway behavior when ai-agents down
- 4.6.1.3.2 Test: Agent tools return error
- 4.6.1.3.3 Test: Error propagated to LLM appropriately
- 4.6.1.3.4 Test: Chat without agent tools still works

##### 4.6.1.4 LLM Provider Failure Tests
- 4.6.1.4.1 Test: Behavior on Anthropic API outage
- 4.6.1.4.2 Test: Behavior on OpenAI API outage
- 4.6.1.4.3 Test: Provider fallback (if configured)
- 4.6.1.4.4 Test: Rate limit handling
- 4.6.1.4.5 Test: Timeout handling
- 4.6.1.4.6 Test: Retry behavior

#### 4.6.2 Network Failure Tests

##### 4.6.2.1 Network Partition Tests
- 4.6.2.1.1 Simulate network partition between services
- 4.6.2.1.2 Test: Gateway handles network timeouts
- 4.6.2.1.3 Test: Partial failures handled gracefully
- 4.6.2.1.4 Test: Recovery after partition heals
- 4.6.2.1.5 Document recovery procedures

##### 4.6.2.2 DNS Failure Tests
- 4.6.2.2.1 Test: Behavior when DNS resolution fails
- 4.6.2.2.2 Test: Cached DNS handling
- 4.6.2.2.3 Test: Recovery when DNS restored

#### 4.6.3 Chaos Engineering (Optional)

##### 4.6.3.1 Chaos Tests
- 4.6.3.1.1 Install chaos testing tool (chaos-mesh, litmus)
- 4.6.3.1.2 Define chaos experiments
- 4.6.3.1.3 Run pod kill experiments
- 4.6.3.1.4 Run network delay experiments
- 4.6.3.1.5 Run resource stress experiments
- 4.6.3.1.6 Document system resilience findings

---

### 4.7 Staging Deployment Validation

> **Acceptance Criteria**: System deployed to staging environment successfully. All E2E tests pass in staging. Performance meets targets in staging. Staging mirrors production configuration.

#### 4.7.1 Staging Deployment

##### 4.7.1.1 Deploy to Staging
- 4.7.1.1.1 Trigger CD pipeline to staging
- 4.7.1.1.2 Verify deployment completes successfully
- 4.7.1.1.3 Verify all pods running and healthy
- 4.7.1.1.4 Verify service endpoints accessible
- 4.7.1.1.5 Verify ingress/load balancer configured
- 4.7.1.1.6 Verify TLS certificates valid

##### 4.7.1.2 Staging Configuration Validation
- 4.7.1.2.1 Verify ConfigMaps applied correctly
- 4.7.1.2.2 Verify Secrets accessible (not values)
- 4.7.1.2.3 Verify resource limits applied
- 4.7.1.2.4 Verify HPA configured
- 4.7.1.2.5 Verify network policies active
- 4.7.1.2.6 Verify monitoring configured

#### 4.7.2 Staging E2E Tests

##### 4.7.2.1 Run E2E Suite in Staging
- 4.7.2.1.1 Configure E2E tests for staging environment
- 4.7.2.1.2 Run full E2E test suite
- 4.7.2.1.3 Run document enhancement tests
- 4.7.2.1.4 Run provider tests with real APIs
- 4.7.2.1.5 Run tool execution tests
- 4.7.2.1.6 Run session tests
- 4.7.2.1.7 Verify all tests pass
- 4.7.2.1.8 Generate test report

##### 4.7.2.2 Staging Performance Validation
- 4.7.2.2.1 Run latency benchmarks in staging
- 4.7.2.2.2 Compare to local benchmarks
- 4.7.2.2.3 Run load tests in staging
- 4.7.2.2.4 Verify performance meets targets
- 4.7.2.2.5 Identify any staging-specific issues

#### 4.7.3 Staging Monitoring Validation

##### 4.7.3.1 Observability Validation
- 4.7.3.1.1 Verify logs flowing to log aggregator
- 4.7.3.1.2 Verify metrics scraped by Prometheus
- 4.7.3.1.3 Verify traces collected by tracing backend
- 4.7.3.1.4 Verify dashboards show data
- 4.7.3.1.5 Verify alerts configured and working
- 4.7.3.1.6 Test alert notification channel

---

### 4.8 Production Readiness Checklist

> **Acceptance Criteria**: All production readiness criteria satisfied. Sign-off obtained from stakeholders. Runbook validated. Rollback procedure tested.

#### 4.8.1 Technical Readiness

##### 4.8.1.1 Code Quality
- 4.8.1.1.1 All unit tests pass
- 4.8.1.1.2 All integration tests pass
- 4.8.1.1.3 All E2E tests pass
- 4.8.1.1.4 Code coverage ≥80%
- 4.8.1.1.5 No critical linting errors
- 4.8.1.1.6 Type checking passes
- 4.8.1.1.7 No known critical bugs

##### 4.8.1.2 Security Readiness
- 4.8.1.2.1 Security tests pass
- 4.8.1.2.2 No critical vulnerabilities in dependencies
- 4.8.1.2.3 Secrets management configured
- 4.8.1.2.4 Network policies in place
- 4.8.1.2.5 Security review completed (if required)

##### 4.8.1.3 Performance Readiness
- 4.8.1.3.1 Performance targets met
- 4.8.1.3.2 Load testing completed
- 4.8.1.3.3 Resource limits validated
- 4.8.1.3.4 Autoscaling tested
- 4.8.1.3.5 No memory leaks detected

##### 4.8.1.4 Reliability Readiness
- 4.8.1.4.1 Failure mode testing completed
- 4.8.1.4.2 Circuit breakers configured
- 4.8.1.4.3 Retry logic validated
- 4.8.1.4.4 Health checks working
- 4.8.1.4.5 Graceful shutdown working

#### 4.8.2 Operational Readiness

##### 4.8.2.1 Documentation
- 4.8.2.1.1 API documentation complete
- 4.8.2.1.2 Architecture documentation updated
- 4.8.2.1.3 Runbook complete and validated
- 4.8.2.1.4 Troubleshooting guide complete
- 4.8.2.1.5 Configuration documentation complete

##### 4.8.2.2 Monitoring & Alerting
- 4.8.2.2.1 Dashboards created and tested
- 4.8.2.2.2 Alerts defined for critical metrics
- 4.8.2.2.3 On-call rotation defined
- 4.8.2.2.4 Escalation procedures documented
- 4.8.2.2.5 Incident response plan created

##### 4.8.2.3 Deployment Procedures
- 4.8.2.3.1 Deployment procedure documented
- 4.8.2.3.2 Rollback procedure documented and tested
- 4.8.2.3.3 Blue-green or canary strategy defined
- 4.8.2.3.4 Database migration strategy (if applicable)
- 4.8.2.3.5 Feature flag strategy (if applicable)

#### 4.8.3 Sign-off

##### 4.8.3.1 Stakeholder Approval
- 4.8.3.1.1 Technical lead sign-off
- 4.8.3.1.2 Security review sign-off (if required)
- 4.8.3.1.3 Operations team sign-off
- 4.8.3.1.4 Product owner sign-off
- 4.8.3.1.5 Document all sign-offs

##### 4.8.3.2 Go-Live Decision
- 4.8.3.2.1 Schedule go-live window
- 4.8.3.2.2 Communicate to stakeholders
- 4.8.3.2.3 Prepare rollback plan
- 4.8.3.2.4 Ensure team availability
- 4.8.3.2.5 Execute deployment to production

---

### 4.9 Production Deployment

> **Acceptance Criteria**: System deployed to production successfully. Smoke tests pass. Monitoring confirms healthy operation. No degradation to existing systems.

#### 4.9.1 Production Deployment Execution

##### 4.9.1.1 Pre-Deployment
- 4.9.1.1.1 Notify stakeholders of deployment
- 4.9.1.1.2 Verify staging sign-off complete
- 4.9.1.1.3 Verify rollback plan ready
- 4.9.1.1.4 Verify team availability
- 4.9.1.1.5 Take pre-deployment snapshot (if applicable)

##### 4.9.1.2 Deployment
- 4.9.1.2.1 Trigger CD pipeline to production
- 4.9.1.2.2 Monitor deployment progress
- 4.9.1.2.3 Verify rolling update proceeds correctly
- 4.9.1.2.4 Verify old pods drain gracefully
- 4.9.1.2.5 Verify new pods become healthy
- 4.9.1.2.6 Verify service continuity during deployment

##### 4.9.1.3 Post-Deployment Verification
- 4.9.1.3.1 Run production smoke tests
- 4.9.1.3.2 Verify health endpoints healthy
- 4.9.1.3.3 Verify key functionality working
- 4.9.1.3.4 Check error rates in monitoring
- 4.9.1.3.5 Check latency metrics
- 4.9.1.3.6 Verify logs flowing correctly
- 4.9.1.3.7 Monitor for 30 minutes post-deployment

#### 4.9.2 Production Validation

##### 4.9.2.1 Functional Validation
- 4.9.2.1.1 Test document enhancement in production
- 4.9.2.1.2 Test tool execution in production
- 4.9.2.1.3 Test session management in production
- 4.9.2.1.4 Verify downstream service connectivity
- 4.9.2.1.5 Verify provider API connectivity

##### 4.9.2.2 Monitoring Validation
- 4.9.2.2.1 Verify metrics visible in dashboards
- 4.9.2.2.2 Verify logs searchable
- 4.9.2.2.3 Verify traces complete
- 4.9.2.2.4 Verify alerts not firing (false positives)
- 4.9.2.2.5 Document baseline metrics

---

### 4.10 Stage 4 Validation and Sign-off

> **Acceptance Criteria**: All Stage 4 tasks completed. All tests pass. Production deployment successful. System operating normally in production.

#### 4.10.1 Final Validation

##### 4.10.1.1 Test Summary
- 4.10.1.1.1 Compile E2E test results
- 4.10.1.1.2 Compile performance test results
- 4.10.1.1.3 Compile security test results
- 4.10.1.1.4 Compile staging validation results
- 4.10.1.1.5 Document any open issues
- 4.10.1.1.6 Generate final test report

##### 4.10.1.2 Production Status
- 4.10.1.2.1 Verify production running smoothly
- 4.10.1.2.2 Document production metrics baseline
- 4.10.1.2.3 Confirm no incidents post-deployment
- 4.10.1.2.4 Close deployment ticket/issue
- 4.10.1.2.5 Celebrate successful launch! 🎉

##### 4.10.1.3 Retrospective
- 4.10.1.3.1 Schedule retrospective meeting
- 4.10.1.3.2 Document lessons learned
- 4.10.1.3.3 Identify process improvements
- 4.10.1.3.4 Update documentation based on learnings
- 4.10.1.3.5 Plan follow-up improvements

---

## 11. Validation Checklist

| Item | Command | Expected Result |
|------|---------|-----------------|
| Dockerfile builds | `docker build -t llm-gateway .` | Exit 0 |
| Container starts | `docker run llm-gateway` | Health endpoint returns 200 |
| Non-root user | `docker run llm-gateway whoami` | `appuser` |
| Kustomize validates | `kubectl kustomize deploy/kubernetes/base` | Valid YAML |
| Helm lint | `helm lint deploy/helm/llm-gateway` | 0 chart(s) failed |
| Network policy test | `kubectl exec ... -- curl semantic-search:8081` | Connection allowed |
| Network policy deny | `kubectl exec ... -- curl unauthorized:8080` | Connection refused |

---

## References

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Service architecture
- [INTEGRATION_MAP.md](./INTEGRATION_MAP.md) - Multi-service integration
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
