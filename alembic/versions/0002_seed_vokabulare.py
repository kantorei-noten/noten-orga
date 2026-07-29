"""Seed: Gesangbücher, Besetzungen, Kirchenjahr/Anlässe

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        insert into gesangbuch (kuerzel, name, sortierung) values
          ('GL','Gotteslob',1),
          ('EG','Evangelisches Gesangbuch',2)
        on conflict (kuerzel) do nothing;
        """
    )
    op.execute(
        """
        insert into besetzung (kuerzel, name, sortierung) values
          ('SATB','Chor 4-stimmig (SATB)',1),
          ('SAB','Chor 3-stimmig (SAB)',2),
          ('SA','Chor 2-stimmig (SA)',3),
          ('SSA','Frauenchor (SSA)',4),
          ('TTBB','Männerchor (TTBB)',5),
          ('Orgel','Orgel',6),
          ('Orgel+Gem','Orgel & Gemeinde',7),
          ('Gemeinde','Gemeinde einstimmig',8),
          ('Kantor','Kantor/Solo',9),
          ('Bläser','Bläsersatz',10),
          ('Instr','Instrumental',11)
        on conflict (kuerzel) do nothing;
        """
    )
    # Anlässe/Kirchenjahr — nur einspielen, wenn noch keine vorhanden (idempotent)
    op.execute(
        """
        insert into anlass (name, sortierung)
        select v.name, v.sort from (values
          ('Advent',1),('Weihnachten',2),('Jahreswechsel',3),('Epiphanias',4),
          ('Passion & Karwoche',5),('Ostern',6),('Christi Himmelfahrt',7),
          ('Pfingsten',8),('Trinitatis & Kirchenjahr',9),('Erntedank',10),
          ('Reformation',11),('Ewigkeitssonntag & Totengedenken',12),
          ('Taufe',13),('Trauung',14),('Trauerfeier & Beerdigung',15),
          ('Ökumene & Andacht',16),('Lob & Dank',17),('Morgen & Abend',18)
        ) as v(name, sort)
        where not exists (select 1 from anlass);
        """
    )


def downgrade() -> None:
    op.execute("delete from anlass;")
    op.execute("delete from besetzung where kuerzel in "
               "('SATB','SAB','SA','SSA','TTBB','Orgel','Orgel+Gem','Gemeinde','Kantor','Bläser','Instr');")
    op.execute("delete from gesangbuch where kuerzel in ('GL','EG');")
