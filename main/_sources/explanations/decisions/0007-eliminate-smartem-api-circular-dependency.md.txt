# 7. Eliminate circular dependency between smartem_api and smartem_backend

Date: 23/08/2025

## Status

Accepted

## Context

The SmartEM Decisions project developed a circular dependency between the `smartem_api` and `smartem_backend` packages 
that violated clean architecture principles and created maintenance challenges for the scientific computing workflow 
automation system.

The circular dependency manifested in two ways:
1. **Package-level dependency**: `smartem_backend` declared dependency on `smartem_api` in its pyproject.toml 
   configuration, requiring the API package for core backend functionality
2. **Module-level imports**: `smartem_api.server` module imported extensively from `smartem_backend` components 
   including database models, message queue publishers, and utility functions

This circular relationship created several problems for the cryo-electron microscopy workflow system:
- **Build complexity**: Package installation order became critical and error-prone during development setup
- **Architectural violation**: Backend logic was split across packages in non-intuitive ways, complicating system 
  understanding
- **Maintenance burden**: Changes to core backend functionality required coordinated updates across multiple packages
- **Import confusion**: Developers struggled to understand which package provided specific functionality
- **Testing complexity**: Circular imports made unit testing and mocking more difficult

The project's multi-package structure (`smartem_backend`, `smartem_agent`, `smartem_common`, `athena_api`) was designed 
to enable modular deployment and clear separation of concerns for the high-throughput microscopy data processing 
requirements. However, the API package had evolved beyond its intended scope as a simple HTTP client interface.

Three approaches were considered for resolving the circular dependency:

1. **Dependency inversion**: Introduce abstract interfaces to break direct import cycles whilst maintaining separate 
   packages
2. **Package splitting**: Further decompose packages to eliminate circular relationships through fine-grained separation
3. **Package consolidation**: Merge `smartem_api` functionality into `smartem_backend` to eliminate the circular 
   dependency entirely

## Decision

We will **consolidate the smartem_api package into smartem_backend** to eliminate the circular dependency completely.

The consolidation will restructure the codebase as follows:
- Move `smartem_api/client.py` to `smartem_backend/api_client.py` for HTTP client functionality
- Move `smartem_api/server.py` to `smartem_backend/api_server.py` for FastAPI server implementation
- Relocate HTTP data models to `smartem_backend/model/http_*.py` alongside existing database models
- Maintain backward compatibility by creating re-export modules in the original `smartem_api/` location
- Remove `smartem_api` as a separate package from pyproject.toml configuration
- Introduce lightweight `client` dependency group for components requiring only API client functionality

The API client will remain accessible to `smartem_agent` and external consumers through the consolidated package 
structure, preserving the modularity required for distributed cryo-electron microscopy workflow processing.

## Consequences

**Positive:**
- Eliminates circular dependency completely, resolving architectural violation and build complexity
- Reduces operational overhead by managing one fewer package in the development and deployment pipeline
- Simplifies import structure with clear single-source responsibility for HTTP API functionality
- Maintains full backward compatibility for existing code using `smartem_api` imports
- Preserves API client reusability for `smartem_agent` and external scientific computing integrations
- Continues to support Swagger documentation generation from the consolidated API server
- Enables cleaner dependency management with optional `client` group for minimal installations

**Negative:**
- Increases `smartem_backend` package scope, potentially affecting cognitive load for developers
- Requires migration period where both import paths coexist, creating temporary code duplication
- May impact deployment strategies that relied on separate API package for containerised microservices
- Documentation and examples require updates to reflect new package structure

**Implementation considerations:**
- Comprehensive testing across all import paths to ensure backward compatibility during transition period
- Documentation updates for installation guides, API usage examples, and architectural diagrams
- Communication to development team about new import paths and deprecation timeline for legacy imports
- Validation of Swagger documentation generation and API client functionality post-consolidation
