[![CI](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/smartem-decisions/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/smartem-decisions)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# smartem_decisions

Project board: <https://github.com/orgs/DiamondLightSource/projects/33/views/1>

This is where you should write a short paragraph that describes what your module does,
how it does it, and why people should use it.

Source          | <https://github.com/DiamondLightSource/smartem-decisions>
:---:           | :---:
Docker          | `docker run ghcr.io/DiamondLightSource/smartem-decisions:latest`
Documentation   | <https://DiamondLightSource.github.io/smartem-decisions>
Releases        | <https://github.com/DiamondLightSource/smartem-decisions/releases>

This is where you should put some images or code snippets that illustrate
some relevant examples. If it is a library then you might put some
introductory code here:

```python
from cryoem_decision_engine_poc import __version__

print(f"Hello cryoem_decision_engine_poc {__version__}")
```

Or if it is a commandline tool then you might put some example commands here:

```
python -m cryoem_decision_engine_poc --version
```

<!-- README only content. Anything below this line won't be included in index.md -->

See https://DiamondLightSource.github.io/smartem-decisions for more detailed documentation.

## Notes

- mock the decision-making stuff
  - to be tackled separately
  - to be decoupled and modular, so we can easily swap out decision-making authorities in the future
- communicate decisions to cryoEM controller API (TBC naming!)
- https://github.com/DiamondLightSource/ispyb-database is a database schema that stores information about 
  what is run, metadata, how many images, sample type etc.
- for context:
  - https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10910546/,
    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10910546/pdf/d-80-00174.pdf
  - https://www.biorxiv.org/content/10.1101/2024.02.12.579963v1,
    https://www.biorxiv.org/content/10.1101/2024.02.12.579963v1.full.pdf
- initially the process produces stuff on the filesystem similar to this example: `doc/metadata_spa_acquisition`
- parts of the current **Data Processing Pipeline**:
  - particle picking service receives a JSON blob via RabitMQ, is given a path to an image, picks on that and produces
    a list of coordinates of particles on that image:
    https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/cryolo.py
  - particle filtering service: https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/select_particles.py

## Developing ~~Smart EPU Decision Service API~~ Athena API

"Athena API" is the API exposed by the microscope, corresponding Open API definition is found under
`docs/assets/swagger-decision-service-after-update.json`. From this definition we have generated some scaffolding
for a mock API backend and a python client library.

### Athena mock API

Mock API backend can be found under `src/athena_api_mock_server` and launched as so:

```bash
cd src/athena_api_mock_server
docker build -t athena_api_mock_server .
docker run -p 8080:8080 athena_api_mock_server
```

At which point the Swagger UI should be available at http://localhost:8080/api/smartepu/docs/ui/

Auto-generated client resides in `src/athena_api_client`

### Simulating various events on the MQ

See: `./src/core/simulate_msg.py --help`
