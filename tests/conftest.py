"""Pytest-Fixtures. Nutzt die isolierte Test-DB (noten_test) auf Port 5433."""
from __future__ import annotations

import os
import tempfile

# Tests laufen IMMER gegen die isolierte Test-DB — nie versehentlich gegen dev/prod,
# auch wenn NOTEN_DATABASE_URL in der Umgebung gesetzt ist (daher hartes Überschreiben).
_TEST_DB = os.environ.get(
    "NOTEN_TEST_DATABASE_URL", "postgresql://noten_app:devpw@localhost:5433/noten_test"
)
os.environ["NOTEN_DATABASE_URL"] = _TEST_DB
os.environ["NOTEN_ENVIRONMENT"] = "test"
# Uploads in ein temporäres Verzeichnis (nicht ins Projekt schreiben)
os.environ.setdefault("NOTEN_DATA_DIR", tempfile.mkdtemp(prefix="noten-test-data-"))

import psycopg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    """Migriert die Test-DB und leert die Domänentabellen (Seeds bleiben)."""
    import psycopg as _pg
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    with _pg.connect(_TEST_DB, autocommit=True) as c:
        c.execute("truncate werk, tag, setliste, benutzer restart identity cascade")
    yield


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture
async def conn():
    async with await psycopg.AsyncConnection.connect(
        os.environ["NOTEN_DATABASE_URL"], autocommit=True, row_factory=dict_row
    ) as c:
        yield c
