from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models import DocumentType, DocumentStatus

class DocumentBase(BaseModel):
    doc_type: DocumentType
    file_path: str
    filename: str
    file_hash: Optional[str] = None
    version: int = 1
    status: DocumentStatus = DocumentStatus.PENDING
    valid_until: Optional[datetime] = None

class DocumentCreate(DocumentBase):
    request_id: int

class Document(DocumentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_id: int
    uploaded_at: datetime
