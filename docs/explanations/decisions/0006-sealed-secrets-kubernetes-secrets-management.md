# 6. Use Sealed Secrets for Kubernetes secrets management

Date: 22/08/2025

## Status

Accepted

## Context

The SmartEM Decisions project requires secure secrets management for Kubernetes deployments across development, staging,
and production environments. The current approach of committing plain secrets.yaml files with test passwords to version
control presents security risks and violates organisational security standards at Diamond Light Source.

The project deploys to three environments using local development machines without CI/CD automation. Secrets include
PostgreSQL database credentials, RabbitMQ message queue authentication, and other sensitive configuration values
required for the scientific computing workflow.

The Diamond Light Source Kubernetes team recommended Sealed Secrets for organisational standardisation, referencing
their internal development portal guide (https://dev-portal.diamond.ac.uk/guide/kubernetes/tutorials/secrets/) for
implementation guidance.

Five approaches were evaluated for secrets management:

1. **Kustomize Secret Generators**: Generate secrets at build time using kustomize secretGenerator functionality
2. **External Secrets Operator**: Pull secrets from external systems such as HashiCorp Vault or AWS Secrets Manager
3. **Sealed Secrets**: Encrypt secrets using asymmetric cryptography that can be safely committed to version control
4. **Environment-Specific .env Files**: Use gitignored .env files with generation scripts for each environment
5. **Development Tools Integration**: Generate secrets dynamically within the existing dev-k8s.sh deployment script

Key requirements included:
- Eliminate plain text secrets from version control
- Support local deployment workflow without CI/CD infrastructure
- Maintain version control history for secret management
- Align with Diamond Light Source organisational standards
- Support secret rotation and environment-specific values

## Decision

We will use **Sealed Secrets** as the primary Kubernetes secrets management solution, implemented through the
sealed-secrets controller and kubeseal CLI tool.

Sealed Secrets uses asymmetric cryptography where secrets are encrypted with a public key and can only be decrypted by
the sealed-secrets controller running in the target Kubernetes cluster. This allows encrypted SealedSecret resources to
be safely committed to version control whilst maintaining security.

Implementation will include:
- Installation of sealed-secrets controller in each Kubernetes environment
- Integration with existing deployment workflow via tools/generate-sealed-secrets.sh script
- Documentation in docs/how-to/manage-kubernetes-secrets.md for team procedures
- Environment-specific encryption keys for development, staging, and production clusters

## Consequences

**Positive:**
- Eliminates security risk of committing plain text secrets to version control
- Aligns with Diamond Light Source organisational standards and team recommendations
- Enables version control tracking of secret changes whilst maintaining security
- Supports local deployment model without requiring external secret management infrastructure
- Provides secret rotation capabilities with audit trail through Git history
- Integrates seamlessly with existing Kubernetes deployment workflow

**Negative:**
- Introduces learning curve for team members unfamiliar with sealed-secrets tooling
- Creates dependency on sealed-secrets controller availability in each cluster environment
- Requires careful management of sealed-secrets private keys for cluster recovery scenarios
- Additional complexity compared to plain Kubernetes secrets for local development workflows

**Implementation considerations:**
- Backup and secure storage of sealed-secrets private keys for disaster recovery
- Documentation of secret rotation procedures for team knowledge sharing
- Integration testing to ensure sealed-secrets work correctly across all three environments
- Training for team members on kubeseal CLI usage and troubleshooting procedures
