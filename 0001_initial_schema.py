"""initial schema with seed data

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "grants_svc"

# Deterministic seed UUIDs
ALICE_ID = "a0000000-0000-0000-0000-000000000001"
BOB_ID = "a0000000-0000-0000-0000-000000000002"
CAROL_ID = "a0000000-0000-0000-0000-000000000003"

DOC_Q1_ID = "d0000000-0000-0000-0000-000000000001"
DOC_ROADMAP_ID = "d0000000-0000-0000-0000-000000000002"
DOC_BUDGET_ID = "d0000000-0000-0000-0000-000000000003"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.execute(
        f"""
        CREATE TYPE {SCHEMA}.permission_enum AS ENUM ('view', 'edit', 'admin')
        """
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "grantor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.users.id"),
            nullable=False,
        ),
        sa.Column(
            "grantee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.users.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.documents.id"),
            nullable=False,
        ),
        sa.Column(
            "permission",
            sa.Enum("view", "edit", "admin", name="permission_enum", schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    # Partial unique index: only one active grant per grantee+document
    op.create_index(
        "uq_one_active_grant_per_grantee_document",
        "grants",
        ["grantee_id", "document_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # Seed users
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.users (id, name, email) VALUES
          ('{ALICE_ID}', 'Alice', 'alice@example.com'),
          ('{BOB_ID}',   'Bob',   'bob@example.com'),
          ('{CAROL_ID}', 'Carol', 'carol@example.com')
        """
    )

    # Seed documents (owned by Alice)
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.documents (id, title, owner_id) VALUES
          ('{DOC_Q1_ID}',      'Q1 Report',       '{ALICE_ID}'),
          ('{DOC_ROADMAP_ID}', 'Product Roadmap',  '{ALICE_ID}'),
          ('{DOC_BUDGET_ID}',  'Budget 2026',      '{ALICE_ID}')
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_one_active_grant_per_grantee_document",
        table_name="grants",
        schema=SCHEMA,
    )
    op.drop_table("grants", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.permission_enum")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
