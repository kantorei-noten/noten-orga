"""ChordPro-Text pro Werk

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-02
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table chordpro (
          werk_id uuid primary key references werk(id) on delete cascade,
          text text not null default '',
          updated_at timestamptz not null default now()
        );
        create trigger trg_chordpro_upd before update on chordpro
          for each row execute function set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists chordpro cascade;")
