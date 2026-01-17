from sqlalchemy import Column, Integer, String, Enum, Date, Float, ForeignKey
from sqlalchemy.orm import relationship
import enum
import datetime
from app.database import Base

class MachineStatus(enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, index=True)
    model = Column(String)
    brand = Column(String)
    installation_date = Column(Date, nullable=True)
    status = Column(Enum(MachineStatus), default=MachineStatus.ACTIVE)
    location = Column(String)

    requests = relationship("Request", back_populates="machine")
    maintenance_logs = relationship("Maintenance", back_populates="machine")

class Maintenance(Base):
    __tablename__ = "maintenance"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    date = Column(Date, default=lambda: datetime.date.today())
    description = Column(String)
    technician = Column(String)
    cost = Column(Float, nullable=True)
    next_maintenance_date = Column(Date, nullable=True)

    machine = relationship("Machine", back_populates="maintenance_logs")
