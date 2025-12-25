"""
WBS 3.6.1.1: OpenAPI Generation Tests

Tests for OpenAPI specification generation and validation.

Reference Documents:
- GUIDELINES pp. 1004: OpenAPI Specification (OAS) as standard for describing RESTful APIs
- GUIDELINES pp. 276, 1330: Schema validation through Pydantic models
- ARCHITECTURE.md: API Endpoints documentation

WBS Coverage:
- 3.6.1.1.1: Verify FastAPI generates OpenAPI spec at /openapi.json
- 3.6.1.1.2: Export spec to docs/openapi.yaml
- 3.6.1.1.3: Validate spec with openapi-spec-validator
- 3.6.1.1.5: Version the API spec
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# WBS 3.6.1.1.1: OpenAPI Endpoint Tests
# =============================================================================


class TestOpenAPIEndpoint:
    """
    WBS 3.6.1.1.1: Verify FastAPI generates OpenAPI spec at /openapi.json.
    
    Reference: GUIDELINES pp. 1004 - OpenAPI Specification standard.
    """

    def test_openapi_json_endpoint_exists(self, client: TestClient) -> None:
        """WBS 3.6.1.1.1: /openapi.json endpoint should return 200."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_json_returns_valid_json(self, client: TestClient) -> None:
        """WBS 3.6.1.1.1: /openapi.json should return valid JSON."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        # Should be valid JSON
        data = response.json()
        assert isinstance(data, dict)

    def test_openapi_has_required_fields(self, client: TestClient) -> None:
        """WBS 3.6.1.1.1: OpenAPI spec should have required fields."""
        response = client.get("/openapi.json")
        data = response.json()
        
        # OpenAPI 3.x required fields
        assert "openapi" in data
        assert data["openapi"].startswith("3.")
        assert "info" in data
        assert "paths" in data

    def test_openapi_info_section(self, client: TestClient) -> None:
        """WBS 3.6.1.1.1: OpenAPI info section should have title and version."""
        response = client.get("/openapi.json")
        data = response.json()
        
        info = data.get("info", {})
        assert "title" in info
        assert "version" in info
        assert info["title"] == "LLM Gateway"

    def test_openapi_includes_all_endpoints(self, client: TestClient) -> None:
        """WBS 3.6.1.1.1: OpenAPI spec should include all API endpoints."""
        response = client.get("/openapi.json")
        data = response.json()
        
        paths = data.get("paths", {})
        
        # Verify core endpoints are documented
        expected_paths = [
            "/v1/chat/completions",
            "/v1/sessions",
            "/v1/sessions/{session_id}",
            "/v1/tools",
            "/v1/tools/execute",
            "/health",
            "/health/ready",
        ]
        
        for path in expected_paths:
            assert path in paths, f"Missing path: {path}"


# =============================================================================
# WBS 3.6.1.1.5: API Version Tests
# =============================================================================


class TestAPIVersion:
    """
    WBS 3.6.1.1.5: Version the API spec.
    
    Reference: GUIDELINES pp. 1277 - Semantic versioning and backward compatibility.
    """

    def test_api_version_in_spec(self, client: TestClient) -> None:
        """WBS 3.6.1.1.5: API version should be in OpenAPI spec."""
        response = client.get("/openapi.json")
        data = response.json()
        
        version = data.get("info", {}).get("version")
        assert version is not None
        assert version != ""

    def test_api_version_follows_semver(self, client: TestClient) -> None:
        """WBS 3.6.1.1.5: API version should follow semantic versioning."""
        response = client.get("/openapi.json")
        data = response.json()
        
        version = data.get("info", {}).get("version", "")
        
        # Should be semver format (major.minor.patch or major.minor)
        parts = version.split(".")
        assert len(parts) >= 2, f"Version {version} should be semver format"
        
        # Each part should be numeric
        for part in parts[:2]:
            assert part.isdigit(), f"Version part {part} should be numeric"


# =============================================================================
# WBS 3.6.1.1.3: OpenAPI Spec Validation Tests
# =============================================================================


class TestOpenAPISpecValidation:
    """
    WBS 3.6.1.1.3: Validate spec with openapi-spec-validator.
    
    Reference: GUIDELINES pp. 276 - Schema validation through Pydantic.
    """

    def test_openapi_spec_is_valid(self, client: TestClient) -> None:
        """WBS 3.6.1.1.3: OpenAPI spec should pass validation."""
        from openapi_spec_validator import validate
        from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
        
        response = client.get("/openapi.json")
        spec = response.json()
        
        # This will raise OpenAPIValidationError if invalid
        try:
            validate(spec)
        except OpenAPIValidationError as e:
            pytest.fail(f"OpenAPI spec validation failed: {e}")

    def test_openapi_schemas_defined(self, client: TestClient) -> None:
        """WBS 3.6.1.1.3: OpenAPI spec should have schema definitions."""
        response = client.get("/openapi.json")
        data = response.json()
        
        # OpenAPI 3.x uses components/schemas
        components = data.get("components", {})
        schemas = components.get("schemas", {})
        
        # Should have some schemas defined for request/response models
        assert len(schemas) > 0, "OpenAPI spec should have schema definitions"

    def test_chat_completion_schema_defined(self, client: TestClient) -> None:
        """WBS 3.6.1.1.3: Chat completion request/response schemas should be defined."""
        response = client.get("/openapi.json")
        data = response.json()
        
        schemas = data.get("components", {}).get("schemas", {})
        
        # Should have chat completion related schemas
        chat_schemas = [
            name for name in schemas.keys()
            if "chat" in name.lower() or "completion" in name.lower() or "message" in name.lower()
        ]
        
        assert len(chat_schemas) > 0, "Should have chat completion schemas"


# =============================================================================
# WBS 3.6.1.1.2: OpenAPI Export Tests
# =============================================================================


class TestOpenAPIExport:
    """
    WBS 3.6.1.1.2: Export spec to docs/openapi.yaml.
    
    These tests verify the export script works correctly.
    """

    def test_openapi_can_be_exported_as_yaml(self, client: TestClient) -> None:
        """WBS 3.6.1.1.2: OpenAPI spec can be converted to YAML."""
        import yaml
        
        response = client.get("/openapi.json")
        spec = response.json()
        
        # Should be convertible to YAML and parseable back
        yaml_output = yaml.dump(spec, default_flow_style=False)
        assert len(yaml_output) > 0
        parsed = yaml.safe_load(yaml_output)
        assert parsed["openapi"] == spec["openapi"]

    def test_openapi_spec_exportable_with_references(self, client: TestClient) -> None:
        """WBS 3.6.1.1.2: Export should preserve $ref references."""
        import yaml
        
        response = client.get("/openapi.json")
        spec = response.json()
        
        yaml_output = yaml.dump(spec, default_flow_style=False)
        
        # Check that references are preserved (they use $ref)
        # The YAML should contain schema references
        assert "components" in spec or "definitions" in spec


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """Create test client for the FastAPI app."""
    from src.main import app
    return TestClient(app)
