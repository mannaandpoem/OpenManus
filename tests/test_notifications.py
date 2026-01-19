import pytest
from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from .test_workflow import TestingSessionLocal, override_get_db, setup_db, client
import datetime

app.dependency_overrides[get_db] = override_get_db

def test_notifications():
    # Create a request with an expiring contract
    today = datetime.date.today()
    expiration = today + datetime.timedelta(days=10)

    # First create a request
    client.post("/api/requests/", json={"description": "Expiring machine", "client_id": "CL-EXP"})
    request_id = 1 # In a fresh DB this will be 1

    # Update contract details
    client.put(f"/api/requests/{request_id}/contract-details", json={
        "contract_expiration": expiration.isoformat(),
        "adjustment_month": today.month
    })

    # Get notifications
    response = client.get("/api/requests/notifications/upcoming")
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["id"] == request_id
