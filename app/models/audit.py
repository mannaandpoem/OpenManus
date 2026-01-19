from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from app.database import Base
import datetime

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String) # e.g., "STATUS_CHANGE", "UPLOAD_DOC"
    resource_type = Column(String) # e.g., "request", "machine"
    resource_id = Column(Integer)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    details = Column(JSON) # Store before/after state
