#!/usr/bin/env python3
"""Generate API documentation from mock servers and OpenAPI specs."""

import json
from pathlib import Path


def use_original_athena_spec():
    """Use the original Athena API spec as the canonical documentation."""
    try:
        source = Path("docs/athena-decision-service-api-spec.json")
        dest = Path("docs/api/athena/swagger.json")

        print("Using original Athena API specification as source of truth...")

        if source.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Load and enhance the original spec
            with open(source) as f:
                original_spec = json.load(f)

            # Add local mock server for development
            if "servers" not in original_spec:
                original_spec["servers"] = []

            # Ensure local mock server is available for testing
            mock_server = {
                "url": "http://localhost:8000",
                "description": "Local mock server for development and testing",
            }

            # Add mock server if not already present
            if not any(server.get("url") == mock_server["url"] for server in original_spec["servers"]):
                original_spec["servers"].insert(0, mock_server)

            # Add metadata about source
            original_spec["info"]["x-source"] = "External Athena Decision Service"
            original_spec["info"]["x-generated-client"] = "Python client generated from this specification"

            with open(dest, "w") as f:
                json.dump(original_spec, f, indent=2)

            print(f"   Athena API spec (from original) saved to {dest}")
            return True
        else:
            print(f"   Original Athena swagger file not found at {source}")
            return False

    except Exception as e:
        print(f"   Error processing original Athena spec: {e}")
        return False


def generate_smartem_from_implementation():
    """Generate SmartEM API spec from SmartEM FastAPI implementation."""
    try:
        print("Generating SmartEM API spec from FastAPI implementation...")

        # Set up minimal environment for FastAPI import
        import os

        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        os.environ.setdefault("SMARTEM_LOG_LEVEL", "ERROR")

        # Skip database initialization in CI environments
        os.environ.setdefault("SKIP_DB_INIT", "true")

        # Import the FastAPI app from SmartEM Backend
        print("Attempting to import smartem_backend.api_server...")
        from smartem_backend.api_server import app

        print("Successfully imported smartem_backend.api_server")

        # Get the OpenAPI spec from the FastAPI app
        openapi_spec = app.openapi()

        # Enhance the spec with development server info
        if "servers" not in openapi_spec or not openapi_spec["servers"]:
            openapi_spec["servers"] = [{"url": "http://localhost:8001", "description": "Local development server"}]

        # Save the spec to the docs directory
        docs_path = Path("docs/api/smartem/swagger.json")
        docs_path.parent.mkdir(parents=True, exist_ok=True)

        with open(docs_path, "w") as f:
            json.dump(openapi_spec, f, indent=2)

        print(f"   SmartEM API spec (from implementation) saved to {docs_path}")
        return True

    except Exception as e:
        print(f"   Error generating SmartEM spec: {e}")
        print("Full error traceback:")
        import traceback

        traceback.print_exc()
        return False


def ensure_api_docs_in_build():
    """Ensure API docs are copied to build directory if it exists."""
    try:
        import shutil

        build_dir = Path("build/html")
        if build_dir.exists():
            api_source = Path("docs/api")
            api_dest = build_dir / "api"
            if api_source.exists():
                if api_dest.exists():
                    shutil.rmtree(api_dest)
                shutil.copytree(api_source, api_dest)
                print(f"   API docs copied to build directory: {api_dest}")
                return True
    except Exception as e:
        print(f"      Could not copy API docs to build directory: {e}")
    return False


if __name__ == "__main__":
    print("🚀 Generating API documentation...")
    print("=" * 50)

    # Athena API: Use original spec as a source of truth
    # SmartEM API: Generate from implementation (placeholder for now)
    results = [use_original_athena_spec(), generate_smartem_from_implementation()]

    # Try to copy to build directory if it exists
    ensure_api_docs_in_build()

    print("=" * 50)
    if all(results):
        print("🎉 All API documentation generated successfully!")
        print("")
        print("📋 Documentation structure:")
        print("  • Athena API: Uses external spec as source of truth")
        print("  • SmartEM API: Generated from implementation")
    else:
        print("      Some API documentation generation failed. Check errors above.")
