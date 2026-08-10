from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
import os
import uuid
from typing import List

router = APIRouter()

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/{request_id}/upload", response_model=schemas.Document)
async def upload_document(
    request_id: int,
    doc_type: models.DocumentType,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    db_request = crud.get_request(db, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Sanitize filename by using a UUID and keeping the extension
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    doc_create = schemas.DocumentCreate(
        request_id=request_id,
        doc_type=doc_type,
        file_path=file_path,
        filename=file.filename
    )

    # Automatically advance status if contract or NF is uploaded
    if doc_type == models.DocumentType.CONTRACT:
        crud.update_request(db, request_id, schemas.RequestUpdate(status=models.RequestStatus.CONTRACTING))
    elif doc_type == models.DocumentType.INVOICE:
        crud.update_request(db, request_id, schemas.RequestUpdate(status=models.RequestStatus.INSTALLATION))
    elif doc_type == models.DocumentType.ACCEPTANCE:
         crud.update_request(db, request_id, schemas.RequestUpdate(status=models.RequestStatus.TECHNICAL_ACCEPTANCE))

    return crud.create_document(db=db, document=doc_create)

@router.get("/{request_id}", response_model=List[schemas.Document])
def list_documents(request_id: int, db: Session = Depends(get_db)):
    db_request = crud.get_request(db, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    return db_request.documents

@router.get("/download/{document_id}")
def download_document(document_id: int, db: Session = Depends(get_db)):
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(db_document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(db_document.file_path, filename=db_document.filename)
