# OpenManus Deployment Guide

Complete step-by-step guide for deploying OpenManus to production environments.

## Quick Start (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus

# 2. Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# 3. Edit configuration
nano .env

# 4. Start services
docker-compose up -d

# 5. Verify
curl http://localhost:8000/health
```

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2+ CPU cores, 4GB+ RAM
- Linux server (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- Internet connectivity for LLM API calls

## Deployment Options

### Option 1: Docker Compose (Recommended for Small-Medium Scale)

Easiest deployment method with built-in monitoring.

**Pros:**
- Simple setup
- Single command deployment
- Includes monitoring stack
- Easy to scale

**Steps:**

```bash
# Clone and setup
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus

# Configure
cp .env.example .env
# Edit .env with your API keys and settings

# Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify
docker-compose ps
curl -H "X-API-Key: $(grep OPENMANUS_API_KEY .env)" http://localhost:8000/api/v1/config
```

### Option 2: Kubernetes (For Large-Scale Production)

Deploy on Kubernetes for high availability and auto-scaling.

**Prerequisites:**
- Kubernetes 1.24+
- kubectl configured
- Container registry access

**Steps:**

```bash
# 1. Build and push image
docker build -t your-registry.com/openmanus:latest .
docker push your-registry.com/openmanus:latest

# 2. Create namespace
kubectl create namespace openmanus
kubectl create secret generic openmanus-secrets \
  --from-literal=api-key=your-api-key \
  --from-literal=openai-key=sk-... \
  -n openmanus

# 3. Deploy using Helm or kubectl
kubectl apply -f k8s/deployment.yaml -n openmanus
kubectl apply -f k8s/service.yaml -n openmanus

# 4. Verify
kubectl get pods -n openmanus
kubectl logs -f deployment/openmanus-api -n openmanus
```

**Kubernetes manifests** (sample):

```yaml
# k8s/deployment.yaml
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
        image: your-registry.com/openmanus:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENMANUS_API_KEY
          valueFrom:
            secretKeyRef:
              name: openmanus-secrets
              key: api-key
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openmanus-secrets
              key: openai-key
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
---
apiVersion: v1
kind: Service
metadata:
  name: openmanus-api
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: openmanus-api
```

### Option 3: Manual Installation (For Development/Testing)

Install directly on server without Docker.

**Steps:**

```bash
# 1. Install dependencies
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip

# 2. Clone repository
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus

# 3. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Configure
cp config/config.example.toml config/config.toml
# Edit config.toml with your settings

# 6. Run with Gunicorn
pip install gunicorn
gunicorn api:app --workers 4 --bind 0.0.0.0:8000

# 7. Setup systemd service (optional)
sudo cat > /etc/systemd/system/openmanus.service << EOF
[Unit]
Description=OpenManus API Service
After=network.target

[Service]
Type=notify
User=openmanus
WorkingDirectory=/opt/openmanus
Environment="PATH=/opt/openmanus/venv/bin"
ExecStart=/opt/openmanus/venv/bin/gunicorn api:app --workers 4 --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable openmanus
sudo systemctl start openmanus
```

## Pre-Production Checklist

- [ ] API keys configured for all LLM providers
- [ ] SSL/TLS certificates installed
- [ ] Environment variables validated
- [ ] Database backups configured
- [ ] Monitoring alerts set up
- [ ] Rate limiting configured
- [ ] CORS origins whitelisted
- [ ] Firewall rules configured
- [ ] Log aggregation set up
- [ ] Disaster recovery plan documented
- [ ] Security audit completed
- [ ] Load testing performed

## Configuration

### Environment Variables

Key production variables to set:

```bash
# Security
OPENMANUS_API_KEY=your-secure-key
OPENAI_API_KEY=sk-your-key

# Performance
WORKERS=4
REQUEST_TIMEOUT=300

# Network
CORS_ORIGINS=https://yourdomain.com
TRUSTED_HOSTS=yourdomain.com

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost/openmanus
```

### SSL/TLS Setup

**Using Let's Encrypt:**

```bash
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Copy to application
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/ssl/key.pem

# Auto-renew
echo "0 0 1 * * certbot renew --quiet" | sudo crontab -
```

## Health Checks & Monitoring

### Health Endpoint

```bash
curl http://localhost:8000/health
# Response: {"status":"healthy","timestamp":"2025-02-25T...","version":"1.0.0"}
```

### Monitoring with Prometheus

Metrics available at `/metrics`

```bash
curl http://localhost:8000/metrics
```

### Prometheus Configuration

Edit `docker/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'openmanus-api'
    static_configs:
      - targets: ['localhost:8000']
```

Access Prometheus dashboard: `http://localhost:9090`

## Scaling

### Horizontal Scaling

**With Docker Compose:**

```bash
docker-compose up -d --scale api=3
```

**With Kubernetes:**

```bash
kubectl scale deployment openmanus-api --replicas=5 -n openmanus
```

### Vertical Scaling

Increase resources in `docker-compose.yml`:

```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '8'
        memory: 16G
```

## Backup & Recovery

### Automatic Backups

Docker Compose production setup includes automated backups (see `docker-compose.prod.yml`)

### Manual Backup

```bash
# Backup configuration and workspace
tar -czf openmanus-backup-$(date +%Y%m%d).tar.gz config/ workspace/

# Upload to S3
aws s3 cp openmanus-backup-*.tar.gz s3://your-bucket/backups/
```

### Restore

```bash
# Extract backup
tar -xzf openmanus-backup-20250225.tar.gz

# Restart services
docker-compose restart
```

## Updates & Maintenance

### Update to Latest Version

```bash
# Pull latest code
git pull origin main

# Rebuild image
docker build -t openmanus:latest .

# Restart services
docker-compose down
docker-compose up -d
```

### Zero-Downtime Updates (with multiple instances)

```bash
# 1. Update one instance at a time
docker-compose up -d --scale api=4

# 2. Replace instances gradually
for i in 1 2 3; do
  docker-compose restart api.$i
  sleep 30
done
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs -f api

# Check disk space
df -h

# Check ports
lsof -i :8000
```

### High Memory Usage

```bash
# Check top consumers
docker stats

# Reduce worker count
WORKERS=2 docker-compose up -d
```

### API Timeouts

```bash
# Increase timeout
REQUEST_TIMEOUT=600 docker-compose up -d

# Check agent logs
docker-compose logs api | grep -i timeout
```

### Database Connection Issues

```bash
# Test connection
docker-compose exec api python3 -c "import psycopg2; psycopg2.connect('dbname=openmanus')"

# Check credentials
env | grep DATABASE_URL
```

## Production Best Practices

1. **Always use HTTPS** - Configure SSL/TLS certificates
2. **Secure API keys** - Use secrets manager, never in code
3. **Enable monitoring** - Track errors, performance, and uptime
4. **Set rate limits** - Protect against abuse
5. **Regular backups** - Daily automated backups
6. **Log aggregation** - Centralized logging system
7. **Disaster recovery** - Plan and test recovery procedures
8. **Security updates** - Keep dependencies updated
9. **Load testing** - Verify capacity before production
10. **Documentation** - Maintain deployment runbooks

## Support

- **Issues**: https://github.com/FoundationAgents/OpenManus/issues
- **Discussions**: https://github.com/FoundationAgents/OpenManus/discussions
- **Email**: support@openmanus.dev
- **Slack**: [Community](https://join.slack.com/t/openmanus/shared_invite/...)

## License

OpenManus is provided under the MIT License.
