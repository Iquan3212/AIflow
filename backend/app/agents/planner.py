from dataclasses import dataclass


@dataclass
class Plan:
    intent: str
    tool: str | None
    confidence: float
    agent: str


class Planner:

    def plan(self, message: str) -> Plan:

        text = message.lower()

        # -------------------------
        # Receptionist
        # -------------------------

        if any(
            word in text
            for word in [
                "appointment",
                "book",
                "schedule",
                "meeting",
                "cancel",
                "reschedule",
            ]
        ):
            return Plan(
                intent="appointment",
                tool="appointment",
                confidence=0.98,
                agent="receptionist",
            )

        # -------------------------
        # Sales
        # -------------------------

        if any(
            word in text
            for word in [
                "price",
                "quotation",
                "quote",
                "cost",
                "buy",
                "purchase",
                "discount",
            ]
        ):
            return Plan(
                intent="sales",
                tool="lead",
                confidence=0.96,
                agent="sales",
            )

        # -------------------------
        # Dashboard
        # -------------------------

        if any(
            word in text
            for word in [
                "dashboard",
                "analytics",
                "summary",
                "today",
                "revenue",
                "lead",
                "appointment",
                "conversation",
                "chat",
            ]
        ):
            return Plan(
                intent="dashboard",
                tool="dashboard",
                confidence=0.95,
                agent="analytics",
            )

        # -------------------------
        # Marketing
        # -------------------------

        if any(
            word in text
            for word in [
                "instagram",
                "facebook",
                "marketing",
                "campaign",
                "caption",
                "post",
            ]
        ):
            return Plan(
                intent="marketing",
                tool=None,
                confidence=0.92,
                agent="marketing",
            )

        # -------------------------
        # Support
        # -------------------------

        if any(
            word in text
            for word in [
                "problem",
                "issue",
                "error",
                "refund",
                "support",
                "help",
            ]
        ):
            return Plan(
                intent="support",
                tool=None,
                confidence=0.91,
                agent="support",
            )

        # -------------------------
        # Default
        # -------------------------

        return Plan(
            intent="chat",
            tool=None,
            confidence=0.80,
            agent="manager",
        )