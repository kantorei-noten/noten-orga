from app.chordpro import transponiere


def test_einzelakkorde():
    assert transponiere("[C]", 2) == "[D]"
    assert transponiere("[Am]", 3) == "[Cm]"
    assert transponiere("[F#m7]", 2) == "[G#m7]"
    assert transponiere("[Bb]", 2) == "[C]"


def test_bass_note():
    assert transponiere("[G/B]", 2) == "[A/C#]"


def test_oktave_identisch():
    assert transponiere("[C]", 12 % 12) == "[C]"
    assert transponiere("[Dm7]", 0) == "[Dm7]"


def test_suffixe_und_text_bleiben():
    assert transponiere("Amazing [C]grace [G7]sound", 2) == "Amazing [D]grace [A7]sound"
    assert transponiere("[Cmaj7]", 2) == "[Dmaj7]"


def test_abschnittsmarke_bleibt():
    assert transponiere("[Chorus]", 2) == "[Chorus]"
