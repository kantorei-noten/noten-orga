"""ChordPro-Generierung: Eigen-Analyzer + Auto-Dispatch (music21 wenn installiert)."""
from app.catalog import chordgen

# Minimaler 2-stimmiger Satz (Melodie mit Text + Bass), C-Dur (fifths=0).
MXML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Melodie</part-name></score-part>
    <score-part id="P2"><part-name>Bass</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions><key><fifths>0</fifths></key></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><lyric><syllabic>single</syllabic><text>Lob</text></lyric></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><lyric><syllabic>single</syllabic><text>sei</text></lyric></note>
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><lyric><syllabic>single</syllabic><text>dem</text></lyric></note>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><lyric><syllabic>single</syllabic><text>Herrn.</text></lyric></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes><divisions>1</divisions></attributes>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note>
      <note><pitch><step>G</step><octave>2</octave></pitch><duration>1</duration></note>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note>
    </measure>
  </part>
</score-partwise>
"""


def _mxml(tmp_path):
    p = tmp_path / "werk.musicxml"
    p.write_text(MXML, encoding="utf-8")
    return str(p)


def test_basis_analyzer_erzeugt_chordpro(tmp_path):
    text = chordgen.chordpro_aus_musicxml(_mxml(tmp_path), "Testlied")
    assert "{title: Testlied}" in text
    assert "{key: C}" in text  # fifths=0 -> C-Dur
    assert "Lob" in text and "Herrn" in text


def test_chordpro_auto_waehlt_engine(tmp_path):
    """Dispatch: music21 wenn installiert, sonst Eigen-Analyzer — beides valider Text."""
    text, engine = chordgen.chordpro_auto(_mxml(tmp_path), "Testlied")
    assert "Lob" in text and "Herrn" in text
    if chordgen.music21_verfuegbar():
        assert engine == "music21"
    else:
        assert engine == "basis"


def test_chordpro_auto_leerer_pfad_faellt_sauber_zurueck():
    text, engine = chordgen.chordpro_auto("/gibt/es/nicht.musicxml", None)
    assert text == "" and engine == "basis"


def test_music21_worker_isoliert(tmp_path):
    """Der Sandbox-Worker (music21) als eigener Subprozess — MusicXML über stdin,
    ChordPro als JSON. Läuft nur, wenn music21 installiert ist (sonst skip)."""
    import importlib.util
    import json
    import subprocess
    import sys

    if importlib.util.find_spec("music21") is None:
        import pytest

        pytest.skip("music21 nicht installiert — Worker-Pfad wird auf Prod/Worker getestet")

    proc = subprocess.run(
        [sys.executable, "-m", "app.ingest.music21_worker", "chordpro", "Testlied", "400"],
        input=MXML.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    out = json.loads(proc.stdout.decode())
    assert "Lob" in out["text"] and "Herrn" in out["text"]
