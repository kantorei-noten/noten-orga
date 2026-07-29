"""WebP-Vorschau aus der ersten PDF-Seite — bevorzugt im isolierten Subprozess."""
from __future__ import annotations

from pathlib import Path


def render_pdf_thumbnail(data: bytes, out_path: Path, settings) -> None:
    """Rendert die erste Seite als WebP. Nicht vertrauenswürdiges PDF wird im
    isolierten Subprozess gerastert (Crash-/Ressourcen-Schutz)."""
    if getattr(settings, "sandbox_enabled", True):
        from .sandbox import run

        run(["thumb", str(out_path), str(settings.thumb_max_px)], data, settings)
        return

    # Inline-Fallback (sandbox_enabled=False)
    import pymupdf
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        page = doc[0]
        longest = max(page.rect.width, page.rect.height) or 1
        zoom = min(settings.thumb_max_px / longest, 4.0)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "WEBP", quality=80, method=4)
