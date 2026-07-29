#!/usr/bin/env python3
"""Import aus CPDL / ChoralWiki (www.cpdl.org) in Noten-Orga.

CPDL läuft auf MediaWiki → api.php + strukturierte Vorlagen
({{Composer}}, {{Genre|Sacred|...}}, {{Voicing|4|SATB}}, {{Language|Latin}})
und Datei-Links [[Media:name.mxl|{{XML}}]] / [[Media:name.pdf|{{pdf}}]].

Pro Werk: Metadaten aus dem Wikitext, beste Datei wählen (MusicXML .mxl/.xml
bevorzugt — .mxl wird zu plain MusicXML entpackt — sonst PDF), an die App hängen.
Datei-URL wird per MD5 des Namens gebildet (MediaWiki-Standardpfad, kein Extra-Call).

Idempotent (Titel+Komponist). Standard-Scope: Category:Masses (geistlich).

Voraussetzungen:  pip install requests
Beispiele:
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_cpdl.py \
      --base-url https://noten.example.org --category Masses --dry-run --limit 10
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_cpdl.py \
      --base-url https://noten.example.org --category Masses
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import sys
import time
import urllib.parse
import zipfile
from getpass import getpass

import requests

WIKI = "https://www.cpdl.org/wiki"
API = WIKI + "/api.php"
# Höfliche Kennung fürs Wiki (MediaWiki-Etikette). Eigene Kontaktangabe per
# NOTEN_IMPORT_KONTAKT setzen — CPDL sieht sonst nur die Projekt-Adresse.
_KONTAKT = os.environ.get("NOTEN_IMPORT_KONTAKT", "https://github.com/kantorei-noten/noten-orga")
UA = f"noten-orga-cpdl-import/1.0 (Kirchenmusik-Archiv; {_KONTAKT})"

SESS = requests.Session()
SESS.headers["User-Agent"] = UA

MUSICXML_EXT = (".mxl", ".musicxml", ".xml")
LANG_MAP = {
    "latin": "la", "german": "de", "english": "en", "french": "fr", "italian": "it",
    "spanish": "es", "dutch": "nl", "portuguese": "pt", "czech": "cs", "polish": "pl",
    "greek": "el", "hebrew": "he", "church slavonic": "cu", "swedish": "sv",
}


# --------------------------------------------------------------------------- #
# CPDL / MediaWiki                                                             #
# --------------------------------------------------------------------------- #
def api_get(params: dict) -> dict:
    params = {**params, "format": "json"}
    for _ in range(4):
        try:
            r = SESS.get(API, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(1.5)
    raise RuntimeError("API-Fehler")


def category_titles(cat: str) -> list[str]:
    """Alle Artikel (namespace 0) einer Kategorie."""
    out: list[str] = []
    cont: dict = {}
    while True:
        d = api_get({
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{cat}", "cmlimit": "500", "cmnamespace": "0", **cont,
        })
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" in d:
            cont = d["continue"]
            time.sleep(0.2)
        else:
            break
    return out


def wikitexts(titles: list[str]) -> dict[str, str]:
    """Wikitext für bis zu 50 Seiten je Anfrage."""
    res: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        d = api_get({
            "action": "query", "prop": "revisions", "rvprop": "content",
            "rvslots": "main", "titles": "|".join(chunk),
        })
        for p in d.get("query", {}).get("pages", {}).values():
            try:
                res[p["title"]] = p["revisions"][0]["slots"]["main"]["*"]
            except (KeyError, IndexError):
                pass
        time.sleep(0.25)
    return res


def cpdl_file_url(filename: str) -> str:
    fn = filename.replace(" ", "_")
    if fn:  # MediaWiki macht den ersten Buchstaben des Dateinamens groß
        fn = fn[0].upper() + fn[1:]
    h = hashlib.md5(fn.encode("utf-8")).hexdigest()
    return f"{WIKI}/images/{h[0]}/{h[:2]}/{urllib.parse.quote(fn)}"


def download(url: str) -> bytes:
    r = SESS.get(url, timeout=120)
    r.raise_for_status()
    head = r.content[:64].lstrip().lower()
    if r.headers.get("Content-Type", "").startswith("text/html") or head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise ValueError("HTML statt Datei erhalten (Pfad falsch?)")
    return r.content


def mxl_to_plain(data: bytes) -> bytes:
    """.mxl (ZIP) -> plain MusicXML-Bytes. Toleriert fälschlich als .mxl benannte
    plain-XML-Dateien und Container-Pfade, die nicht exakt im Archiv liegen."""
    head = data[:64].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<score"):
        return data  # ist bereits plain MusicXML (nur .mxl benannt)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    score = None
    try:
        cont = z.read("META-INF/container.xml").decode("utf-8", "replace")
        m = re.search(r'full-path="([^"]+)"', cont)
        if m and m.group(1) in names:
            score = m.group(1)
    except Exception:
        pass
    if not score:
        cands = [n for n in names
                 if n.lower().endswith((".xml", ".musicxml")) and not n.startswith("META-INF")]
        if not cands:
            raise ValueError("keine Score-XML im mxl")
        score = cands[0]
    return z.read(score)


# --------------------------------------------------------------------------- #
# Wikitext-Parsing                                                            #
# --------------------------------------------------------------------------- #
def _tmpl(wt: str, name: str) -> list[str]:
    """Argumente der ersten {{name|...}}-Vorlage (per | getrennt, ohne verschachtelte)."""
    m = re.search(r"\{\{" + re.escape(name) + r"\s*\|([^{}]*?)\}\}", wt, re.I)
    return [a.strip() for a in m.group(1).split("|")] if m else []


def parse_besetzung(voicing: str, allowed: set[str] | None) -> str | None:
    v = (voicing or "").split(",")[0].strip().upper()
    kuerzel = {"SATB": "SATB", "SAB": "SAB", "SA": "SA", "SSA": "SSA", "TTBB": "TTBB"}.get(v)
    if kuerzel and (not allowed or kuerzel in allowed):
        return kuerzel
    return None


def best_file(wt: str) -> tuple[str, str] | None:
    """(filename, art) — MusicXML bevorzugt, sonst PDF."""
    media = re.findall(r"\[\[\s*Media:([^\|\]]+?)\s*[\|\]]", wt)
    xmls = [m for m in media if m.lower().endswith(MUSICXML_EXT)]
    pdfs = [m for m in media if m.lower().endswith(".pdf")]
    if xmls:
        return xmls[0], "musicxml"
    if pdfs:
        return pdfs[0], "scan_pdf"
    return None


def build(title: str, wt: str, allowed: set[str] | None) -> dict | None:
    genre = _tmpl(wt, "Genre")
    sacred = bool(genre) and genre[0].lower().startswith("sacred")
    comp = _tmpl(wt, "Composer")
    komponist = comp[0] if comp else None
    if not komponist:
        m = re.search(r"\(([^)]+)\)\s*$", title)
        komponist = m.group(1).strip() if m else None
    titel = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    voic = _tmpl(wt, "Voicing")
    voicing_str = voic[1] if len(voic) > 1 else (voic[0] if voic else "")
    lang = _tmpl(wt, "Language")
    lang0 = lang[0].strip().lower() if lang else ""
    cpdlno = "".join(_tmpl(wt, "CPDLno")[:1])
    genre_typ = genre[1] if len(genre) > 1 else ""

    tags = ["CPDL", "geistlich" if sacred else "weltlich"]
    if genre_typ:
        tags.append(genre_typ)
    if voicing_str:
        tags.append(voicing_str)
    return {
        "titel": titel[:500],
        "komponist": komponist,
        "gattung": genre_typ or ("Messe" if "mass" in (genre_typ or "").lower() else "Chorwerk"),
        "sprache": LANG_MAP.get(lang0),
        "besetzung": parse_besetzung(voicing_str, allowed),
        "tags": tags,
        "notiz": (f"Quelle: CPDL / ChoralWiki. Genre: {'/'.join(genre) or '—'}. "
                  f"Besetzung: {voicing_str or '—'}. Sprache: {lang[0] if lang else '—'}. "
                  f"CPDL {cpdlno or '—'}. {WIKI}/index.php/{urllib.parse.quote(title.replace(' ', '_'))}"),
        "_sacred": sacred,
        "_file": best_file(wt),
    }


def safe_filename(titel: str, art: str) -> str:
    base = re.sub(r"[^\w\-. ]", "_", titel, flags=re.UNICODE).strip().strip(".") or "cpdl"
    return base[:80] + (".musicxml" if art == "musicxml" else ".pdf")


# --------------------------------------------------------------------------- #
# Noten-Orga-API                                                              #
# --------------------------------------------------------------------------- #
class NotenClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "noten-orga-cpdl-import/1.0"

    def login(self, user, password, totp=""):
        cfg = self.s.get(f"{self.base}/api/auth/config", timeout=30); cfg.raise_for_status()
        if cfg.json().get("totp_pflicht") and not totp:
            totp = os.environ.get("NOTEN_TOTP", "") or input("TOTP-Code: ").strip()
        r = self.s.post(f"{self.base}/api/auth/login",
                        json={"username": user, "password": password, "totp": totp}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"Login fehlgeschlagen ({r.status_code}): {r.text[:200]}")

    def valid_besetzungen(self):
        try:
            r = self.s.get(f"{self.base}/api/besetzungen", timeout=30); r.raise_for_status()
            return {row["kuerzel"] for row in r.json()}
        except Exception:
            return set()

    def existing_keys(self):
        r = self.s.get(f"{self.base}/api/werke/export-csv", timeout=120); r.raise_for_status()
        keys = set()
        for row in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"):
            t = (row.get("titel") or "").strip().lower()
            if t:
                keys.add((t, (row.get("komponist") or "").strip().lower()))
        return keys

    def create_werk(self, payload):
        r = self.s.post(f"{self.base}/api/werke", json=payload, timeout=60); r.raise_for_status()
        au = r.json().get("ausgaben") or []
        if not au:
            raise RuntimeError("Werk ohne Ausgabe")
        return au[0]["id"]

    def attach(self, ausgabe_id, filename, data, art):
        mime = "application/vnd.recordare.musicxml+xml" if art == "musicxml" else "application/pdf"
        r = self.s.post(f"{self.base}/api/dateien",
                        data={"ausgabe_id": ausgabe_id, "art": art},
                        files={"file": (filename, data, mime)}, timeout=180)
        r.raise_for_status()
        return r.json()


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="CPDL/ChoralWiki importieren")
    ap.add_argument("--base-url", default=os.environ.get("NOTEN_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--user", default=os.environ.get("NOTEN_USER"))
    ap.add_argument("--password", default=os.environ.get("NOTEN_PASS"))
    ap.add_argument("--category", default="Masses", help="CPDL-Kategorie (z.B. Masses, Motets, Anthems)")
    ap.add_argument("--only-sacred", action="store_true", help="nur Werke mit Genre Sacred")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.4, help="Pause zwischen Downloads (höflich zu CPDL)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Hole Kategorie '{args.category}' …")
    titles = category_titles(args.category)
    print(f"-> {len(titles)} Seiten.")
    if args.limit:
        titles = titles[: args.limit * 3]  # Puffer für Übersprungene beim Limit

    client = None
    existing: set = set()
    allowed: set = set()
    if not args.dry_run:
        if not args.user:
            args.user = input("Benutzer: ").strip()
        if not args.password:
            args.password = getpass("Passwort: ")
        client = NotenClient(args.base_url)
        client.login(args.user, args.password, os.environ.get("NOTEN_TOTP", ""))
        existing = client.existing_keys()
        allowed = client.valid_besetzungen()
        print(f"[i] {len(existing)} bestehende Werke; {len(allowed)} Besetzungs-Kürzel.\n")

    created = skipped = nofile = failed = filtered = 0
    wt_map = wikitexts(titles)
    for title in titles:
        if args.limit and created >= args.limit:
            break
        wt = wt_map.get(title)
        if not wt:
            continue
        meta = build(title, wt, allowed)
        if not meta or not meta["titel"]:
            continue
        if args.only_sacred and not meta["_sacred"]:
            filtered += 1
            continue
        key = (meta["titel"].strip().lower(), (meta["komponist"] or "").strip().lower())
        if key in existing:
            skipped += 1
            continue
        fileinfo = meta.pop("_file")
        meta.pop("_sacred")
        if not fileinfo:
            nofile += 1
            continue

        if args.dry_run:
            print(f"  + {meta['titel'][:42]:42} | {(meta['komponist'] or '—')[:22]:22} | "
                  f"{meta['besetzung'] or '—':5} | {meta['sprache'] or '—':3} | {fileinfo[1]}:{fileinfo[0][:24]}")
            existing.add(key)
            created += 1
            continue

        fn, art = fileinfo
        try:
            data = download(cpdl_file_url(fn))
            if fn.lower().endswith(".mxl"):
                data = mxl_to_plain(data)
                art = "musicxml"
            ausgabe_id = client.create_werk(meta)
            r = client.attach(ausgabe_id, safe_filename(meta["titel"], art), data, art)
            existing.add(key)
            created += 1
            if created % 25 == 0:
                print(f"  … {created} angelegt (zuletzt: {meta['titel'][:38]})")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            msg = str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                msg = f"{exc.response.status_code}: {exc.response.text[:120]}"
            print(f"  ! FEHLER {meta['titel'][:38]}: {msg}")
        time.sleep(args.sleep)

    print(f"\nFertig. angelegt={created}  übersprungen={skipped}  ohne_datei={nofile}  "
          f"gefiltert={filtered}  fehler={failed}" + ("  (Trockenlauf)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
