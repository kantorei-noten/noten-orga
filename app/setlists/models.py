"""Pydantic-Schemata für Setlisten (Gottesdienstablauf)."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class SetlisteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    datum: date | None = None
    anlass_id: UUID | None = None
    notiz: str | None = None


class SetlisteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    datum: date | None = None
    anlass_id: UUID | None = None
    notiz: str | None = None


class EintragCreate(BaseModel):
    # typ: 'werk' (ganzes Stück), 'abschnitt' (Seitenbereich/Strophe), 'notiz'
    typ: str = Field(default="werk", pattern="^(werk|abschnitt|notiz)$")
    werk_id: UUID | None = None
    ausgabe_id: UUID | None = None
    datei_id: UUID | None = None  # optional: bestimmtes Blatt/Stimme
    titel: str | None = None
    seite_von: int | None = Field(default=None, ge=1)
    seite_bis: int | None = Field(default=None, ge=1)


class EintragUpdate(BaseModel):
    # Nachträgliches Bearbeiten: Blatt umhängen + Seitenbereich (None/None = ganzes Blatt), Titel (Abschnitt)
    datei_id: UUID | None = None
    titel: str | None = None
    seite_von: int | None = Field(default=None, ge=1)
    seite_bis: int | None = Field(default=None, ge=1)


class Reihenfolge(BaseModel):
    eintrag_ids: list[UUID] = Field(min_length=1)
