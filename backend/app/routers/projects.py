"""
Agency-side Project endpoints - all authenticated, all agency-scoped via
get_current_agency (see app/deps.py), matching every other CRUD router in
this app (leads.py, knowledge.py). This is the ONLY way a Project can
ever be created or changed.

  GET    /projects              list this agency's projects (with counts)
  POST   /projects              create a project
  GET    /projects/{id}         one project's detail + inventory summary
  PATCH  /projects/{id}         update a project
  DELETE /projects/{id}         delete, or archive if it still has inventory
  POST   /projects/{id}/media   upload a project image
  GET    /projects/{id}/media   list a project's media
  GET    /projects/{id}/media/{media_id}/file   fetch the raw file bytes
  DELETE /projects/{id}/media/{media_id}
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.billing.entitlement_service import ProjectLimitReachedError
from app.services.inventory.media_service import InvalidMediaUploadError, PropertyMediaService, content_type_for
from app.services.inventory.project_service import (
    InvalidAmenityError,
    InvalidProjectStatusError,
    InvalidProjectTypeError,
    ProjectService,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[schemas.ProjectWithCountsOut])
def list_projects(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    rows = ProjectService(db).get_with_counts(agency.id)
    return [
        schemas.ProjectWithCountsOut(
            **schemas.ProjectOut.model_validate(project).model_dump(),
            total_properties=total,
            available_properties=available,
        )
        for project, total, available in rows
    ]


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    payload: schemas.ProjectCreate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return ProjectService(db).create(agency.id, payload)
    except (InvalidAmenityError, InvalidProjectTypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ProjectLimitReachedError as exc:
        raise HTTPException(status_code=402, detail=str(exc))


@router.get("/{project_id}", response_model=schemas.ProjectWithCountsOut)
def get_project(
    project_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = ProjectService(db)
    project = service.get(project_id, agency.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    summary = service.inventory_summary(project_id, agency.id)
    return schemas.ProjectWithCountsOut(
        **schemas.ProjectOut.model_validate(project).model_dump(),
        total_properties=summary["total_properties"],
        available_properties=summary["available_properties"],
    )


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: str,
    payload: schemas.ProjectUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        project = ProjectService(db).update(project_id, agency.id, payload)
    except (InvalidAmenityError, InvalidProjectTypeError, InvalidProjectStatusError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    if not ProjectService(db).delete(project_id, agency.id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted or archived successfully"}


# ---- project media --------------------------------------------------

@router.post("/{project_id}/media", response_model=schemas.PropertyMediaOut, status_code=201)
async def upload_project_media(
    project_id: str,
    file: UploadFile,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    project = ProjectService(db).get(project_id, agency.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    try:
        return PropertyMediaService(db).upload_for_project(
            agency.id, project, file.filename or "image", content, models.PropertyMediaType.image,
        )
    except InvalidMediaUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{project_id}/media", response_model=list[schemas.PropertyMediaOut])
def list_project_media(
    project_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    project = ProjectService(db).get(project_id, agency.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return sorted(project.media, key=lambda m: m.sort_order)


@router.get("/{project_id}/media/{media_id}/file")
def get_project_media_file(
    project_id: str,
    media_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    media = PropertyMediaService(db).get(media_id, agency.id)
    if media is None or media.project_id != project_id:
        raise HTTPException(status_code=404, detail="Media not found")
    content = PropertyMediaService(db).read_content(media)
    return Response(content=content, media_type=content_type_for(media.file_type))


@router.delete("/{project_id}/media/{media_id}")
def delete_project_media(
    project_id: str,
    media_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    media = PropertyMediaService(db).get(media_id, agency.id)
    if media is None or media.project_id != project_id:
        raise HTTPException(status_code=404, detail="Media not found")
    PropertyMediaService(db).delete(media_id, agency.id)
    return {"message": "Media deleted successfully"}
