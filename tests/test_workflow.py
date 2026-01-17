import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.main import app
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_get_current_user():
    return User(id=1, email="test@example.com", full_name="Test User", role=UserRole.ADMIN, is_active=True)

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_full_workflow():
    # 1. Create Partner
    response = client.post("/api/partners/", json={"name": "Supplier X", "contact_info": "x@supplier.com"})
    assert response.status_code == 200
    partner_id = response.json()["id"]

    # 2. Create Request
    response = client.post("/api/requests/", json={"description": "New Dishwasher", "client_id": "CL-001"})
    assert response.status_code == 200
    request_id = response.json()["id"]
    assert response.json()["status"] == "quotation"

    # 3. Submit Quote
    response = client.post(f"/api/requests/{request_id}/quotes", json={
        "partner_id": partner_id,
        "price": 1200.50,
        "details": "High speed model"
    })
    assert response.status_code == 200
    quote_id = response.json()["id"]

    # Check status changed to supplier_interaction
    response = client.get(f"/api/requests/{request_id}")
    assert response.json()["status"] == "supplier_interaction"

    # 4. Select Quote
    response = client.post(f"/api/requests/{request_id}/select-quote", params={"quote_id": quote_id})
    assert response.status_code == 200
    assert response.json()["status"] == "selection"
    assert response.json()["selected_quote_id"] == quote_id

    # 5. Upload Contract
    with open("test_contract.txt", "w") as f:
        f.write("test contract")
    with open("test_contract.txt", "rb") as f:
        response = client.post(
            f"/api/documents/{request_id}/upload",
            params={"doc_type": "contract"},
            files={"file": ("contract.txt", f)}
        )
    assert response.status_code == 200
    assert response.json()["doc_type"] == "contract"

    # Check status changed to contracting
    response = client.get(f"/api/requests/{request_id}")
    assert response.json()["status"] == "contracting"

    # 6. Upload Invoice (NF)
    with open("test_nf.txt", "w") as f:
        f.write("test nf")
    with open("test_nf.txt", "rb") as f:
        response = client.post(
            f"/api/documents/{request_id}/upload",
            params={"doc_type": "invoice"},
            files={"file": ("nf.txt", f)}
        )
    assert response.status_code == 200

    # Check status changed to installation
    response = client.get(f"/api/requests/{request_id}")
    assert response.json()["status"] == "installation"

    # 7. Upload Acceptance Document
    with open("test_acc.txt", "w") as f:
        f.write("test acc")
    with open("test_acc.txt", "rb") as f:
        response = client.post(
            f"/api/documents/{request_id}/upload",
            params={"doc_type": "acceptance"},
            files={"file": ("acc.txt", f)}
        )
    assert response.status_code == 200

    # Check request status changed to technical_acceptance
    response = client.get(f"/api/requests/{request_id}")
    assert response.json()["status"] == "technical_acceptance"

    # 8. Complete Request
    response = client.post(f"/api/requests/{request_id}/complete-technical-acceptance")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    # Cleanup
    os.remove("test_contract.txt")
    os.remove("test_nf.txt")
    os.remove("test_acc.txt")
