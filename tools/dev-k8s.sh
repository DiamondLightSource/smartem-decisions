#!/bin/bash

set -e

NAMESPACE="smartem-decisions"
K8S_ENV_PATH="k8s/environments/development"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_ENV="${DEPLOY_ENV:-development}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables from environment-specific .env file
load_env_file() {
    local env_file

    # Determine which .env file to load based on DEPLOY_ENV
    case "$DEPLOY_ENV" in
        development)
            env_file="$PROJECT_ROOT/.env.k8s.development"
            ;;
        staging)
            env_file="$PROJECT_ROOT/.env.k8s.staging"
            ;;
        production)
            env_file="$PROJECT_ROOT/.env.k8s.production"
            ;;
        *)
            log_error "Unknown DEPLOY_ENV: $DEPLOY_ENV"
            log_error "Valid values: development, staging, production"
            exit 1
            ;;
    esac

    # Check if environment-specific file exists
    if [[ ! -f "$env_file" ]]; then
        if [[ "$DEPLOY_ENV" == "development" ]]; then
            log_error "Missing .env.k8s.development file at: $env_file"
            log_error "Please copy .env.example.k8s.development to .env.k8s.development and configure your credentials"
            log_error "Or use --docker-password parameter with 'gh auth token'"
            exit 1
        else
            log_warning "Environment file not found: $env_file"
            log_warning "Using shell environment variables and hardcoded defaults"
            return 0
        fi
    fi

    # Source the .env file
    set -a  # automatically export all variables
    source "$env_file"
    set +a  # disable automatic export

    log_info "Loaded environment variables from $env_file"
}

# Validate required environment variables
validate_credentials() {
    local missing_vars=()
    
    # Check GHCR credentials (supporting both old and new variable names for compatibility)
    [[ -z "${DOCKER_USERNAME:-}" ]] && missing_vars+=("DOCKER_USERNAME")
    [[ -z "${DOCKER_EMAIL:-}" ]] && missing_vars+=("DOCKER_EMAIL")

    # Try to get token from gh auth if DOCKER_PASSWORD is not set
    if [[ -z "${DOCKER_PASSWORD:-}" ]]; then
        if command -v gh &> /dev/null && gh auth status &> /dev/null; then
            log_info "DOCKER_PASSWORD not set, attempting to use 'gh auth token'"
            DOCKER_PASSWORD=$(gh auth token 2>/dev/null)
            if [[ -n "$DOCKER_PASSWORD" ]]; then
                log_info "Successfully obtained token from 'gh auth token'"
                export DOCKER_PASSWORD
            else
                log_warn "Failed to obtain token from 'gh auth token'"
                missing_vars+=("DOCKER_PASSWORD")
            fi
        else
            missing_vars+=("DOCKER_PASSWORD")
        fi
    fi
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        log_error "Please check .env.example.k8s.development for required variables or use --docker-password parameter"
        exit 1
    fi
    
    # Basic validation for token format (GitHub tokens start with ghp_, gho_, ghu_, ghs_, or ghr_)
    if [[ ! "$DOCKER_PASSWORD" =~ ^gh[porus]_[A-Za-z0-9_]+ ]]; then
        log_error "DOCKER_PASSWORD does not appear to be a valid GitHub token"
        log_error "GitHub tokens should start with 'ghp_', 'gho_', 'ghu_', 'ghs_', or 'ghr_'"
        exit 1
    fi
    
    log_info "All required credentials are present and valid"
}

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

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
}

# Check current running resources
check_current_status() {
    log_info "Checking current status of namespace: $NAMESPACE"
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Namespace $NAMESPACE does not exist yet"
        return 0
    fi
    
    echo -e "\n${BLUE}Current Pods:${NC}"
    kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null || echo "No pods found"
    
    echo -e "\n${BLUE}Current Services:${NC}"
    kubectl get services -n "$NAMESPACE" --no-headers 2>/dev/null || echo "No services found"
    
    echo -e "\n${BLUE}Current Deployments:${NC}"
    kubectl get deployments -n "$NAMESPACE" --no-headers 2>/dev/null || echo "No deployments found"
}

