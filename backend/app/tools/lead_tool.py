from sqlalchemy.orm import Session

from app.services.lead_service import LeadService


class LeadTool:

    def __init__(self, db: Session):

        self.service = LeadService(db)

    def execute(
        self,
        business_id,
        conversation_id,
        message,
    ):

        return self.service.process_message(
            business_id=business_id,
            conversation_id=conversation_id,
            message=message,
        )