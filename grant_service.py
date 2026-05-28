import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.models import Document, Grant, User
from app.schemas.schemas import GrantCreate, GrantListParams


class GrantServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GrantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_404(self, model, id_: uuid.UUID):
        result = await self.db.get(model, id_)
        if result is None:
            raise GrantServiceError(
                f"{model.__name__} {id_} not found", status_code=404
            )
        return result

    async def create_grant(self, payload: GrantCreate) -> Grant:
        # Validate all referenced entities exist
        await self._get_or_404(User, payload.grantor_id)
        await self._get_or_404(User, payload.grantee_id)
        await self._get_or_404(Document, payload.document_id)

        # Enforce: only one active grant per grantee/document pair
        existing = await self.db.execute(
            select(Grant).where(
                and_(
                    Grant.grantee_id == payload.grantee_id,
                    Grant.document_id == payload.document_id,
                    Grant.revoked_at.is_(None),
                    Grant.expires_at > datetime.now(timezone.utc),
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise GrantServiceError(
                "An active grant already exists for this grantee/document pair",
                status_code=409,
            )

        grant = Grant(
            grantor_id=payload.grantor_id,
            grantee_id=payload.grantee_id,
            document_id=payload.document_id,
            permission=payload.permission,
            expires_at=payload.expires_at,
        )
        self.db.add(grant)
        await self.db.flush()
        await self.db.refresh(grant)

        log = logger.bind(grant_id=str(grant.id))
        log.info("grant_created", permission=grant.permission)
        return grant

    async def list_grants(self, params: GrantListParams) -> list[Grant]:
        q = select(Grant)

        if params.grantor_id:
            q = q.where(Grant.grantor_id == params.grantor_id)
        if params.grantee_id:
            q = q.where(Grant.grantee_id == params.grantee_id)
        if params.document_id:
            q = q.where(Grant.document_id == params.document_id)
        if params.status:
            now = datetime.now(timezone.utc)
            if params.status == "active":
                q = q.where(Grant.revoked_at.is_(None), Grant.expires_at > now)
            elif params.status == "revoked":
                q = q.where(Grant.revoked_at.is_not(None))
            elif params.status == "expired":
                q = q.where(Grant.revoked_at.is_(None), Grant.expires_at <= now)

        q = q.offset(params.offset).limit(params.limit).order_by(Grant.created_at.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_grant(self, grant_id: uuid.UUID) -> Grant:
        return await self._get_or_404(Grant, grant_id)

    async def revoke_grant(self, grant_id: uuid.UUID, requestor_id: uuid.UUID) -> Grant:
        grant = await self._get_or_404(Grant, grant_id)

        # Only the creator can revoke
        if grant.grantor_id != requestor_id:
            raise GrantServiceError("Only the grant creator can revoke it", status_code=403)

        # Cannot revoke already-revoked or expired grants
        if grant.revoked_at is not None:
            raise GrantServiceError("Grant is already revoked", status_code=409)
        if grant.expires_at <= datetime.now(timezone.utc):
            raise GrantServiceError("Cannot revoke an expired grant", status_code=409)

        grant.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(grant)

        logger.info("grant_revoked", grant_id=str(grant_id), requestor_id=str(requestor_id))
        return grant

    async def check_grant(self, grant_id: uuid.UUID) -> Grant:
        return await self._get_or_404(Grant, grant_id)

    async def get_summary(self) -> list[dict]:
        """Bonus: per-document grant summary."""
        now = datetime.now(timezone.utc)

        rows = await self.db.execute(
            select(
                Document.id.label("document_id"),
                Document.title.label("document_title"),
                func.count(Grant.id).label("total"),
                func.sum(
                    func.cast(
                        and_(Grant.revoked_at.is_(None), Grant.expires_at > now),
                        type_=func.count(Grant.id).type,
                    )
                ).label("active"),
                func.sum(
                    func.cast(
                        Grant.revoked_at.is_not(None),
                        type_=func.count(Grant.id).type,
                    )
                ).label("revoked"),
                func.sum(
                    func.cast(
                        and_(Grant.revoked_at.is_(None), Grant.expires_at <= now),
                        type_=func.count(Grant.id).type,
                    )
                ).label("expired"),
            )
            .join(Grant, Grant.document_id == Document.id, isouter=True)
            .group_by(Document.id, Document.title)
            .order_by(Document.title)
        )
        return [dict(r._mapping) for r in rows.all()]