# Force delete stuck namespace
force_delete_namespace() {
    log_warning "Attempting to force delete stuck namespace: $NAMESPACE"
    
    # Try to remove finalizers and force delete
    if kubectl get namespace "$NAMESPACE" -o json > /tmp/ns-backup.json 2>/dev/null; then
        if command -v jq &> /dev/null; then
            cat /tmp/ns-backup.json | jq '.spec.finalizers = []' | kubectl replace --raw "/api/v1/namespaces/$NAMESPACE/finalize" -f - &>/dev/null || true
        else
            kubectl patch namespace "$NAMESPACE" -p '{"spec":{"finalizers":[]}}' --type=merge &>/dev/null || true
        fi
        
        kubectl delete namespace "$NAMESPACE" --force --grace-period=0 &>/dev/null || true
        rm -f /tmp/ns-backup.json
        
        # Wait a bit for forced deletion to take effect
        sleep 5
        
        if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
            log_success "Namespace force deleted successfully"
            return 0
        else
            log_error "Failed to force delete namespace"
            return 1
        fi
    fi
}

# Clean up existing resources
cleanup_environment() {
    log_info "Cleaning up existing resources in namespace: $NAMESPACE"
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Namespace $NAMESPACE does not exist, nothing to clean up"
        return 0
    fi
    
    # Delete all resources using kustomization
    cd "$PROJECT_ROOT"
    if kubectl delete -k "$K8S_ENV_PATH" --timeout=60s 2>/dev/null; then
        log_success "Resources deleted successfully"
    else
        log_warning "Some resources may not have been deleted cleanly"
    fi
    
    # Wait for pods to terminate
    log_info "Waiting for pods to terminate..."
    local timeout=30
    while kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q "Terminating" && [ $timeout -gt 0 ]; do
        sleep 2
        ((timeout--))
    done
    
    if [ $timeout -eq 0 ]; then
        log_warning "Timeout waiting for pods to terminate"
    fi
    
    # Wait for namespace to be fully deleted if it exists
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Waiting for namespace to be fully deleted..."
        timeout=60
        while kubectl get namespace "$NAMESPACE" &> /dev/null && [ $timeout -gt 0 ]; do
            sleep 2
            ((timeout--))
        done
        
        if [ $timeout -eq 0 ]; then
            log_warning "Timeout waiting for namespace deletion"
            # Try force deletion if normal deletion times out
            force_delete_namespace
        else
            log_success "Namespace deleted successfully"
        fi
    fi
}

# Ensure GHCR secret exists
ensure_ghcr_secret() {
    log_info "Ensuring GHCR secret exists..."

    if kubectl get secret ghcr-secret -n "$NAMESPACE" &> /dev/null; then
        log_success "GHCR secret already exists"
        return 0
    fi

    log_info "Creating GHCR secret..."
    kubectl create secret docker-registry ghcr-secret \
        --docker-server=ghcr.io \
        --docker-username="$DOCKER_USERNAME" \
        --docker-password="$DOCKER_PASSWORD" \
        --docker-email="$DOCKER_EMAIL" \
        --namespace="$NAMESPACE"

    log_success "GHCR secret created successfully"
}

