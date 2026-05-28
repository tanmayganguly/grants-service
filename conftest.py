import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, get_db
from app.main import app
from app.models.models import Document, Grant, User

# ---------------------------------------------------------------------------
# Use SQLite in-memory for speed; integration tests use the real PG URL.
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

ALICE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
BOB_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")
CAROL_ID = uuid.UUID("a0000000-0000-0000-0000-000000000003")
DOC_Q1_ID = uuid.UUID("d0000000-0000-0000-0000-000000000001")
DOC_ROADMAP_ID = uuid.UUID("d0000000-0000-0000-0000-000000000002")
DOC_BUDGET_ID = uuid.UUID("d0000000-0000-0000-0000-000000000003")


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )

    # SQLite needs schema emulation — strip schema prefix from table names
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    # Patch metadata to remove schema for SQLite
    for table in Base.metadata.tables.values():
        table.schema = None

    async with engine.begin() as conn:
        # Create enum-like check constraint for SQLite
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Restore schemas for other uses
    from app.core.config import settings

    for table in Base.metadata.tables.values():
        table.schema = settings.DB_SCHEMA

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    alice = User(id=ALICE_ID, name="Alice", email="alice@example.com")
    bob = User(id=BOB_ID, name="Bob", email="bob@example.com")
    carol = User(id=CAROL_ID, name="Carol", email="carol@example.com")
    db_session.add_all([alice, bob, carol])

    doc_q1 = Document(id=DOC_Q1_ID, title="Q1 Report", owner_id=ALICE_ID)
    doc_roadmap = Document(id=DOC_ROADMAP_ID, title="Product Roadmap", owner_id=ALICE_ID)
    doc_budget = Document(id=DOC_BUDGET_ID, title="Budget 2026", owner_id=ALICE_ID)
    db_session.add_all([doc_q1, doc_roadmap, doc_budget])
    await db_session.commit()
    return db_session


@pytest_asyncio.fixture(scope="function")
async def client(seeded_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


def future_dt(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
