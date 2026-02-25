# OpenManus Production Deployment Guide

This guide covers deploying OpenManus as a production-grade AI agent service with security hardening, monitoring, and high availability.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Docker Deployment](#docker-deployment)
4. [Security Configuration](#security-configuration)
5. [Environment Variables](#environment-variables)
6. [Monitoring & Logging](#monitoring--logging)
7. [API Usage](#api-usage)
8. [Troubleshooting](#troubleshooting)
9. [Scaling & Performance](#scaling--performance)

## System Requirements

### Minimum

- CPU: 2 cores
- Memory: 4GB RAM
- Disk: 20GB SSD
- Network: 1Gbps connection
- OS: Linux (Ubuntu 20.04+, Debian 11+)

### Recommended for Production

- CPU: 4+ cores
- Memory: 8GB+ RAM
- Disk: 50GB SSD
- Network: 1Gbps+ connection
- Container Orchestration: Kubernetes or Docker Swarm

### Software

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.12+ (if running without Docker)

## Pre-Deployment Checklist

- [ ] API keys for LLM providers (OpenAI, AWS Bedrock, etc.)
- [ ] SSL/TLS certificates (for HTTPS)
- [ ] Database setup (optional, for persistence)
- [ ] Monitoring system setup (Prometheus, ELK, etc.)
- [ ] Backup strategy defined
- [ ] Rate limiting thresholds configured
- [ ] CORS origins whitelist prepared
- [ ] API authentication tokens generated

## Docker Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus

# 2. Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# 3. Start services
docker-compose up -d

# 4. Verify health
curl http://localhost:8000/health
```

### Production Deployment

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check logs
docker-compose logs -f api

# Scale API workers
docker-compose up -d --scale api=3
```

### Building Custom Image

```bash
# Build image
docker build -t openmanus:latest .

# Push to registry
docker tag openmanus:latest myregistry.com/openmanus:latest
docker push myregistry.com/openmanus:latest

# Run
docker run -d \
  -e OPENMANUS_API_KEY=your-key \
  -e OPENAI_API_KEY=sk-xxx \
  -p 8000:8000 \
  myregistry.com/openmanus:latest
```

## Security Configuration

### 1. API Key Management

**Never commit secrets to version control.**

```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in environment
export OPENMANUS_API_KEY="your-generated-key-here"
```

**In production, use a secrets manager:**

```bash
# AWS Secrets Manager
aws secretsmanager create-secret --name openmanus/api-key --secret-string "key-value"

# HashiCorp Vault
vault kv put secret/openmanus/api-key value="key-value"

# Kubernetes Secrets
kubectl create secret generic openmanus-secrets --from-literal=api-key=value
```

### 2. HTTPS/SSL Configuration

Generate self-signed cert (development):

```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
mkdir -p docker/ssl
cp cert.pem docker/ssl/
cp key.pem docker/ssl/
```

Use Let's Encrypt (production):

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy to docker directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/ssl/key.pem
```

### 3. Firewall Rules

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block other ports
sudo ufw enable
```

### 4. Network Security

**Set CORS properly:**

```env
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

**Set trusted hosts:**

```env
TRUSTED_HOSTS=yourdomain.com,api.yourdomain.com
```

### 5. Rate Limiting

Edit `api.py` or use nginx configuration:

```conf
# In docker/nginx.conf
limit_req_zone $binary_remote_addr zone=general:10m rate=100r/m;
limit_req_zone $http_x_api_key zone=api_key:10m rate=1000r/m;

location /api/ {
    limit_req zone=general burst=20 nodelay;
    limit_req zone=api_key burst=100 nodelay;
}
```

## Environment Variables

### Required

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Or use AWS Bedrock
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
BEDROCK_MODEL=anthropic.claude-3-sonnet

# OpenManus API
OPENMANUS_API_KEY=your-secure-key
PORT=8000
WORKERS=2
```

### Optional

```bash
# Logging
LOG_LEVEL=INFO

# CORS & Security
CORS_ORIGINS=http://localhost:3000
TRUSTED_HOSTS=localhost,127.0.0.1

# Performance
WORKERS=4
MAX_RETRIES=3
REQUEST_TIMEOUT=300

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
```

### Full .env Template

See `.env.example` in repository.

## Monitoring & Logging

### Structured Logging

```python
# Logs are sent to stdout/stderr
# In docker-compose.yml:
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

### Integration with ELK Stack

```yaml
# docker-compose.yml addition
filebeat:
  image: elastic/filebeat:8.0.0
  volumes:
    - ./logs:/app/logs:ro
    - ./docker/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
  environment:
    - ELASTICSEARCH_HOSTS=elasticsearch:9200
```

### Prometheus Metrics

```bash
# Add to requirements.txt
prometheus-client

# Access metrics at /metrics
curl http://localhost:8000/metrics
```

### Health Checks

```bash
# Simple health check
curl http://localhost:8000/health

# With API key
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/config
```

## API Usage

### Authentication

All `/api/v1/*` endpoints require API key header:

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/agent/run
```

### Run Agent

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Write a Python hello world program",
    "agent_type": "manus",
    "timeout": 60,
    "verbose": false
  }'
```

### Response Example

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "#!/usr/bin/env python3\nprint(\"Hello, World!\")",
  "elapsed_seconds": 2.5,
  "timestamp": "2025-02-25T12:34:56Z"
}
```

### Documentation

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Verify image
docker images

# Test build
docker build -t openmanus:test .
```

### High CPU Usage

```bash
# Reduce workers
WORKERS=1 docker-compose up

# Check running tasks
docker-compose exec api ps aux

# Monitor resources
docker stats openmanus-api
```

### Out of Memory

```bash
# Increase memory limit in docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 8G

# Or via CLI
docker update --memory 8g openmanus-api
```

### API Key Issues

```bash
# Verify API key is set
docker-compose exec api env | grep OPENMANUS_API_KEY

# Update API key
docker-compose down
export OPENMANUS_API_KEY="new-key"
docker-compose up -d
```

### Connection Refused

```bash
# Check if port is in use
lsof -i :8000

# Check container networking
docker-compose exec api netstat -tlnp

# Verify firewall
sudo ufw status
```

## Scaling & Performance

### Horizontal Scaling

```bash
# Scale API instances
docker-compose up -d --scale api=5

# With load balancer (nginx in docker-compose.yml)
docker-compose up -d
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openmanus-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: openmanus-api
  template:
    metadata:
      labels:
        app: openmanus-api
    spec:
      containers:
      - name: api
        image: openmanus:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENMANUS_API_KEY
          valueFrom:
            secretKeyRef:
              name: openmanus-secrets
              key: api-key
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
```

### Performance Tuning

```bash
# Increase worker processes
WORKERS=4 docker-compose up

# Tune timeouts
REQUEST_TIMEOUT=300

# Connection pooling
POOL_SIZE=20

# Caching (implement based on use case)
CACHE_ENABLED=true
CACHE_TTL=300
```

## Maintenance

### Backup

```bash
# Backup configuration
tar -czf openmanus-backup-$(date +%Y%m%d).tar.gz config/ workspace/

# Restore
tar -xzf openmanus-backup-20250225.tar.gz
```

### Updates

```bash
# Update image
git pull origin main
docker build -t openmanus:latest .

# Restart with new image
docker-compose up -d
```

### Monitoring Uptime

```bash
# Add to crontab for health checks
* * * * * curl -f http://localhost:8000/health || echo "OpenManus down at $(date)" >> /var/log/openmanus-health.log
```

## Support

For issues and support:

- GitHub Issues: https://github.com/FoundationAgents/OpenManus/issues
- Documentation: https://github.com/FoundationAgents/OpenManus
- Email: team@openmanus.dev
