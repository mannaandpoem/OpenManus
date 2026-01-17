from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import crud, schemas, models
from app.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.Partner, summary="Register a partner")
def create_partner(partner: schemas.PartnerCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Registers a new partner/supplier in the system."""
    return crud.create_partner(db=db, partner=partner)

@router.get("/", response_model=List[schemas.Partner], summary="List partners")
def read_partners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_partners(db, skip=skip, limit=limit)
