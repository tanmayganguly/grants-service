"""Integration tests — all endpoints against real (SQLite-backed) DB."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import ALICE_ID, BOB_ID, CAROL_ID, DOC_Q1_ID, DOC_ROADMAP_ID


def _future(minutes: int = 120) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------------------
# POST /grants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_grant_201(client: AsyncClient):
    resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["permission"] == "view"


@pytest.mark.asyncio
async def test_create_grant_invalid_expiry_422(client: AsyncClient):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": past,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_active_grant_409(client: AsyncClient):
    payload = {
        "grantor_id": str(ALICE_ID),
        "grantee_id": str(BOB_ID),
        "document_id": str(DOC_Q1_ID),
        "permission": "view",
        "expires_at": _future(),
    }
    r1 = await client.post("/grants", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/grants", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_grant_unknown_user_404(client: AsyncClient):
    resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(uuid.uuid4()),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /grants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_grants_empty(client: AsyncClient):
    resp = await client.get("/grants")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_grants_returns_created(client: AsyncClient):
    await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "edit",
            "expires_at": _future(),
        },
    )
    resp = await client.get("/grants")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_grants_filter_by_status(client: AsyncClient):
    # Create two grants then revoke one
    r1 = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    r2 = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(CAROL_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    grant1_id = r1.json()["id"]
    await client.delete(f"/grants/{grant1_id}?requestor_id={ALICE_ID}")

    active = await client.get("/grants?status=active")
    revoked = await client.get("/grants?status=revoked")
    assert len(active.json()) == 1
    assert len(revoked.json()) == 1


# ---------------------------------------------------------------------------
# GET /grants/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_grant_200(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "admin",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]
    resp = await client.get(f"/grants/{grant_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == grant_id


@pytest.mark.asyncio
async def test_get_grant_404(client: AsyncClient):
    resp = await client.get(f"/grants/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /grants/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_grant_200(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]

    revoke_resp = await client.delete(f"/grants/{grant_id}?requestor_id={ALICE_ID}")
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_wrong_requestor_403(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]

    resp = await client.delete(f"/grants/{grant_id}?requestor_id={BOB_ID}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoke_already_revoked_409(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]

    await client.delete(f"/grants/{grant_id}?requestor_id={ALICE_ID}")
    resp = await client.delete(f"/grants/{grant_id}?requestor_id={ALICE_ID}")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /grants/{id}/check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_active_grant(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "edit",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]

    resp = await client.get(f"/grants/{grant_id}/check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert data["status"] == "active"
    assert data["permission"] == "edit"


@pytest.mark.asyncio
async def test_check_revoked_grant_shows_inactive(client: AsyncClient):
    create_resp = await client.post(
        "/grants",
        json={
            "grantor_id": str(ALICE_ID),
            "grantee_id": str(BOB_ID),
            "document_id": str(DOC_Q1_ID),
            "permission": "view",
            "expires_at": _future(),
        },
    )
    grant_id = create_resp.json()["id"]
    await client.delete(f"/grants/{grant_id}?requestor_id={ALICE_ID}")

    resp = await client.get(f"/grants/{grant_id}/check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["status"] == "revoked"
    assert data["permission"] is None


@pytest.mark.asyncio
async def test_check_grant_404(client: AsyncClient):
    resp = await client.get(f"/grants/{uuid.uuid4()}/check")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /grants/summary (bonus)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_returns_all_documents(client: AsyncClient):
    resp = await client.get("/grants/summary")
    assert resp.status_code == 200
    titles = [r["document_title"] for r in resp.json()]
    assert "Q1 Report" in titles
    assert "Product Roadmap" in titles
    assert "Budget 2026" in titles
