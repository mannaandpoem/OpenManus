from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, date
from app.models import RequestStatus
from .machine import Machine

class QuoteBase(BaseModel):
    partner_id: int
    price: float
    details: str

class QuoteCreate(QuoteBase):
    request_id: int

class Quote(QuoteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_id: int

class RequestBase(BaseModel):
    description: str
    client_id: str
    machine_id: Optional[int] = None

class RequestCreate(RequestBase):
    pass

class HistoricalRequestImport(RequestBase):
    status: Optional[RequestStatus] = RequestStatus.COMPLETED
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[int] = None

class RequestUpdate(BaseModel):
    status: Optional[RequestStatus] = None
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[int] = None
    selected_quote_id: Optional[int] = None

class Request(RequestBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: RequestStatus
    created_at: datetime
    contract_expiration: Optional[date] = None
    adjustment_month: Optional[int] = None
    machine_id: Optional[int] = None
    selected_quote_id: Optional[int] = None
    quotes: List[Quote] = []
    documents: List["Document"] = []
    machine: Optional[Machine] = None

# Forward reference for Document
from .document import Document
Request.model_rebuild()
