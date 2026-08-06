from sqlalchemy.orm import Session

from app.agents.employee_agent import EmployeeAgent
from app.config import get_settings


class EmployeeService:

    def __init__(
        self,
        db: Session,
    ):

        self.agent = EmployeeAgent(db)

    def chat(
        self,
        business_id,
        message,
        conversation_id=None,
    ):

        return self.agent.process(
            business_id=business_id,
            conversation_id=conversation_id,
            message=message,
        )

    def status(self):

        return {
            "status": "online",
            "agent": "Receptionist AI",
            "model": get_settings().llm_model,
            "tools": [
                "Dashboard summary",
                "Lead CRM",
                "Availability",
                "Appointment booking",
            ],
        }

    def history(self, business_id, conversation_id=None):
        return self.agent.history(business_id, conversation_id)
