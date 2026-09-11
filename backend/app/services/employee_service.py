from sqlalchemy.orm import Session

from app.agents.employee_agent import EmployeeAgent
from app.services.llm_client import get_llm_status


class EmployeeService:

    def __init__(
        self,
        db: Session,
    ):

        self.agent = EmployeeAgent(db)

    def chat(
        self,
        agency_id,
        message,
        conversation_id=None,
    ):

        return self.agent.process(
            agency_id=agency_id,
            conversation_id=conversation_id,
            message=message,
        )

    def status(self):

        llm_status = get_llm_status()

        return {
            "status": "online",
            "agent": "Receptionist AI",
            "model": llm_status["model"],
            "tools": [
                "Dashboard summary",
                "Lead CRM",
                "Availability",
                "Appointment booking",
            ],
            "provider": llm_status["provider"],
            "fallback_provider": llm_status["fallback_provider"],
        }

    def history(self, agency_id, conversation_id=None):
        return self.agent.history(agency_id, conversation_id)
