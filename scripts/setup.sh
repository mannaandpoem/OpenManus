#!/bin/bash

###############################################################################
# OpenManus Production Setup Script
#
# Automates initial setup and configuration for production deployment
# Usage: ./scripts/setup.sh [--prod] [--with-monitoring] [--with-ssl]
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PRODUCTION_MODE=false
SETUP_MONITORING=false
SETUP_SSL=false

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_requirements() {
    print_header "Checking Requirements"

    local missing=0

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker 20.10+"
        missing=$((missing + 1))
    else
        print_success "Docker installed: $(docker --version)"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose 2.0+"
        missing=$((missing + 1))
    else
        print_success "Docker Compose installed: $(docker-compose --version)"
    fi

    # Check Python (optional)
    if command -v python3 &> /dev/null; then
        print_success "Python 3 installed: $(python3 --version)"
    else
        print_warning "Python 3 not found (optional for CLI tools)"
    fi

    if [ $missing -gt 0 ]; then
        print_error "Missing $missing required tools. Please install them and try again."
        exit 1
    fi
}

setup_directories() {
    print_header "Setting Up Directories"

    mkdir -p "${PROJECT_DIR}/config"
    mkdir -p "${PROJECT_DIR}/workspace"
    mkdir -p "${PROJECT_DIR}/logs"
    mkdir -p "${PROJECT_DIR}/backups"
    mkdir -p "${PROJECT_DIR}/docker/ssl"

    print_success "Created necessary directories"
}

setup_env_file() {
    print_header "Setting Up Environment Configuration"

    if [ -f "${PROJECT_DIR}/.env" ]; then
        print_warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping .env setup"
            return
        fi
    fi

    # Generate secure API key
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "change-me-$(date +%s)")

    cat > "${PROJECT_DIR}/.env" << EOF
# OpenManus Production Environment Configuration
# Generated: $(date)

# Core API
PORT=8000
WORKERS=2
LOG_LEVEL=INFO

# LLM Provider (set your API keys)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o

# API Security
OPENMANUS_API_KEY=${API_KEY}

# Network
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
TRUSTED_HOSTS=localhost,127.0.0.1

# Feature Flags
DEBUG=false
ENABLE_DOCS=true
EOF

    chmod 600 "${PROJECT_DIR}/.env"
    print_success "Created .env file (do not commit this file!)"
    print_warning "IMPORTANT: Edit .env to add your LLM API keys"
}

setup_ssl_certificates() {
    print_header "Setting Up SSL Certificates"

    if [ -f "${PROJECT_DIR}/docker/ssl/cert.pem" ] && [ -f "${PROJECT_DIR}/docker/ssl/key.pem" ]; then
        print_warning "SSL certificates already exist"
        return
    fi

    print_info "Generating self-signed certificate for development..."
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out "${PROJECT_DIR}/docker/ssl/cert.pem" \
        -keyout "${PROJECT_DIR}/docker/ssl/key.pem" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=OpenManus/CN=localhost"

    print_success "Generated self-signed certificate"
    print_warning "For production, use Let's Encrypt or a commercial CA"
}

setup_config_files() {
    print_header "Setting Up Configuration Files"

    # Copy example config if needed
    if [ ! -f "${PROJECT_DIR}/config/config.toml" ]; then
        if [ -f "${PROJECT_DIR}/config/config.example.toml" ]; then
            cp "${PROJECT_DIR}/config/config.example.toml" "${PROJECT_DIR}/config/config.toml"
            print_success "Created config/config.toml from example"
        fi
    fi
}

build_docker_image() {
    print_header "Building Docker Image"

    print_info "Building OpenManus Docker image..."
    docker build -t openmanus:latest "${PROJECT_DIR}"

    print_success "Docker image built successfully"
}

