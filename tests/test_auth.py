"""Comptes, rôles et sessions. La séparation consultant / client est appliquée
côté serveur : c'est elle qui empêche un client de voir la marque d'un autre."""

import pytest

from agent_growth import auth, store

KEY = b"cle-de-test"


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def brands(conn):
    a = store.add_brand(conn, slug="egyptours", name="Egyptours", url="https://egyptours.fr")
    b = store.add_brand(conn, slug="oria", name="Oria", url="https://oria.fr")
    return a, b


def test_password_is_never_stored_in_clear(conn):
    auth.create_user(conn, email="a@x.fr", password="un-mot-de-passe-long", role="consultant")
    stored = conn.execute("SELECT password_hash FROM app_user").fetchone()["password_hash"]
    assert "un-mot-de-passe-long" not in stored
    assert stored.startswith("scrypt$")


def test_short_passwords_are_refused(conn):
    with pytest.raises(ValueError, match="10 caractères"):
        auth.create_user(conn, email="a@x.fr", password="court", role="consultant")


def test_login_is_case_insensitive_on_email_and_strict_on_password(conn):
    auth.create_user(conn, email="Aziz@Exemple.fr", password="un-mot-de-passe-long", role="consultant")
    assert auth.authenticate(conn, "aziz@exemple.fr", "un-mot-de-passe-long") is not None
    assert auth.authenticate(conn, "aziz@exemple.fr", "Un-mot-de-passe-long") is None
    assert auth.authenticate(conn, "inconnu@exemple.fr", "un-mot-de-passe-long") is None


def test_a_client_account_must_belong_to_a_brand(conn):
    with pytest.raises(ValueError, match="rattaché"):
        auth.create_user(conn, email="c@x.fr", password="un-mot-de-passe-long", role="client")


def test_a_client_only_sees_its_own_brands(conn, brands):
    egy, oria = brands
    cid = auth.create_user(conn, email="c@x.fr", password="un-mot-de-passe-long",
                           role="client", brand_ids=[egy])
    client = auth.get_user(conn, cid)
    assert auth.visible_brand_ids(conn, client) == {egy}
    assert auth.can_see(conn, client, egy)
    assert not auth.can_see(conn, client, oria)


def test_a_consultant_sees_everything(conn, brands):
    uid = auth.create_user(conn, email="a@x.fr", password="un-mot-de-passe-long", role="consultant")
    consultant = auth.get_user(conn, uid)
    assert auth.visible_brand_ids(conn, consultant) is None
    assert all(auth.can_see(conn, consultant, b) for b in brands)


def test_session_round_trip(conn):
    uid = auth.create_user(conn, email="a@x.fr", password="un-mot-de-passe-long", role="consultant")
    token = auth.make_session(auth.get_user(conn, uid), now=1_000, key=KEY)
    assert auth.read_session(token, now=1_001, key=KEY) == uid


def test_a_tampered_session_is_rejected(conn):
    uid = auth.create_user(conn, email="a@x.fr", password="un-mot-de-passe-long", role="client",
                           brand_ids=[store.add_brand(conn, slug="x", name="X", url="https://x.fr")])
    token = auth.make_session(auth.get_user(conn, uid), now=1_000, key=KEY)
    body, sig = token.split(".")
    # Un client qui réécrit sa session pour se faire passer pour le compte n° 1,
    # en gardant l'ancienne signature.
    import base64, json
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload.update(u=1, r="consultant")
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert forged != body
    assert auth.read_session(f"{forged}.{sig}", now=1_001, key=KEY) is None
    assert auth.read_session(token, now=1_001, key=b"autre-cle") is None
    assert auth.read_session("n'importe-quoi", now=1_001, key=KEY) is None


def test_an_expired_session_is_rejected(conn):
    uid = auth.create_user(conn, email="a@x.fr", password="un-mot-de-passe-long", role="consultant")
    token = auth.make_session(auth.get_user(conn, uid), now=1_000, key=KEY)
    assert auth.read_session(token, now=1_000 + auth.SESSION_TTL_SECONDS + 1, key=KEY) is None
