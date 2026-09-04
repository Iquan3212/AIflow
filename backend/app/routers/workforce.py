from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.agents.orchestrator import AIOrchestrator
from app.database import get_db
from app.deps import get_current_business

router = APIRouter(prefix="/workforce", tags=["AI Workforce"])

_DISPLAY_NAMES = {
    "sales": "Sales AI",
    "receptionist": "Receptionist AI",
    "support": "Support AI",
    "finance": "Finance AI",
    "marketing": "Marketing AI",
    "analytics": "Analytics AI",
    "manager": "Manager AI",
}


def _employee_info(name: str, registry) -> dict:
    return {
        "id": name,
        "name": _DISPLAY_NAMES.get(name, name.capitalize()),
        "status": "online",
        "online": True,
        "tools": registry.employee_tools(name),
    }


@router.get("")
def list_workforce(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    orchestrator = AIOrchestrator(db=db, business=business, conversation=None, lead=None)
    employees = [_employee_info(name, orchestrator.registry) for name in orchestrator.registry.all_employees()]
    online = sum(1 for e in employees if e["online"])
    return {"employees": employees, "stats": {"total": len(employees), "online": online, "busy": 0}}


@router.get("/{employee_id}")
def get_employee(
    employee_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    orchestrator = AIOrchestrator(db=db, business=business, conversation=None, lead=None)
    if orchestrator.registry.get_employee(employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _employee_info(employee_id, orchestrator.registry)
