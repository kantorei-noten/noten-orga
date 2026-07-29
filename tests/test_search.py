import pyotp

from app.auth import service as auth_service


async def _login(client, conn, name="such", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": name, "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 200


async def _mkwerk(client, **payload):
    r = await client.post("/api/werke", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_fulltext_and_unaccent(client, conn):
    await _login(client, conn)
    await _mkwerk(client, titel="Nun danket alle Gott (Suche)", komponist="Johann Crüger")
    r = await client.get("/api/suche", params={"q": "danket"})
    assert any(w["titel"].startswith("Nun danket") for w in r.json()["ergebnisse"])
    # akzentunempfindlich: Crüger -> cruger
    r = await client.get("/api/suche", params={"q": "cruger"})
    assert any("Crüger" in (w["komponist"] or "") for w in r.json()["ergebnisse"])


async def test_search_by_gl_number(client, conn):
    await _login(client, conn)
    await _mkwerk(
        client, titel="Großer Gott wir loben dich", gesangbuch=[{"buch": "GL", "nummer": "380"}]
    )
    r = await client.get("/api/suche", params={"q": "380"})
    assert any(w["titel"].startswith("Großer Gott") for w in r.json()["ergebnisse"])


async def test_fuzzy_typo(client, conn):
    await _login(client, conn)
    await _mkwerk(client, titel="Geh aus mein Herz und suche Freud")
    r = await client.get(
        "/api/suche", params={"q": "Geh aus mein Herz und suche Freid"}  # Tippfehler
    )
    assert any(w["titel"].startswith("Geh aus mein Herz") for w in r.json()["ergebnisse"])


async def test_facet_filter_and_counts(client, conn):
    await _login(client, conn)
    g = "TestGattungXYZ"
    await _mkwerk(client, titel="Facet A", gattung=g)
    await _mkwerk(client, titel="Facet B", gattung=g)
    body = (await client.get("/api/suche", params={"gattung": g})).json()
    assert body["total"] == 2
    assert all(w["gattung"] == g for w in body["ergebnisse"])
    gz = {f["wert"]: f["anzahl"] for f in body["facetten"]["gattung"]}
    assert gz.get(g) == 2


async def test_facet_besetzung(client, conn):
    await _login(client, conn)
    await _mkwerk(client, titel="Besetzungstest", besetzung="TTBB")
    body = (await client.get("/api/suche", params={"besetzung": "TTBB"})).json()
    assert any(w["titel"] == "Besetzungstest" for w in body["ergebnisse"])
    bz = {f["wert"]: f["anzahl"] for f in body["facetten"]["besetzung"]}
    assert bz.get("TTBB", 0) >= 1


async def test_anlass_rekursiv(client, conn):
    await _login(client, conn)
    cur = await conn.execute("insert into anlass (name) values ('TestEltern') returning id")
    parent = (await cur.fetchone())["id"]
    cur = await conn.execute(
        "insert into anlass (name, parent_id) values ('TestKind', %s) returning id", (parent,)
    )
    child = (await cur.fetchone())["id"]
    await _mkwerk(client, titel="Kind-Anlass-Werk", anlass_ids=[str(child)])

    # direkt am Kind: gefunden
    r = await client.get("/api/suche", params={"anlass_id": str(child)})
    assert any(w["titel"] == "Kind-Anlass-Werk" for w in r.json()["ergebnisse"])
    # am Eltern ohne Rekursion: NICHT gefunden
    r = await client.get("/api/suche", params={"anlass_id": str(parent)})
    assert not any(w["titel"] == "Kind-Anlass-Werk" for w in r.json()["ergebnisse"])
    # am Eltern MIT Rekursion: gefunden
    r = await client.get("/api/suche", params={"anlass_id": str(parent), "anlass_rekursiv": "true"})
    assert any(w["titel"] == "Kind-Anlass-Werk" for w in r.json()["ergebnisse"])


async def test_search_requires_auth(client):
    assert (await client.get("/api/suche", params={"q": "test"})).status_code == 401
