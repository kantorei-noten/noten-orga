"""ChordPro: Transposition (zustandslos) + Text pro Werk (gespeichert)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..auth.deps import current_user, require_role
from ..chordpro import transponiere
from ..db import get_conn

router = APIRouter(prefix="/chordpro", tags=["chordpro"])


class ChordProIn(BaseModel):
    text: str
    halbtoene: int = Field(default=0, ge=-11, le=11)


@router.post("/transponieren")
async def transponieren(data: ChordProIn, user=Depends(current_user)):
    return {"text": transponiere(data.text, data.halbtoene)}


class ChordProText(BaseModel):
    text: str = Field(default="", max_length=100_000)


@router.get("/werk/{werk_id}")
async def hole(werk_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        "select text, updated_at from chordpro where werk_id = %s", (werk_id,)
    )
    row = await cur.fetchone()
    return {
        "text": row["text"] if row else "",
        "updated_at": row["updated_at"] if row else None,
    }


@router.put("/werk/{werk_id}")
async def speichern(
    werk_id: UUID,
    data: ChordProText,
    user=Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    await conn.execute(
        """insert into chordpro (werk_id, text) values (%s, %s)
           on conflict (werk_id) do update set text = excluded.text""",
        (werk_id, data.text),
    )
    return {"status": "ok"}
