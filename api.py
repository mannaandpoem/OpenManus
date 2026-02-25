"""
Production FastAPI REST API for OpenManus.

Provides a scalable, authenticated REST interface for OpenManus agents
with comprehensive error handling, rate limiting, and OpenAPI documentation.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.agent.manus import ManusAgent
from app.config import Config


# ============================================================================
# Models & Schemas
# ============================================================================

class AgentRequest(BaseModel):
    """Request model for agent execution."""
    task: str = Field(..., min_length=1, max_length=10000, description="Task description")
    agent_type: str = Field(
        default="manus",
        description="Type of agent: manus, browser, swe, data_analysis"
    )
    timeout: int = Field(default=300, ge=10, le=3600, description="Timeout in seconds")
    verbose: bool = Field(default=False, description="Enable verbose logging")


class AgentResponse(BaseModel):
    """Response model for agent execution."""
    id: str = Field(..., description="Unique request ID")
    status: str = Field(..., description="Status: pending, running, completed, error")
    result: Optional[str] = Field(None, description="Agent result")
    error: Optional[str] = Field(None, description="Error message if failed")
    elapsed_seconds: float = Field(..., description="Execution time in seconds")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str
    code: str
    timestamp: str
    request_id: Optional[str] = None


# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="OpenManus API",
    description="Production REST API for OpenManus AI Agent Framework",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter


# ============================================================================
# Middleware
# ============================================================================

# CORS - Configure allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Security - Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
)


# ============================================================================
# Security & Authentication
# ============================================================================

def verify_api_key(x_api_key: str = Header(None)) -> str:
    """Verify API key from header."""
    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing API key")

    valid_key = os.getenv("OPENMANUS_API_KEY", "dev-key-change-in-production")
    if x_api_key != valid_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return x_api_key


async def get_request_id(request: Request) -> str:
    """Extract or generate request ID."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "code": "RATE_LIMIT_EXCEEDED",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code="HTTP_ERROR",
            timestamp=datetime.utcnow().isoformat(),
            request_id=request_id,
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            code="INTERNAL_ERROR",
            timestamp=datetime.utcnow().isoformat(),
            request_id=request_id,
        ).dict(),
    )


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post(
    "/api/v1/agent/run",
    response_model=AgentResponse,
    tags=["Agent"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def run_agent(request: Request, payload: AgentRequest):
    """
    Run an OpenManus agent with the given task.

    - **task**: Description of what the agent should do
    - **agent_type**: Type of agent to use (manus, browser, swe, data_analysis)
    - **timeout**: Maximum execution time in seconds (10-3600)
    - **verbose**: Enable verbose logging for debugging
    """
    request_id = await get_request_id(request)
    start_time = datetime.utcnow()

    try:
        # Validate input
        if not payload.task.strip():
            raise HTTPException(status_code=400, detail="Task cannot be empty")

        # Initialize config
        config = Config()

        # Create agent (simplified - extend with other agent types as needed)
        agent = ManusAgent(config)

        # Run agent with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(agent.run, payload.task),
                timeout=payload.timeout
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"Agent execution timeout after {payload.timeout} seconds"
            )

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return AgentResponse(
            id=request_id,
            status="completed",
            result=str(result),
            elapsed_seconds=elapsed,
            timestamp=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        return AgentResponse(
            id=request_id,
            status="error",
            error=str(e),
            elapsed_seconds=elapsed,
            timestamp=datetime.utcnow().isoformat(),
        )


@app.get(
    "/api/v1/agent/status/{request_id}",
    response_model=dict,
    tags=["Agent"],
    dependencies=[Depends(verify_api_key)],
)
async def get_agent_status(request_id: str):
    """Get status of a previous agent execution (requires implementation of persistence)."""
    return {
        "request_id": request_id,
        "status": "pending",
        "message": "Status tracking requires persistence layer implementation"
    }


@app.get("/api/v1/config", tags=["Config"], dependencies=[Depends(verify_api_key)])
async def get_config():
    """Get current server configuration (non-sensitive)."""
    return {
        "api_version": "1.0.0",
        "agent_types": ["manus", "browser", "swe", "data_analysis"],
        "max_timeout": 3600,
        "rate_limit": "100/minute",
    }


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    print("OpenManus API starting up...")
    # Initialize any required services here


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("OpenManus API shutting down...")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=int(os.getenv("WORKERS", 2)),
    )
