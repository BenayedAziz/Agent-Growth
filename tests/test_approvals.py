"""La file de validation. C'est elle qui garde l'argent et les comptes clients."""

import sqlite3

import pytest

from agent_growth import store


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def brand_id(conn):
    return store.add_brand(conn, slug="oria", name="Oria", url="https://oria.fr")


def _campaign(conn, brand_id, cap=300.0):
    cur = conn.execute(
        """INSERT INTO campaign (brand_id, channel, name, hard_cap_eur, created_at)
           VALUES (?, 'meta_ads', 'Automne', ?, ?)""",
        (brand_id, cap, store.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _state(conn, table, row_id):
    return conn.execute(f"SELECT state FROM {table} WHERE id = ?", (row_id,)).fetchone()["state"]


def test_requesting_puts_the_subject_on_hold(conn, brand_id):
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer Automne", amount_eur=300)
    assert aid is not None
    assert _state(conn, "campaign", cid) == "a_valider"


def test_approving_advances_the_subject(conn, brand_id):
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer", amount_eur=300)
    assert store.decide(conn, aid, approve=True, by="test") is True
    assert _state(conn, "campaign", cid) == "active"


def test_refusing_sends_the_subject_back(conn, brand_id):
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer", amount_eur=300)
    store.decide(conn, aid, approve=False, by="test")
    assert _state(conn, "campaign", cid) == "brouillon"


def test_a_double_tap_never_applies_twice(conn, brand_id):
    """Un double appui sur « Valider » ne doit jamais lancer deux dépenses."""
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer", amount_eur=300)
    assert store.decide(conn, aid, approve=True, by="telegram") is True
    assert store.decide(conn, aid, approve=True, by="telegram") is False
    assert store.decide(conn, aid, approve=False, by="console") is False   # trop tard
    assert _state(conn, "campaign", cid) == "active"


def test_only_one_pending_request_per_subject(conn, brand_id):
    cid = _campaign(conn, brand_id)
    store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                           brand_id=brand_id, summary="Lancer", amount_eur=300)
    with pytest.raises(sqlite3.IntegrityError):
        store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                               brand_id=brand_id, summary="Encore", amount_eur=300)


def test_an_expired_request_cannot_be_approved(conn, brand_id):
    """Une dépense validée trop tard s'appliquerait à un contexte qui n'existe plus."""
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer", amount_eur=300)
    conn.execute("UPDATE approval SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (aid,))
    conn.commit()
    assert store.decide(conn, aid, approve=True, by="telegram") is False
    # La campagne n'est ni lancée ni bloquée : elle revient en brouillon.
    assert _state(conn, "campaign", cid) == "brouillon"
    assert store.expire_stale(conn) == 0      # déjà marquée expirée par decide
    assert store.get_approval(conn, aid)["state"] == "expire"


def test_expire_stale_puts_subjects_back_in_draft(conn, brand_id):
    cid = _campaign(conn, brand_id)
    aid = store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                 brand_id=brand_id, summary="Lancer", amount_eur=300)
    conn.execute("UPDATE approval SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (aid,))
    conn.commit()
    assert store.expire_stale(conn) == 1
    assert _state(conn, "campaign", cid) == "brouillon"


def test_auto_rule_approves_publications_without_asking(conn, brand_id):
    store.add_auto_rule(conn, brand_id, "publication", channel="instagram")
    cur = conn.execute(
        "INSERT INTO content (brand_id, channel, created_at) VALUES (?, 'instagram', ?)",
        (brand_id, store.now()),
    )
    content_id = int(cur.lastrowid)
    aid = store.request_approval(conn, kind="publication", subject_table="content",
                                 subject_id=content_id, brand_id=brand_id, channel="instagram",
                                 summary="Post du mardi")
    assert aid is None
    assert _state(conn, "content", content_id) == "valide"


def test_auto_rule_on_one_channel_does_not_cover_another(conn, brand_id):
    store.add_auto_rule(conn, brand_id, "publication", channel="instagram")
    cur = conn.execute(
        "INSERT INTO content (brand_id, channel, created_at) VALUES (?, 'linkedin', ?)",
        (brand_id, store.now()),
    )
    aid = store.request_approval(conn, kind="publication", subject_table="content",
                                 subject_id=int(cur.lastrowid), brand_id=brand_id,
                                 channel="linkedin", summary="Post LinkedIn")
    assert aid is not None


def test_automatic_spending_requires_a_cap(conn, brand_id):
    """Le schéma refuse une dépense automatique sans plafond."""
    with pytest.raises(sqlite3.IntegrityError):
        store.add_auto_rule(conn, brand_id, "depense", channel="meta_ads")


def test_spending_above_the_cap_goes_back_to_a_human(conn, brand_id):
    store.add_auto_rule(conn, brand_id, "depense", channel="meta_ads", max_eur=100)
    small = _campaign(conn, brand_id, cap=80)
    big = _campaign(conn, brand_id, cap=500)
    assert store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=small,
                                  brand_id=brand_id, channel="meta_ads", summary="petit",
                                  amount_eur=80) is None
    assert store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=big,
                                  brand_id=brand_id, channel="meta_ads", summary="gros",
                                  amount_eur=500) is not None


def test_spending_with_unknown_amount_is_never_automatic(conn, brand_id):
    store.add_auto_rule(conn, brand_id, "depense", channel="meta_ads", max_eur=100)
    cid = _campaign(conn, brand_id)
    assert store.request_approval(conn, kind="depense", subject_table="campaign", subject_id=cid,
                                  brand_id=brand_id, channel="meta_ads", summary="?",
                                  amount_eur=None) is not None


def test_site_change_waits_for_approval(conn, brand_id):
    site_id = store.add_site(conn, brand_id, "https://oria.fr", platform="sur_mesure",
                             secret_ref="ORIA_GITHUB_TOKEN", config={"repo": "moi/oria"})
    change_id, aid = store.propose_site_change(conn, site_id, kind="page_create",
                                               title="Nos offres", body="<p>…</p>")
    assert aid is not None
    assert _state(conn, "site_change", change_id) == "a_valider"
    assert store.site_changes(conn, "approuve") == []
    store.decide(conn, aid, approve=True, by="test")
    assert [r["id"] for r in store.site_changes(conn, "approuve")] == [change_id]


def test_site_write_access_follows_the_platform(conn, brand_id):
    wp = store.add_site(conn, brand_id, "https://a.fr", platform="wordpress", secret_ref="WP_PASS")
    sm = store.add_site(conn, brand_id, "https://b.fr", platform="speedmedia")
    bare = store.add_site(conn, brand_id, "https://c.fr", platform="shopify")
    assert store.get_site(conn, wp)["write_access"] == "api"
    assert store.get_site(conn, sm)["write_access"] == "manuel"
    assert store.get_site(conn, bare)["write_access"] == "aucun"     # pas d'accès déclaré


def test_unknown_platform_is_refused(conn, brand_id):
    with pytest.raises(ValueError, match="Plateforme inconnue"):
        store.add_site(conn, brand_id, "https://x.fr", platform="geocities")
