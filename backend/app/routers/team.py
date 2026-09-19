"""
Agency team management: view/invite/re-role/remove staff, and the public
invite-acceptance flow.

  GET    /team/members                owner/admin/member (any signed-in agency user) - view roster
  GET    /team/invites                 owner/admin - view pending invites
  POST   /team/invites                 owner/admin - invite a new member/admin
  DELETE /team/invites/{invite_id}     owner/admin - revoke a pending invite
  PATCH  /team/members/{user_id}/role  owner/admin - change a member's role
  DELETE /team/members/{user_id}       owner/admin - remove a member
  POST   /team/invites/accept          public (token-authenticated, not bearer) - accept an invite

Never lets the client choose a price/limit/role outside {member, admin} -
the owner role is set once at signup and is never assignable or
removable through this router (see team_service.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency, get_current_user, require_team_manager
from app.rate_limit import INVITE_ACCEPT_RATE_LIMIT, limiter
from app.routers.auth import _issue_tokens
from app.services.team_service import (
    CannotModifyOwnerError,
    DuplicateInviteError,
    EmailAlreadyRegisteredError,
    InviteExpiredError,
    InviteNotFoundError,
    MemberNotFoundError,
    SelfRemovalError,
    TeamLimitReachedError,
    TeamService,
)

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members", response_model=list[schemas.TeamMemberOut])
def list_members(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return TeamService(db).list_members(agency)


@router.get("/invites", response_model=list[schemas.TeamInviteOut])
def list_invites(
    agency: models.Agency = Depends(require_team_manager),
    db: Session = Depends(get_db),
):
    return TeamService(db).list_pending_invites(agency)


@router.post("/invites", response_model=schemas.TeamInviteOut, status_code=201)
def create_invite(
    payload: schemas.TeamInviteCreate,
    agency: models.Agency = Depends(require_team_manager),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return TeamService(db).invite(agency, user, email=payload.email, role=payload.role)
    except TeamLimitReachedError as exc:
        # 402 matches the existing plan-limit convention (see
        # routers/properties.py, routers/projects.py) so the frontend's
        # isPlanLimitError()/UpgradePrompt reuse the same signal.
        raise HTTPException(status_code=402, detail=str(exc))
    except (DuplicateInviteError, EmailAlreadyRegisteredError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/invites/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: str,
    agency: models.Agency = Depends(require_team_manager),
    db: Session = Depends(get_db),
):
    try:
        TeamService(db).revoke_invite(agency, invite_id)
    except InviteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


@router.patch("/members/{user_id}/role", response_model=schemas.TeamMemberOut)
def update_member_role(
    user_id: str,
    payload: schemas.TeamMemberRoleUpdate,
    agency: models.Agency = Depends(require_team_manager),
    db: Session = Depends(get_db),
):
    try:
        return TeamService(db).update_role(agency, target_user_id=user_id, new_role=payload.role)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CannotModifyOwnerError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/members/{user_id}", status_code=204)
def remove_member(
    user_id: str,
    agency: models.Agency = Depends(require_team_manager),
    acting_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        TeamService(db).remove_member(agency, target_user_id=user_id, acting_user_id=acting_user.id)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CannotModifyOwnerError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except SelfRemovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return None


@router.post("/invites/accept", response_model=schemas.TokenResponse)
@limiter.limit(INVITE_ACCEPT_RATE_LIMIT)
def accept_invite(payload: schemas.TeamInviteAcceptRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user, agency = TeamService(db).accept_invite(token=payload.token, password=payload.password)
    except (InviteNotFoundError, InviteExpiredError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TeamLimitReachedError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _issue_tokens(db, user, agency, request)
