import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.schemas import (
    GrantCheckOut,
    GrantCreate,
    GrantListParams,
    GrantOut,
    GrantSummary,
    StatusType,
)
from app.services.grant_service import GrantService, GrantServiceError

router = APIRouter(prefix="/grants", tags=["grants"])


def _svc(db: AsyncSession = Depends(get_db)) -> GrantService:
    return GrantService(db)


def _handle(e: GrantServiceError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)


@router.post("", response_model=GrantOut, status_code=201)
async def create_grant(
    payload: GrantCreate,
    svc: GrantService = Depends(_svc),
):
    try:
        grant = await svc.create_grant(payload)
    except GrantServiceError as e:
        raise _handle(e)
    return grant


@router.get("", response_model=list[GrantOut])
async def list_grants(
    grantor_id: uuid.UUID | None = Query(default=None),
    grantee_id: uuid.UUID | None = Query(default=None),
    document_id: uuid.UUID | None = Query(default=None),
    status: StatusType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    svc: GrantService = Depends(_svc),
):
    params = GrantListParams(
        grantor_id=grantor_id,
        grantee_id=grantee_id,
        document_id=document_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return await svc.list_grants(params)


@router.get("/summary", response_model=list[GrantSummary])
async def grant_summary(svc: GrantService = Depends(_svc)):
    """Bonus: per-document grant summary."""
    return await svc.get_summary()


@router.get("/{grant_id}", response_model=GrantOut)
async def get_grant(grant_id: uuid.UUID, svc: GrantService = Depends(_svc)):
    try:
        return await svc.get_grant(grant_id)
    except GrantServiceError as e:
        raise _handle(e)


@router.delete("/{grant_id}", response_model=GrantOut)
async def revoke_grant(
    grant_id: uuid.UUID,
    requestor_id: uuid.UUID = Query(..., description="ID of the user revoking the grant"),
    svc: GrantService = Depends(_svc),
):
    try:
        return await svc.revoke_grant(grant_id, requestor_id)
    except GrantServiceError as e:
        raise _handle(e)


@router.get("/{grant_id}/check", response_model=GrantCheckOut)
async def check_grant(grant_id: uuid.UUID, svc: GrantService = Depends(_svc)):
    try:
        grant = await svc.check_grant(grant_id)
    except GrantServiceError as e:
        raise _handle(e)
    return GrantCheckOut(
        grant_id=grant.id,
        is_active=grant.is_active,
        status=grant.status,
        permission=grant.permission if grant.is_active else None,
        expires_at=grant.expires_at if grant.is_active else None,
    )
