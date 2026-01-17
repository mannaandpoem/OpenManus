from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import get_db
from app.api.deps import get_current_user
from typing import List

router = APIRouter()

@router.get("/summary", summary="Get system-wide summary for external dashboards")
def get_system_summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns a consolidated summary of the system state for integration with external dashboards (e.g. Firebase)."""
    total_requests = db.query(models.Request).count()
    active_requests = db.query(models.Request).filter(models.Request.status != models.RequestStatus.COMPLETED).count()
    total_machines = db.query(models.Machine).count()
    active_machines = db.query(models.Machine).filter(models.Machine.status == models.MachineStatus.ACTIVE).count()

    # Recent activity
    recent_requests = db.query(models.Request).order_by(models.Request.created_at.desc()).limit(5).all()

    return {
        "stats": {
            "total_requests": total_requests,
            "active_requests": active_requests,
            "total_machines": total_machines,
            "active_machines": active_machines
        },
        "recent_activity": [
            {"id": r.id, "client": r.client_id, "status": r.status} for r in recent_requests
        ]
    }

@router.post("/notify-external", summary="Simulate notification to external system")
def notify_external(event_type: str, payload: dict, current_user: models.User = Depends(get_current_user)):
    """Simulates sending a webhook notification to an external system (like the DIVERSEY PWA)."""
    # In a real scenario, this would send an HTTP request to a configured URL
    return {"status": "success", "message": f"Notification for {event_type} sent to external system"}
