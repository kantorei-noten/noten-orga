#!/usr/bin/env python3
"""Import des Josquin Research Project (JRP) in Noten-Orga.

JRP (josquin.stanford.edu) = geistliche/weltliche Renaissance-Vokalpolyphonie
(ca. 1420–1520), als **kern** in GitHub-Repos pro Komponist
(github.com/josquin-research-project/<Code>). Wir holen die kern-Datei, wandeln
sie mit music21 in **MusicXML** (→ Verovio-Ansicht, Transponieren, Spielansicht,
Notizen, Druck) und hängen sie an.

Für jeden Satz (.krn):
  1. Metadaten aus den kern-Headern (!!!COM/OTL/OPR/AGN/voices)
  2. music21: kern -> MusicXML (DOCTYPE gestrippt)
  3. POST /api/werke -> Ausgabe, dann POST /api/dateien (art=musicxml)

Idempotent (Titel+Komponist). Genre als Tag geistlich/weltlich (aus AGN).

Voraussetzungen (lokal):  pip install music21 requests verovio
  (verovio nur für den Fallback bei langen/mensuralen Sätzen nötig)
Beispiele:
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_jrp.py \
      --base-url https://noten.example.org --dry-run --limit 8
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_jrp.py \
      --base-url https://noten.example.org --scope all
"""
from __future__ import annotations

import argparse
import csv
import html as _html
import io
import json
import os
import re
import sys
import time
import urllib.request
from getpass import getpass

import requests

GH_API = "https://api.github.com"
GH_RAW = "https://raw.githubusercontent.com"
JRP = "josquin-research-project"
UA = "noten-orga-jrp-import/1.0 (Kirchenmusik-Archiv)"

SACRED = ("mass", "motet", "hymn", "psalm", "magnificat", "antiphon", "sacred",
          "lauda", "responsory", "sequence", "chant", "sanctus", "kyrie", "gloria",
          "credo", "agnus", "benedic", "salve", "ave", "lament")


