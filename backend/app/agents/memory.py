from collections import Counter


class ConversationMemory:
    """
    Shared memory used by every AI Employee.

    The database remains the source of truth.
    This class simply converts previous messages into
    useful context for the AI Workforce.
    """

    def summarize(
        self,
        history,
        limit: int = 20,
    ) -> str:

        if not history:
            return "No previous conversation."

        recent = history[-limit:]

        summary = []

        for msg in recent:

            if isinstance(msg, dict):

                role = msg.get("role", "")

                content = msg.get("content", "")

            else:

                role = getattr(msg, "role", "")

                content = getattr(msg, "content", "")

            if content:

                summary.append(
                    f"{role}: {content}"
                )

        return "\n".join(summary)

    def detect_topics(
        self,
        history,
    ) -> list[str]:

        text = " ".join(

            msg.content.lower()

            if hasattr(msg, "content")

            else msg.get("content", "").lower()

            for msg in history

        )

        topics = []

        keywords = {

            "appointment": [
                "appointment",
                "schedule",
                "meeting",
                "book",
                "reschedule",
                "cancel",
            ],

            "sales": [
                "price",
                "quotation",
                "quote",
                "discount",
                "buy",
                "purchase",
            ],

            "lead": [
                "phone",
                "email",
                "contact",
                "name",
            ],

            "support": [
                "problem",
                "issue",
                "error",
                "refund",
                "help",
            ],

            "marketing": [
                "instagram",
                "facebook",
                "campaign",
                "caption",
                "promotion",
            ],

        }

        for topic, words in keywords.items():

            if any(word in text for word in words):

                topics.append(topic)

        return topics

    def conversation_stats(
        self,
        history,
    ) -> dict:

        roles = Counter()

        for msg in history:

            role = (

                msg.role

                if hasattr(msg, "role")

                else msg.get("role", "")

            )

            roles[role] += 1

        return {

            "messages": len(history),

            "user_messages": roles["user"],

            "assistant_messages": roles["assistant"],

        }

    def shared_context(
        self,
        history,
    ) -> dict:

        return {

            "summary": self.summarize(history),

            "topics": self.detect_topics(history),

            "stats": self.conversation_stats(history),

        }