# Ensure application secrets exist
ensure_app_secrets() {
    log_info "Ensuring application secrets exist..."

    if kubectl get secret smartem-secrets -n "$NAMESPACE" &> /dev/null; then
        log_success "Application secrets already exist"
        return 0
    fi

    # Priority: shell env → environment-specific .env file → hardcoded defaults
    local postgres_user="${POSTGRES_USER:-username}"
    local postgres_password="${POSTGRES_PASSWORD:-password}"
    local postgres_db="${POSTGRES_DB:-smartem_db}"
    local rabbitmq_user="${RABBITMQ_USER:-username}"
    local rabbitmq_password="${RABBITMQ_PASSWORD:-password}"

    # Warn if using defaults (not from env or .env file)
    local using_defaults=false
    if [[ "$postgres_user" == "username" ]] || [[ "$postgres_password" == "password" ]]; then  # pragma: allowlist secret
        using_defaults=true
    fi
    if [[ "$rabbitmq_user" == "username" ]] || [[ "$rabbitmq_password" == "password" ]]; then  # pragma: allowlist secret
        using_defaults=true
    fi

    if [[ "$using_defaults" == true ]]; then
        log_warning "Using hardcoded default credentials!"
        log_warning "Set environment variables or create .env.k8s.$DEPLOY_ENV file with real credentials"
        log_warning "See .env.example.k8s.$DEPLOY_ENV for required variables"
    fi

    log_info "Creating application secrets for environment: $DEPLOY_ENV"
    log_info "POSTGRES_USER=$postgres_user, POSTGRES_DB=$postgres_db"
    log_info "RABBITMQ_USER=$rabbitmq_user"

    kubectl create secret generic smartem-secrets \
        --from-literal=POSTGRES_USER="$postgres_user" \
        --from-literal=POSTGRES_PASSWORD="$postgres_password" \
        --from-literal=POSTGRES_DB="$postgres_db" \
        --from-literal=RABBITMQ_USER="$rabbitmq_user" \
        --from-literal=RABBITMQ_PASSWORD="$rabbitmq_password" \
        --namespace="$NAMESPACE"

    log_success "Application secrets created successfully"
}

# Ensure application configmap exists with dynamic values
ensure_app_configmap() {
    log_info "Ensuring application configmap exists with values from .env..."

    # Priority: shell env → environment-specific .env file → skip override (use YAML defaults)
    local postgres_host="${POSTGRES_HOST:-}"
    local postgres_port="${POSTGRES_PORT:-}"
    local postgres_db="${POSTGRES_DB:-}"
    local rabbitmq_host="${RABBITMQ_HOST:-}"
    local rabbitmq_port="${RABBITMQ_PORT:-}"
    local http_api_port="${HTTP_API_PORT:-}"
    local adminer_port="${ADMINER_PORT:-}"
    local cors_allowed_origins="${CORS_ALLOWED_ORIGINS:-}"

    # Check if any env vars are set
    local has_env_overrides=false
    if [[ -n "$postgres_host" ]] || [[ -n "$postgres_port" ]] || [[ -n "$postgres_db" ]] || \
       [[ -n "$rabbitmq_host" ]] || [[ -n "$rabbitmq_port" ]] || \
       [[ -n "$http_api_port" ]] || [[ -n "$adminer_port" ]] || [[ -n "$cors_allowed_origins" ]]; then
        has_env_overrides=true
    fi

    if [[ "$has_env_overrides" == false ]]; then
        log_info "No ConfigMap env vars found in .env file, using hardcoded values from YAML"
        return 0
    fi

    # If ConfigMap exists and we have env overrides, recreate it with env values
    if kubectl get configmap smartem-config -n "$NAMESPACE" &> /dev/null; then
        log_info "ConfigMap exists and .env has overrides, recreating with current values..."
        kubectl delete configmap smartem-config -n "$NAMESPACE"
    fi

    # Set defaults for any unset values
    postgres_host="${postgres_host:-postgres-service}"
    postgres_port="${postgres_port:-5432}"
    postgres_db="${postgres_db:-smartem_db}"
    rabbitmq_host="${rabbitmq_host:-rabbitmq-service}"
    rabbitmq_port="${rabbitmq_port:-5672}"
    http_api_port="${http_api_port:-8000}"
    adminer_port="${adminer_port:-8080}"
    cors_allowed_origins="${cors_allowed_origins:-*}"

    log_info "Creating application ConfigMap for environment: $DEPLOY_ENV"
    log_info "POSTGRES_HOST=$postgres_host, POSTGRES_PORT=$postgres_port, POSTGRES_DB=$postgres_db"
    log_info "RABBITMQ_HOST=$rabbitmq_host, RABBITMQ_PORT=$rabbitmq_port"
    log_info "HTTP_API_PORT=$http_api_port, CORS_ALLOWED_ORIGINS=$cors_allowed_origins"

    kubectl create configmap smartem-config \
        --from-literal=POSTGRES_HOST="$postgres_host" \
        --from-literal=POSTGRES_PORT="$postgres_port" \
        --from-literal=POSTGRES_DB="$postgres_db" \
        --from-literal=RABBITMQ_HOST="$rabbitmq_host" \
        --from-literal=RABBITMQ_PORT="$rabbitmq_port" \
        --from-literal=HTTP_API_PORT="$http_api_port" \
        --from-literal=ADMINER_PORT="$adminer_port" \
        --from-literal=CORS_ALLOWED_ORIGINS="$cors_allowed_origins" \
        --namespace="$NAMESPACE"

    log_success "Application ConfigMap created with .env overrides"
}

