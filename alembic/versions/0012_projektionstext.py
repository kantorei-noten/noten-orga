"""Werk: Projektionstext (Liedtext für die Gemeinde-Projektion)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table werk add column projektionstext text;")


def downgrade() -> None:
    op.execute("alter table werk drop column if exists projektionstext cascade;")
