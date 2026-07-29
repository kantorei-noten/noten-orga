"""Annotationen (SVG-Overlay pro Ausgabe/Seite/Benutzer)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table annotation (
          id uuid primary key default gen_random_uuid(),
          ausgabe_id uuid not null references ausgabe(id) on delete cascade,
          benutzer_id uuid not null references benutzer(id) on delete cascade,
          ebene text not null default 'notiz',
          seite int not null default 1,
          daten jsonb not null default '{}'::jsonb,
          sichtbar boolean not null default true,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create unique index annotation_uq on annotation(ausgabe_id, benutzer_id, ebene, seite);
        create index annotation_lookup on annotation(ausgabe_id, benutzer_id, seite);
        create trigger trg_annotation_upd before update on annotation
          for each row execute function set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists annotation cascade;")
