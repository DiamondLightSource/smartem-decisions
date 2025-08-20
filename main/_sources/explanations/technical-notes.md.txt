# Technical Notes

## Cryo-EM Data Acquisition Scale

Understanding the scale and volume of cryo-electron microscopy data acquisition is crucial for system design and performance considerations:

### Micrograph Statistics
- **Micrographs per foil hole**: Typically 4-10 images per foil hole
- **Grid-level acquisition**: 10,000-50,000 micrographs per complete grid session
- **Particle density**: Approximately 300 particles identified per micrograph
- **Selection efficiency**: Roughly 50% of identified particles are selected for further processing

These statistics inform the design requirements for data processing pipelines and storage allocation strategies.

## System Architecture Considerations

### Decision-Making Framework
The SmartEM system implements a modular decision-making architecture designed for flexibility and extensibility:

- **Modular design**: Decision-making components are decoupled from data acquisition systems
- **Pluggable authorities**: Different decision-making algorithms can be easily substituted
- **Future extensibility**: Architecture supports integration of additional decision-making systems

### API Integration
Communication between SmartEM components and external cryo-EM control systems occurs through well-defined API interfaces, ensuring compatibility with various microscope control software packages.

## Data Management and Storage

### ISPyB Integration
The project integrates with the [ISPyB database schema](https://github.com/DiamondLightSource/ispyb-database), which provides comprehensive metadata storage for:

- Experimental run information
- Session metadata and parameters
- Image counts and acquisition statistics
- Sample type and classification data

### File System Organisation
Data acquisition produces structured file system layouts that facilitate automated processing and quality assessment workflows.

## Processing Pipeline Components

### Particle Processing Workflow
The automated processing pipeline comprises several specialised services:

#### Particle Picking Service
- **Input**: JSON message via RabbitMQ containing image path and processing parameters
- **Processing**: Automated particle identification and coordinate extraction
- **Output**: List of particle coordinates for each processed micrograph
- **Implementation**: [CryOLO service](https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/cryolo.py)

#### Particle Selection Service
- **Function**: Quality-based filtering and selection of identified particles
- **Integration**: Seamless integration with particle picking results
- **Implementation**: [Selection service](https://github.com/DiamondLightSource/cryoem-services/blob/main/src/cryoemservices/services/select_particles.py)

## Scientific Context and References

The SmartEM system builds upon established methodologies and practices in automated cryo-electron microscopy:

### Key Publications
- [Structural Biology Methods](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10910546/) - Comprehensive overview of automated cryo-EM data collection strategies
- [Advanced Automation Techniques](https://www.biorxiv.org/content/10.1101/2024.02.12.579963v1) - Recent developments in real-time decision making for cryo-EM workflows

These references provide scientific context for the automated decision-making algorithms implemented within the SmartEM framework.
