# Gateway Routing Refactor WBS

**Objective**: Route ALL external requests through LLM Gateway per Kitchen Brigade architecture

**Created**: December 2025  
**Status**: 🟡 PARTIALLY COMPLETE  
**Last Updated**: December 12, 2025  
**TDD Methodology**: RED → GREEN → REFACTOR  

---

## Implementation Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| GatewayProvider | ✅ COMPLETE | `workflows/shared/providers/gateway_provider.py` |
| GatewaySearchClient | ✅ COMPLETE | `workflows/shared/clients/gateway_search_client.py` |
| Factory Pattern | ✅ COMPLETE | `llm_enhance_guideline.py` uses `create_llm_provider()` |
| Unit Tests | ✅ COMPLETE | `tests/unit/providers/`, `tests/unit/clients/` |
| Integration Tests | ✅ COMPLETE | `tests/integration/test_gateway_routing.py` |
| E2E Tests | ✅ COMPLETE | `tests/e2e/test_gateway_routing_e2e.py` |
| ai-agents Config | ❌ PENDING | Still defaults to `:8081` in `src/core/config.py` |
| Metadata Enrichment | ❌ PENDING | `enrich_metadata_per_book.py` uses direct `:8081` |
| Docker Compose Defaults | ❌ PENDING | Still hardcodes semantic-search URLs |

---

## Executive Summary

### Original State (PROBLEM)
- ~~`llm_enhance_guideline.py` calls Anthropic SDK **directly** (bypasses Gateway)~~ ✅ FIXED
- `search_client.py` calls semantic-search:8081 **directly** (bypasses Gateway) - **STILL AN ISSUE**
- `ai-agents` calls semantic-search:8081 **directly** (bypasses Gateway) - **STILL AN ISSUE**

### Target State (SOLUTION)
- ALL LLM requests → Gateway `/v1/chat/completions` ✅ COMPLETE
- ALL search requests → Gateway tool `search_corpus` - **PENDING**
- ALL cross-reference requests → Gateway tool `cross_reference` - **PENDING**

### Reference Documents
| Priority | Document | Key Pattern |
|----------|----------|-------------|
| 1 | ARCHITECTURE.md | Kitchen Brigade "Router" - Gateway is single entry point |
| 2 | CODING_PATTERNS_ANALYSIS.md | Anti-Pattern #12 - Connection pooling, no new client per request |
| 3 | TIER_RELATIONSHIP_DIAGRAM.md | 7-step workflow with content retrieval |
| 4 | Comp_Static_Analysis_Report_20251203.md | 52 resolved anti-patterns |

---

## Phase 1: Infrastructure Verification
**Gate 0**: ✅ COMPLETE (verified 2025-01-XX)

| ID | Task | Status | Verification |
|----|------|--------|--------------|
| 1.1 | Gateway service running | ✅ PASS | curl :8080/health → healthy |
| 1.2 | Semantic-search running | ✅ PASS | curl :8081/health → healthy |
| 1.3 | ai-agents running | ✅ PASS | curl :8082/health → healthy |
| 1.4 | Neo4j running | ✅ PASS | curl :7474 → 200 |
| 1.5 | Qdrant running | ✅ PASS | curl :6333/collections → 200 |
| 1.6 | Redis running | ✅ PASS | docker ps shows redis |

---

## Phase 2: TDD RED - Write Failing Tests

### 2.1 LLM Provider Factory Tests
**File**: `tests/unit/providers/test_factory_gateway_default.py`  
**Status**: ✅ TESTS WRITTEN AND PASSING

| ID | Test Case | Status | Description |
|----|-----------|--------|-------------|
| 2.1.1 | test_default_provider_is_gateway | ✅ GREEN | Factory returns GatewayProvider by default |
| 2.1.2 | test_env_override_still_works | ✅ GREEN | LLM_PROVIDER=anthropic still works |
| 2.1.3 | test_gateway_url_from_env | ✅ GREEN | LLM_GATEWAY_URL configures GatewayProvider |

### 2.2 Search Client Gateway Routing Tests
**File**: `tests/unit/clients/test_search_via_gateway.py`  
**Status**: ✅ TESTS WRITTEN AND PASSING

| ID | Test Case | Status | Description |
|----|-----------|--------|-------------|
| 2.2.1 | test_search_calls_gateway_tool | ✅ GREEN | GatewaySearchClient uses Gateway search_corpus tool |
| 2.2.2 | test_hybrid_search_via_gateway | 🔴 RED | hybrid_search should proxy through Gateway |
| 2.2.3 | test_embed_via_gateway | 🔴 RED | embed() should use Gateway endpoint |

### 2.3 Integration Tests
**File**: `tests/integration/test_gateway_routing.py`

| ID | Test Case | Status | Description |
|----|-----------|--------|-------------|
| 2.3.1 | test_no_direct_8081_calls | 🔴 RED | Verify no traffic to :8081 during enhancement |
| 2.3.2 | test_all_traffic_via_8080 | 🔴 RED | All requests should go through :8080 |
| 2.3.3 | test_tool_execution_via_gateway | 🔴 RED | search_corpus tool executes via Gateway |

---

## Phase 3: TDD GREEN - Implement Gateway Routing

### 3.1 Factory Default Change
**File**: `workflows/shared/providers/factory.py`

