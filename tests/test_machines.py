import pytest
from .test_workflow import client, override_get_db, setup_db
from app.database import get_db
from app.main import app

app.dependency_overrides[get_db] = override_get_db

def test_machine_maintenance_workflow():
    # 1. Create Machine
    response = client.post("/api/v1/machines/", json={
        "serial_number": "SN-123",
        "model": "Turbo Clean 3000",
        "brand": "Hobart",
        "location": "Main Kitchen"
    })
    assert response.status_code == 200
    machine_id = response.json()["id"]
    assert response.json()["status"] == "active"

    # 2. Log Maintenance
    response = client.post(f"/api/v1/machines/{machine_id}/maintenance", json={
        "machine_id": machine_id,
        "date": "2024-05-20",
        "description": "General cleaning and filter replacement",
        "technician": "John Doe",
        "next_maintenance_date": "2024-11-20"
    })
    assert response.status_code == 200
    assert response.json()["machine_id"] == machine_id

    # 3. Get History
    response = client.get(f"/api/v1/machines/{machine_id}/maintenance")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["technician"] == "John Doe"

def test_workflow_machine_integration():
    # 1. Create Machine (status active by default)
    machine_res = client.post("/api/v1/machines/", json={
        "serial_number": "SN-INT",
        "model": "Integration Model",
        "brand": "TestBrand"
    })
    machine_id = machine_res.json()["id"]

    # 2. Create Request linked to machine
    req_res = client.post("/api/v1/requests/", json={
        "description": "Repair request",
        "client_id": "CL-INT",
        "machine_id": machine_id
    })
    request_id = req_res.json()["id"]

    # 3. Advance request through stages to completion
    # Quotation -> Supplier Interaction
    client.post(f"/api/v1/requests/{request_id}/quotes", json={
        "partner_id": 1, "price": 100, "details": "test"
    })
    # Supplier Interaction -> Selection
    client.post(f"/api/v1/requests/{request_id}/select-quote", params={"quote_id": 1})
    # Selection -> Contracting
    client.post(f"/api/v1/documents/{request_id}/upload", params={"doc_type": "contract"}, files={"file": ("c.txt", "content")})
    # Contracting -> Installation
    client.post(f"/api/v1/documents/{request_id}/upload", params={"doc_type": "invoice"}, files={"file": ("i.txt", "content")})
    # Installation -> Technical Acceptance
    client.post(f"/api/v1/documents/{request_id}/upload", params={"doc_type": "acceptance"}, files={"file": ("a.txt", "content")})

    # Technical Acceptance -> Completed
    response = client.post(f"/api/v1/requests/{request_id}/complete-technical-acceptance")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    # Verify machine installation date was updated (as per WorkflowService logic)
    # Actually WorkflowService.complete_request updates installation_date if it was an installation
    # Our logic does it for any request linked to a machine upon completion.
    machine_verify = client.get(f"/api/v1/machines/{machine_id}")
    assert machine_verify.json()["installation_date"] is not None
