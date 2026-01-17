from pydantic import BaseModel, ConfigDict

class PartnerBase(BaseModel):
    name: str
    contact_info: str

class PartnerCreate(PartnerBase):
    pass

class Partner(PartnerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
