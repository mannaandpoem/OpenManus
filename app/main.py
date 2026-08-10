from fastapi import FastAPI
from .routers import requests, partners, documents
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Dishwasher Workflow System")

app.include_router(requests.router, prefix="/requests", tags=["Requests"])
app.include_router(partners.router, prefix="/partners", tags=["Partners"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Dishwasher Workflow System API"}