# Build and import local image for development
ensure_local_image() {
    log_info "Ensuring local SmartEM image is available..."

    local image_name="smartem-decisions:latest"
    local temp_tar="/tmp/smartem-decisions-local.tar"

    # Check if image exists in Docker
    if ! docker image inspect "$image_name" &> /dev/null; then
        log_info "Building SmartEM image..."
        cd "$PROJECT_ROOT"
        docker build -t "$image_name" .
    else
        log_info "SmartEM image already exists in Docker"
    fi

    # Export and import to K3s (only if we have permissions)
    if command -v k3s &> /dev/null; then
        log_info "Importing image to K3s..."
        docker save "$image_name" -o "$temp_tar"

        # Try to import with different methods based on available permissions
        if sudo -n k3s ctr images import "$temp_tar" 2>/dev/null; then
            log_success "Image imported to K3s successfully"
        elif k3s ctr images import "$temp_tar" 2>/dev/null; then
            log_success "Image imported to K3s successfully"
        else
            log_warning "Could not import image to K3s (permission/access issue)"
            log_warning "SmartEM containers may fail to start"
        fi

        # Cleanup
        rm -f "$temp_tar"
    else
        log_warning "K3s not available, skipping image import"
    fi
}

# Deploy the environment
deploy_environment() {
    log_info "Deploying development environment..."

    cd "$PROJECT_ROOT"

    # Apply the kustomization first to create namespace
    kubectl apply -k "$K8S_ENV_PATH"

    # Ensure GHCR secret exists after namespace is created
    ensure_ghcr_secret

    # Ensure application secrets exist after namespace is created
    ensure_app_secrets

    # Ensure application configmap exists with dynamic values from .env
    ensure_app_configmap

    # Ensure local image is built and available for development
    ensure_local_image

    log_success "Deployment initiated"
}

# Wait for all pods to be ready
wait_for_pods() {
    log_info "Waiting for all pods to be ready..."
    
    local timeout=300  # 5 minutes
    local ready=false
    
    while [ $timeout -gt 0 ]; do
        local pending_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -E "(ContainerCreating|Pending|ImagePullBackOff|ErrImagePull)" | wc -l)
        local failed_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -E "(CrashLoopBackOff|Error|Failed)" | wc -l)
        local running_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "Running" | wc -l)
        local total_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
        
        if [ "$failed_pods" -gt 0 ]; then
            log_error "Some pods have failed. Check with: kubectl get pods -n $NAMESPACE"
            return 1
        fi
        
        if [ "$pending_pods" -eq 0 ] && [ "$running_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
            ready=true
            break
        fi
        
        echo -n "."
        sleep 5
        ((timeout -= 5))
    done
    
    echo ""  # New line after dots
    
    if [ "$ready" = true ]; then
        log_success "All pods are running!"
        return 0
    else
        log_error "Timeout waiting for pods to be ready"
        return 1
    fi
}

