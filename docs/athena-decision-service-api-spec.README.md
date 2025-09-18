# Athena Decision Service API Specification

## Overview

This file (`athena-decision-service-api-spec.json`) contains the **authoritative OpenAPI specification** for the external Athena Decision Service API.

## Important Notes

- **Source of Truth**: This specification is the canonical definition of the Athena API
- **External Service**: The Athena Decision Service is developed and maintained externally
- **Generated Code**: Our Python client (`src/athena_api/`) and mock server are generated from this specification
- **Documentation**: The interactive API documentation is built from this specification

## Usage

### For Developers

When working with the Athena API:

1. **Refer to this specification** for the definitive API contract
2. **Use the generated Python client** for integration
3. **Use the mock server** for development and testing
4. **Check the interactive docs** for examples and testing

### For Documentation

The API documentation generation process:

1. **This file** → Processed by `tools/generate_api_docs.py`
2. **Generates** → `docs/api/athena/swagger.json` (for Swagger UI)
3. **Creates** → Interactive documentation at `/api/athena/`

### Updating the Specification

**Important**: This file should only be updated when the external Athena service changes their API specification.

**Process for updates**:
1. Obtain the new specification from the Athena service maintainers
2. Replace the contents of this file
3. Run `python tools/generate_api_docs.py` to update documentation
4. Regenerate the Python client if there are breaking changes
5. Update the mock server implementation if needed
6. Test integration and update any affected code

## Related Files

- **Python Client**: `src/athena_api/client.py` - Generated from this spec
- **Mock Server**: `src/athena_api/mock/server.py` - Implements this spec for testing
- **Documentation**: `docs/api/athena/` - Interactive docs based on this spec
- **Generation Script**: `tools/generate_api_docs.py` - Processes this spec for documentation

## Specification Details

- **Format**: OpenAPI 3.0.1
- **Service**: Athena Decision Service for CryoEM
- **Purpose**: Automated decision making for microscopy workflows
- **Endpoints**: Session management, decision recording, algorithm results, area management
