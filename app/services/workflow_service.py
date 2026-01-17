from sqlalchemy.orm import Session
from app import crud, models, schemas
from fastapi import HTTPException, BackgroundTasks
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
import logging
import datetime

logger = logging.getLogger(__name__)

class WorkflowService:
    ALLOWED_TRANSITIONS = {
        models.RequestStatus.QUOTATION: [models.RequestStatus.SUPPLIER_INTERACTION],
        models.RequestStatus.SUPPLIER_INTERACTION: [models.RequestStatus.SELECTION],
        models.RequestStatus.SELECTION: [models.RequestStatus.CONTRACTING],
        models.RequestStatus.CONTRACTING: [models.RequestStatus.INSTALLATION],
        models.RequestStatus.INSTALLATION: [models.RequestStatus.TECHNICAL_ACCEPTANCE],
        models.RequestStatus.TECHNICAL_ACCEPTANCE: [models.RequestStatus.COMPLETED],
    }

    @staticmethod
    def validate_transition(current_status: models.RequestStatus, next_status: models.RequestStatus):
        if next_status not in WorkflowService.ALLOWED_TRANSITIONS.get(current_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition from {current_status.value} to {next_status.value}"
            )

    @staticmethod
    def select_quote(db: Session, request_id: int, quote_id: int, user_id: int = None, background_tasks: BackgroundTasks = None):
        db_request = crud.get_request(db, request_id=request_id)
        if not db_request:
            raise HTTPException(status_code=404, detail="Request not found")

        WorkflowService.validate_transition(db_request.status, models.RequestStatus.SELECTION)

        # Verify quote exists and belongs to this request
        db_quote = db.query(models.Quote).filter(
            models.Quote.id == quote_id,
            models.Quote.request_id == request_id
        ).first()
        if not db_quote:
            raise HTTPException(status_code=404, detail="Quote not found for this request")

        logger.info(f"Request {request_id}: Selecting quote {quote_id}")

        old_status = db_request.status.value
        result = crud.update_request(db, request_id, schemas.RequestUpdate(
            status=models.RequestStatus.SELECTION,
            selected_quote_id=quote_id
        ))

        if background_tasks:
            background_tasks.add_task(
                NotificationService.notify_status_change,
                request_id, db_request.client_id, old_status, models.RequestStatus.SELECTION.value
            )

        AuditService.log_action(
            db,
            action="SELECT_QUOTE",
            resource_type="request",
            resource_id=request_id,
            user_id=user_id,
            details={"quote_id": quote_id}
        )

        return result

    @staticmethod
    def handle_quote_submission(db: Session, request_id: int, user_id: int = None):
        db_request = crud.get_request(db, request_id=request_id)
        if not db_request:
            raise HTTPException(status_code=404, detail="Request not found")

        if db_request.status == models.RequestStatus.QUOTATION:
            WorkflowService.validate_transition(db_request.status, models.RequestStatus.SUPPLIER_INTERACTION)
            crud.update_request(db, request_id, schemas.RequestUpdate(status=models.RequestStatus.SUPPLIER_INTERACTION))

            AuditService.log_action(
                db,
                action="ADVANCE_STATUS",
                resource_type="request",
                resource_id=request_id,
                user_id=user_id,
                details={"new_status": "supplier_interaction", "trigger": "quote_submission"}
            )

    @staticmethod
    def handle_document_upload(db: Session, request_id: int, doc_type: models.DocumentType, user_id: int = None, background_tasks: BackgroundTasks = None):
        db_request = crud.get_request(db, request_id=request_id)
        if not db_request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Automatically advance status based on doc type
        status_update = None
        if doc_type == models.DocumentType.CONTRACT:
            status_update = models.RequestStatus.CONTRACTING
        elif doc_type == models.DocumentType.INVOICE:
            status_update = models.RequestStatus.INSTALLATION
        elif doc_type == models.DocumentType.ACCEPTANCE:
            status_update = models.RequestStatus.TECHNICAL_ACCEPTANCE

        if status_update:
            WorkflowService.validate_transition(db_request.status, status_update)

            old_status = db_request.status.value
            crud.update_request(db, request_id, schemas.RequestUpdate(status=status_update))
            logger.info(f"Request {request_id} advanced to {status_update} via document upload")

            if background_tasks:
                background_tasks.add_task(
                    NotificationService.notify_status_change,
                    request_id, db_request.client_id, old_status, status_update.value
                )

            AuditService.log_action(
                db,
                action="ADVANCE_STATUS",
                resource_type="request",
                resource_id=request_id,
                user_id=user_id,
                details={"new_status": status_update.value, "trigger": "document_upload", "doc_type": doc_type.value}
            )

            # Simulate integration notification
            logger.info(f"INTEGRATION: Notifying external system about status change for Request {request_id}")

    @staticmethod
    def complete_request(db: Session, request_id: int, user_id: int = None):
        db_request = crud.get_request(db, request_id=request_id)
        if not db_request:
            raise HTTPException(status_code=404, detail="Request not found")

        WorkflowService.validate_transition(db_request.status, models.RequestStatus.COMPLETED)

        # If it's a new installation and we have machine data, update machine status
        if db_request.machine_id:
            db_machine = crud.get_machine(db, db_request.machine_id)
            if db_machine:
                db_machine.status = models.MachineStatus.ACTIVE
                db_machine.installation_date = datetime.date.today()
                db.commit()
                logger.info(f"Machine {db_machine.id} marked as ACTIVE upon request completion")

        result = crud.update_request(db, request_id, schemas.RequestUpdate(status=models.RequestStatus.COMPLETED))

        AuditService.log_action(
            db,
            action="COMPLETE_REQUEST",
            resource_type="request",
            resource_id=request_id,
            user_id=user_id
        )

        return result
