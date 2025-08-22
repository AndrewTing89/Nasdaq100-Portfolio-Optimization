#!/bin/bash
# ================================================================
# Portfolio Optimization Docker Deployment Script
# Complete setup and deployment automation
# ================================================================

set -e

# Color output functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="portfolio-optimization"
DOCKER_COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE_FILE="$SCRIPT_DIR/.env.example"

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to setup environment
setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE_FILE" ]; then
            log_info "Creating .env file from example..."
            cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
            log_warning "Please review and customize the .env file before proceeding"
            log_info "Key settings to review:"
            echo "  - HOST_DATA_DIR (where to store data)"
            echo "  - HOST_LOGS_DIR (where to store logs)"  
            echo "  - CRON_SCHEDULE (when to run analysis)"
            echo "  - RISK_FREE_RATE and other financial parameters"
            echo ""
            read -p "Press Enter after reviewing .env file..."
        else
            log_error ".env.example file not found"
            exit 1
        fi
    else
        log_info ".env file already exists"
    fi
}

# Function to create required directories
create_directories() {
    log_info "Creating required directories..."
    
    # Source environment variables
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
    fi
    
    # Default directories
    DATA_DIR="${HOST_DATA_DIR:-./data}"
    LOGS_DIR="${HOST_LOGS_DIR:-./logs}"
    SSL_DIR="${SSL_CERT_DIR:-./config/ssl}"
    
    # Create directories
    mkdir -p "$DATA_DIR"/{raw,processed,stocks,results,logs}
    mkdir -p "$LOGS_DIR"
    mkdir -p "$SSL_DIR"
    mkdir -p config
    mkdir -p scheduler
    mkdir -p dashboard
    mkdir -p static
    
    # Set permissions
    chmod 755 "$DATA_DIR"
    chmod 755 "$LOGS_DIR"
    
    log_success "Directories created"
}

# Function to validate configuration files
validate_config() {
    log_info "Validating configuration files..."
    
    required_files=(
        "$DOCKER_COMPOSE_FILE"
        "Dockerfile.data-pipeline"
        "Dockerfile.dashboard"
        "Dockerfile.scheduler"
        "requirements-data-pipeline.txt"
        "requirements-dashboard.txt"
        "config/nginx.conf"
        "config/nginx-default.conf"
    )
    
    missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -f "$SCRIPT_DIR/$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        log_error "Missing configuration files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
    
    log_success "Configuration validation passed"
}

# Function to build images
build_images() {
    log_info "Building Docker images..."
    
    cd "$SCRIPT_DIR"
    
    # Build with docker-compose
    if command -v docker-compose &> /dev/null; then
        docker-compose build --parallel
    else
        docker compose build --parallel
    fi
    
    log_success "Images built successfully"
}

# Function to start services
start_services() {
    log_info "Starting services..."
    
    cd "$SCRIPT_DIR"
    
    # Determine profiles to use
    profiles=""
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
        if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
            profiles="--profile cloudflare"
        fi
    fi
    
    # Start services
    if command -v docker-compose &> /dev/null; then
        docker-compose $profiles up -d
    else
        docker compose $profiles up -d
    fi
    
    log_success "Services started"
}

# Function to check service health
check_health() {
    log_info "Checking service health..."
    
    # Wait a bit for services to start
    sleep 10
    
    services=("data-pipeline" "dashboard" "nginx")
    healthy_services=()
    unhealthy_services=()
    
    for service in "${services[@]}"; do
        if docker ps --filter "name=portfolio-$service" --filter "status=running" | grep -q portfolio-$service; then
            healthy_services+=("$service")
        else
            unhealthy_services+=("$service")
        fi
    done
    
    if [ ${#unhealthy_services[@]} -eq 0 ]; then
        log_success "All services are healthy"
    else
        log_warning "Some services are not healthy:"
        for service in "${unhealthy_services[@]}"; do
            echo "  - $service"
        done
    fi
    
    # Show running services
    log_info "Running services:"
    docker ps --filter "name=portfolio-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to show access information
show_access_info() {
    log_info "Deployment completed successfully!"
    echo ""
    echo "Access Information:"
    echo "=================="
    
    # Source environment for port information
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
    fi
    
    HTTP_PORT="${HTTP_PORT:-80}"
    DASHBOARD_PORT="8501"
    API_PORT="8080"
    
    echo "Dashboard:     http://localhost:$DASHBOARD_PORT"
    echo "API Endpoint:  http://localhost:$API_PORT"
    echo "Nginx Proxy:   http://localhost:$HTTP_PORT"
    echo ""
    echo "Health Checks:"
    echo "=============="
    echo "Pipeline:      curl http://localhost:$API_PORT/health"
    echo "Dashboard:     curl http://localhost:$DASHBOARD_PORT/_stcore/health"
    echo "Nginx:         curl http://localhost:$HTTP_PORT/health"
    echo ""
    echo "Useful Commands:"
    echo "==============="
    echo "View logs:     docker-compose logs -f [service-name]"
    echo "Stop services: docker-compose down"
    echo "Restart:       docker-compose restart"
    echo "Execute pipeline: curl -X POST http://localhost:$API_PORT/execute -d '{\"command\":\"full\"}' -H 'Content-Type: application/json'"
    echo ""
    
    # Show scheduler info if configured
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
        if [ -n "$CRON_SCHEDULE" ]; then
            echo "Scheduled Execution: $CRON_SCHEDULE"
            echo ""
        fi
    fi
}

# Function to display usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Complete deployment (default)"
    echo "  build     - Build Docker images only"
    echo "  start     - Start services"
    echo "  stop      - Stop services"
    echo "  restart   - Restart services"
    echo "  logs      - Show service logs"
    echo "  status    - Show service status"
    echo "  clean     - Clean up containers and images"
    echo "  help      - Show this help message"
}

# Function to stop services
stop_services() {
    log_info "Stopping services..."
    cd "$SCRIPT_DIR"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose down
    else
        docker compose down
    fi
    
    log_success "Services stopped"
}

# Function to restart services
restart_services() {
    log_info "Restarting services..."
    stop_services
    start_services
    check_health
}

# Function to show logs
show_logs() {
    cd "$SCRIPT_DIR"
    
    if [ $# -gt 1 ]; then
        service=$2
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f "$service"
        else
            docker compose logs -f "$service"
        fi
    else
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f
        else
            docker compose logs -f
        fi
    fi
}

# Function to show status
show_status() {
    log_info "Service status:"
    docker ps --filter "name=portfolio-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    log_info "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker ps --filter "name=portfolio-" -q)
}

# Function to clean up
clean_up() {
    log_warning "This will remove all containers, images, and data. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        cd "$SCRIPT_DIR"
        
        # Stop and remove containers
        if command -v docker-compose &> /dev/null; then
            docker-compose down -v --rmi all
        else
            docker compose down -v --rmi all
        fi
        
        # Remove orphaned containers
        docker container prune -f
        docker image prune -f
        
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

# Main execution
main() {
    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            setup_environment
            create_directories
            validate_config
            build_images
            start_services
            check_health
            show_access_info
            ;;
        build)
            check_prerequisites
            validate_config
            build_images
            ;;
        start)
            check_prerequisites
            start_services
            check_health
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs "$@"
            ;;
        status)
            show_status
            ;;
        clean)
            clean_up
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"