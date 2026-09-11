"""
Knowledge Base retrieval as a Tool Router capability - the SAME pipeline
every other tool goes through (permission-checked by Registry, invoked
via ToolRouter.execute(), never bypassing Manager/Planner). This keeps
Knowledge a DATA/RETRIEVAL layer feeding the existing AI Workforce, not a
second AI brain - see ARCHITECTURE.md's "Knowledge Base / RAG" section.

Read-only and side-effect-free: this never writes anything, so unlike
Gmail there is no permission/approval concern beyond the same tenant
isolation retrieval.py already enforces via agency_id.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.knowledge.retrieval import retrieve


class KnowledgeSearchTool:
    def execute(
        self, message: str, db: Session = None, agency: models.Agency = None,
        conversation=None, lead=None, query: str | None = None, top_k: int = 4, **kwargs,
    ) -> dict:
        if agency is None:
            return {"ok": False, "error": "missing_agency"}
        results = retrieve(db, agency.id, query or message, top_k=top_k)
        return {
            "ok": True,
            "results": [
                {
                    "document_name": r.document_name,
                    "content": r.content,
                    "score": r.score,
                }
                for r in results
            ],
        }
