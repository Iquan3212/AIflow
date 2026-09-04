from app.agents.llm_reply import facts_context, generate_employee_reply
from app.agents.memory import ConversationMemory


class ReceptionistAgent:
    """
    AI Workforce - Receptionist AI

    Responsibilities
    ----------------
    - Book appointments
    - Reschedule appointments
    - Cancel appointments
    - Answer appointment questions
    - Detect scheduling intent

    Actual booking is still performed by the
    existing Appointment Tool / Tool Dispatcher.
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead

        self.memory = ConversationMemory()

    @property
    def system_prompt(self):

        return f"""
You are the Receptionist AI for {self.business.name}.

ROLE

You are responsible for scheduling appointments.

RESPONSIBILITIES

- Book appointments

- Check availability

- Cancel appointments

- Reschedule appointments

- Explain scheduling process

RULES

Never book an appointment yourself.

Always allow the Appointment Tool
to verify availability first.

Never invent available slots.

Never invent appointment confirmations.

If customer information is missing,
collect it politely.

Always remain professional.
"""

    def analyze(
        self,
        message: str,
        history,
    ):

        context = self.memory.shared_context(history)

        text = message.lower()

        appointment_type = "general"

        if "cancel" in text:
            appointment_type = "cancel"

        elif "reschedule" in text:
            appointment_type = "reschedule"

        elif any(
            word in text
            for word in [
                "book",
                "schedule",
                "appointment",
                "meeting",
            ]
        ):
            appointment_type = "book"

        needs_contact = False

        if self.lead is not None:

            if not self.lead.name:

                needs_contact = True

            elif not (
                self.lead.phone
                or self.lead.email
            ):

                needs_contact = True

        return {

            "employee": "receptionist",

            "intent": "appointment",

            "appointment_type": appointment_type,

            "needs_contact": needs_contact,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def respond(self, message: str, history, tool_router=None) -> dict:
        analysis = self.analyze(message, history)

        tool_result = None
        if tool_router is not None and analysis.get("appointment_type") in ("book", "reschedule", "cancel"):
            res = tool_router.execute(
                employee="receptionist",
                tool_name="appointment",
                message=message,
                action=analysis["appointment_type"],
            )
            tool_result = res.get("result") if res.get("success") else {
                "ok": False,
                "error": res.get("error"),
                "message": res.get("message"),
            }

        reply = generate_employee_reply(
            "receptionist", self.system_prompt, message, history,
            tool_result=tool_result, extra_context=facts_context(analysis),
        )
        analysis["reply"] = reply
        analysis["tool_result"] = tool_result
        return analysis

    def handoff(self):

        """
        Employees Receptionist AI
        can delegate work to.
        """

        return [

            "sales",

            "support",

            "manager",

        ]