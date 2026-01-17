from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import crud, models, schemas
from app.database import get_db
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.Machine, summary="Create a new machine")
def create_machine(machine: schemas.MachineCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.create_machine(db=db, machine=machine)

@router.get("/", response_model=List[schemas.Machine], summary="List all machines")
def read_machines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_machines(db, skip=skip, limit=limit)

@router.get("/{machine_id}", response_model=schemas.Machine, summary="Get machine details")
def read_machine(machine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_machine = crud.get_machine(db, machine_id=machine_id)
    if db_machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    return db_machine

@router.post("/{machine_id}/maintenance", response_model=schemas.Maintenance, summary="Log maintenance")
def log_maintenance(machine_id: int, maintenance: schemas.MaintenanceCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if machine_id != maintenance.machine_id:
        raise HTTPException(status_code=400, detail="Machine ID mismatch")
    return crud.create_maintenance(db=db, maintenance=maintenance)

@router.get("/{machine_id}/maintenance", response_model=List[schemas.Maintenance], summary="Get maintenance history")
def read_maintenance(machine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_machine_maintenance(db, machine_id=machine_id)
