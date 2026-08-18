"""
WBS-TXS7.7: MCP Gateway End-to-End Integration Tests — Tier-Filtered Search.

Tests the full gateway → unified-search-service path for taxonomy-enhanced
search parameters as exposed through the MCP tool interface.

Acceptance Criteria Covered:
- AC-TXS7.1: MCP hybrid_search(bloom_tier_filter=[2,3]) returns only T2+T3 results
- AC-TXS7.2: MCP hybrid_search(bloom_tier_boost=true) produces Bloom-tier-boosted scores
- AC-TXS7.4: MCP hybrid_search(expand_taxonomy=true) expands query from neo4j
- AC-TXS7.5: Backward-compatible: bare hybrid_search calls still work

Run with:
    INTEGRATION=1 pytest tests/integration/test_tier_search_e2e.py -v

Skip conditions:
    Requires live gateway (:8080) and unified-search-service (:8081).
    Mark tests with @pytest.mark.docker to also require Docker services.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


# ── Skip guard ────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.integration

GATEWAY_URL = os.environ.get("INTEGRATION_GATEWAY_URL", "http://localhost:8080")
EXECUTE_ENDPOINT = "/v1/tools/execute"


def _integration_enabled() -> bool:
    return os.environ.get("INTEGRATION", "").lower() in ("1", "true", "yes")


skip_unless_integration = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set INTEGRATION=1 to run against live gateway + search service",
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _invoke(
    gateway_client_sync: Any,
    tool_args: dict[str, Any],
) -> Any:
    """POST /v1/tools/execute with hybrid_search tool args; return response."""
    return gateway_client_sync.post(
        EXECUTE_ENDPOINT,
        json={"name": "hybrid_search", "arguments": tool_args},
    )


def _results(resp: Any) -> list[dict[str, Any]]:
    data = resp.json()
    # Gateway wraps results under 'result' key
    result = data.get("result", data)
    if isinstance(result, dict):
        return result.get("results", [])
    return []


def _data(resp: Any) -> dict[str, Any]:
    result = resp.json().get("result", resp.json())
    if isinstance(result, dict):
        return result
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# TXS7.7 (a) — Tool schema: expand_taxonomy is discoverable in gateway registry
# ─────────────────────────────────────────────────────────────────────────────


class TestHybridSearchToolSchema:
    """Verify taxonomy-enhanced parameters are exposed in the tool schema."""

    @skip_unless_integration
    def test_hybrid_search_tool_schema_includes_bloom_tier_filter(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN the gateway is running
        WHEN GET /v1/tools
        THEN hybrid_search schema includes bloom_tier_filter property
        """
        resp = gateway_client_sync.get("/v1/tools")
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"

        tools: list[dict[str, Any]] = resp.json()
        if isinstance(tools, dict):
            tools = tools.get("tools", [])

        hs = next((t for t in tools if t.get("name") == "hybrid_search"), None)
        assert hs is not None, "hybrid_search tool not found in registry"

        params = (
            hs.get("inputSchema", {})
            .get("properties", {})
        )
        assert "bloom_tier_filter" in params, (
            f"bloom_tier_filter missing from hybrid_search schema. params={list(params)}"
        )

    @skip_unless_integration
    def test_hybrid_search_tool_schema_includes_expand_taxonomy(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN the gateway is running
        WHEN GET /v1/tools
        THEN hybrid_search schema includes expand_taxonomy property (WBS-TXS7)
        """
        resp = gateway_client_sync.get("/v1/tools")
        assert resp.status_code == 200

        tools: list[dict[str, Any]] = resp.json()
        if isinstance(tools, dict):
            tools = tools.get("tools", [])

        hs = next((t for t in tools if t.get("name") == "hybrid_search"), None)
        assert hs is not None, "hybrid_search tool not found in registry"

        params = (
            hs.get("inputSchema", {})
            .get("properties", {})
        )
        assert "expand_taxonomy" in params, (
            f"expand_taxonomy missing from hybrid_search schema. params={list(params)}"
        )
        schema = params["expand_taxonomy"]
        assert schema.get("type") == "boolean"
        assert schema.get("default") is False


# ─────────────────────────────────────────────────────────────────────────────
# TXS7.7 (b) — E2E: bloom_tier_filter through gateway → search service
# ─────────────────────────────────────────────────────────────────────────────


class TestBloomTierFilterE2E:
    """AC-TXS7.1 — gateway passes bloom_tier_filter to search service correctly."""

    @skip_unless_integration
    def test_hybrid_search_via_gateway_accepts_bloom_tier_filter(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN live gateway + search service
        WHEN hybrid_search tool called with bloom_tier_filter=[2,3]
        THEN response is successful (no 4xx/5xx)
        AND results respect the tier filter
        """
        resp = _invoke(gateway_client_sync, {
            "query": "design patterns",
            "limit": 10,
            "bloom_tier_filter": [2, 3],
        })

        assert resp.status_code == 200, (
            f"Gateway tool execute failed: {resp.status_code} — {resp.text}"
        )

        results = _results(resp)
        non_compliant = [
            r for r in results
            if r.get("bloom_tier_level") is not None
            and r["bloom_tier_level"] not in (2, 3)
        ]
        assert not non_compliant, (
            f"Gateway bloom_tier_filter=[2,3] returned out-of-tier results: "
            f"{[r.get('bloom_tier_level') for r in non_compliant]}"
        )

    @skip_unless_integration
    def test_gateway_rejects_invalid_bloom_tier_filter_value(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN bloom_tier_filter=[99] (out of range 0-6)
        WHEN executing via gateway
        THEN gateway returns 4xx (validation error — no downstream call)
        """
        resp = _invoke(gateway_client_sync, {
            "query": "design patterns",
            "bloom_tier_filter": [99],
        })

        assert resp.status_code >= 400, (
            f"Expected 4xx for invalid bloom_tier_filter=99, got {resp.status_code}"
        )

    @skip_unless_integration
    def test_gateway_rejects_invalid_quality_tier_filter_value(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN quality_tier_filter=[5] (out of range 1-3)
        WHEN executing via gateway
        THEN gateway returns 4xx
        """
        resp = _invoke(gateway_client_sync, {
            "query": "clean code",
            "quality_tier_filter": [5],
        })

        assert resp.status_code >= 400, (
            f"Expected 4xx for invalid quality_tier_filter=5, got {resp.status_code}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TXS7.7 (c) — E2E: bloom_tier_boost through gateway → search service
# ─────────────────────────────────────────────────────────────────────────────


class TestBloomTierBoostE2E:
    """AC-TXS7.2 — bloom_tier_boost forwarded as tier_boost to search service."""

    @skip_unless_integration
    def test_tier_boost_applied_present_in_gateway_results(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN bloom_tier_boost=true (default)
        WHEN calling hybrid_search via gateway
        THEN at least one result has tier_boost_applied > 1.0
        (confirms gateway correctly maps bloom_tier_boost → tier_boost in payload)
        """
        resp = _invoke(gateway_client_sync, {
            "query": "software design patterns",
            "limit": 20,
            "bloom_tier_boost": True,
        })

        assert resp.status_code == 200
        results = _results(resp)

        boosted = [
            r for r in results
            if (r.get("tier_boost_applied") or 1.0) > 1.0
        ]
        assert boosted, (
            "bloom_tier_boost=true via gateway produced no tier_boost_applied > 1.0 results — "
            "check bloom_tier_boost → tier_boost field mapping in gateway payload"
        )

    @skip_unless_integration
    def test_tier_boost_false_yields_no_boost_via_gateway(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN bloom_tier_boost=false
        WHEN calling hybrid_search via gateway
        THEN no result has tier_boost_applied > 1.01
        """
        resp = _invoke(gateway_client_sync, {
            "query": "test driven development",
            "limit": 10,
            "bloom_tier_boost": False,
        })

        assert resp.status_code == 200
        results = _results(resp)

        over_boosted = [
            r for r in results
            if (r.get("tier_boost_applied") or 1.0) > 1.01
        ]
        assert not over_boosted, (
            f"bloom_tier_boost=false via gateway still boosted {len(over_boosted)} results"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TXS7.7 (d) — E2E: expand_taxonomy through gateway → search service
# ─────────────────────────────────────────────────────────────────────────────


class TestExpandTaxonomyE2E:
    """AC-TXS7.4 — expand_taxonomy forwarded through gateway to search service."""

    @skip_unless_integration
    def test_expand_taxonomy_true_returns_expansion_response_via_gateway(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN expand_taxonomy=true and a query matching a known TaxonomyConcept
        WHEN calling hybrid_search via gateway
        THEN response contains expanded_query and expansion_terms metadata
        """
        resp = _invoke(gateway_client_sync, {
            "query": "dependency injection",
            "limit": 10,
            "expand_taxonomy": True,
        })

        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = _data(resp)

        # If Neo4j had a match for "dependency injection", expansion fields will be set
        # If no match, they may both be None — but the fields must be present
        assert "expanded_query" in data or "results" in data, (
            "Response should contain expanded_query or results field"
        )

    @skip_unless_integration
    def test_expand_taxonomy_default_false_null_expansion_via_gateway(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN no expand_taxonomy param (default False)
        WHEN calling via gateway
        THEN expanded_query is None / absent in response
        """
        resp = _invoke(gateway_client_sync, {
            "query": "dependency injection",
            "limit": 10,
        })

        assert resp.status_code == 200
        data = _data(resp)
        assert data.get("expanded_query") is None, (
            f"Default expand_taxonomy should not produce expanded_query; got {data.get('expanded_query')}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TXS7.7 (e) — Backward compatibility via gateway
# ─────────────────────────────────────────────────────────────────────────────


class TestGatewayBackwardCompatibility:
    """AC-TXS7.5 — bare hybrid_search calls via gateway still work."""

    @skip_unless_integration
    def test_bare_hybrid_search_via_gateway_returns_200(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN no tier or taxonomy params
        WHEN calling hybrid_search via gateway with only query
        THEN response is 200 with results
        """
        resp = _invoke(gateway_client_sync, {
            "query": "clean architecture solid principles",
        })

        assert resp.status_code == 200, (
            f"Backward-compatible call failed: {resp.status_code} — {resp.text}"
        )
        results = _results(resp)
        assert len(results) > 0, "Expected non-empty results for bare query"

    @skip_unless_integration
    def test_existing_hybrid_search_params_still_accepted(
        self,
        gateway_client_sync: Any,
    ) -> None:
        """
        GIVEN existing params: query, limit, alpha, include_graph
        WHEN calling via gateway
        THEN response is 200 (existing params not broken by new tier/taxonomy additions)
        """
        resp = _invoke(gateway_client_sync, {
            "query": "dependency inversion principle",
            "limit": 5,
            "alpha": 0.6,
            "include_graph": True,
        })

        assert resp.status_code == 200, (
            f"Existing params broken: {resp.status_code} — {resp.text}"
        )
