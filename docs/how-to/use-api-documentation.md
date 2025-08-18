# Using the API Documentation

This guide explains how to use the interactive API documentation for SmartEM Decisions services.

## Overview

SmartEM Decisions provides interactive API documentation built with Swagger UI, giving you:

- **Live API exploration** - Try endpoints directly in your browser
- **Complete specifications** - Full OpenAPI 3.0 documentation
- **Example requests/responses** - See exactly what data to send and expect
- **Authentication helpers** - Built-in tools for API authentication

## Accessing the Documentation

### Online Documentation

Visit the hosted API documentation at:
- **Athena Decision Service**: [Athena API Docs](../api/athena/index.html)
- **SmartEM Core API**: [SmartEM API Docs](../api/smartem/index.html)

### Local Documentation

To run the documentation locally with a live mock server:

```bash
# Install mock dependencies
pip install -e ".[mock]"

# Start the Athena mock server
python -c "
from athena_api.mock import AthenaAPIServer
server = AthenaAPIServer()
server.run()
"

# Visit http://localhost:8000/docs
```

## Using the Interactive Features

### Try It Out

1. **Expand an endpoint** by clicking on it
2. **Click "Try it out"** to enable the interactive form
3. **Fill in parameters** using the provided form fields
4. **Click "Execute"** to make a real API call
5. **View the response** including status code, headers, and body

### Authentication

For endpoints requiring authentication:

1. **Click the "Authorize" button** at the top of the page
2. **Enter your credentials** (API key, bearer token, etc.)
3. **Click "Authorize"** to save credentials for all requests

### Request Examples

Each endpoint shows:
- **Parameter descriptions** - What each field does
- **Example values** - Sample data to help you understand the format
- **Schema definitions** - Complete data structure specifications
- **Response examples** - What to expect back from the API

## API Specifications

### Understanding API Sources

**Athena Decision Service API** - External service integration:
- **Source of Truth**: External Athena service OpenAPI specification (`docs/athena-decision-service-api-spec.json`)
- **Our Implementation**: Python client and mock server generated from spec
- **Documentation**: Based on the authoritative external specification

**SmartEM Core API** - Our implementation:
- **Source of Truth**: Our FastAPI/Django implementation
- **Our Implementation**: Backend service with business logic
- **Documentation**: Generated from our actual API endpoints

### Download Specifications

You can download the raw OpenAPI specifications:

- [Athena API Spec](../api/athena/swagger.json) - Official external specification
- [Athena Source Spec](../athena-decision-service-api-spec.json) - Original specification file
- [SmartEM API Spec](../api/smartem/swagger.json) - Generated from our implementation

### Using Specifications

Import these into your favorite API tools:
- **Postman** - Import → Link → Paste URL
- **Insomnia** - Create → Import/Export → From URL
- **VS Code REST Client** - Use with OpenAPI extensions
- **Code generators** - Generate client libraries in various languages

## Common Workflows

### Testing Decision Service Integration

1. **Start with session management**:
   ```bash
   POST /api/v1/Session
   # Register a new acquisition session
   ```

2. **Register areas**:
   ```bash
   POST /api/v1/Area
   # Add grid squares and foil holes
   ```

3. **Record decisions**:
   ```bash
   POST /api/v1/Decision
   # Log automated decisions
   ```

4. **Store algorithm results**:
   ```bash
   POST /api/v1/AlgorithmResult
   # Save processing outcomes
   ```

### Monitoring Acquisition Status

1. **Check application state**:
   ```bash
   GET /api/v1/CurrentApplicationState
   # Get current system status
   ```

2. **Query area states**:
   ```bash
   GET /api/v1/Session/{sessionId}/AreaStates
   # Monitor area processing status
   ```

3. **Retrieve decisions**:
   ```bash
   GET /api/v1/Session/{sessionId}/Decisions
   # Review automated decisions
   ```

## Development Tips

### Mock Server for Development

The Athena API includes a full mock server for development:

```python
from athena_api.mock import AthenaAPIServer

# Create and configure mock server
server = AthenaAPIServer()

# Customize host/port
server.run(host="0.0.0.0", port=8080)
```

### Client Library Usage

Use the Python client library for programmatic access:

```python
from athena_api import AthenaClient
from athena_api.model.request import Session
from uuid import uuid4
from datetime import datetime

# Connect to API
client = AthenaClient("http://localhost:8000")

# Create a session
session = Session(
    sessionId=uuid4(),
    sessionName="Test Session",
    timestamp=datetime.now(),
    gridType="HoleyCarbon"
)

# Register the session
response = client.register_session(session)
print(f"Session created: {response.sessionId}")
```

### Error Handling

The API follows standard HTTP status codes:

- **200-299**: Success responses
- **400-499**: Client errors (bad requests, missing data)
- **500-599**: Server errors (system failures)

Check the API documentation for specific error responses and how to handle them.

## Support

For API-related questions:

1. **Check the interactive documentation** for endpoint details
2. **Review the example code** in this documentation
3. **Examine the client library** source code for usage patterns
4. **Open an issue** on the [GitHub repository](https://github.com/DiamondLightSource/smartem-decisions/issues)

The API documentation is automatically updated with each release, ensuring you always have access to the latest features and changes.
