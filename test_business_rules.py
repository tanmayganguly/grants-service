"""Unit tests for business rules (no HTTP layer)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.schemas import GrantCreate
from app.services.grant_service import GrantService, GrantServiceError
from tests.conftest import ALICE_ID, BOB_ID, CAROL_ID, DOC_Q1_ID, DOC_ROADMAP_ID


def _future(minutes: int = 60) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _past(minutes: int = 60) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# Expiration validation (schema-level)
# ---------------------------------------------------------------------------


def test_expiry_must_be_at_least_1_minute_in_future():
    with pytest.raises(Exception, match="at least 1 minute"):
        GrantCreate(
            grantor_id=ALICE_ID,
            grantee_id=BOB_ID,
            document_id=DOC_Q1_ID,
            permission="view",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        )


def test_expiry_exactly_1_minute_is_rejected():
    with pytest.raises(Exception):
        GrantCreate(
            grantor_id=ALICE_ID,
            grantee_id=BOB_ID,
            document_id=DOC_Q1_ID,
            permission="view",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )


def test_expiry_in_past_is_rejected():
    with pytest.raises(Exception):
        GrantCreate(
            grantor_id=ALICE_ID,
            grantee_id=BOB_ID,
            document_id=DOC_Q1_ID,
            permission="view",
            expires_at=_past(30),
        )


def test_valid_expiry_accepted():
    g = GrantCreate(
        grantor_id=ALICE_ID,
        grantee_id=BOB_ID,
        document_id=DOC_Q1_ID,
        permission="edit",
        expires_at=_future(120),
    )
    assert g.expires_at > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Grant.status / is_active property
# ---------------------------------------------------------------------------


def _make_grant(**kwargs):
    from app.models.models import Grant

    defaults = dict(
        id=uuid.uuid4(),
        grantor_id=ALICE_ID,
        grantee_id=BOB_ID,
        document_id=DOC_Q1_ID,
        permission="view",
        expires_at=_future(60),
        revoked_at=None,
    )
    defaults.update(kwargs)
    g = Grant(**defaults)
    return g


def test_active_grant_status():
    g = _make_grant()
    assert g.status == "active"
    assert g.is_active is True


def test_revoked_grant_status():
    g = _make_grant(revoked_at=datetime.now(timezone.utc))
    assert g.status == "revoked"
    assert g.is_active is False


def test_expired_grant_status():
    g = _make_grant(expires_at=_past(10))
    assert g.status == "expired"
    assert g.is_active is False


# ---------------------------------------------------------------------------
# Service-level business rules (against in-memory DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_active_grant_blocked(seeded_db):
    svc = GrantService(seeded_db)

    payload = GrantCreate(
        grantor_id=ALICE_ID,
        grantee_id=BOB_ID,
        document_id=DOC_Q1_ID,
        permission="view",
        expires_at=_future(120),
    )
    await svc.create_grant(payload)

    with pytest.raises(GrantServiceError, match="active grant already exists"):
        await svc.create_grant(payload)


@pytest.mark.asyncio
async def test_second_grant_allowed_after_first_revoked(seeded_db):
    svc = GrantService(seeded_db)
    payload = GrantCreate(
        grantor_id=ALICE_ID,
        grantee_id=BOB_ID,
        document_id=DOC_Q1_ID,
        permission="view",
        expires_at=_future(120),
    )
    grant1 = await svc.create_grant(payload)
    await svc.revoke_grant(grant1.id, ALICE_ID)

    grant2 = await svc.create_grant(payload)
    assert grant2.id != grant1.id


@pytest.mark.asyncio
async def test_only_creator_can_revoke(seeded_db):
    svc = GrantService(seeded_db)
    grant = await svc.create_grant(
        GrantCreate(
            grantor_id=ALICE_ID,
            grantee_id=BOB_ID,
            document_id=DOC_Q1_ID,
            permission="view",
            expires_at=_future(120),
        )
    )

    with pytest.raises(GrantServiceError, match="Only the grant creator"):
        await svc.revoke_grant(grant.id, BOB_ID)


@pytest.mark.asyncio
async def test_cannot_revoke_already_revoked(seeded_db):
    svc = GrantService(seeded_db)
    grant = await svc.create_grant(
        GrantCreate(
            grantor_id=ALICE_ID,
            grantee_id=BOB_ID,
            document_id=DOC_Q1_ID,
            permission="view",
            expires_at=_future(120),
        )
    )
    await svc.revoke_grant(grant.id, ALICE_ID)

    with pytest.raises(GrantServiceError, match="already revoked"):
        await svc.revoke_grant(grant.id, ALICE_ID)
