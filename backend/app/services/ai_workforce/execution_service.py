"""
Phase 10A: AgentExecution persistence - real observability for the
bounded LLM tool-calling loop (app.agents.tool_loop.run_bounded_tool_loop),
NOT Phase 12 analytics. One row per tool-calling-capable employee turn:
which employee ran, for which agency/conversation/lead, what tools it
called, how long it took, and whether it succeeded.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app import models


class AgentExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        agency_id: UUID,
        *,
        employee: str,
        status: models.AgentExecutionStatus,
        conversation_id: UUID | None = None,
        lead_id: UUID | None = None,
        outcome: str | None = None,
        tool_calls: list | None = None,
        duration_ms: int | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> models.AgentExecution:
        row = models.AgentExecution(
            agency_id=agency_id,
            employee=employee,
            conversation_id=conversation_id,
            lead_id=lead_id,
            status=status,
            outcome=outcome,
            tool_calls=tool_calls or [],
            duration_ms=duration_ms,
            model=model,
            provider=provider,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get(self, execution_id: UUID, agency_id: UUID) -> models.AgentExecution | None:
        return (
            self.db.query(models.AgentExecution)
            .filter(
                models.AgentExecution.id == execution_id,
                models.AgentExecution.agency_id == agency_id,
            )
            .first()
        )

    def list_for_agency(self, agency_id: UUID, *, limit: int = 50) -> list[models.AgentExecution]:
        return (
            self.db.query(models.AgentExecution)
            .filter(models.AgentExecution.agency_id == agency_id)
            .order_by(models.AgentExecution.created_at.desc())
            .limit(limit)
            .all()
        )
