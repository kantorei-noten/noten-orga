"""OMR-Veredelungs-Status auf Ausgabe

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        alter table ausgabe
          add column omr_status text not null default 'kein'
            check (omr_status in ('kein','geplant','ok','geprueft','archiv_only')),
          add column omr_confidence real;
        """
    )


def downgrade() -> None:
    op.execute("alter table ausgabe drop column if exists omr_status, drop column if exists omr_confidence;")