| ID | Task | Status | Change |
|----|------|--------|--------|
| 3.1.1 | Change default provider | 🟡 PENDING | `os.getenv("LLM_PROVIDER", "anthropic")` → `os.getenv("LLM_PROVIDER", "gateway")` |

```python
# BEFORE (line 47)
provider_name = os.getenv("LLM_PROVIDER", "anthropic").lower()

# AFTER
provider_name = os.getenv("LLM_PROVIDER", "gateway").lower()
```

### 3.2 Gateway Search Client
**File**: `workflows/shared/clients/gateway_search_client.py` (NEW)

| ID | Task | Status | Description |
|----|------|--------|-------------|
| 3.2.1 | Create GatewaySearchClient | 🟡 PENDING | Adapter that calls Gateway tools |
| 3.2.2 | Implement search() via search_corpus | 🟡 PENDING | Use Gateway tool execution |
| 3.2.3 | Implement hybrid_search() | 🟡 PENDING | Route through Gateway |
| 3.2.4 | Add connection pooling | 🟡 PENDING | Anti-Pattern #12 prevention |

### 3.3 Update llm_enhance_guideline.py
**File**: `workflows/llm_enhancement/scripts/llm_enhance_guideline.py`

| ID | Task | Status | Change |
|----|------|--------|--------|
| 3.3.1 | Change import | 🟡 PENDING | `from workflows.shared.providers import AnthropicProvider` → `from workflows.shared.providers import GatewayProvider` |
| 3.3.2 | Use factory instead | 🟡 PENDING | `provider = create_llm_provider()` (respects env var) |

### 3.4 Docker Compose Environment
**File**: `docker-compose.yml`

| ID | Task | Status | Change |
|----|------|--------|--------|
| 3.4.1 | Add LLM_PROVIDER env | 🟡 PENDING | `LLM_PROVIDER=gateway` |
| 3.4.2 | Add LLM_GATEWAY_URL env | 🟡 PENDING | `LLM_GATEWAY_URL=http://llm-gateway:8080` |

---

## Phase 4: TDD REFACTOR - Optimize & Cleanup

### 4.1 Remove Direct Dependencies

| ID | Task | Status | Description |
|----|------|--------|-------------|
| 4.1.1 | Audit for direct :8081 calls | 🟡 PENDING | grep for localhost:8081 |
| 4.1.2 | Update SemanticSearchClient | 🟡 PENDING | Deprecate or proxy through Gateway |
| 4.1.3 | Remove unused anthropic import | 🟡 PENDING | If not needed as fallback |

### 4.2 Documentation Updates

| ID | Task | Status | Description |
|----|------|--------|-------------|
| 4.2.1 | Update ARCHITECTURE.md | 🟡 PENDING | Document new data flow |
| 4.2.2 | Update README.md | 🟡 PENDING | Add Gateway configuration |
| 4.2.3 | Add ADR for routing decision | 🟡 PENDING | Architecture Decision Record |

---

## Phase 5: Verification

### 5.1 Unit Test Pass

| ID | Test | Status | Command |
|----|------|--------|---------|
| 5.1.1 | All factory tests pass | 🟡 PENDING | `pytest tests/unit/providers/` |
| 5.1.2 | All client tests pass | 🟡 PENDING | `pytest tests/unit/clients/` |

### 5.2 Integration Test Pass

| ID | Test | Status | Command |
|----|------|--------|---------|
| 5.2.1 | Gateway routing tests | 🟡 PENDING | `pytest tests/integration/test_gateway_routing.py` |
| 5.2.2 | E2E enhancement test | 🟡 PENDING | Run full enhancement with Gateway |

### 5.3 Traffic Verification

| ID | Check | Status | Method |
|----|-------|--------|--------|
| 5.3.1 | No direct :8081 traffic | 🟡 PENDING | tcpdump or Gateway logs |
| 5.3.2 | All traffic via :8080 | 🟡 PENDING | Gateway access logs |
| 5.3.3 | Circuit breaker engaged | 🟡 PENDING | Gateway metrics |

---

## Dependencies

```
Phase 1 ✅ → Phase 2 🔴 → Phase 3 🟢 → Phase 4 ♻️ → Phase 5 ✔️
     │           │           │           │
     └───────────┴───────────┴───────────┘
            Services must be running
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gateway single point of failure | HIGH | Circuit breaker, health checks |
| Latency increase from proxy | MEDIUM | Connection pooling, keep-alive |
| Breaking existing functionality | HIGH | TDD approach, feature flags |

---

## Success Criteria

✅ All tests pass (unit + integration)  
✅ Zero direct calls to :8081 from llm-document-enhancer  
✅ All LLM requests route through Gateway :8080  
✅ All search requests use Gateway tools  
✅ Comp_Static_Analysis patterns maintained  

---

## Appendix: Files to Modify

| File | Type | Change |
|------|------|--------|
| `workflows/shared/providers/factory.py` | MODIFY | Default to gateway |
| `workflows/shared/clients/gateway_search_client.py` | CREATE | New Gateway search adapter |
| `workflows/llm_enhancement/scripts/llm_enhance_guideline.py` | MODIFY | Use factory, not AnthropicProvider |
| `docker-compose.yml` | MODIFY | Add LLM_PROVIDER env |
| `tests/unit/providers/test_factory_gateway_default.py` | CREATE | RED phase tests |
| `tests/unit/clients/test_search_via_gateway.py` | CREATE | RED phase tests |
| `tests/integration/test_gateway_routing.py` | CREATE | Integration tests |
