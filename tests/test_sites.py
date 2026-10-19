"""Les adaptateurs d'écriture. Aucun appel réseau : une fausse API répond."""

import base64
import json

import httpx2

from agent_growth.sites import adapter_for
from agent_growth.sites.base import AI_MARK_HTML, Change
from agent_growth.sites.github import GitHubAdapter
from agent_growth.sites.manual import ManualAdapter
from agent_growth.sites.shopify import ShopifyAdapter
from agent_growth.sites.wordpress import WordPressAdapter


def client(handler):
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def page(**kw):
    base = dict(id=7, kind="page_create", title="Croisière sur le Nil", body="<p>Texte</p>",
                slug="croisiere-nil", meta={"description": "Le Nil autrement"})
    base.update(kw)
    return Change(**base)


# ---------------------------------------------------------------- marquage IA

def test_generated_content_is_marked_once():
    c = page()
    assert c.marked_body().count(AI_MARK_HTML) == 1
    assert Change(**{**c.__dict__, "body": c.marked_body()}).marked_body().count(AI_MARK_HTML) == 1


def test_human_content_is_not_marked():
    assert AI_MARK_HTML not in page(ai_generated=False).marked_body()


# -------------------------------------------------------------------- WordPress

def test_wordpress_creates_a_draft_with_app_password():
    seen = {}

    def api(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(201, json={"id": 12, "status": "draft", "link": "https://egy.fr/?p=12"})

    result = WordPressAdapter("https://egy.fr/", user="admin", app_password="abcd efgh",
                              client=client(api)).apply(page())
    assert result.ok and result.state == "applique"
    assert seen["url"] == "https://egy.fr/wp-json/wp/v2/pages"
    assert seen["auth"].startswith("Basic ")
    assert seen["body"]["status"] == "draft"          # brouillon par défaut
    assert AI_MARK_HTML in seen["body"]["content"]
    assert "brouillon" in result.detail


def test_wordpress_reports_a_refused_access_in_plain_french():
    result = WordPressAdapter("https://egy.fr", user="a", app_password="b",
                              client=client(lambda r: httpx2.Response(401))).apply(page())
    assert not result.ok and result.state == "echec"
    assert "mot de passe d'application" in result.detail


def test_wordpress_update_needs_a_numeric_page_id():
    result = WordPressAdapter("https://egy.fr", user="a", app_password="b",
                              client=client(lambda r: httpx2.Response(200, json={}))
                              ).apply(page(kind="page_update", target="/a-propos"))
    assert result.state == "echec"


# ---------------------------------------------------------------------- Shopify

def test_shopify_creates_an_unpublished_page():
    seen = {}

    def api(request):
        seen["token"] = request.headers["x-shopify-access-token"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"data": {"pageCreate": {
            "page": {"id": "gid://shopify/Page/1", "handle": "croisiere-nil"}, "userErrors": []}}})

    result = ShopifyAdapter("oria.myshopify.com", token="shpat_x", client=client(api)).apply(page())
    assert result.ok
    assert seen["token"] == "shpat_x"
    assert seen["url"].endswith("/admin/api/2026-07/graphql.json")
    assert seen["body"]["variables"]["page"]["isPublished"] is False
    assert result.url == "https://oria.myshopify.com/pages/croisiere-nil"


def test_shopify_user_errors_are_surfaced():
    api = lambda r: httpx2.Response(200, json={"data": {"pageCreate": {
        "page": None, "userErrors": [{"field": ["handle"], "message": "Handle already taken"}]}}})
    result = ShopifyAdapter("oria.myshopify.com", token="t", client=client(api)).apply(page())
    assert result.state == "echec" and "already taken" in result.detail


# ----------------------------------------------------------------------- GitHub

def test_github_opens_a_pull_request_never_pushes_to_main():
    calls = []

    def api(request):
        path, method = request.url.path, request.method
        calls.append((method, path))
        if method == "GET" and path.endswith("/git/ref/heads/main"):
            return httpx2.Response(200, json={"object": {"sha": "abc"}})
        if method == "POST" and path.endswith("/git/refs"):
            return httpx2.Response(201, json={})
        if method == "GET" and "/contents/" in path:
            return httpx2.Response(404, json={})
        if method == "PUT":
            body = json.loads(request.content)
            assert body["branch"].startswith("agent-growth/")
            text = base64.b64decode(body["content"]).decode()
            assert "ai_generated: true" in text and 'title: "Croisière sur le Nil"' in text
            return httpx2.Response(201, json={})
        if method == "POST" and path.endswith("/pulls"):
            return httpx2.Response(201, json={"html_url": "https://github.com/moi/oria/pull/3"})
        return httpx2.Response(500)

    result = GitHubAdapter("moi/oria", token="ghp_x", client=client(api)).apply(page())
    assert result.ok and result.url.endswith("/pull/3")
    assert ("PUT", "/repos/moi/oria/contents/content/pages/croisiere-nil.md") in calls
    # Jamais d'écriture sur la branche principale.
    assert not any(m == "PATCH" and "heads/main" in p for m, p in calls)


def test_github_reports_missing_access():
    result = GitHubAdapter("moi/oria", token="x",
                           client=client(lambda r: httpx2.Response(404))).apply(page())
    assert result.state == "echec" and "accès refusé" in result.detail


# ----------------------------------------------------------------------- manuel

def test_manual_pack_is_ready_to_paste(tmp_path):
    result = ManualAdapter(tmp_path, platform="speedmedia", site_url="https://egyptours.fr").apply(page())
    assert result.state == "manuel"
    text = (tmp_path / "00007-croisiere-nil.md").read_text(encoding="utf-8")
    assert "SpeedMedia" in text
    assert "Croisière sur le Nil" in text and "Le Nil autrement" in text
    assert AI_MARK_HTML in text


# -------------------------------------------------------------- choix d'adaptateur

def _site(platform, secret_ref="", config=None):
    return {"platform": platform, "secret_ref": secret_ref, "url": "https://x.fr",
            "config": json.dumps(config or {})}


def test_without_a_secret_every_platform_falls_back_to_manual(tmp_path):
    for platform in ("wordpress", "shopify", "sur_mesure", "speedmedia"):
        a = adapter_for(_site(platform, "MISSING_VAR"), brand_slug="x", pack_dir=tmp_path, env={})
        assert a.name == "manuel", platform


def test_secrets_are_read_from_the_environment_never_the_database(tmp_path):
    a = adapter_for(_site("wordpress", "WP_PASS", {"user": "admin"}), brand_slug="x",
                    pack_dir=tmp_path, env={"WP_PASS": "s3cret"})
    assert a.name == "wordpress"
    assert a.auth == ("admin", "s3cret")


def test_a_hostile_brand_slug_cannot_escape_the_pack_directory(tmp_path):
    a = adapter_for(_site("speedmedia"), brand_slug="../../etc", pack_dir=tmp_path / "packs", env={})
    a.apply(page())
    written = list(tmp_path.rglob("*.md"))
    assert written and all((tmp_path / "packs") in w.parents for w in written)
