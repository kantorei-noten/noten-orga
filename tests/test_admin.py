import pyotp

from app.auth import service as auth_service


async def _mk(conn, name, rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    return await auth_service.create_user(conn, name, "Geheim1234!", rolle)


async def _login(client, conn, name, rolle="musiker"):
    u = await _mk(conn, name, rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login", json={"username": name, "password": "Geheim1234!", "totp": code}
    )
    assert r.status_code == 200
    return u


async def test_change_password(client, conn):
    await _login(client, conn, "pwuser")
    r = await client.post(
        "/api/auth/passwort",
        json={"altes_passwort": "Geheim1234!", "neues_passwort": "NeuesGeheim99"},
    )
    assert r.status_code == 200
    # Altes Passwort wird jetzt abgelehnt
    r = await client.post(
        "/api/auth/passwort",
        json={"altes_passwort": "Geheim1234!", "neues_passwort": "NochNeuer1234"},
    )
    assert r.status_code == 400


async def test_password_min_length(client, conn):
    await _login(client, conn, "pwuser2")
    r = await client.post(
        "/api/auth/passwort", json={"altes_passwort": "Geheim1234!", "neues_passwort": "kurz"}
    )
    assert r.status_code == 422


async def test_admin_create_and_list_user(client, conn):
    await _login(client, conn, "chef", rolle="admin")
    await conn.execute("delete from benutzer where benutzername = %s", ("neuer_saenger",))
    r = await client.post(
        "/api/benutzer",
        json={"benutzername": "neuer_saenger", "passwort": "Geheim12345", "rolle": "chor"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rolle"] == "chor"
    assert "otpauth://" in body["totp_uri"]

    liste = (await client.get("/api/benutzer")).json()
    assert any(x["benutzername"] == "neuer_saenger" for x in liste)

    # Duplikat -> 409
    r = await client.post(
        "/api/benutzer",
        json={"benutzername": "neuer_saenger", "passwort": "Geheim12345", "rolle": "chor"},
    )
    assert r.status_code == 409


async def test_admin_edit_user(client, conn):
    await _login(client, conn, "chef_e", rolle="admin")
    target = await _mk(conn, "ziel", rolle="chor")
    tid = str(target["id"])

    # Benutzername ändern
    r = await client.patch(f"/api/benutzer/{tid}", json={"benutzername": "ziel_neu"})
    assert r.status_code == 200, r.text
    assert r.json()["benutzername"] == "ziel_neu"

    # Passwort setzen (Admin, ohne altes) → 204
    r = await client.post(f"/api/benutzer/{tid}/passwort", json={"passwort": "GanzNeu12345"})
    assert r.status_code == 204

    # Passwort zu kurz → 422
    r = await client.post(f"/api/benutzer/{tid}/passwort", json={"passwort": "kurz"})
    assert r.status_code == 422

    # 2FA aus
    r = await client.post(f"/api/benutzer/{tid}/2fa", json={"aktiv": False})
    assert r.status_code == 200 and r.json()["totp_aktiviert"] is False
    # 2FA an → neue Enrollment-URI
    r = await client.post(f"/api/benutzer/{tid}/2fa", json={"aktiv": True})
    assert r.status_code == 200 and r.json()["totp_aktiviert"] is True
    assert "otpauth://" in r.json()["totp_uri"]

    # Liste enthält totp_aktiviert
    liste = (await client.get("/api/benutzer")).json()
    assert any(x["benutzername"] == "ziel_neu" and x["totp_aktiviert"] is True for x in liste)


async def test_admin_delete_user(client, conn):
    admin = await _login(client, conn, "chef_d", rolle="admin")
    # Sich selbst löschen → 400
    r = await client.delete(f"/api/benutzer/{admin['id']}")
    assert r.status_code == 400
    # Anderen (Nicht-Admin) löschen → 204, danach weg
    target = await _mk(conn, "weg", rolle="chor")
    r = await client.delete(f"/api/benutzer/{target['id']}")
    assert r.status_code == 204
    assert not any(x["benutzername"] == "weg" for x in (await client.get("/api/benutzer")).json())


async def test_admin_endpoints_require_admin(client, conn):
    await _login(client, conn, "nur_chor", rolle="chor")
    target = await _mk(conn, "opfer", rolle="chor")
    tid = str(target["id"])
    assert (await client.post(f"/api/benutzer/{tid}/passwort", json={"passwort": "Geheim12345"})).status_code == 403
    assert (await client.post(f"/api/benutzer/{tid}/2fa", json={"aktiv": False})).status_code == 403
    assert (await client.delete(f"/api/benutzer/{tid}")).status_code == 403


async def test_backup_config(client, conn):
    await _login(client, conn, "chef_bk", rolle="admin")
    cfg = (await client.get("/api/backup/config")).json()
    assert "ziel" in cfg and "uhrzeit" in cfg and "keep_daily" in cfg
    # gültig speichern
    r = await client.put(
        "/api/backup/config",
        json={"ziel": "/var/backups/noten/repo", "keep_daily": 10, "keep_weekly": 4, "keep_monthly": 6, "uhrzeit": "02:15"},
    )
    assert r.status_code == 200 and r.json()["keep_daily"] == 10 and r.json()["uhrzeit"] == "02:15"
    assert (await client.get("/api/backup/config")).json()["uhrzeit"] == "02:15"
    # ungültige Uhrzeit -> 400
    assert (
        await client.put("/api/backup/config", json={"ziel": "/var/backups/noten/repo", "keep_daily": 1, "keep_weekly": 1, "keep_monthly": 1, "uhrzeit": "99:99"})
    ).status_code == 400
    # relatives Ziel -> 400
    assert (
        await client.put("/api/backup/config", json={"ziel": "nicht/absolut", "keep_daily": 1, "keep_weekly": 1, "keep_monthly": 1, "uhrzeit": "03:00"})
    ).status_code == 400


async def test_backup_config_requires_admin(client, conn):
    await _login(client, conn, "bk_musiker", rolle="musiker")
    assert (await client.get("/api/backup/config")).status_code == 403


async def test_job_flow(client, conn):
    await conn.execute("delete from job")
    await _login(client, conn, "chef_job", rolle="admin")
    r = await client.post("/api/jobs", json={"typ": "chordpro_music21", "params": {}})
    assert r.status_code == 201 and r.json()["status"] == "offen"
    jid = r.json()["id"]
    # gleicher Typ läuft schon -> 409
    assert (await client.post("/api/jobs", json={"typ": "chordpro_music21"})).status_code == 409
    # unbekannter Typ -> 400
    assert (await client.post("/api/jobs", json={"typ": "quatsch"})).status_code == 400
    # Status + Liste
    assert (await client.get(f"/api/jobs/{jid}")).json()["typ"] == "chordpro_music21"
    assert any(x["id"] == jid for x in (await client.get("/api/jobs")).json())
    # abbrechen
    assert (await client.post(f"/api/jobs/{jid}/abbrechen")).status_code == 204
    assert (await client.get(f"/api/jobs/{jid}")).json()["status"] == "abgebrochen"


async def test_jobs_requires_admin(client, conn):
    await _login(client, conn, "job_musiker", rolle="musiker")
    assert (await client.get("/api/jobs")).status_code == 403
    assert (await client.post("/api/jobs", json={"typ": "chordpro_music21"})).status_code == 403


async def test_cli_create_admin(conn):
    from app import cli

    await conn.execute("delete from benutzer where benutzername = %s", ("clidmin",))
    assert await cli._create_admin("clidmin", "Geheim1234!", None) == 0
    cur = await conn.execute("select rolle from benutzer where benutzername = %s", ("clidmin",))
    assert (await cur.fetchone())["rolle"] == "admin"
    # doppelt -> 1 (kein Überschreiben)
    assert await cli._create_admin("clidmin", "Geheim1234!", None) == 1


async def test_benutzer_requires_admin(client, conn):
    await _login(client, conn, "nur_musiker", rolle="musiker")
    r = await client.post(
        "/api/benutzer", json={"benutzername": "x", "passwort": "Geheim12345"}
    )
    assert r.status_code == 403
