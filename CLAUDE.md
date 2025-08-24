# SmartEM Decisions Project Guidelines

## Development Environment
- **Python Version**: 3.12+ (strict requirement - utilize modern typing features)
- **venv**: Use `source .venv/bin/activate` for tools such as pip, ruff or tox
- **Package Management**: Use `pip install -e .[all]` for full development setup
- **Code Style**: Ruff (120 char line length) with pyright type checking

## Code Standards
- **MANDATORY PRE-COMMIT WORKFLOW**: After creating or modifying ANY file, immediately run
  `pre-commit run --files <files>` and fix all issues. This is not optional - no task is complete until pre-commit
  passes cleanly
- **New line at end of file**: All files must end with a newline (pre-commit enforces this)
- **No Comments**: Code should be self-explanatory - avoid explanatory comments
- **Modern Python**: Use Python 3.12 typing features (no legacy `typing` imports where unnecessary)
- **Line Length**: 120 characters maximum (ruff enforces this)
- **Import Sorting**: Use ruff's import sorting (I001 rule)
- **Type Annotations**: Use modern `dict[str, Any]` not `Dict[str, Any]` (UP006, UP007 rules)
- **XML Parsing**: Use lxml for all XML processing needs
- **CLI Tools**: Prefer rich/typer for beautiful command-line interfaces

## Claude Workflow Requirements
Claude must follow this exact sequence for ANY file creation or modification:
1. Create/modify file using Write, Edit, or MultiEdit tools
2. IMMEDIATELY run `pre-commit run --files <modified-files>`
3. Fix any issues found by pre-commit
4. Re-run pre-commit until all checks pass
5. Only then consider the task complete

This applies to ALL files: Python code, Markdown documentation, configuration files, agent definitions, etc.

## Common Commands
```bash
# Development setup
pip install -e .[all]

# Testing
pytest

# Type checking  
pyright src tests

# Linting and formatting
ruff check
ruff format

# Pre-commit checks
pre-commit run --all-files

# Documentation
sphinx-build -E docs build/html
sphinx-autobuild docs build/html  # Live reload

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "Description"
```

## Project Architecture
- **Multi-package structure**: `smartem_backend`, `smartem_agent`, `smartem_common`, `athena_api`
- **Scientific computing focus**: Cryo-electron microscopy workflow automation
- **Microservices**: FastAPI backend with message queue (RabbitMQ) communication
- **Database**: PostgreSQL with SQLModel/Alembic migrations
- **Containerized deployment**: Kubernetes-ready with multi-environment configs

## Scientific Domain Context
- **Cryo-EM workflows**: Real-time microscopy data processing and decision making
- **High-throughput**: Handle 1000+ images/hour processing requirements
- **Research reproducibility**: Maintain data provenance and scientific rigor
- **Open source**: Apache 2.0 licensed research software

## Testing & Quality
- **Coverage**: Tests run with coverage reporting
- **Doctests**: Documentation examples are executable
- **Multiple environments**: tox for cross-environment testing
- **CI/CD**: GitHub Actions with pre-commit hooks

## Documentation
- **Sphinx**: Auto-generated API docs with Napoleon (Google-style docstrings)
- **MyST**: Markdown support in documentation
- **Live development**: Use sphinx-autobuild for real-time doc updates
- **API documentation**: Swagger/OpenAPI specs auto-generated

## Claude Code Agents
Available specialised agents in `.claude/agents/`:
- **project-owner**: Strategic project guidance, requirements, scientific domain decisions
- **software-engineer**: Architecture decisions, DevOps, system design, performance optimisation
- **database-admin**: PostgreSQL expertise, Alembic migrations, scientific data management
- **devops**: DevOps and DevX expert specialising in CI/CD, containerisation, Kubernetes operations, and scientific computing deployment workflows
- **technical-writer**: Documentation, British English, technical writing, Markdown formatting

Claude Code will automatically invoke appropriate agents based on task context. For documentation tasks, the
technical-writer agent ensures British English usage and professional formatting.

## Dependencies of Note
- **Web**: FastAPI, uvicorn, httpx, requests
- **Data**: Pydantic v2, SQLModel, lxml, watchdog
- **Scientific**: Designed for (but not exclusive to) Diamond Light Source facility integration
- **Monitoring**: Rich CLI output, structured logging support
