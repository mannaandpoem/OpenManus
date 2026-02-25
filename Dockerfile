# ============================================================================
# Multi-stage build for optimized production image
# ============================================================================

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution
RUN pip install --no-cache-dir uv

# Copy requirements and build dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# ============================================================================
# Stage 2: Runtime
# ============================================================================

FROM python:3.12-slim

LABEL maintainer="OpenManus <team@openmanus.dev>"
LABEL description="Production-grade OpenManus AI Agent Framework API"
LABEL version="1.0.0"

WORKDIR /app

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r openmanus && useradd -r -g openmanus openmanus

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=openmanus:openmanus . .

# Create necessary directories
RUN mkdir -p config workspace logs && \
    chown -R openmanus:openmanus config workspace logs

# Switch to non-root user
USER openmanus

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    WORKERS=2 \
    LOG_LEVEL=INFO

EXPOSE 8000

# Default command: start API server
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
