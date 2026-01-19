from sqlalchemy import Column, Integer, String, Enum, Boolean
from app.database import Base
import enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    COMMERCIAL = "commercial"
    SUPERVISOR = "supervisor"
    PARTNER = "partner"
    CLIENT = "client"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.CLIENT)
    is_active = Column(Boolean, default=True)
