#!/bin/bash

set -e

NAMESPACE="smartem-decisions"
K8S_ENV_PATH="k8s/environments/development"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables from .dev.env
load_env_file() {
    local env_file="$PROJECT_ROOT/.dev.env"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Missing .dev.env file at: $env_file"
        log_error "Please copy .dev.env.example to .dev.env and configure your credentials"
        log_error "Example file location: $PROJECT_ROOT/.dev.env.example"
        log_error "Or use --docker-password parameter with 'gh auth token'"
        exit 1
    fi
    
    # Source the .dev.env file
    set -a  # automatically export all variables
    source "$env_file"
    set +a  # disable automatic export
    
    log_info "Loaded environment variables from .dev.env"
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
        log_error "Please check .dev.env.example for required variables or use --docker-password parameter"
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

# Deploy the environment
deploy_environment() {
    log_info "Deploying development environment..."
    
    cd "$PROJECT_ROOT"
    
    # Apply the kustomization first to create namespace
    kubectl apply -k "$K8S_ENV_PATH"
    
    # Ensure GHCR secret exists after namespace is created
    ensure_ghcr_secret
    
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
    echo -e "  ${BLUE}📊 Adminer (Database UI):${NC}     http://localhost:30808"
    echo -e "  ${BLUE}🐰 RabbitMQ Management:${NC}       http://localhost:30673"
    echo -e "  ${BLUE}📡 SmartEM HTTP API:${NC}          http://localhost:30080"
    echo -e "  ${BLUE}📚 API Documentation:${NC}         http://localhost:30080/docs"
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