start_services() {
    print_header "Starting Services"

    if [ "$PRODUCTION_MODE" = true ]; then
        print_info "Starting in PRODUCTION mode..."
        cd "${PROJECT_DIR}"
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    else
        print_info "Starting in DEVELOPMENT mode..."
        cd "${PROJECT_DIR}"
        docker-compose up -d
    fi

    print_success "Services started"
    print_info "Waiting for services to be healthy..."
    sleep 5
}

verify_deployment() {
    print_header "Verifying Deployment"

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "API is healthy"
            break
        fi
        attempt=$((attempt + 1))
        if [ $((attempt % 5)) -eq 0 ]; then
            print_info "Waiting for API to be ready... ($attempt/$max_attempts)"
        fi
        sleep 1
    done

    if [ $attempt -eq $max_attempts ]; then
        print_error "API failed to start after ${max_attempts} seconds"
        echo "Logs:"
        docker-compose logs api | tail -20
        exit 1
    fi

    # Test API
    print_info "Testing API endpoint..."
    RESPONSE=$(curl -s http://localhost:8000/health)
    if echo "$RESPONSE" | grep -q "healthy"; then
        print_success "API endpoint is responding correctly"
    else
        print_error "API health check failed"
        echo "Response: $RESPONSE"
        exit 1
    fi
}

show_summary() {
    print_header "Setup Complete!"

    echo ""
    echo -e "${GREEN}OpenManus is ready for use!${NC}"
    echo ""
    echo "Key Information:"
    echo "================"
    echo -e "  API URL:            ${YELLOW}http://localhost:8000${NC}"
    echo -e "  Documentation:      ${YELLOW}http://localhost:8000/api/docs${NC}"
    echo -e "  API Key:            ${YELLOW}Check .env file${NC}"
    echo ""
    echo "Quick Commands:"
    echo "==============="
    echo "  View logs:          docker-compose logs -f api"
    echo "  Stop services:      docker-compose down"
    echo "  Restart services:   docker-compose restart"
    echo "  Check status:       docker-compose ps"
    echo ""
    echo "Next Steps:"
    echo "==========="
    echo "  1. Edit .env file with your LLM API keys"
    echo "  2. Visit http://localhost:8000/api/docs for API documentation"
    echo "  3. Test API with: curl -H 'X-API-Key: YOUR_KEY' http://localhost:8000/api/v1/config"
    echo ""

    if [ "$PRODUCTION_MODE" = true ]; then
        echo -e "${YELLOW}Production Mode Settings:${NC}"
        echo "  - Running with monitoring stack"
        echo "  - Prometheus: http://localhost:9090"
        echo "  - Automatic backups enabled"
        echo "  - Enhanced logging"
        echo ""
    fi

    echo "Documentation:"
    echo "=============="
    echo "  - API Guide:         ./API.md"
    echo "  - Production Guide:  ./PRODUCTION.md"
    echo "  - README:            ./README.md"
    echo ""
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --prod)
                PRODUCTION_MODE=true
                shift
                ;;
            --with-monitoring)
                SETUP_MONITORING=true
                shift
                ;;
            --with-ssl)
                SETUP_SSL=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Usage: ./scripts/setup.sh [OPTIONS]

Options:
  --prod              Setup for production deployment (includes monitoring)
  --with-monitoring   Enable monitoring stack (Prometheus, etc.)
  --with-ssl          Generate SSL certificates
  --help              Show this help message

Examples:
  ./scripts/setup.sh                    # Development setup
  ./scripts/setup.sh --prod --with-ssl  # Production setup with SSL
EOF
}

###############################################################################
# Main Execution
###############################################################################

main() {
    print_header "OpenManus Production Setup"
    print_info "Setting up OpenManus for deployment..."
    echo ""

    parse_arguments "$@"

    check_requirements
    setup_directories
    setup_env_file
    setup_config_files

    if [ "$SETUP_SSL" = true ]; then
        setup_ssl_certificates
    fi

    build_docker_image
    start_services
    verify_deployment
    show_summary
}

# Run main function
main "$@"
