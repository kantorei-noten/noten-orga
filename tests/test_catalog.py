import pyotp

from app.auth import service as auth_service


async def _login(client, conn, name="kat", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": name, "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 200


async def test_ausgabe_rechtestatus(client, conn):
    await _login(client, conn, name="rechtekat", rolle="admin")
    werk = (await client.post("/api/werke", json={"titel": "Motette"})).json()
    aus = werk["ausgaben"][0]
    assert aus["rechtestatus"] == "unbekannt"
    # einzeln setzen
    r = await client.patch(f"/api/ausgaben/{aus['id']}", json={"rechtestatus": "public_domain"})
    assert r.status_code == 200 and r.json()["rechtestatus"] == "public_domain"
    # ungültiger Status -> 422
    assert (await client.patch(f"/api/ausgaben/{aus['id']}", json={"rechtestatus": "quatsch"})).status_code == 422
    # Masse: alle 'unbekannt' -> 'lizenziert'
    r = await client.post("/api/ausgaben/rechtestatus-masse", json={"von": "unbekannt", "auf": "lizenziert"})
    assert r.status_code == 200 and "geaendert" in r.json()


async def test_ausgabe_rechte_rollen(client, conn):
    # Masse ist Admin-only
    await _login(client, conn, name="rechtemus", rolle="musiker")
    assert (await client.post("/api/ausgaben/rechtestatus-masse", json={"von": "unbekannt", "auf": "public_domain"})).status_code == 403
    # Einzeln ist gast verboten
    await _login(client, conn, name="rechtegast", rolle="gast")
    fake = "00000000-0000-0000-0000-000000000000"
    assert (await client.patch(f"/api/ausgaben/{fake}", json={"rechtestatus": "public_domain"})).status_code == 403


async def test_werk_baum(client, conn):
    await _login(client, conn, name="baumkat")
    await client.post("/api/werke", json={"titel": "Werk A", "komponist": "Bach", "gattung": "Choral"})
    await client.post("/api/werke", json={"titel": "Werk B", "komponist": "Bach", "gattung": "Motette"})
    await client.post("/api/werke", json={"titel": "Werk C", "komponist": "Schütz", "gattung": "Motette"})

    # nach Komponist: Bach hat 2 Werke
    baum = (await client.get("/api/werke/baum?feld=komponist")).json()
    bach = next(g for g in baum if g["gruppe"] == "Bach")
    assert bach["anzahl"] == 2
    assert {w["titel"] for w in bach["werke"]} == {"Werk A", "Werk B"}

    # nach Gattung: Motette hat mind. 2 (B, C)
    baum = (await client.get("/api/werke/baum?feld=gattung")).json()
    motette = next(g for g in baum if g["gruppe"] == "Motette")
    assert {"Werk B", "Werk C"} <= {w["titel"] for w in motette["werke"]}

    # ungültiges Feld -> 422
    assert (await client.get("/api/werke/baum?feld=quatsch")).status_code == 422


async def test_create_and_get_werk(client, conn):
    await _login(client, conn)
    payload = {
        "titel": "Nun danket alle Gott",
        "komponist": "Johann Crüger",
        "gattung": "Choral",
        "besetzung": "SATB",
        "tonart": "D-Dur",
        "gesangbuch": [{"buch": "GL", "nummer": "405"}, {"buch": "EG", "nummer": "321"}],
        "tags": ["Dank", "Choral"],
    }
    r = await client.post("/api/werke", json=payload)
    assert r.status_code == 201, r.text
    werk = r.json()
    assert werk["titel"] == "Nun danket alle Gott"
    assert len(werk["ausgaben"]) == 1  # Default-Ausgabe automatisch erzeugt
    assert {g["buch"] + " " + g["nummer"] for g in werk["gesangbuch"]} == {"GL 405", "EG 321"}
    assert set(werk["tags"]) == {"Dank", "Choral"}

    r2 = await client.get(f"/api/werke/{werk['id']}")
    assert r2.status_code == 200
    assert r2.json()["komponist"] == "Johann Crüger"


async def test_list_update_delete(client, conn):
    await _login(client, conn)
    wid = (await client.post("/api/werke", json={"titel": "Testlied"})).json()["id"]
    assert any(w["id"] == wid for w in (await client.get("/api/werke")).json())
    r = await client.patch(f"/api/werke/{wid}", json={"komponist": "Anonymus"})
    assert r.json()["komponist"] == "Anonymus"
    assert (await client.delete(f"/api/werke/{wid}")).status_code == 204
    assert (await client.get(f"/api/werke/{wid}")).status_code == 404


async def test_duplicate_warning(client, conn):
    await _login(client, conn)
    await client.post("/api/werke", json={"titel": "Lobe den Herren, den mächtigen König"})
    r = await client.get(
        "/api/werke/aehnlich", params={"titel": "Lobe den Herren, den mächtigen König"}
    )
    assert r.status_code == 200
    assert any(w["titel"].startswith("Lobe den Herren") for w in r.json())


async def test_csv_export_import(client, conn):
    await _login(client, conn)
    await client.post("/api/werke", json={"titel": "Exportlied", "komponist": "X"})
    r = await client.get("/api/werke/export-csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Exportlied" in r.text

    csv_text = "titel;komponist;GL;tags\r\nExportlied;X;;\r\nImportlied;Y;100;Advent\r\n"
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    r = await client.post("/api/werke/import-csv", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["angelegt"] == 1
    assert body["uebersprungen"] == 1


async def test_batch_tag(client, conn):
    await _login(client, conn)
    w1 = (await client.post("/api/werke", json={"titel": "B1"})).json()["id"]
    w2 = (await client.post("/api/werke", json={"titel": "B2"})).json()["id"]
    r = await client.post("/api/werke/batch/tags", json={"werk_ids": [w1, w2], "tag": "Ostern"})
    assert r.json()["gesetzt"] == 2
    assert "Ostern" in (await client.get(f"/api/werke/{w1}")).json()["tags"]


async def test_refs_and_autocomplete(client, conn):
    await _login(client, conn)
    assert len((await client.get("/api/besetzungen")).json()) >= 5
    assert len((await client.get("/api/anlaesse")).json()) >= 10
    await client.post("/api/werke", json={"titel": "K1", "komponist": "Bachmann, Felix"})
    r = await client.get("/api/komponisten", params={"q": "Bachm"})
    assert any("Bachm" in k for k in r.json())


async def test_create_requires_role(client, conn):
    await _login(client, conn, name="gast2", rolle="gast")
    assert (await client.post("/api/werke", json={"titel": "Verboten"})).status_code == 403
