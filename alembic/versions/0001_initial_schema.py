"""Initiales FRBR-Schema + deutsche Volltextsuche

Revision ID: 0001
Revises:
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Erweiterungen + deutsche, akzentunempfindliche Textsuche-Konfiguration ---
    op.execute("create extension if not exists unaccent;")
    op.execute("create extension if not exists pg_trgm;")
    op.execute(
        """
        create text search configuration deutsch_unaccent ( copy = german );
        alter text search configuration deutsch_unaccent
            alter mapping for hword, hword_part, word with unaccent, german_stem;
        """
    )

    # --- Gemeinsame Trigger-Funktionen ---
    op.execute(
        """
        create function set_updated_at() returns trigger language plpgsql as $$
        begin new.updated_at := now(); return new; end $$;
        """
    )
    op.execute(
        """
        create function werk_such_tsv() returns trigger language plpgsql as $$
        begin
          new.such_tsv := to_tsvector('deutsch_unaccent',
            coalesce(new.titel,'') || ' ' || coalesce(new.komponist,'') || ' ' ||
            coalesce(new.textdichter,'') || ' ' || coalesce(new.gattung,''));
          return new;
        end $$;
        """
    )

    # --- Referenz-/Vokabular-Tabellen ---
    op.execute(
        """
        create table gesangbuch (
          kuerzel text primary key,
          name text not null,
          sortierung int not null default 0
        );
        create table besetzung (
          kuerzel text primary key,
          name text not null,
          sortierung int not null default 0
        );
        create table anlass (
          id uuid primary key default gen_random_uuid(),
          parent_id uuid references anlass(id) on delete cascade,
          name text not null,
          sortierung int not null default 0
        );
        create index anlass_parent_idx on anlass(parent_id);
        create table tag (
          id uuid primary key default gen_random_uuid(),
          name text not null unique
        );
        """
    )

    # --- FRBR-Kern: werk -> fassung -> ausgabe -> datei -> stimme ---
    op.execute(
        """
        create table werk (
          id uuid primary key default gen_random_uuid(),
          titel text not null,
          komponist text,
          textdichter text,
          gattung text,
          sprache text default 'de',
          entstehungsjahr int,
          notiz text,
          such_tsv tsvector,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create table fassung (
          id uuid primary key default gen_random_uuid(),
          werk_id uuid not null references werk(id) on delete cascade,
          name text,
          besetzung text references besetzung(kuerzel),
          tonart text,
          schwierigkeit int check (schwierigkeit between 1 and 5),
          bearbeiter text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create index fassung_werk_idx on fassung(werk_id);
        create table ausgabe (
          id uuid primary key default gen_random_uuid(),
          fassung_id uuid not null references fassung(id) on delete cascade,
          name text,
          verlag text,
          jahr int,
          rechtestatus text not null default 'unbekannt'
            check (rechtestatus in ('public_domain','lizenziert','unbekannt','gesperrt')),
          bevorzugt boolean not null default false,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create index ausgabe_fassung_idx on ausgabe(fassung_id);
        create table datei (
          id uuid primary key default gen_random_uuid(),
          ausgabe_id uuid not null references ausgabe(id) on delete cascade,
          art text not null check (art in ('scan_pdf','import_pdf','musicxml','thumbnail')),
          sha256 char(64) not null,
          pfad text not null,
          mime text not null,
          groesse_bytes bigint not null,
          seiten int,
          original_name text,
          created_at timestamptz not null default now()
        );
        create index datei_ausgabe_idx on datei(ausgabe_id);
        create index datei_sha_idx on datei(sha256);
        create table stimme (
          id uuid primary key default gen_random_uuid(),
          datei_id uuid not null references datei(id) on delete cascade,
          name text not null,
          seite_von int,
          seite_bis int,
          sortierung int not null default 0
        );
        create index stimme_datei_idx on stimme(datei_id);
        """
    )

    # --- Gesangbuch-Nummern + Verknüpfungen ---
    op.execute(
        """
        create table gesangbuch_eintrag (
          id uuid primary key default gen_random_uuid(),
          werk_id uuid not null references werk(id) on delete cascade,
          buch text not null references gesangbuch(kuerzel),
          nummer text not null,
          teil text
        );
        create unique index gb_eintrag_uq on gesangbuch_eintrag(werk_id, buch, nummer, coalesce(teil,''));
        create index gb_eintrag_nummer_idx on gesangbuch_eintrag(buch, nummer);
        create table werk_anlass (
          werk_id uuid references werk(id) on delete cascade,
          anlass_id uuid references anlass(id) on delete cascade,
          primary key (werk_id, anlass_id)
        );
        create table werk_tag (
          werk_id uuid references werk(id) on delete cascade,
          tag_id uuid references tag(id) on delete cascade,
          primary key (werk_id, tag_id)
        );
        """
    )

    # --- Setlisten (ganze Stücke UND Abschnitte/Bookmarks) ---
    op.execute(
        """
        create table setliste (
          id uuid primary key default gen_random_uuid(),
          name text not null,
          datum date,
          anlass_id uuid references anlass(id) on delete set null,
          notiz text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );
        create table setliste_eintrag (
          id uuid primary key default gen_random_uuid(),
          setliste_id uuid not null references setliste(id) on delete cascade,
          position int not null,
          typ text not null default 'werk' check (typ in ('werk','abschnitt','notiz')),
          werk_id uuid references werk(id) on delete set null,
          ausgabe_id uuid references ausgabe(id) on delete set null,
          titel text,
          seite_von int,
          seite_bis int
        );
        create index setliste_eintrag_idx on setliste_eintrag(setliste_id, position);
        """
    )

    # --- Trigger + Suchindizes ---
    op.execute(
        """
        create trigger trg_werk_tsv before insert or update on werk
          for each row execute function werk_such_tsv();
        create trigger trg_werk_upd before update on werk
          for each row execute function set_updated_at();
        create trigger trg_fassung_upd before update on fassung
          for each row execute function set_updated_at();
        create trigger trg_ausgabe_upd before update on ausgabe
          for each row execute function set_updated_at();
        create trigger trg_setliste_upd before update on setliste
          for each row execute function set_updated_at();
        create index werk_such_tsv_gin on werk using gin(such_tsv);
        create index werk_titel_trgm on werk using gin (titel gin_trgm_ops);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table if exists setliste_eintrag, setliste,
          werk_tag, werk_anlass, gesangbuch_eintrag,
          stimme, datei, ausgabe, fassung, werk,
          tag, anlass, besetzung, gesangbuch cascade;
        drop function if exists werk_such_tsv();
        drop function if exists set_updated_at();
        drop text search configuration if exists deutsch_unaccent;
        """
    )
