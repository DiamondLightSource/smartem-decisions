# 5. Use detect-secrets for secret scanning

Date: 21/08/2025

## Status

Accepted

## Context

The SmartEM Decisions project requires robust secret scanning to protect sensitive research data, database
credentials, API keys, and Kubernetes cluster secrets. As part of the Diamond Light Source facility infrastructure,
high security standards are essential whilst supporting scientific computing workflows.

The development team evaluated secret scanning tools for integration into the existing sophisticated pre-commit and
CI/CD pipeline (Python 3.12+, ruff, pyright). The organisational cybersecurity team recommended Gitleaks for
standardisation across projects.

Key requirements included:
- Integration with Python 3.12+ ecosystem and existing toolchain
- Handling scientific computing patterns (chemical formulas, gene sequences, scientific notation) without excessive
  false positives
- Support for high-throughput processing without workflow disruption
- Enterprise-grade baseline management for research environments

Three tools were evaluated:
- **Gitleaks**: High-performance Go implementation, organisational preference, but higher false positives in
  scientific contexts
- **TruffleHog**: Advanced entropy analysis, but resource-intensive with SaaS dependencies
- **detect-secrets**: Python-native, superior false positive handling, sophisticated baseline management

## Decision

We will use **detect-secrets** as the primary secret scanning tool, integrated into both pre-commit hooks and
CI/CD pipelines, despite the organisational preference for Gitleaks standardisation.

## Consequences

**Positive:**
- Native Python integration with existing development workflow
- Superior false positive management for scientific computing patterns
- Enterprise-grade baseline system for managing known safe patterns
- Faster CI/CD execution through incremental scanning approach
- Flexible plugin architecture for research-specific customisation

**Negative:**
- Divergence from organisational tooling standardisation
- Potential knowledge silos between teams using different tools
- Responsibility for maintaining tool-specific expertise within the team

**Mitigation:**
- Comprehensive documentation of configuration and workflows
