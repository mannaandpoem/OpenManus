from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from typing import Any, Optional

class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        resource_type: str,
        resource_id: int,
        user_id: Optional[int] = None,
        details: Optional[Any] = None
    ):
        db_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details
        )
        db.add(db_log)
        db.commit()
