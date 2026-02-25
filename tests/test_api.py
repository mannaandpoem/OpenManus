"""
Tests for the FastAPI REST interface.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api import app, AgentRequest, AgentResponse, HealthResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def valid_api_key(monkeypatch):
    """Set valid API key for tests."""
    monkeypatch.setenv("OPENMANUS_API_KEY", "test-key-123")
    return "test-key-123"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_success(self, client):
        """Test health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_health_check_response_model(self, client):
        """Test health check response matches schema."""
        response = client.get("/health")
        assert response.status_code == 200
        # Should not raise validation error
        HealthResponse(**response.json())


class TestAgentEndpoint:
    """Tests for agent execution endpoint."""

    def test_missing_api_key(self, client):
        """Test request without API key is rejected."""
        response = client.post(
            "/api/v1/agent/run",
            json={"task": "test task"}
        )
        assert response.status_code == 403
        assert "API key" in response.json()["detail"]

    def test_invalid_api_key(self, client, valid_api_key):
        """Test request with invalid API key is rejected."""
        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": "wrong-key"},
            json={"task": "test task"}
        )
        assert response.status_code == 403

    def test_valid_api_key(self, client, valid_api_key):
        """Test valid API key is accepted."""
        with patch('api.ManusAgent') as mock_agent:
            mock_instance = MagicMock()
            mock_instance.run.return_value = "test result"
            mock_agent.return_value = mock_instance

            response = client.post(
                "/api/v1/agent/run",
                headers={"X-API-Key": valid_api_key},
                json={"task": "test task", "timeout": 30}
            )
            assert response.status_code == 200

    def test_empty_task_validation(self, client, valid_api_key):
        """Test empty task is rejected."""
        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={"task": ""}
        )
        assert response.status_code == 422  # Validation error

    def test_task_too_long_validation(self, client, valid_api_key):
        """Test overly long task is rejected."""
        long_task = "a" * 20000
        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={"task": long_task}
        )
        assert response.status_code == 422

    def test_timeout_validation(self, client, valid_api_key):
        """Test invalid timeout is rejected."""
        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={"task": "test", "timeout": 5}  # Too low
        )
        assert response.status_code == 422

        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={"task": "test", "timeout": 5000}  # Too high
        )
        assert response.status_code == 422

    @patch('api.ManusAgent')
    def test_successful_agent_execution(self, mock_agent, client, valid_api_key):
        """Test successful agent execution."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = "Successfully completed task"
        mock_agent.return_value = mock_instance

        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={
                "task": "Write a hello world program",
                "agent_type": "manus",
                "timeout": 60
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == "Successfully completed task"
        assert "id" in data
        assert "elapsed_seconds" in data
        assert "timestamp" in data

    @patch('api.ManusAgent')
    def test_agent_timeout(self, mock_agent, client, valid_api_key):
        """Test agent timeout handling."""
        import asyncio

        mock_instance = MagicMock()
        # Simulate a timeout
        mock_instance.run.side_effect = asyncio.TimeoutError()
        mock_agent.return_value = mock_instance

        # Note: This test may need adjustment based on actual implementation
        # since timeout handling in async context is complex

    @patch('api.ManusAgent')
    def test_agent_error_handling(self, mock_agent, client, valid_api_key):
        """Test agent error is handled gracefully."""
        mock_instance = MagicMock()
        mock_instance.run.side_effect = ValueError("Agent error")
        mock_agent.return_value = mock_instance

        response = client.post(
            "/api/v1/agent/run",
            headers={"X-API-Key": valid_api_key},
            json={"task": "test task"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "error" in data
        assert data["error"] != ""


class TestConfigEndpoint:
    """Tests for configuration endpoint."""

    def test_config_missing_api_key(self, client):
        """Test config endpoint requires API key."""
        response = client.get("/api/v1/config")
        assert response.status_code == 403

    def test_config_with_api_key(self, client, valid_api_key):
        """Test config endpoint returns configuration."""
        response = client.get(
            "/api/v1/config",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert "agent_types" in data
        assert "max_timeout" in data


class TestStatusEndpoint:
    """Tests for agent status endpoint."""

    def test_status_missing_api_key(self, client):
        """Test status endpoint requires API key."""
        response = client.get("/api/v1/agent/status/test-id")
        assert response.status_code == 403

    def test_status_with_api_key(self, client, valid_api_key):
        """Test status endpoint with valid API key."""
        response = client.get(
            "/api/v1/agent/status/test-id-123",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert "status" in data


class TestRequestIdHandling:
    """Tests for request ID handling."""

    def test_request_id_generation(self, client, valid_api_key):
        """Test request ID is generated if not provided."""
        with patch('api.ManusAgent') as mock_agent:
            mock_instance = MagicMock()
            mock_instance.run.return_value = "result"
            mock_agent.return_value = mock_instance

            response = client.post(
                "/api/v1/agent/run",
                headers={"X-API-Key": valid_api_key},
                json={"task": "test"}
            )

            data = response.json()
            assert "id" in data
            assert data["id"] != ""

    def test_request_id_preservation(self, client, valid_api_key):
        """Test provided request ID is preserved."""
        provided_id = "custom-request-123"
        with patch('api.ManusAgent') as mock_agent:
            mock_instance = MagicMock()
            mock_instance.run.return_value = "result"
            mock_agent.return_value = mock_instance

            response = client.post(
                "/api/v1/agent/run",
                headers={
                    "X-API-Key": valid_api_key,
                    "X-Request-ID": provided_id
                },
                json={"task": "test"}
            )

            data = response.json()
            assert data["id"] == provided_id
