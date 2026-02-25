# OpenManus REST API Documentation

Complete REST API reference for the OpenManus AI Agent Framework.

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Endpoints](#endpoints)
- [Examples](#examples)
- [SDKs](#sdks)

## Base URL

```
https://api.yourdomain.com/api/v1
# or locally
http://localhost:8000/api/v1
```

## Authentication

All API endpoints (except `/health`) require API key authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" https://api.yourdomain.com/api/v1/agent/run
```

### Getting an API Key

1. Contact administrator
2. Generate via management panel
3. Or set `OPENMANUS_API_KEY` environment variable

### API Key Security

- Keep keys secret
- Use HTTPS only
- Rotate keys regularly
- Use separate keys for different environments
- Never commit keys to version control

## Response Format

All responses are JSON with consistent structure:

### Success Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "Agent execution result...",
  "elapsed_seconds": 2.5,
  "timestamp": "2025-02-25T12:34:56Z"
}
```

### Error Response

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "timestamp": "2025-02-25T12:34:56Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Fix request format/validation |
| 403 | Forbidden | Check API key or permissions |
| 429 | Too Many Requests | Reduce request rate, wait then retry |
| 500 | Server Error | Retry with exponential backoff |
| 504 | Timeout | Agent execution exceeded timeout |

### Error Codes

- `INVALID_API_KEY` - API key missing or invalid
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `VALIDATION_ERROR` - Request validation failed
- `TIMEOUT_ERROR` - Agent execution timeout
- `AGENT_ERROR` - Agent execution failed
- `INTERNAL_ERROR` - Server error

### Retry Strategy

```python
import time
import requests

def call_with_retry(url, headers, json_data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=json_data)
            if response.status_code == 429:
                wait_time = (2 ** attempt)  # Exponential backoff
                time.sleep(wait_time)
                continue
            return response
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

## Rate Limiting

### Limits

- **Default**: 100 requests/minute per IP
- **With API key**: 1000 requests/minute

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1614344400
```

### Handling Rate Limits

When rate limited (429 response):

1. Check `X-RateLimit-Reset` header
2. Wait until that timestamp
3. Retry request

## Endpoints

### Health Check

Check API server health.

```
GET /health
```

**Authentication**: None required

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-02-25T12:34:56Z",
  "version": "1.0.0"
}
```

### Run Agent

Execute an agent with a given task.

```
POST /api/v1/agent/run
```

**Authentication**: Required (X-API-Key)

**Request Body**:
```json
{
  "task": "Write a Python script to calculate fibonacci numbers",
  "agent_type": "manus",
  "timeout": 60,
  "verbose": false
}
```

**Parameters**:
- `task` (string, required): Description of task (1-10000 chars)
- `agent_type` (string, optional): Type of agent to use
  - `manus` - General purpose (default)
  - `browser` - Web browsing and interaction
  - `swe` - Software engineering tasks
  - `data_analysis` - Data analysis and visualization
- `timeout` (integer, optional): Max execution time in seconds (10-3600, default: 300)
- `verbose` (boolean, optional): Enable verbose logging (default: false)

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "#!/usr/bin/env python3\ndef fibonacci(n):\n...",
  "elapsed_seconds": 2.5,
  "timestamp": "2025-02-25T12:34:56Z"
}
```

**Status Values**:
- `pending` - Queued for execution
- `running` - Currently executing
- `completed` - Successfully completed
- `error` - Failed with error

### Get Agent Status

Get status of a previous agent execution.

```
GET /api/v1/agent/status/{request_id}
```

**Authentication**: Required (X-API-Key)

**Parameters**:
- `request_id` (string): ID from previous agent run

**Response**:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "...",
  "timestamp": "2025-02-25T12:34:56Z"
}
```

**Note**: Status tracking requires persistence layer implementation.

### Get Configuration

Retrieve API configuration.

```
GET /api/v1/config
```

**Authentication**: Required (X-API-Key)

**Response**:
```json
{
  "api_version": "1.0.0",
  "agent_types": ["manus", "browser", "swe", "data_analysis"],
  "max_timeout": 3600,
  "rate_limit": "100/minute"
}
```

## Examples

### Python

```python
import requests
import json

BASE_URL = "https://api.yourdomain.com/api/v1"
API_KEY = "your-api-key-here"

def run_agent(task, agent_type="manus", timeout=60):
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "task": task,
        "agent_type": agent_type,
        "timeout": timeout,
        "verbose": False
    }

    response = requests.post(
        f"{BASE_URL}/agent/run",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Result: {result['result']}")
        print(f"Time: {result['elapsed_seconds']}s")
    else:
        print(f"Error: {response.json()}")

# Usage
run_agent("Write a hello world program in Python")
```

### JavaScript/Node.js

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "https://api.yourdomain.com/api/v1";

async function runAgent(task, agentType = "manus", timeout = 60) {
  const response = await fetch(`${BASE_URL}/agent/run`, {
    method: "POST",
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      task: task,
      agent_type: agentType,
      timeout: timeout,
      verbose: false
    })
  });

  if (response.ok) {
    const result = await response.json();
    console.log(`Result: ${result.result}`);
    console.log(`Time: ${result.elapsed_seconds}s`);
  } else {
    const error = await response.json();
    console.error(`Error: ${error.error}`);
  }
}

// Usage
runAgent("Write a hello world program in JavaScript");
```

### cURL

```bash
# Basic request
curl -X POST https://api.yourdomain.com/api/v1/agent/run \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Write a hello world program",
    "timeout": 60
  }'

# With custom request ID
curl -X POST https://api.yourdomain.com/api/v1/agent/run \
  -H "X-API-Key: your-api-key" \
  -H "X-Request-ID: custom-request-123" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze this CSV data",
    "agent_type": "data_analysis"
  }'

# Check health
curl https://api.yourdomain.com/health
```

## SDKs

### Official SDKs

- **Python**: `pip install openmanus-sdk`
- **JavaScript/TypeScript**: `npm install openmanus-sdk`
- **Go**: `go get github.com/openmanus/sdk-go`

### Community SDKs

- **Rust**: [openmanus-rs](https://github.com/community/openmanus-rs)
- **Java**: [openmanus-java](https://github.com/community/openmanus-java)

## API Standards

### Request ID Tracking

Provide an optional `X-Request-ID` header for request tracing:

```bash
curl -H "X-Request-ID: my-unique-id" https://api.yourdomain.com/api/v1/agent/run
```

### Pagination (Future)

When pagination is implemented:

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 10,
  "pages": 10
}
```

## Best Practices

### Error Handling

```python
try:
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e.response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"Request Error: {e}")
```

### Timeout Configuration

```python
# Always set reasonable timeouts
response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30  # 30 seconds for HTTP request
)
```

### Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(total=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

response = session.post(url, headers=headers, json=payload)
```

### Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.info(f"Calling agent with task: {task}")
logger.debug(f"Request ID: {request_id}")
```

## Support & Feedback

- GitHub Issues: https://github.com/FoundationAgents/OpenManus/issues
- Email: api-support@openmanus.dev
- Slack: [Join community](https://slack.openmanus.dev)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for API version history and breaking changes.

## License

OpenManus API is provided under the MIT License.
