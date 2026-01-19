from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings
from app.database import engine
from app import models
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import logging
import uuid
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

# Create initial admin user if not exists
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core import security
db = SessionLocal()
admin_user = db.query(User).filter(User.email == "admin@example.com").first()
if not admin_user:
    admin_user = User(
        email="admin@example.com",
        hashed_password=security.get_password_hash("admin123"),
        full_name="Administrator",
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
db.close()

app = FastAPI(
    title="Dishwasher Workflow System",
    description="""
    API for managing the lifecycle of dishwasher procurement and maintenance.

    ## Workflow
    1. **Quotation**: Sales/Client initiates a request.
    2. **Supplier Interaction**: Partners submit quotes.
    3. **Selection**: A quote/partner is selected.
    4. **Contracting**: Contract is uploaded.
    5. **Installation**: Invoice (NF) is uploaded.
    6. **Technical Acceptance**: Final acceptance document is uploaded.
    7. **Completed**: Workflow finished.

    ## Features
    - Partner/Supplier management.
    - Document storage (Contracts, NFs, etc.) with security.
    - Contract expiration and adjustment notifications.
    - Historical data import.
    """,
    version="1.0.0"
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Keep old routes for compatibility or redirect them
app.include_router(api_router, prefix="/api")

# Mount static files
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(f"RID: {correlation_id} - {request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    return response

@app.get("/", include_in_schema=False)
def read_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")
