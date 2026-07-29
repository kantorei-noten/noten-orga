import pyotp

from app.auth import service
from app.config import Settings


async def test_totp_optional_im_demomodus(conn):
    await conn.execute("delete from benutzer where benutzername = %s", ("nototp",))
    await service.create_user(conn, "nototp", "Geheim1234!", "musiker")
    # 2FA aus -> Login nur mit Passwort (leerer Code) klappt
    user, err = await service.authenticate(conn, "nototp", "Geheim1234!", "", Settings(totp_pflicht=False))
    assert user is not None and err is None
    # 2FA an -> leerer Code wird abgelehnt
    user, err = await service.authenticate(conn, "nototp", "Geheim1234!", "", Settings(totp_pflicht=True))
    assert user is None and err == "invalid"


async def _mk_user(conn, name, pw="Geheim1234!", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    return await service.create_user(conn, name, pw, rolle)


async def test_login_success_and_me(client, conn):
    u = await _mk_user(conn, "tester")
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": "tester", "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 200, r.text
    assert r.json()["rolle"] == "musiker"

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["benutzername"] == "tester"


async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_wrong_password_rejected(client, conn):
    u = await _mk_user(conn, "t2")
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": "t2", "password": "FALSCH", "totp": code},
    )
    assert r.status_code == 401


async def test_wrong_totp_rejected(client, conn):
    await _mk_user(conn, "t3")
    r = await client.post(
        "/api/auth/login",
        json={"username": "t3", "password": "Geheim1234!", "totp": "000000"},
    )
    assert r.status_code == 401


async def test_totp_replay_rejected(client, conn):
    u = await _mk_user(conn, "t4")
    code = pyotp.TOTP(u["totp_secret"]).now()
    r1 = await client.post(
        "/api/auth/login",
        json={"username": "t4", "password": "Geheim1234!", "totp": code},
    )
    assert r1.status_code == 200
    await client.post("/api/auth/logout")
    # gleicher Code (gleicher Zeitschritt) → Replay muss scheitern
    r2 = await client.post(
        "/api/auth/login",
        json={"username": "t4", "password": "Geheim1234!", "totp": code},
    )
    assert r2.status_code == 401


async def test_lockout_after_failures(client, conn):
    u = await _mk_user(conn, "t5")
    for _ in range(5):
        await client.post(
            "/api/auth/login",
            json={"username": "t5", "password": "FALSCH", "totp": "000000"},
        )
    # trotz korrekter Daten gesperrt — aber EINHEITLICHER 401 (keine Enumeration über den Status)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": "t5", "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 401


async def test_unbekannter_nutzer_gleicher_status(client, conn):
    # Unbekannter Benutzer liefert denselben 401 wie falsches Passwort (Anti-Enumeration)
    r = await client.post(
        "/api/auth/login",
        json={"username": "gibtsganzsichernicht", "password": "x", "totp": "000000"},
    )
    assert r.status_code == 401


def test_rate_limit_helper():
    from app.routers.auth import _LOGIN_MAX, _client_ip, _login_hits, _rate_ok

    _login_hits.clear()
    ip = "203.0.113.7"
    ok = [_rate_ok(ip) for _ in range(_LOGIN_MAX + 3)]
    assert all(ok[:_LOGIN_MAX]) and not ok[_LOGIN_MAX]  # erst nach dem Limit gesperrt

    class _Req:
        def __init__(self, xff=None, peer=None):
            self.headers = {"x-forwarded-for": xff} if xff else {}
            self.client = type("C", (), {"host": peer})() if peer else None

    # Der Proxy hängt an: '<gefälscht>, <echte IP>' — es zählt der letzte Eintrag
    assert _client_ip(_Req("198.51.100.9, 10.0.0.1", "172.18.0.5")) == "10.0.0.1"
    # Ohne Proxy davor wird der Header ignoriert (sonst wäre das Limit fälschbar)
    assert _client_ip(_Req("198.51.100.9", "203.0.113.200")) == "203.0.113.200"
    # Kein Header: die Peer-Adresse
    assert _client_ip(_Req(peer="203.0.113.7")) == "203.0.113.7"


async def test_logout_clears_session(client, conn):
    u = await _mk_user(conn, "t6")
    code = pyotp.TOTP(u["totp_secret"]).now()
    await client.post(
        "/api/auth/login",
        json={"username": "t6", "password": "Geheim1234!", "totp": code},
    )
    assert (await client.get("/api/auth/me")).status_code == 200
    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401