# --------------------------------------------------------------------------- #
# GitHub / Werkliste                                                          #
# --------------------------------------------------------------------------- #
def _gh(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return json.load(urllib.request.urlopen(req, timeout=40))


def _raw(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def werkliste(jrp_dir: str) -> list[tuple[str, str]]:
    """(composer, dateipfad) aller .krn im lokalen jrp-scores-Klon.

    Klonen (kein GitHub-API-Rate-Limit):
      git clone --depth 1 --recursive --shallow-submodules \\
        https://github.com/josquin-research-project/jrp-scores.git
    Struktur: <jrp_dir>/<Composer>/kern/*.krn
    """
    out: list[tuple[str, str]] = []
    for composer in sorted(os.listdir(jrp_dir)):
        kdir = os.path.join(jrp_dir, composer, "kern")
        if not os.path.isdir(kdir):
            continue
        for fn in sorted(os.listdir(kdir)):
            if fn.endswith(".krn"):
                out.append((composer, os.path.join(kdir, fn)))
    return out


def kern_header(text: str, key: str) -> str:
    m = re.search(rf"^!!!{re.escape(key)}:\s*(.+?)\s*$", text, re.M)
    return _html.unescape(m.group(1).strip()) if m else ""  # z.B. F&eacute;vin -> Févin


# --------------------------------------------------------------------------- #
# Mapping                                                                      #
# --------------------------------------------------------------------------- #
def ist_sakral(agn: str) -> bool:
    a = (agn or "").lower()
    return any(s in a for s in SACRED)


def map_gattung(agn: str) -> str:
    a = (agn or "").lower()
    for key, val in (
        ("mass", "Messe"), ("motet", "Motette"), ("chanson", "Chanson"),
        ("madrigal", "Madrigal"), ("frottola", "Frottola"), ("lauda", "Lauda"),
        ("magnificat", "Magnificat"), ("psalm", "Psalm"), ("hymn", "Hymnus"),
        ("song", "Lied"), ("instrumental", "Instrumental"), ("secular", "Weltliches Werk"),
    ):
        if key in a:
            return val
    return (agn.split(";")[0].strip() if agn else "Vokalwerk")


# JRP-Komponisten-Code (Verzeichnis) -> Name; Fallback wenn kern kein COM/COA hat
JRP_COMPOSERS = {
    "Agr": "Alexander Agricola", "Ano": "Anonymous", "Bin": "Gilles Binchois",
    "Bru": "Antoine Brumel", "Bus": "Antoine Busnoys", "Com": "Loyset Compère",
    "Das": "Ludwig Daser", "Duf": "Guillaume Du Fay", "Fry": "Walter Frye",
    "Fva": "Antoine de Févin", "Gas": "Gaspar van Weerbeke", "Isa": "Heinrich Isaac",
    "Jap": "Jean Japart", "Jos": "Josquin des Prez", "Mar": "Johannes Martini",
    "Mou": "Mouton", "Obr": "Jacob Obrecht", "Oke": "Johannes Okeghem",
    "Ort": "Marbrianus de Orto", "Pip": "Matthaeus Pipelare", "Reg": "Johannes Regis",
    "Rue": "Pierre de la Rue", "Tin": "Johannes Tinctoris",
}


def norm_komponist(com: str) -> str | None:
    """'Agricola, Alexander' -> 'Alexander Agricola' (einheitliche Facette)."""
    com = (com or "").strip()
    if not com:
        return None
    if "," in com:
        parts = [p.strip() for p in com.split(",")]
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[1]} {parts[0]}"
    return com


def map_besetzung(voices: int | None) -> str | None:
    return {2: "SA", 3: "SAB", 4: "SATB"}.get(voices or 0)


def map_sprache(agn: str) -> str | None:
    a = (agn or "").lower()
    if ist_sakral(agn):
        return "la"
    if "chanson" in a:
        return "fr"
    if "madrigal" in a or "frottola" in a:
        return "it"
    return None


def titel_aus_pfad(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"^[A-Za-z]{2,4}\d+[a-z]?-", "", base)  # ID-Präfix weg
    return base.replace("_", " ").strip() or "Ohne Titel"


def build_meta(text: str, path: str) -> dict:
    # COA = 'composer attributed' (zugeschriebene Werke, z.B. viele Josquin) als Fallback
    com = kern_header(text, "COM") or kern_header(text, "COA")
    komp = norm_komponist(com)
    if not komp:  # kern ohne COM/COA -> Komponist aus dem JRP-Verzeichnis (Pfad)
        code = path.replace("\\", "/").split("/")[-3:-2]
        komp = JRP_COMPOSERS.get(code[0]) if code else None
    otl = kern_header(text, "OTL")
    opr = kern_header(text, "OPR")
    agn = kern_header(text, "AGN")
    sca = kern_header(text, "SCA") or kern_header(text, "SCT")
    jid = kern_header(text, "jrpid")
    try:
        voices = int(kern_header(text, "voices") or 0) or None
    except ValueError:
        voices = None

    if opr and otl:
        titel = f"{opr}: {otl}"
    elif opr:
        titel = opr
    elif otl:
        titel = otl
    else:
        titel = titel_aus_pfad(path)

    gattung = map_gattung(agn)
    tags = ["JRP", "Renaissance", gattung, "geistlich" if ist_sakral(agn) else "weltlich"]
    if opr:
        tags.append(opr)  # alle Sätze eines Werks teilen einen Tag
    return {
        "titel": titel[:500],
        "komponist": komp,
        "gattung": gattung,
        "sprache": map_sprache(agn),
        "besetzung": map_besetzung(voices),
        "entstehungsjahr": None,
        "notiz": (
            f"Quelle: Josquin Research Project (kern→MusicXML). Genre: {agn or '—'}. "
            f"Stimmen: {voices or '?'}. Edition: {sca or '—'}. jrpid {jid or '—'}."
        ),
        "tags": tags,
    }


DOCTYPE_RE = re.compile(rb"<!DOCTYPE[^>]*>\s*", re.IGNORECASE)


def kern_zu_musicxml(kern_bytes: bytes, tmp_path: str) -> bytes:
    from music21 import converter
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    with open(tmp_path, "wb") as f:
        f.write(kern_bytes)
    try:
        score = converter.parse(tmp_path)  # .krn -> Humdrum autodetektiert
        data = GeneralObjectExporter(score).parse()
    except Exception:
        # Fallback (lange/mensurale Sätze, wo music21s kern-Parser/makeTies scheitert):
        # verovio kern->MEI, dann music21 MEI->MusicXML. makeNotation False dann True;
        # leere Beams setzen (sonst 'Rest' has no attribute 'beams' bei makeNotation=False).
        import verovio
        from music21 import beam

        tk = verovio.toolkit()
        tk.setInputFrom("humdrum")
        tk.loadData(kern_bytes.decode("utf-8", "replace"))
        mei = tk.getMEI()
        data = last = None
        for mk in (False, True):
            try:
                score = converter.parse(mei, format="mei")
                for n in score.recurse().notesAndRests:
                    if getattr(n, "beams", None) is None:
                        n.beams = beam.Beams()
                gex = GeneralObjectExporter(score)
                gex.makeNotation = mk
                data = gex.parse()
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
        if data is None:
            raise last
    if isinstance(data, str):
        data = data.encode("utf-8")
    return DOCTYPE_RE.sub(b"", data)


def safe_filename(titel: str) -> str:
    base = re.sub(r"[^\w\-. ]", "_", titel, flags=re.UNICODE).strip().strip(".") or "jrp"
    return f"{base[:80]}.musicxml"


# --------------------------------------------------------------------------- #
# API-Client                                                                   #
# --------------------------------------------------------------------------- #
class NotenClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "noten-orga-jrp-import/1.0"

    def login(self, user: str, password: str, totp: str = "") -> None:
        cfg = self.s.get(f"{self.base}/api/auth/config", timeout=30)
        cfg.raise_for_status()
        if cfg.json().get("totp_pflicht") and not totp:
            totp = os.environ.get("NOTEN_TOTP", "") or input("TOTP-Code: ").strip()
        r = self.s.post(f"{self.base}/api/auth/login",
                        json={"username": user, "password": password, "totp": totp}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"Login fehlgeschlagen ({r.status_code}): {r.text[:200]}")

    def valid_besetzungen(self) -> set[str]:
        try:
            r = self.s.get(f"{self.base}/api/besetzungen", timeout=30)
            r.raise_for_status()
            return {row["kuerzel"] for row in r.json()}
        except Exception:
            return set()

    def existing_keys(self) -> set[tuple[str, str]]:
        r = self.s.get(f"{self.base}/api/werke/export-csv", timeout=120)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";")
        keys = set()
        for row in reader:
            t = (row.get("titel") or "").strip().lower()
            if t:
                keys.add((t, (row.get("komponist") or "").strip().lower()))
        return keys

    def create_werk(self, payload: dict) -> str:
        r = self.s.post(f"{self.base}/api/werke", json=payload, timeout=60)
        r.raise_for_status()
        ausgaben = r.json().get("ausgaben") or []
        if not ausgaben:
            raise RuntimeError("Werk ohne Ausgabe")
        return ausgaben[0]["id"]

    def attach_musicxml(self, ausgabe_id: str, filename: str, xml: bytes) -> dict:
        files = {"file": (filename, xml, "application/vnd.recordare.musicxml+xml")}
        r = self.s.post(f"{self.base}/api/dateien",
                        data={"ausgabe_id": ausgabe_id, "art": "musicxml"}, files=files, timeout=180)
        r.raise_for_status()
        return r.json()


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="JRP (Josquin Research Project) importieren")
    ap.add_argument("--base-url", default=os.environ.get("NOTEN_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--user", default=os.environ.get("NOTEN_USER"))
    ap.add_argument("--password", default=os.environ.get("NOTEN_PASS"))
    ap.add_argument("--jrp-dir", default=os.environ.get("JRP_DIR", "jrp-scores"),
                    help="lokaler jrp-scores-Klon (git clone --recursive)")
    ap.add_argument("--scope", choices=["all", "sacred"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.05)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "jrp_work.krn")

    if not os.path.isdir(args.jrp_dir):
        sys.exit(f"jrp-scores-Klon nicht gefunden: {args.jrp_dir}\n"
                 "git clone --depth 1 --recursive --shallow-submodules "
                 "https://github.com/josquin-research-project/jrp-scores.git")
    liste = werkliste(args.jrp_dir)
    print(f"JRP: {len(liste)} kern-Sätze in {args.jrp_dir}\n")

    client = None
    existing: set[tuple[str, str]] = set()
    allowed_bes: set[str] = set()
    if not args.dry_run:
        if not args.user:
            args.user = input("Benutzer: ").strip()
        if not args.password:
            args.password = getpass("Passwort: ")
        client = NotenClient(args.base_url)
        client.login(args.user, args.password, os.environ.get("NOTEN_TOTP", ""))
        existing = client.existing_keys()
        allowed_bes = client.valid_besetzungen()
        print(f"[i] {len(existing)} bestehende Werke; {len(allowed_bes)} Besetzungs-Kürzel.\n")

    created = skipped = failed = filtered = 0
    n = 0
    for composer, path in liste:
        if args.limit and n >= args.limit:
            break
        try:
            with open(path, "rb") as f:
                kern = f.read()
            text = kern.decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ! kern-Lesen {path}: {exc}")
            continue

        agn = kern_header(text, "AGN")
        if args.scope == "sacred" and not ist_sakral(agn):
            filtered += 1
            continue

        meta = build_meta(text, path)
        n += 1
        key = (meta["titel"].strip().lower(), (meta["komponist"] or "").strip().lower())
        if key in existing:
            skipped += 1
            continue
        bes = meta["besetzung"]
        if bes and allowed_bes and bes not in allowed_bes:
            meta["besetzung"] = None

        if args.dry_run:
            print(f"  + {meta['titel'][:50]:50} | {(meta['komponist'] or '—')[:20]:20} | "
                  f"{meta['gattung']:10} | {meta['besetzung'] or '—':5} | {meta['tags'][3]}")
            existing.add(key)
            created += 1
            continue

        try:
            xml = kern_zu_musicxml(kern, tmp)
            ausgabe_id = client.create_werk(meta)
            res = client.attach_musicxml(ausgabe_id, safe_filename(meta["titel"]), xml)
            existing.add(key)
            created += 1
            if created % 25 == 0:
                print(f"  … {created} angelegt (zuletzt: {meta['titel'][:40]})")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            msg = str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                msg = f"{exc.response.status_code}: {exc.response.text[:120]}"
            print(f"  ! FEHLER {meta['titel'][:40]}: {msg}")
        if args.sleep:
            time.sleep(args.sleep)

    print(f"\nFertig. angelegt={created}  übersprungen={skipped}  gefiltert={filtered}  "
          f"fehler={failed}" + ("  (Trockenlauf)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
