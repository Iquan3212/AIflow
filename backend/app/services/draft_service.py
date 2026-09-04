from sqlalchemy.orm import Session

from app import models


class DraftService:
    """CRUD over AIDraft - the persisted output of the Finance (Quotation)
    and Marketing (Campaign) AI Workforce employees."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        business_id: str,
        kind: str,
        content: str,
        title: str | None = None,
        lead_id: str | None = None,
    ) -> models.AIDraft:
        draft = models.AIDraft(
            business_id=business_id,
            kind=kind,
            content=content,
            title=title,
            lead_id=lead_id,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def get_all(self, business_id: str, kind: str | None = None) -> list[models.AIDraft]:
        query = self.db.query(models.AIDraft).filter(models.AIDraft.business_id == business_id)
        if kind:
            query = query.filter(models.AIDraft.kind == kind)
        return query.order_by(models.AIDraft.created_at.desc()).all()

    def get(self, draft_id: str, business_id: str) -> models.AIDraft | None:
        return (
            self.db.query(models.AIDraft)
            .filter(models.AIDraft.id == draft_id, models.AIDraft.business_id == business_id)
            .first()
        )

    def update_status(self, draft_id: str, business_id: str, status: str) -> models.AIDraft | None:
        draft = self.get(draft_id, business_id)
        if draft is None:
            return None
        draft.status = status
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def delete(self, draft_id: str, business_id: str) -> bool:
        draft = self.get(draft_id, business_id)
        if draft is None:
            return False
        self.db.delete(draft)
        self.db.commit()
        return True
