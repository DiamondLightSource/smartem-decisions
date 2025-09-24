# Development Tools

Collection of utility tools for development, testing, and maintenance of the SmartEM Decisions project.

## XML Formatting Tools

### Format XML Files for Human Readability

Transform single-line XML and .dm files into human-readable format with proper indentation:

```bash
# Reformat all .xml and .dm files in a directory recursively
python tools/format_xml.py <directory_path> -r

# Process multiple directories
python tools/format_xml.py -r \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20250114_220855_23_epuBSAd20_GrOxDDM \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20241220_140307_72_et2_gangshun \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20250108_101446_62_cm40593-1_EPU

# Display all available options
python tools/format_xml.py --help
```

## Data Analysis and Debugging Tools

### Find Foil Hole Manifest Duplicates

Identify duplicate foil hole manifests within directory structures to detect data inconsistencies:

```bash
# Display help and usage information
tools/find_foilhole_duplicates.py --help

# Example: Search for duplicates in test data
tools/find_foilhole_duplicates.py ./tests/testdata/bi37708-28
```

### File Size Analysis

List files matching specific patterns, sorted by size for storage analysis:

```bash
# Find GridSquare files sorted by size (largest first)
rg --files -g 'GridSquare_*.dm' ./tests/testdata/bi37708-28 \
  | xargs -d '\n' ls -lh | sort -k5 -rn | awk '{print $9, $5}'
```

## Test Dataset Management

### File Extension Analysis

Analyse the composition of test datasets by file type:

```bash
# Recursively find all distinct file extensions with counts
find . -type f |
  sed -E 's/.*\.([^.]+)$/\1/' |
  grep -v "/" |
  sort |
  uniq -c |
  sort -nr
```

### Dataset Size Reduction

Reduce test dataset storage requirements whilst maintaining directory structure:

```bash
# Empty image and data files whilst preserving metadata structure
find . -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.mrc" \) -exec truncate -s 0 {} \;
```

**Warning:** This command permanently removes file contents. Use only on test datasets, not production data.

## Development Monitoring

### Directory Growth Monitoring

Monitor directory metrics during data acquisition or processing:

```bash
# Watch directory size and file count with 1-second updates
watch -n 1 'echo "Size: $(du -sh .)"; echo "Files: $(find . -type f | wc -l)"'
```

This tool is particularly useful for monitoring EPU data acquisition progress or debugging processing pipeline performance.

## Message Testing and Communication Tools

### External Message Simulator

Comprehensive CLI tool for simulating external data processing messages that would normally come from ML pipelines and image processing systems:

```bash
# List all available message types
python tools/external_message_simulator.py list-messages

# Individual message simulation examples
python tools/external_message_simulator.py motion-correction --foilhole-id "FH_001_001_001" --quality-score 0.85
python tools/external_message_simulator.py ctf-complete --foilhole-id "FH_001_001_001" --resolution 3.2
python tools/external_message_simulator.py gridsquare-prediction --gridsquare-id "GS_001_001" --prediction-score 0.85
python tools/external_message_simulator.py model-update --model-name "ResNet-50"

# Complete workflow simulation for a single grid square
python tools/external_message_simulator.py workflow-simulation --gridsquare-id "DEV_001"

# Batch simulation with different quality scenarios
python tools/external_message_simulator.py batch-simulation --gridsquare-count 5 --scenario mixed
python tools/external_message_simulator.py batch-simulation --gridsquare-count 3 --scenario good
python tools/external_message_simulator.py batch-simulation --gridsquare-count 2 --scenario poor
```

**Available Message Types:**
- `MOTION_CORRECTION_COMPLETE` - Motion correction processing finished
- `CTF_COMPLETE` - CTF estimation completed
- `PARTICLE_PICKING_COMPLETE` - Particle identification finished
- `PARTICLE_SELECTION_COMPLETE` - Particle quality assessment done
- `GRIDSQUARE_MODEL_PREDICTION` - ML prediction for grid square quality
- `FOILHOLE_MODEL_PREDICTION` - ML prediction for foilhole targeting
- `MODEL_PARAMETER_UPDATE` - ML model parameter updates

### SSE Client Testing

Example client for testing agent-backend communication via Server-Sent Events:

```bash
# Start the SSE client to receive instructions from backend
python tools/sse_client_example.py

# The client will:
# 1. Auto-create a new session with the backend
# 2. Connect to the SSE stream for real-time instructions
# 3. Acknowledge received instructions
# 4. Measure processing time for performance testing
```

This tool is particularly useful for:
- Testing the complete agent-backend communication pipeline
- Validating instruction delivery and acknowledgement mechanisms
- Performance testing of SSE communication
- Development of new agent integrations

Both tools work together to simulate the complete external data flow into the SmartEM system, enabling comprehensive testing without requiring actual microscopy equipment or external processing systems.

## Additional Development Commands

### Pre-commit Workflow

Maintain code quality during development:

```bash
# Run pre-commit checks on specific files
pre-commit run --files <file1> <file2>

# Run all pre-commit checks
pre-commit run --all-files
```

### Testing and Quality Assurance

```bash
# Run comprehensive test suite
pytest

# Type checking with pyright
pyright src tests

# Code formatting and linting
ruff check
ruff format
```
