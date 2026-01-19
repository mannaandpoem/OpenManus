from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date
from app.models import MachineStatus

class MachineBase(BaseModel):
    serial_number: str
    model: str
    brand: str
    installation_date: Optional[date] = None
    status: MachineStatus = MachineStatus.ACTIVE
    location: Optional[str] = None

class MachineCreate(MachineBase):
    pass

class Machine(MachineBase):
    model_config = ConfigDict(from_attributes=True)
    id: int

class MaintenanceBase(BaseModel):
    machine_id: int
    date: date
    description: str
    technician: str
    cost: Optional[float] = None
    next_maintenance_date: Optional[date] = None

class MaintenanceCreate(MaintenanceBase):
    pass

class Maintenance(MaintenanceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
