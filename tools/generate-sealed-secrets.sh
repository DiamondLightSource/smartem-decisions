#!/bin/bash

# SmartEM Decisions - Sealed Secrets Generation Script
# Generates Bitnami Sealed Secrets for Kubernetes deployments
# Follows Diamond Light Source security pattern: temporary files + kubeseal

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENVIRONMENTS=("development" "staging" "production")
SECRET_NAME="smartem-secrets"  # pragma: allowlist secret
TEMP_DIR=""

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function - called on script exit
cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        log_info "Cleaning up temporary files..."
        rm -rf "${TEMP_DIR}"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [ENVIRONMENT]

Generate Bitnami Sealed Secrets for SmartEM Decisions Kubernetes deployments.

ENVIRONMENTS:
  development  - Auto-generate secure random passwords
  staging      - Prompt for credentials interactively
  production   - Prompt for credentials interactively
  all          - Generate for all environments

EXAMPLES:
  $0 development      # Generate development secrets
  $0 production       # Generate production secrets
  $0 all              # Generate all environment secrets

REQUIREMENTS:
  - kubectl (configured with cluster access)
  - kubeseal (Bitnami Sealed Secrets CLI)
  - openssl (for password generation)

SECURITY NOTES:
  - Temporary files are created in secure temp directory
  - All temp files are automatically cleaned up on exit
  - Credentials never appear in shell history
  - Generated sealed secrets are safe to commit to version control

EOF
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if ! command -v kubeseal &> /dev/null; then
        missing_tools+=("kubeseal")
    fi
    
    if ! command -v openssl &> /dev/null; then
        missing_tools+=("openssl")
    fi
    
    if ! command -v base64 &> /dev/null; then
        missing_tools+=("base64")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install missing tools and try again"
        exit 1
    fi
    
    # Check kubectl cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        log_error "Please ensure kubectl is configured correctly"
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Function to validate environment
validate_environment() {
    local env="$1"
    
    for valid_env in "${ENVIRONMENTS[@]}"; do
        if [[ "$env" == "$valid_env" ]]; then
            return 0
        fi
    done
    
    log_error "Invalid environment: $env"
    log_error "Valid environments: ${ENVIRONMENTS[*]}"
    return 1
}

# Function to get namespace for environment
get_namespace() {
    local env="$1"
    
    case "$env" in
        development)
            echo "smartem-decisions"
            ;;
        staging)
            echo "smartem-decisions-staging"
            ;;
        production)
            echo "smartem-decisions-production"
            ;;
        *)
            log_error "Unknown environment: $env"
            exit 1
            ;;
    esac
}

# Function to generate secure random password
generate_password() {
    local length="${1:-24}"
    openssl rand -base64 "$length" | tr -d "=+/" | cut -c1-"$length"
}

# Function to read password securely (no echo)
read_password() {
    local prompt="$1"
    local password
    
    echo -n "$prompt"
    read -rs password
    echo
    
    if [[ -z "$password" ]]; then
        log_error "Password cannot be empty"
        return 1
    fi
    
    echo "$password"
}

# Function to collect credentials for environment
collect_credentials() {
    local env="$1"
    local creds_file="$2"
    
    log_info "Collecting credentials for $env environment..."
    
    case "$env" in
        development)
            log_info "Generating secure random passwords for development..."
            cat > "$creds_file" << EOF
POSTGRES_USER=smartem_dev_$(generate_password 8)
POSTGRES_PASSWORD=$(generate_password 32)
RABBITMQ_USER=rabbitmq_dev_$(generate_password 8)
RABBITMQ_PASSWORD=$(generate_password 32)
EOF
            ;;
        staging|production)
            log_warning "Please provide secure credentials for $env environment"
            echo
            
            local postgres_user
            local postgres_password
            local rabbitmq_user
            local rabbitmq_password
            
            echo -n "PostgreSQL username: "
            read -r postgres_user
            
            if [[ -z "$postgres_user" ]]; then
                log_error "PostgreSQL username cannot be empty"
                return 1
            fi
            
            postgres_password=$(read_password "PostgreSQL password: ")
            if [[ $? -ne 0 ]]; then
                return 1
            fi
            
            echo -n "RabbitMQ username: "
            read -r rabbitmq_user
            
            if [[ -z "$rabbitmq_user" ]]; then
                log_error "RabbitMQ username cannot be empty"
                return 1
            fi
            
            rabbitmq_password=$(read_password "RabbitMQ password: ")
            if [[ $? -ne 0 ]]; then
                return 1
            fi
            
            cat > "$creds_file" << EOF
