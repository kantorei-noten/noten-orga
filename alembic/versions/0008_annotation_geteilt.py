"""annotation.geteilt (Ebene für Ensemble sichtbar)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table annotation add column geteilt boolean not null default false;")


def downgrade() -> None:
    op.execute("alter table annotation drop column if exists geteilt;")
