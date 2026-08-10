from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
from .models import RequestStatus, DocumentType

class QuoteBase(BaseModel):
    partner_id: int
    price: float
    details: str

class QuoteCreate(QuoteBase):
    request_id: int

class Quote(QuoteBase):
    id: int
    request_id: int

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    doc_type: DocumentType
    file_path: str
    filename: str

class DocumentCreate(DocumentBase):
    request_id: int

class Document(DocumentBase):
    id: int
    request_id: int
    uploaded_at: datetime

    class Config:
        from_attributes = True

class RequestBase(BaseModel):
    description: str
    client_id: str

class RequestCreate(RequestBase):
    pass

class HistoricalRequestImport(RequestBase):
    status: Optional[RequestStatus] = RequestStatus.COMPLETED
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[str] = None

class RequestUpdate(BaseModel):
    status: Optional[RequestStatus] = None
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[str] = None
    selected_quote_id: Optional[int] = None

class Request(RequestBase):
    id: int
    status: RequestStatus
    created_at: datetime
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[str] = None
    selected_quote_id: Optional[int] = None
    quotes: List[Quote] = []
    documents: List[Document] = []

    class Config:
        from_attributes = True

class PartnerBase(BaseModel):
    name: str
    contact_info: str

class PartnerCreate(PartnerBase):
    pass

class Partner(PartnerBase):
    id: int

    class Config:
        from_attributes = True
