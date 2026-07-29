#!/usr/bin/env python3
"""Import des music21-Corpus (Bach-Choräle, Palestrina …) in Noten-Orga.

Für jedes Stück:
  1. POST /api/werke        -> legt Werk+Fassung+Ausgabe an, liefert ausgabe_id zurück
  2. MusicXML aus music21 exportieren (DOCTYPE gestrippt, damit defusedxml es akzeptiert)
  3. POST /api/dateien      -> hängt die MusicXML an die Ausgabe (art=musicxml, sha256-Dedup)

Idempotent: bereits vorhandene Werke (gleicher Titel+Komponist) werden übersprungen
(dieselbe Dedup-Logik wie der Server-CSV-Import).

Voraussetzungen (lokal, z. B. auf dem Mac):
    pip install music21 requests

Beispiele:
    # Trockenlauf: nur zeigen, was importiert würde (nichts schreiben)
    NOTEN_USER=admin NOTEN_PASS=... python scripts/import_music21.py \
        --base-url https://noten.example.org --dry-run --limit 5

    # Scharf: alle Bach-Choräle
    NOTEN_USER=admin NOTEN_PASS=... python scripts/import_music21.py \
        --base-url https://noten.example.org --source chorales

    # Bach-Choräle + Palestrina
    ... --source both

TOTP: Wenn die 2FA-Pflicht am Server aktiv ist, wird der Code aus NOTEN_TOTP genommen
oder interaktiv abgefragt.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import time
from getpass import getpass

import requests

DOCTYPE_RE = re.compile(rb"<!DOCTYPE[^>]*>\s*", re.IGNORECASE)
BWV_RE = re.compile(r"bwv[\s._-]?(\d+[a-z]?)", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# music21-Seite                                                               #
# --------------------------------------------------------------------------- #
def _lazy_music21():
    try:
        import music21  # noqa: F401
    except ImportError:
        sys.exit("Fehlt: music21. Installieren mit  pip install music21")
    return __import__("music21")


def to_musicxml_bytes(score) -> bytes:
    """MusicXML-Bytes ohne DOCTYPE (externe DTD-Referenz würde defusedxml irritieren)."""
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    data = GeneralObjectExporter(score).parse()
    if isinstance(data, str):
        data = data.encode("utf-8")
    return DOCTYPE_RE.sub(b"", data)


def _german_key(score) -> str | None:
    """Tonart als 'G-Dur' / 'g-Moll' — best effort, darf fehlschlagen."""
    try:
        k = score.analyze("key")
    except Exception:
        return None
    tonic = (k.tonic.name or "").replace("-", "b").replace("#", "is")
    if not tonic:
        return None
    if k.mode == "minor":
        return f"{tonic.lower()}-Moll"
    return f"{tonic}-Dur"


def _besetzung(score, default: str | None) -> str | None:
    """Besetzung als kontrolliertes Kürzel (FK -> noten.besetzung.kuerzel).
    Nur eindeutige Chor-Kürzel; sonst default (ggf. None)."""
    try:
        n = len(score.parts)
    except Exception:
        n = 0
    return {2: "SA", 3: "SAB", 4: "SATB"}.get(n, default)


def iter_chorales(limit: int | None):
    """Bach-Choräle (Riemenschneider 371). Liefert (titel, meta_dict, score)."""
    m21 = _lazy_music21()
    from music21 import corpus

    n = 0
    for chorale in corpus.chorales.Iterator(returnType="stream"):
        md = chorale.metadata
        path = ""
        for attr in ("corpusFilePath", "filePath"):
            try:
                path = str(getattr(md, attr, "") or "") or path
            except Exception:
                pass
        m = BWV_RE.search(path) or BWV_RE.search(md.title or "")
        bwv = m.group(1) if m else None
        title = (md.title or getattr(md, "movementName", None) or "").strip()
        if not title:
            title = f"Choral BWV {bwv}" if bwv else (os.path.splitext(os.path.basename(path))[0] or "Ohne Titel")
        tags = ["music21", "Bach-Choral"]
        if bwv:
            tags.append(f"BWV {bwv}")
        meta = dict(
            komponist="Johann Sebastian Bach",
            gattung="Choral",
            sprache="de",
            besetzung=_besetzung(chorale, "SATB"),
            tonart=_german_key(chorale),
            tags=tags,
            notiz="Quelle: music21-Corpus (Bach-Choräle), MusicXML. Gemeinfrei.",
        )
        yield title, meta, chorale
        n += 1
        if limit and n >= limit:
            break


def iter_palestrina(limit: int | None):
    """Palestrina-Werke aus dem Corpus (Messen/Motetten, lateinisch)."""
    _lazy_music21()
    from music21 import corpus

    bundle = corpus.search("palestrina", field="composer")
    n = 0
    for entry in bundle:
        try:
            score = entry.parse()
        except Exception:
            continue
        md = score.metadata
        title = (md.title or getattr(md, "movementName", None) or "").strip() or "Ohne Titel"
        gattung = "Messe" if re.search(r"mass|missa|kyrie|gloria|credo|sanctus|agnus", title, re.I) else "Motette"
        meta = dict(
            komponist="Giovanni Pierluigi da Palestrina",
            gattung=gattung,
            sprache="la",
            besetzung=_besetzung(score, None),
            tonart=None,
            tags=["music21", "Palestrina", "Renaissance"],
            notiz="Quelle: music21-Corpus (Palestrina), MusicXML. Gemeinfrei.",
        )
        yield title, meta, score
        n += 1
        if limit and n >= limit:
            break


SOURCES = {
    "chorales": iter_chorales,
    "palestrina": iter_palestrina,
}


# --------------------------------------------------------------------------- #
# Noten-Orga-API-Seite                                                        #
# --------------------------------------------------------------------------- #
class NotenClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "noten-orga-music21-import/1.0"

    def login(self, user: str, password: str, totp: str = "") -> None:
        cfg = self.s.get(f"{self.base}/api/auth/config", timeout=30)
        cfg.raise_for_status()
        if cfg.json().get("totp_pflicht") and not totp:
            totp = os.environ.get("NOTEN_TOTP", "") or input("TOTP-Code: ").strip()
        r = self.s.post(
            f"{self.base}/api/auth/login",
            json={"username": user, "password": password, "totp": totp},
            timeout=30,
        )
        if r.status_code != 200:
            sys.exit(f"Login fehlgeschlagen ({r.status_code}): {r.text[:200]}")

    def valid_besetzungen(self) -> set[str]:
        """Erlaubte Besetzungs-Kürzel (FK-Zielwerte). Leer -> Prüfung wird übersprungen."""
        try:
            r = self.s.get(f"{self.base}/api/besetzungen", timeout=30)
            r.raise_for_status()
            return {row["kuerzel"] for row in r.json()}
        except Exception:
            return set()

    def existing_keys(self) -> set[tuple[str, str]]:
        """(titel, komponist) aller vorhandenen Werke — für Dedup wie beim Server."""
        r = self.s.get(f"{self.base}/api/werke/export-csv", timeout=120)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        keys = set()
        for row in reader:
            t = (row.get("titel") or "").strip().lower()
            k = (row.get("komponist") or "").strip().lower()
            if t:
                keys.add((t, k))
        return keys

    def create_werk(self, titel: str, meta: dict) -> str:
        payload = {
            "titel": titel,
            "komponist": meta.get("komponist"),
            "gattung": meta.get("gattung"),
            "sprache": meta.get("sprache", "de"),
            "besetzung": meta.get("besetzung"),
            "tonart": meta.get("tonart"),
            "notiz": meta.get("notiz"),
            "tags": meta.get("tags", []),
        }
        r = self.s.post(f"{self.base}/api/werke", json=payload, timeout=60)
        r.raise_for_status()
        werk = r.json()
        ausgaben = werk.get("ausgaben") or []
        if not ausgaben:
            raise RuntimeError("Werk ohne Ausgabe zurückgekommen")
        return ausgaben[0]["id"]

    def attach_musicxml(self, ausgabe_id: str, filename: str, xml_bytes: bytes) -> dict:
        files = {"file": (filename, xml_bytes, "application/vnd.recordare.musicxml+xml")}
        data = {"ausgabe_id": ausgabe_id, "art": "musicxml"}
        r = self.s.post(f"{self.base}/api/dateien", data=data, files=files, timeout=120)
        r.raise_for_status()
        return r.json()


def _safe_filename(titel: str) -> str:
    base = re.sub(r"[^\w\-. ]", "_", titel, flags=re.UNICODE).strip().strip(".") or "werk"
    return f"{base[:80]}.musicxml"


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="music21-Corpus in Noten-Orga importieren")
    ap.add_argument("--base-url", default=os.environ.get("NOTEN_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--user", default=os.environ.get("NOTEN_USER"))
    ap.add_argument("--password", default=os.environ.get("NOTEN_PASS"))
    ap.add_argument("--source", choices=["chorales", "palestrina", "both"], default="chorales")
    ap.add_argument("--limit", type=int, default=0, help="max. Stücke pro Quelle (0 = alle)")
    ap.add_argument("--sleep", type=float, default=0.0, help="Pause zwischen Uploads (Sek.)")
    ap.add_argument("--dry-run", action="store_true", help="nichts schreiben, nur anzeigen")
    args = ap.parse_args()

    if not args.dry_run:
        if not args.user:
            args.user = input("Benutzer: ").strip()
        if not args.password:
            args.password = getpass("Passwort: ")

    client = None
    existing: set[tuple[str, str]] = set()
    allowed_bes: set[str] = set()
    if not args.dry_run:
        client = NotenClient(args.base_url)
        client.login(args.user, args.password, os.environ.get("NOTEN_TOTP", ""))
        existing = client.existing_keys()
        allowed_bes = client.valid_besetzungen()
        print(f"[i] {len(existing)} bestehende Werke geladen (Dedup); "
              f"{len(allowed_bes)} gültige Besetzungs-Kürzel.")

    limit = args.limit or None
    sources = ["chorales", "palestrina"] if args.source == "both" else [args.source]

    created = skipped = failed = 0
    for src in sources:
        print(f"\n=== Quelle: {src} ===")
        for titel, meta, score in SOURCES[src](limit):
            # Besetzung ist ein FK: ungültige Kürzel weglassen (als Tag sichern),
            # sonst würde POST /api/werke mit 500 (ForeignKeyViolation) scheitern.
            bes = meta.get("besetzung")
            if bes and allowed_bes and bes not in allowed_bes:
                meta = {**meta, "besetzung": None, "tags": meta["tags"] + [bes]}

            key = (titel.strip().lower(), (meta.get("komponist") or "").strip().lower())
            if key in existing:
                skipped += 1
                print(f"  · übersprungen (existiert): {titel}")
                continue

            if args.dry_run:
                print(f"  + WÜRDE anlegen: {titel} | {meta['komponist']} | "
                      f"{meta['gattung']} | {meta.get('besetzung')} | {meta.get('tonart') or '—'} | "
                      f"tags={','.join(meta['tags'])}")
                existing.add(key)
                created += 1
                continue

            try:
                xml = to_musicxml_bytes(score)
                ausgabe_id = client.create_werk(titel, meta)
                res = client.attach_musicxml(ausgabe_id, _safe_filename(titel), xml)
                existing.add(key)
                created += 1
                flag = "neu" if res.get("neu") else "dedup"
                print(f"  + {titel}  ->  Ausgabe {ausgabe_id[:8]} · Datei {res['id'][:8]} ({flag})")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                msg = str(exc)
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    msg = f"{exc.response.status_code}: {exc.response.text[:160]}"
                print(f"  ! FEHLER bei {titel}: {msg}")
            if args.sleep:
                time.sleep(args.sleep)

    print(f"\nFertig. angelegt={created}  übersprungen={skipped}  fehler={failed}"
          + ("  (Trockenlauf)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
