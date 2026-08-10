from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
import datetime
import enum
from .database import Base

class RequestStatus(enum.Enum):
    QUOTATION = "quotation"
    SUPPLIER_INTERACTION = "supplier_interaction"
    SELECTION = "selection"
    CONTRACTING = "contracting"
    INSTALLATION = "installation"
    TECHNICAL_ACCEPTANCE = "technical_acceptance"
    COMPLETED = "completed"

class DocumentType(enum.Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"  # NF
    ACCEPTANCE = "acceptance"
    OTHER = "other"

class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    status = Column(Enum(RequestStatus), default=RequestStatus.QUOTATION)
    client_id = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Contract related fields
    contract_expiration = Column(Date, nullable=True)
    adjustment_month = Column(Integer, nullable=True) # 1-12
    machine_id = Column(String, nullable=True) # For machine history
    selected_quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=True)

    quotes = relationship("Quote", back_populates="request", foreign_keys="Quote.request_id")
    documents = relationship("Document", back_populates="request")

class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    contact_info = Column(String)

    quotes = relationship("Quote", back_populates="partner")

class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"))
    partner_id = Column(Integer, ForeignKey("partners.id"))
    price = Column(Float)
    details = Column(String)

    request = relationship("Request", back_populates="quotes", foreign_keys=[request_id])
    partner = relationship("Partner", back_populates="quotes")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"))
    doc_type = Column(Enum(DocumentType))
    file_path = Column(String)
    filename = Column(String)
    uploaded_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    request = relationship("Request", back_populates="documents")
