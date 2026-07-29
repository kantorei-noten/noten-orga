"""Sicherheits-Primitive: Passwort-Hashing (Argon2id), TOTP (mit Replay-Schutz), Session-Token."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_ph = PasswordHasher()  # Argon2id mit sicheren Defaults


# --- Passwörter ---
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# Fester Dummy-Hash: gegen ihn wird bei UNBEKANNTEM Benutzer verifiziert, damit die
# Login-Antwortzeit gleich lang ist wie bei existierendem Konto (gegen Enumeration per Timing).
DUMMY_HASH = _ph.hash("timing-equalizer-not-a-real-secret")


def needs_rehash(stored_hash: str) -> bool:
    return _ph.check_needs_rehash(stored_hash)


# --- TOTP (Pflicht-2FA) ---
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str, issuer: str = "Kantorei") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str, last_step: int, valid_window: int = 1) -> tuple[bool, int]:
    """Prüft einen TOTP-Code. Gibt (ok, neuer_last_step) zurück.

    Replay-Schutz: ein bereits benutzter Zeitschritt (<= last_step) wird abgelehnt.
    """
    if not code or not code.strip().isdigit():
        return False, last_step
    code = code.strip()
    totp = pyotp.TOTP(secret)
    current = int(time.time()) // 30
    for offset in range(-valid_window, valid_window + 1):
        step = current + offset
        if hmac.compare_digest(totp.at(step * 30), code):
            if step <= last_step:  # Wiederverwendung → Replay
                return False, last_step
            return True, step
    return False, last_step


# --- Session-Token (opaque; in der DB nur als Hash) ---
def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
