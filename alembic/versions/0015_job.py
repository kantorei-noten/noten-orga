"""Hintergrund-Jobs (Import/Analyse) mit Fortschritt — vom Worker abgearbeitet

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table job (
          id uuid primary key default gen_random_uuid(),
          typ text not null,
          status text not null default 'offen'
            check (status in ('offen','laeuft','fertig','fehler','abgebrochen')),
          fortschritt int not null default 0,
          gesamt int not null default 0,
          aktuell text,
          log text,
          params jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create index job_status_idx on job(status, created_at);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists job;")
