"""Isolierter Worker für PyMuPDF-Operationen auf NICHT vertrauenswürdigen PDFs.

Läuft als EIGENER Prozess (Ressourcenlimits + Timeout setzt der Aufrufer
`app.ingest.sandbox`), damit ein bösartiges/kaputtes PDF weder den API-Prozess
crasht (Segfault in MuPDF) noch ihn mit RAM/CPU/Zeit erschöpft (Dekompressionsbombe,
Endlosschleife). PDF-Bytes kommen über stdin, das Ergebnis als JSON auf stdout.
Importiert bewusst KEINEN App-Code — nur pymupdf/Pillow.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    data = sys.stdin.buffer.read()
    import pymupdf

    if op == "pages":
        doc = pymupdf.open(stream=data, filetype="pdf")
        n = int(doc.page_count)
        doc.close()
        sys.stdout.write(json.dumps({"pages": n}))
        return 0

    if op == "textlines":
        # Text-Zeilen der ersten Seiten (nur Spans mit hohem Buchstabenanteil = Text-Font,
        # nicht Musik-Glyphen). Für die Liedtext-Extraktion — hält PyMuPDF im Subprozess.
        max_seiten = int(sys.argv[2]) if len(sys.argv) > 2 else 8
        doc = pymupdf.open(stream=data, filetype="pdf")
        lines: list[str] = []
        for i in range(min(max_seiten, doc.page_count)):
            for block in doc[i].get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    spantext = " ".join(
                        s["text"]
                        for s in line.get("spans", [])
                        if (sum(c.isalpha() for c in s["text"]) / max(1, len(s["text"]))) >= 0.45
                    )
                    if spantext.strip():
                        lines.append(spantext)
        doc.close()
        sys.stdout.write(json.dumps({"lines": lines}))
        return 0

    if op == "thumb":
        out_path, max_px = sys.argv[2], int(sys.argv[3])
        import os

        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 64_000_000
        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            page = doc[0]
            longest = max(page.rect.width, page.rect.height) or 1
            zoom = min(max_px / longest, 4.0)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        finally:
            doc.close()
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        img.save(out_path, "WEBP", quality=80, method=4)
        sys.stdout.write(json.dumps({"ok": True}))
        return 0

    sys.stderr.write("unknown op\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
