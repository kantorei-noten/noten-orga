"""Gruppen & Dienstplanung

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table gruppe (
          id uuid primary key default gen_random_uuid(),
          name text not null,
          art text not null default 'chor' check (art in ('chor','blaeser','band','sonstige')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create trigger trg_gruppe_upd before update on gruppe
          for each row execute function set_updated_at();
        create table gruppe_mitglied (
          gruppe_id uuid references gruppe(id) on delete cascade,
          benutzer_id uuid references benutzer(id) on delete cascade,
          primary key (gruppe_id, benutzer_id)
        );
        create table dienst (
          id uuid primary key default gen_random_uuid(),
          gruppe_id uuid not null references gruppe(id) on delete cascade,
          setliste_id uuid references setliste(id) on delete set null,
          datum date,
          bestaetigt boolean not null default false,
          notiz text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create trigger trg_dienst_upd before update on dienst
          for each row execute function set_updated_at();
        create index dienst_gruppe_idx on dienst(gruppe_id);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists dienst, gruppe_mitglied, gruppe cascade;")
