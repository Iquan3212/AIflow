class AppointmentTool:

    def __init__(self, db):
        self.db = db

    def execute(
        self,
        **kwargs,
    ):
        return {
            "tool": "appointment",
            "status": "ready",
        }