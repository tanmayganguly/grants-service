import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import timezone, timedelta


PermissionType = Literal["view", "edit", "admin"]
StatusType = Literal["active", "revoked", "expired"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    owner_id: uuid.UUID


class GrantCreate(BaseModel):
    grantor_id: uuid.UUID
    grantee_id: uuid.UUID
    document_id: uuid.UUID
    permission: PermissionType
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        min_expiry = now + timedelta(minutes=1)
        if v <= min_expiry:
            raise ValueError("expires_at must be at least 1 minute in the future")
        return v


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    grantor_id: uuid.UUID
    grantee_id: uuid.UUID
    document_id: uuid.UUID
    permission: PermissionType
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    status: str


class GrantCheckOut(BaseModel):
    grant_id: uuid.UUID
    is_active: bool
    status: StatusType
    permission: PermissionType | None = None
    expires_at: datetime | None = None


class GrantListParams(BaseModel):
    grantor_id: uuid.UUID | None = None
    grantee_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    status: StatusType | None = None
    limit: int = 50
    offset: int = 0


class GrantSummary(BaseModel):
    document_id: uuid.UUID
    document_title: str
    total: int
    active: int
    revoked: int
    expired: int
