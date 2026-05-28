# Document Access Grant Service

A REST API that manages document access grants — share documents with fine-grained permissions and expiry.

## Stack

- **Python 3.11+** · FastAPI · SQLAlchemy 2.0 (async) · asyncpg · PostgreSQL · Alembic · Pydantic v2
- **Tests:** pytest + pytest-asyncio (SQLite in-memory for unit/integration, real PG optional)
- **Observability:** structlog structured logging

---

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. Migrations and seed data run automatically.

Interactive docs: `http://localhost:8000/docs`

---

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL running (or use Docker Compose for just the DB)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit DATABASE_URL if needed
```

### Run migrations

```bash
alembic upgrade head
```

### Start the server

```bash
uvicorn app.main:app --reload
```

---

## Running Tests

Tests use an **in-memory SQLite** database — no external services needed.

```bash
pytest -v
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/grants` | Create a grant |
| `GET` | `/grants` | List grants (filterable) |
| `GET` | `/grants/{id}` | Get a single grant |
| `DELETE` | `/grants/{id}?requestor_id=<uuid>` | Revoke a grant |
| `GET` | `/grants/{id}/check` | Check grant status |
| `GET` | `/grants/summary` | Per-document grant summary (bonus) |

### Create Grant — `POST /grants`

```json
{
  "grantor_id": "a0000000-0000-0000-0000-000000000001",
  "grantee_id": "a0000000-0000-0000-0000-000000000002",
  "document_id": "d0000000-0000-0000-0000-000000000001",
  "permission": "view",
  "expires_at": "2025-12-31T23:59:00Z"
}
```

### List Grants — `GET /grants`

Query params: `grantor_id`, `grantee_id`, `document_id`, `status` (`active` | `revoked` | `expired`), `limit`, `offset`

### Revoke Grant — `DELETE /grants/{id}`

Requires `?requestor_id=<uuid>`. Only the original grantor can revoke.

---

## Seed Data

| Entity | ID |
|--------|----|
| Alice | `a0000000-0000-0000-0000-000000000001` |
| Bob | `a0000000-0000-0000-0000-000000000002` |
| Carol | `a0000000-0000-0000-0000-000000000003` |
| Q1 Report | `d0000000-0000-0000-0000-000000000001` |
| Product Roadmap | `d0000000-0000-0000-0000-000000000002` |
| Budget 2026 | `d0000000-0000-0000-0000-000000000003` |
