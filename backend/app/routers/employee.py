from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.employee_service import EmployeeService

router = APIRouter(
    prefix="/manager",
    tags=["AI Employee"],
)


@router.get(
    "/status",
    response_model=schemas.EmployeeStatus,
)
def status(
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)
    return service.status()


@router.get("/conversation", response_model=schemas.EmployeeConversationResponse)
def employee_conversation(
    conversation_id: str | None = None,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return EmployeeService(db).history(agency.id, conversation_id)


@router.post(
    "/chat",
    response_model=schemas.EmployeeChatResponse,
)
def employee_chat(
    payload: schemas.EmployeeChatRequest,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    return service.chat(
        agency_id=agency.id,
        conversation_id=str(payload.conversation_id) if payload.conversation_id else None,
        message=payload.message,
    )
