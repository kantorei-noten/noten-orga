"""Auth: Benutzer + Sitzungen

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table benutzer (
          id uuid primary key default gen_random_uuid(),
          benutzername text not null unique,
          email text unique,
          passwort_hash text not null,
          totp_secret text not null,
          totp_aktiviert boolean not null default true,
          totp_last_step bigint not null default 0,
          rolle text not null default 'gast'
            check (rolle in ('admin','musiker','chor','gast')),
          aktiv boolean not null default true,
          fehlversuche int not null default 0,
          gesperrt_bis timestamptz,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create trigger trg_benutzer_upd before update on benutzer
          for each row execute function set_updated_at();

        create table sitzung (
          token_hash char(64) primary key,
          benutzer_id uuid not null references benutzer(id) on delete cascade,
          created_at timestamptz not null default now(),
          last_seen timestamptz not null default now(),
          expires_at timestamptz not null,
          user_agent text,
          ip text
        );
        create index sitzung_benutzer_idx on sitzung(benutzer_id);
        create index sitzung_expires_idx on sitzung(expires_at);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists sitzung, benutzer cascade;")
