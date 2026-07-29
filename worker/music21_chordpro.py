"""music21-ChordPro für den Worker — nutzt die geteilte Implementierung in
`app.catalog.chordgen_m21` (das App-Paket liegt im Worker-Image, s. Dockerfile.worker),
damit es genau EINE music21-Variante gibt. Der Batch-Job `chordpro_music21` ruft
`werk_chordpro` (Alias) auf.
"""
from __future__ import annotations

from app.catalog.chordgen_m21 import chordpro_aus_musicxml as werk_chordpro

__all__ = ["werk_chordpro"]