POSTGRES_USER=$postgres_user
POSTGRES_PASSWORD=$postgres_password
RABBITMQ_USER=$rabbitmq_user
RABBITMQ_PASSWORD=$rabbitmq_password
EOF
            ;;
    esac
    
    log_success "Credentials collected successfully"
}

# Function to generate sealed secret for environment
generate_sealed_secret() {
    local env="$1"
    
    log_info "Generating sealed secret for $env environment..."
    
    local namespace
    namespace=$(get_namespace "$env")
    
    local env_dir="$PROJECT_ROOT/k8s/environments/$env"
    if [[ ! -d "$env_dir" ]]; then
        log_error "Environment directory not found: $env_dir"
        return 1
    fi
    
    # Create temporary files for this environment
    local temp_secret_file="$TEMP_DIR/secret-$env.yaml"
    local temp_sealed_file="$TEMP_DIR/sealed-secret-$env.yaml"
    local temp_creds_file="$TEMP_DIR/creds-$env.env"
    
    # Collect credentials
    collect_credentials "$env" "$temp_creds_file"
    
    # Source credentials
    source "$temp_creds_file"
    
    # Create temporary Kubernetes secret using kubectl (dry-run)
    kubectl create secret generic "$SECRET_NAME" \
        --namespace="$namespace" \
        --from-literal=POSTGRES_USER="$POSTGRES_USER" \
        --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        --from-literal=RABBITMQ_USER="$RABBITMQ_USER" \
        --from-literal=RABBITMQ_PASSWORD="$RABBITMQ_PASSWORD" \
        --dry-run=client \
        --output=yaml > "$temp_secret_file"
    
    # Generate sealed secret using kubeseal
    kubeseal \
        --format=yaml \
        --namespace="$namespace" \
        < "$temp_secret_file" > "$temp_sealed_file"
    
    # Verify sealed secret was generated
    if [[ ! -s "$temp_sealed_file" ]]; then
        log_error "Failed to generate sealed secret for $env"
        return 1
    fi
    
    # Add header comment to sealed secret
    local output_file="$env_dir/secrets.yaml"
    cat > "$output_file" << EOF
# Generated by tools/generate-sealed-secrets.sh
# This is a Bitnami Sealed Secret - safe to commit to version control
# The sealed-secrets controller will decrypt this into a regular Secret
---
EOF
    cat "$temp_sealed_file" >> "$output_file"
    
    log_success "Sealed secret generated: $output_file"
    
    # Display summary for development environment
    if [[ "$env" == "development" ]]; then
        echo
        log_info "Development credentials summary:"
        echo "  PostgreSQL User: $POSTGRES_USER"
        echo "  RabbitMQ User: $RABBITMQ_USER"
        echo "  (Passwords are randomly generated and sealed)"
    fi
}

# Function to generate all environment secrets
generate_all_secrets() {
    log_info "Generating sealed secrets for all environments..."
    
    for env in "${ENVIRONMENTS[@]}"; do
        echo
        generate_sealed_secret "$env"
    done
    
    echo
    log_success "All sealed secrets generated successfully!"
}

# Main function
main() {
    # Parse command line arguments
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi
    
    local environment="$1"
    
    if [[ "$environment" == "--help" || "$environment" == "-h" ]]; then
        show_usage
        exit 0
    fi
    
    # Create secure temporary directory
    TEMP_DIR=$(mktemp -d -t smartem-sealed-secrets.XXXXXX)
    chmod 700 "$TEMP_DIR"
    
    log_info "SmartEM Decisions - Sealed Secrets Generator"
    log_info "Temporary directory: $TEMP_DIR"
    echo
    
    check_prerequisites
    echo
    
    if [[ "$environment" == "all" ]]; then
        generate_all_secrets
    else
        validate_environment "$environment"
        generate_sealed_secret "$environment"
    fi
    
    echo
    log_info "Security reminders:"
    echo "  - Sealed secrets are safe to commit to version control"
    echo "  - Only the sealed-secrets controller can decrypt them"
    echo "  - Original credentials were handled securely (no shell history)"
    echo "  - Temporary files have been cleaned up automatically"
    echo
    log_success "Sealed secrets generation completed!"
}

# Run main function with all arguments
main "$@"
