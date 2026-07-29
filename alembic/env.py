"""Alembic-Umgebung. DB-URL aus NOTEN_DATABASE_URL, psycopg3-Dialekt, reine SQL-Migrationen."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

_url = os.environ.get(
    "NOTEN_DATABASE_URL", "postgresql://noten_app:devpw@localhost:5433/noten"
)
# SQLAlchemy braucht den expliziten psycopg3-Dialekt
if _url.startswith("postgresql://"):
    _url = "postgresql+psycopg://" + _url[len("postgresql://") :]
config.set_main_option("sqlalchemy.url", _url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # reine Raw-SQL-Migrationen, kein Autogenerate


def run_migrations_offline() -> None:
    context.configure(url=_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
