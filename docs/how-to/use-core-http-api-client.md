# How to Use the SmartEM API Client

This guide explains how to use the unified SmartEM API client to communicate with the SmartEM Core API.

## Overview

The SmartEM API Client provides a unified interface to interact with the SmartEM Core API. It supports both
synchronous and asynchronous operations, making it flexible for different usage scenarios. The client also includes
data conversion utilities to convert between EPU data models and API request/response models.

## Installation

The SmartEM API Client is included with the SmartEM Decisions package, so no additional installation is required.

## Basic Usage

### Importing the Client

```python
from smartem_backend.api_client import SmartEMAPIClient
```

### Creating a Client Instance

```python
# Create a client with default timeout (10 seconds)
client = SmartEMAPIClient("http://localhost:8000")

# Create a client with custom timeout
client = SmartEMAPIClient("http://localhost:8000", timeout=30.0)

# Create a client with custom logger
import logging
logger = logging.getLogger("my_logger")
client = SmartEMAPIClient("http://localhost:8000", logger=logger)
```

### Using the Client with Context Managers

The client supports context managers to ensure proper resource cleanup:

```python
# Synchronous context manager
with SmartEMAPIClient("http://localhost:8000") as client:
    # Use the client...
    status = client.get_status()
    print(status)

# Asynchronous context manager
async with SmartEMAPIClient("http://localhost:8000") as client:
    # Use the client asynchronously...
    status = await client.aget_status()
    print(status)
```

## Synchronous vs Asynchronous Methods

The client provides both synchronous and asynchronous methods for all operations. The asynchronous methods are
prefixed with `a` (e.g., `aget_status` vs `get_status`).

```python
# Synchronous method
acquisitions = client.get_acquisitions()

# Asynchronous method
acquisitions = await client.aget_acquisitions()
```

## Working with Acquisitions

### Creating an Acquisition

```python
from smartem_agent.model.schemas import EpuSessionData
from datetime import datetime

# Create an acquisition from EPU session data
session = EpuSessionData(
    id="my-acquisition-id",
    name="My Acquisition",
    start_time=datetime.now(),
    storage_path="/path/to/storage"
)
response = client.create_acquisition(session)
print(f"Created acquisition with ID: {response.id}")

# Alternatively, create directly with an API request model
from smartem_backend.model.http_request import AcquisitionCreateRequest

request = AcquisitionCreateRequest(
    id="my-acquisition-id",
    name="My Acquisition"
)
response = client.create_acquisition(request)
```

### Retrieving Acquisitions

```python
# Get all acquisitions
acquisitions = client.get_acquisitions()
for acq in acquisitions:
    print(f"Acquisition: {acq.id} - {acq.name}")

# Get a specific acquisition
acquisition = client.get_acquisition("acquisition-id")
print(f"Acquisition details: {acquisition.name}, Status: {acquisition.status}")
```

### Updating an Acquisition

```python
from smartem_backend.model.http_request import AcquisitionUpdateRequest

update = AcquisitionUpdateRequest(
    name="Updated Acquisition Name",
    status="completed"
)
updated = client.update_acquisition("acquisition-id", update)
```

### Deleting an Acquisition

```python
client.delete_acquisition("acquisition-id")
```

## Working with Hierarchical Data

The client supports the full hierarchy of entities:

1. Acquisition
2. Grid
3. Grid Square
4. Foil Hole
5. Micrograph

Here's an example of creating entities at each level:

```python
# Create an acquisition
acquisition = client.create_acquisition(EpuSessionData(id="acq-1", name="Test Acquisition"))

# Create a grid for the acquisition
from smartem_agent.model.schemas import GridData

grid = GridData(data_dir="/path/to/grid")
grid_response = client.create_acquisition_grid(acquisition.id, grid)

# Create a grid square for the grid
from smartem_agent.model.schemas import GridSquareData

gridsquare = GridSquareData(id="gs-1", data_dir="/path/to/gridsquare")
gridsquare_response = client.create_grid_gridsquare(grid_response.id, gridsquare)

# Create a foil hole for the grid square
from smartem_agent.model.schemas import FoilHoleData

foilhole = FoilHoleData(id="fh-1", gridsquare_id=gridsquare.id)
foilhole_response = client.create_gridsquare_foilhole(gridsquare_response.id, foilhole)

# Create a micrograph for the foil hole
from smartem_agent.model.schemas import MicrographData, MicrographManifest

manifest = MicrographManifest(
    unique_id="mic-1",
    acquisition_datetime=datetime.now(),
    detector_name="K3",
    energy_filter=True,
    phase_plate=False,
    binning_x=1,
    binning_y=1
)
micrograph = MicrographData(
    id="mic-1",
    gridsquare_id=gridsquare.id,
    foilhole_id=foilhole.id,
    location_id="loc-1",
    high_res_path="/path/to/mic.mrc",
    manifest_file="/path/to/manifest.xml",
    manifest=manifest
)
micrograph_response = client.create_foilhole_micrograph(foilhole_response.id, micrograph)
```

## EntityStore Compatibility

The client maintains compatibility with the existing `EntityStore` API for seamless integration:

```python
# Create an entity through the EntityStore compatibility API
success = client.create("acquisition", "acq-id", session_data, parent=None)

# Create a grid with parent relationship
success = client.create("grid", "grid-id", grid_data, parent=("acquisition", "acq-id"))
```

## Error Handling

The client includes comprehensive error handling:

```python
try:
    response = client.get_acquisition("non-existent-id")
except httpx.HTTPStatusError as e:
    print(f"HTTP error {e.response.status_code}: {e}")
except Exception as e:
    print(f"Error: {e}")
```

## Logging

The client includes detailed logging. You can configure the log level to control verbosity:

```python
import logging
logging.basicConfig(level=logging.INFO)  # For normal operation
logging.basicConfig(level=logging.DEBUG)  # For more detailed logs including request/response data
```

## Advanced Usage

### Working with Raw API Responses

If you need to work with the raw API responses rather than parsed models:

```python
raw_response = await client._request("get", "status")
print(raw_response)
```

### Managing the ID Mapping Cache

The client maintains a cache of entity IDs to database IDs:

```python
# Get a mapped database ID
db_id = client._get_db_id("acquisition", "entity-id")

# Store a mapping manually (normally done automatically)
client._store_entity_id_mapping("acquisition", "entity-id", "db-id")
```

## Closing the Client

Always close the client when you're done to free up resources:

```python
# Explicitly close
client.close()

# Or use context managers (recommended)
with SmartEMAPIClient("http://localhost:8000") as client:
    # Client will be automatically closed when exiting the context
    pass
```
