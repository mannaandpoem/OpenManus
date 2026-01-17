from fastapi import APIRouter
from app.api.v1.endpoints import requests, partners, documents, machines, integration, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(requests.router, prefix="/requests", tags=["Requests"])
api_router.include_router(partners.router, prefix="/partners", tags=["Partners"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(machines.router, prefix="/machines", tags=["Machines"])
api_router.include_router(integration.router, prefix="/integration", tags=["Integration"])
