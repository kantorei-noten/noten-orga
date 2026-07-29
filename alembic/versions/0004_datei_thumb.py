"""datei: Vorschau-Pfad (thumb_pfad)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table datei add column thumb_pfad text;")


def downgrade() -> None:
    op.execute("alter table datei drop column if exists thumb_pfad;")
