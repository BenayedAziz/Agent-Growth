"""Comptes, mots de passe et sessions.

Tout en bibliothèque standard : scrypt pour les mots de passe, HMAC pour signer
les sessions. Pas de dépendance de plus pour un problème que Python résout.

Deux rôles, et la règle qui les sépare est appliquée côté serveur, jamais
seulement à l'affichage :

- **consultant** : voit et pilote toutes les marques ;
- **client** : voit uniquement les marques qui lui sont rattachées, ne déclenche
  aucune action, ne valide rien.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass

from . import store

SESSION_COOKIE = "ag_session"
SESSION_TTL_SECONDS = 14 * 24 * 3600

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: str
    role: str

    @property
    def is_consultant(self) -> bool:
        return self.role == "consultant"


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #

def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Le mot de passe doit faire au moins 10 caractères.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


# --------------------------------------------------------------------------- #
# Comptes
# --------------------------------------------------------------------------- #

def create_user(conn: sqlite3.Connection, *, email: str, password: str, role: str,
                name: str = "", brand_ids: list[int] | None = None) -> int:
    if role not in ("consultant", "client"):
        raise ValueError("Rôle inconnu.")
    if role == "client" and not brand_ids:
        raise ValueError("Un compte client doit être rattaché à au moins une marque.")
    cur = conn.execute(
        "INSERT INTO app_user (email, name, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (email.strip().lower(), name.strip(), role, hash_password(password), store.now()),
    )
    user_id = int(cur.lastrowid)
    for brand_id in brand_ids or []:
        conn.execute("INSERT OR IGNORE INTO user_brand (user_id, brand_id) VALUES (?, ?)",
                     (user_id, brand_id))
    store.log(conn, actor="humain", action=f"compte {role} créé", rationale=email)
    conn.commit()
    return user_id


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> User | None:
    row = conn.execute("SELECT * FROM app_user WHERE email = ?", (email.strip().lower(),)).fetchone()
    if row is None:
        # On calcule quand même un hachage : la durée de réponse ne doit pas
        # révéler si l'adresse existe.
        verify_password(password, "scrypt$" + "00" * 16 + "$" + "00" * 32)
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    conn.execute("UPDATE app_user SET last_login_at = ? WHERE id = ?", (store.now(), row["id"]))
    conn.commit()
    return User(int(row["id"]), row["email"], row["name"], row["role"])


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()
    return User(int(row["id"]), row["email"], row["name"], row["role"]) if row else None


def count_users(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM app_user").fetchone()["n"])


def visible_brand_ids(conn: sqlite3.Connection, user: User) -> set[int] | None:
    """Les marques qu'un compte peut voir. `None` = toutes (consultant)."""
    if user.is_consultant:
        return None
    rows = conn.execute("SELECT brand_id FROM user_brand WHERE user_id = ?", (user.id,)).fetchall()
    return {int(r["brand_id"]) for r in rows}


def can_see(conn: sqlite3.Connection, user: User, brand_id: int) -> bool:
    allowed = visible_brand_ids(conn, user)
    return allowed is None or brand_id in allowed


# --------------------------------------------------------------------------- #
# Sessions signées
# --------------------------------------------------------------------------- #

def secret_key() -> bytes:
    """La clé qui signe les sessions. En production, `AG_SECRET_KEY` est
    obligatoire ; en local, une clé éphémère suffit (les sessions tombent au
    redémarrage, ce qui est sans gravité)."""
    global _EPHEMERAL
    value = os.environ.get("AG_SECRET_KEY", "")
    if value:
        return value.encode("utf-8")
    if _EPHEMERAL is None:
        _EPHEMERAL = secrets.token_bytes(32)
    return _EPHEMERAL


_EPHEMERAL: bytes | None = None


def make_session(user: User, *, now: float | None = None, key: bytes | None = None) -> str:
    payload = {"u": user.id, "r": user.role, "exp": int((now or time.time()) + SESSION_TTL_SECONDS)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(key or secret_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def read_session(token: str, *, now: float | None = None, key: bytes | None = None) -> int | None:
    """Renvoie l'identifiant du compte si la session est intacte et valide."""
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    expected = hmac.new(key or secret_key(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < (now or time.time()):
        return None
    return int(payload["u"])