# Print access URLs
print_access_urls() {
    log_success "Development environment is ready!"
    echo ""
    echo -e "${GREEN}🌐 Access URLs:${NC}"
    echo -e "  ${BLUE}   Adminer (Database UI):${NC}     http://localhost:30808"
    echo -e "  ${BLUE}   RabbitMQ Management:${NC}       http://localhost:30673"
    echo -e "  ${BLUE}   SmartEM HTTP API:${NC}          http://localhost:30080"
    echo -e "  ${BLUE}   API Documentation:${NC}         http://localhost:30080/docs"
    echo ""
    echo -e "${YELLOW}💡 Quick Commands:${NC}"
    echo -e "  View all resources:    ${BLUE}kubectl get all -n $NAMESPACE${NC}"
    echo -e "  View pod logs:         ${BLUE}kubectl logs -f deployment/smartem-http-api -n $NAMESPACE${NC}"
    echo -e "  Stop environment:      ${BLUE}$0 down${NC}"
    echo ""
}

# Show status of the environment
show_status() {
    check_current_status
    
    echo ""
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        local ready_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "1/1.*Running" | wc -l)
        local total_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
        
        if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
            log_success "Environment is healthy ($ready_pods/$total_pods pods running)"
            print_access_urls
        else
            log_warning "Environment is not fully ready ($ready_pods/$total_pods pods running)"
        fi
    else
        log_info "Environment is not deployed"
    fi
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --docker-password)
                DOCKER_PASSWORD="$2"
                export DOCKER_PASSWORD
                log_info "Using provided docker password"
                shift 2
                ;;
            --docker-password=*)
                DOCKER_PASSWORD="${1#*=}"
                export DOCKER_PASSWORD
                log_info "Using provided docker password"
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                echo "Use '$0 help' for usage information"
                exit 1
                ;;
            *)
                # This is the command, stop parsing options
                COMMAND="$1"
                shift
                break
                ;;
        esac
    done
}

# Parse arguments first
COMMAND="${1:-up}"
if [[ "$1" == --* ]]; then
    parse_arguments "$@"
else
    shift || true  # Remove the command from arguments if it exists
fi

# Main command processing
case "$COMMAND" in
    "up")
        check_kubectl
        load_env_file
        validate_credentials
        check_current_status
        cleanup_environment
        deploy_environment
        if wait_for_pods; then
            print_access_urls
        else
            log_error "Deployment failed"
            exit 1
        fi
        ;;
    "down")
        check_kubectl
        cleanup_environment
        log_success "Environment stopped"
        ;;
    "status")
        check_kubectl
        show_status
        ;;
    "restart")
        check_kubectl
        load_env_file
        validate_credentials
        log_info "Restarting development environment..."
        cleanup_environment
        deploy_environment
        if wait_for_pods; then
            print_access_urls
        else
            log_error "Restart failed"
            exit 1
        fi
        ;;
    "logs")
        check_kubectl
        service="${2:-smartem-http-api}"
        log_info "Showing logs for $service..."
        kubectl logs -f "deployment/$service" -n "$NAMESPACE"
        ;;
    "help"|"-h"|"--help")
        echo "SmartEM Backend Development Environment Manager"
        echo ""
        echo "Usage: $0 [OPTIONS] [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  up       Start the development environment (default)"
        echo "  down     Stop and clean up the development environment"
        echo "  restart  Restart the development environment"
        echo "  status   Show current status of the environment"
        echo "  logs     Show logs for a service (default: smartem-http-api)"
        echo "  help     Show this help message"
        echo ""
        echo "Options:"
        echo "  --docker-password TOKEN   Use specific docker password/token"
        echo "                            (optional - auto-detects from 'gh auth token' if not set)"
        echo ""
        echo "Examples:"
        echo "  $0                              # Start environment (auto-detects token)"
        echo "  $0 up                           # Start environment"
        echo "  $0 down                         # Stop environment"
        echo "  $0 status                       # Check status"
        echo "  $0 logs smartem-worker          # Show worker logs"
        echo "  $0 --docker-password \"\$(gh auth token)\" up   # Explicit token override"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
