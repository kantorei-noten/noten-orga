"""Sammlungen (Collections als Unter-Bibliotheken)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table sammlung (
          id uuid primary key default gen_random_uuid(),
          name text not null,
          art text not null default 'allgemein'
            check (art in ('orgel','chor','gemeinde','anlass','allgemein')),
          notiz text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create trigger trg_sammlung_upd before update on sammlung
          for each row execute function set_updated_at();
        create table werk_sammlung (
          werk_id uuid references werk(id) on delete cascade,
          sammlung_id uuid references sammlung(id) on delete cascade,
          primary key (werk_id, sammlung_id)
        );
        create index werk_sammlung_s_idx on werk_sammlung(sammlung_id);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists werk_sammlung, sammlung cascade;")
