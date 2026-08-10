from sqlalchemy.orm import Session
from . import models, schemas

def get_request(db: Session, request_id: int):
    return db.query(models.Request).filter(models.Request.id == request_id).first()

def get_requests(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Request).offset(skip).limit(limit).all()

def create_request(db: Session, request: schemas.RequestCreate):
    db_request = models.Request(**request.model_dump())
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

def update_request(db: Session, request_id: int, request_update: schemas.RequestUpdate):
    db_request = get_request(db, request_id)
    if db_request:
        update_data = request_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_request, key, value)
        db.commit()
        db.refresh(db_request)
    return db_request

def create_partner(db: Session, partner: schemas.PartnerCreate):
    db_partner = models.Partner(**partner.model_dump())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

def get_partners(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Partner).offset(skip).limit(limit).all()

def create_quote(db: Session, quote: schemas.QuoteCreate):
    db_quote = models.Quote(**quote.model_dump())
    db.add(db_quote)
    db.commit()
    db.refresh(db_quote)
    return db_quote

def create_document(db: Session, document: schemas.DocumentCreate):
    db_document = models.Document(**document.model_dump())
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document
