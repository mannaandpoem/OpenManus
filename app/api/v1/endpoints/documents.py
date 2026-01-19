from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app import crud, models, schemas
from app.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings
from app.services.workflow_service import WorkflowService
import os
import uuid
import hashlib
from typing import List

router = APIRouter()

if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR)

@router.post("/{request_id}/upload", response_model=schemas.Document, summary="Upload a document")
async def upload_document(
    request_id: int,
    doc_type: models.DocumentType,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: models.User = Depends(get_current_user)
):
    """Uploads a document (Contract, NF, etc.) and automatically advances the request status."""
    db_request = crud.get_request(db, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Sanitize filename by using a UUID and keeping the extension
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Versioning: check if this doc_type already exists for this request
    existing_docs = db.query(models.Document).filter(
        models.Document.request_id == request_id,
        models.Document.doc_type == doc_type
    ).all()
    version = len(existing_docs) + 1

    doc_create = schemas.DocumentCreate(
        request_id=request_id,
        doc_type=doc_type,
        file_path=file_path,
        filename=file.filename,
        file_hash=file_hash,
        version=version
    )

    # Automatically advance status
    WorkflowService.handle_document_upload(db, request_id, doc_type, user_id=current_user.id, background_tasks=background_tasks)

    return crud.create_document(db=db, document=doc_create)

@router.get("/{request_id}", response_model=List[schemas.Document], summary="List documents for a request")
def list_documents(request_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_request = crud.get_request(db, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    return db_request.documents

@router.get("/download/{document_id}", summary="Download a document")
def download_document(document_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(db_document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(db_document.file_path, filename=db_document.filename)
