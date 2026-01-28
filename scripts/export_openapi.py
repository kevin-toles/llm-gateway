#!/usr/bin/env python3
"""
WBS 3.6.1.1.2: Export OpenAPI Specification

This script exports the FastAPI-generated OpenAPI specification to both
JSON and YAML formats for documentation and contract validation.

Usage:
    python scripts/export_openapi.py
    
Outputs:
    - docs/openapi.json  (JSON format)
    - docs/openapi.yaml  (YAML format)

Reference Documents:
- GUIDELINES pp. 1004: OpenAPI Specification (OAS) standard
- ARCHITECTURE.md: API documentation requirements
"""

import json
import sys
from pathlib import Path

import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.main import app  # noqa: E402


def export_openapi_spec() -> None:
    """
    Export the OpenAPI specification to JSON and YAML formats.
    
    WBS 3.6.1.1.2: Export spec to docs/openapi.yaml
    WBS 3.6.1.1.5: Version the API spec (version comes from FastAPI app)
    """
    # Get the OpenAPI spec from FastAPI
    openapi_spec = app.openapi()
    
    # Output directory
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Export as JSON
    json_path = docs_dir / "openapi.json"
    with open(json_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)
    print(f"✅ Exported OpenAPI spec to {json_path}")
    
    # Export as YAML
    yaml_path = docs_dir / "openapi.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(openapi_spec, f, default_flow_style=False, sort_keys=False)
    print(f"✅ Exported OpenAPI spec to {yaml_path}")
    
    # Print summary
    print(f"\n📋 OpenAPI Specification Summary:")
    print(f"   Title: {openapi_spec.get('info', {}).get('title', 'N/A')}")
    print(f"   Version: {openapi_spec.get('info', {}).get('version', 'N/A')}")
    print(f"   Paths: {len(openapi_spec.get('paths', {}))}")
    
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    print(f"   Schemas: {len(schemas)}")


def validate_exported_spec() -> bool:
    """
    Validate the exported OpenAPI specification.
    
    WBS 3.6.1.1.3: Validate spec with openapi-spec-validator
    
    Returns:
        True if validation passes, False otherwise
    """
    from openapi_spec_validator import validate
    from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
    
    docs_dir = Path(__file__).parent.parent / "docs"
    json_path = docs_dir / "openapi.json"
    
    if not json_path.exists():
        print(f"❌ OpenAPI spec not found at {json_path}")
        return False
    
    with open(json_path) as f:
        spec = json.load(f)
    
    try:
        validate(spec)
        print("✅ OpenAPI spec validation passed")
        return True
    except OpenAPIValidationError as e:
        print(f"❌ OpenAPI spec validation failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Export and validate OpenAPI specification"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing spec without exporting"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation after export"
    )
    
    args = parser.parse_args()
    
    if args.validate_only:
        success = validate_exported_spec()
        sys.exit(0 if success else 1)
    
    export_openapi_spec()
    
    if not args.skip_validation:
        success = validate_exported_spec()
        sys.exit(0 if success else 1)
