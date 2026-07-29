"""Referenzlisten pflegbar: Sammlungs-Art vom CHECK-Enum zur Tabelle

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists sammlung_art (
          kuerzel text primary key,
          name text not null,
          sortierung int not null default 0
        );
        insert into sammlung_art (kuerzel, name, sortierung) values
          ('orgel','Orgel',1), ('chor','Chor',2), ('gemeinde','Gemeinde',3),
          ('anlass','Anlass',4), ('allgemein','Allgemein',5)
        on conflict (kuerzel) do nothing;

        -- alten CHECK auf sammlung.art entfernen (Name unabhängig ermitteln)
        do $$
        declare r record;
        begin
          for r in select conname from pg_constraint
                   where conrelid = 'sammlung'::regclass and contype = 'c' loop
            execute 'alter table sammlung drop constraint ' || quote_ident(r.conname);
          end loop;
        end $$;

        alter table sammlung
          add constraint sammlung_art_fk foreign key (art)
          references sammlung_art(kuerzel) on update cascade;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table sammlung drop constraint if exists sammlung_art_fk;
        alter table sammlung add constraint sammlung_art_check
          check (art in ('orgel','chor','gemeinde','anlass','allgemein'));
        drop table if exists sammlung_art;
        """
    )
