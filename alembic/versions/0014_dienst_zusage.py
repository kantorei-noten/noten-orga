"""Dienst-Zusagen pro Mitglied (kann/kann nicht + Notiz)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table dienst_zusage (
          dienst_id uuid not null references dienst(id) on delete cascade,
          benutzer_id uuid not null references benutzer(id) on delete cascade,
          status text not null check (status in ('zugesagt','abgesagt')),
          notiz text,
          updated_at timestamptz not null default now(),
          primary key (dienst_id, benutzer_id)
        );
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists dienst_zusage;")
