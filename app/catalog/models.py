"""Pydantic-Schemata für Katalog-/Erfassungs-Endpunkte."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class GesangbuchEintragIn(BaseModel):
    buch: str = Field(pattern="^(GL|EG)$")
    nummer: str = Field(min_length=1, max_length=20)
    teil: str | None = None


class WerkCreate(BaseModel):
    titel: str = Field(min_length=1, max_length=500)
    komponist: str | None = None
    textdichter: str | None = None
    gattung: str | None = None
    sprache: str | None = "de"
    entstehungsjahr: int | None = None
    notiz: str | None = None
    # Default-Fassung (Erfassung erzeugt sofort Fassung + Ausgabe zum Hochladen)
    besetzung: str | None = None
    tonart: str | None = None
    schwierigkeit: int | None = Field(default=None, ge=1, le=5)
    # Beziehungen
    gesangbuch: list[GesangbuchEintragIn] = []
    tags: list[str] = []
    anlass_ids: list[UUID] = []


class WerkUpdate(BaseModel):
    titel: str | None = Field(default=None, min_length=1, max_length=500)
    komponist: str | None = None
    textdichter: str | None = None
    gattung: str | None = None
    sprache: str | None = None
    entstehungsjahr: int | None = None
    notiz: str | None = None


class BatchTag(BaseModel):
    werk_ids: list[UUID] = Field(min_length=1)
    tag: str = Field(min_length=1)


class BatchAnlass(BaseModel):
    werk_ids: list[UUID] = Field(min_length=1)
    anlass_id: UUID
