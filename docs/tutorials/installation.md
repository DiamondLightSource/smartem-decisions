# Installation

## Check Your Version of Python

SmartEM Decisions requires Python 3.12 or later for optimal performance and access to modern typing features. You can check your current Python version by entering the following command in a terminal:

```bash
python3 --version
```

**Note:** The project specifically requires Python 3.12+ to utilise advanced typing features and maintain compatibility with the latest scientific computing libraries.

## Create a Virtual Environment

It is strongly recommended that you install SmartEM Decisions within a virtual environment to prevent conflicts with existing Python installations and maintain a clean development environment:

```bash
python3 -m venv /path/to/venv
source /path/to/venv/bin/activate
```

For development work, consider creating the virtual environment within the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Installing the Library

### Standard Installation

You can install the library and its core dependencies using `pip`:

```bash
python3 -m pip install smartem-decisions
```

### Development Installation

For development work or if you require the latest features, install directly from the source repository:

```bash
# Clone and install in development mode
git clone https://github.com/DiamondLightSource/smartem-decisions.git
cd smartem-decisions
pip install -e .[all]
```

### Installation with Optional Dependencies

Install with specific feature sets:

```bash
# Install with MCP (Model Context Protocol) support
pip install -e .[mcp]

# Install with all optional dependencies (recommended for development)
pip install -e .[all]
```

## Verify Installation

The library should now be installed with the command-line interface available on your system path. Verify the installation by checking the installed version:

```bash
smartem-decisions --version
```

You can also verify that all components are correctly installed by running:

```bash
# Test core functionality
python -c "import smartem_backend, smartem_agent, smartem_common; print('Core components imported successfully')"

# Test MCP functionality (if installed with MCP support)
python -c "import smartem_mcp; print('MCP components available')"
```

## Next Steps

Once installation is complete, you can proceed to:

- [Run the backend service](../how-to/run-backend.md)
- [Deploy using containers](../how-to/run-container.md)  
- [Set up the development environment](../how-to/development-tools.md)
- [Configure logging](../how-to/configure-logging.md)
