"""Stimmen-Liste je Ausgabe (für die Chor-/Ensemble-Verteilung).

Die PDF je Stimme liefert /api/druck/stimme/{stimme_id}.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from ..auth.deps import current_user
from ..db import get_conn

router = APIRouter(prefix="/ausgaben", tags=["stimmen"])


@router.get("/{ausgabe_id}/stimmen-liste")
async def stimmen_liste(ausgabe_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        """select st.id, st.name, st.seite_von, st.seite_bis, st.datei_id
           from stimme st join datei d on d.id = st.datei_id
           where d.ausgabe_id = %s order by st.sortierung, st.name""",
        (ausgabe_id,),
    )
    return await cur.fetchall()
