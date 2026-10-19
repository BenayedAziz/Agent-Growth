"""L'audit SEO / GEO, sur un faux site servi par une fausse API. Aucun réseau.

Les cas testés ici sont ceux qui ont produit de faux constats lors du premier
passage sur de vrais sites : une page comptée deux fois après redirection, une
coupure passagère prise pour un domaine mort, et des fichiers « absents »
vérifiés sur une adresse qui ne répondait pas.
"""

import httpx2
import pytest

from agent_growth import audit, store

HOME = """<html lang="fr"><head><title>Banque franco-tunisienne pour particuliers et pros</title>
<meta name="description" content="Comptes, crédits et transferts entre la France et la Tunisie, en agence ou en ligne.">
<meta name="viewport" content="width=device-width"><link rel="canonical" href="https://site.fr/">
<meta property="og:title" content="X"></head><body><h1>Votre banque des deux rives</h1>
<p>{words}</p><a href="/contact">Contact</a><a href="/choisir-1/">c</a><a href="/credit-3/">c</a>
<a href="/accueil">accueil</a><a href="/vieux">vieux</a></body></html>"""

PAGE = """<html lang="fr"><head><title>{title}</title><meta name="viewport" content="x">
<link rel="canonical" href="https://site.fr{path}"><meta property="og:title" content="x"></head>
<body><h1>{h1}</h1><p>{words}</p></body></html>"""


def fake_site(*, www_dead=True, flaky=None, sitemap=False, all_dead=False):
    calls = {}
    words = "mot " * 300

    def handler(request: httpx2.Request) -> httpx2.Response:
        url = str(request.url)
        host, path = request.url.host, request.url.path
        calls[url] = calls.get(url, 0) + 1
        if all_dead or (www_dead and host == "www.site.fr"):
            raise httpx2.ConnectError("connexion refusée")
        if flaky and url == flaky and calls[url] == 1:
            raise httpx2.ConnectError("coupure passagère")
        if request.url.scheme == "http":
            return httpx2.Response(301, headers={"location": f"https://{host}{path}"})
        if path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nAllow: /")
        if path == "/sitemap.xml":
            return httpx2.Response(200 if sitemap else 404, text="<urlset/>")
        if path == "/llms.txt":
            return httpx2.Response(404)
        if path == "/accueil":      # même page que l'accueil, par une autre adresse
            return httpx2.Response(301, headers={"location": "https://site.fr/"})
        if path == "/":
            return httpx2.Response(200, html=HOME.format(words=words))
        if path == "/contact":
            return httpx2.Response(200, html=PAGE.format(title="Contact", h1="Contact", path=path, words=words))
        if path == "/choisir-1/":
            return httpx2.Response(200, html=PAGE.format(title="choisir 1 – SITE", h1="x", path=path, words=words))
        if path == "/credit-3/":
            return httpx2.Response(200, html=PAGE.format(title="Crédit logement en France", h1="Crédit", path=path, words=words))
        if path == "/vieux":
            return httpx2.Response(404, html="<html><title>404</title></html>")
        return httpx2.Response(404)

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=True)
    return client, calls


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(audit, "RETRY_DELAY", 0)


def codes(result):
    return {f.code: f for f in result.findings}


def test_a_page_reached_by_two_addresses_is_read_once():
    """« /accueil » redirige vers « / » : un seul titre, donc pas de faux doublon."""
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    urls = [p.url for p in result.pages]
    assert urls.count("https://site.fr/") == 1
    assert "title-duplique" not in codes(result)


def test_dead_www_is_critical_and_says_how_to_check():
    client, _ = fake_site(www_dead=True)
    f = codes(audit.run("https://site.fr/", client=client))["domaine-injoignable"]
    assert f.severity == "critique"
    assert "www.site.fr" in f.title
    assert "navigateur" in f.why


def test_a_transient_failure_is_retried_not_reported():
    """Une seule coupure ne doit jamais devenir un constat critique."""
    client, calls = fake_site(www_dead=False, flaky="https://www.site.fr/")
    result = audit.run("https://site.fr/", client=client)
    assert calls["https://www.site.fr/"] >= 2
    assert "domaine-injoignable" not in codes(result)


def test_starting_from_the_dead_variant_falls_back_to_the_live_one():
    """Lancé sur « www » mort, l'audit doit lire la version sans www — et ne
    pas conclure « pas de robots.txt » depuis une adresse qui ne répond pas."""
    client, _ = fake_site(www_dead=True)
    result = audit.run("https://www.site.fr/", client=client)
    assert result.pages[0].url == "https://site.fr/"
    assert "robots-absent" not in codes(result)


def test_unreadable_site_yields_one_honest_finding_and_nothing_else():
    client, _ = fake_site(all_dead=True)
    result = audit.run("https://site.fr/", client=client)
    assert [f.code for f in result.findings] == ["site-illisible"]
    assert result.score == 0


def test_site_files_are_checked():
    client, _ = fake_site(sitemap=False)
    c = codes(audit.run("https://site.fr/", client=client))
    assert "sitemap-absent" in c and "llms-absent" in c
    assert "robots-absent" not in c
    client, _ = fake_site(sitemap=True)
    assert "sitemap-absent" not in codes(audit.run("https://site.fr/", client=client))


def test_page_level_rules():
    client, _ = fake_site()
    c = codes(audit.run("https://site.fr/", client=client))
    assert c["title-court"].urls == ["https://site.fr/contact"]
    assert c["page-brouillon"].urls == ["https://site.fr/choisir-1/"]
    assert c["page-doublon"].urls == ["https://site.fr/credit-3/"]
    assert "https://site.fr/vieux" in c["pages-cassees"].urls
    assert c["jsonld-absent"].category == "geo"
    assert "https://site.fr/contact" in c["meta-absente"].urls
    assert "https://site.fr/" not in c["meta-absente"].urls


def test_a_draft_page_is_not_also_counted_as_a_duplicate():
    """« choisir-2 » est un brouillon ; le signaler aussi comme doublon gonflerait l'audit."""
    page = audit.Page(url="https://site.fr/choisir-2/", status=200, role="page", text="x",
                      seo=audit.Page.__annotations__ and None)
    from agent_growth.crawl import parse_html

    seo, text, _ = parse_html("https://site.fr/choisir-2/", PAGE.format(
        title="choisir 2 – SITE", h1="x", path="/choisir-2/", words="mot " * 300))
    page = audit.Page(url="https://site.fr/choisir-2/", status=200, role="page", text=text, seo=seo)
    c = codes(audit.AuditResult("https://site.fr/", [page], audit.page_checks([page]), 0))
    assert "page-brouillon" in c
    assert "page-doublon" not in c


def test_findings_are_sorted_by_severity_and_scored():
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    order = [f.severity for f in result.findings]
    rank = {"critique": 0, "important": 1, "amelioration": 2}
    assert order == sorted(order, key=rank.get)
    assert 0 < result.score < 100


def test_score_never_collapses_to_zero_for_a_live_site():
    many = [audit.Finding(f"x{i}", "important", "contenu", "t", "w", "f", ["u"] * 20) for i in range(30)]
    assert audit.score(many) > 0
    assert audit.score([]) == 100


def test_audits_are_kept_over_time(tmp_path):
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    conn = store.connect(tmp_path / "c.db")
    first = store.save_audit(conn, result)
    second = store.save_audit(conn, result)
    history = store.audit_history(conn, url="https://site.fr/")
    assert [h["id"] for h in history] == [second, first]
    findings = store.audit_findings(conn, first)
    assert findings[0]["severity"] == "critique"
    assert isinstance(findings[0]["urls"], list)


def test_advice_never_names_another_client():
    """Un audit part chez un prospect : aucun conseil ne doit citer une autre marque."""
    client, _ = fake_site()
    text = " ".join(f.title + f.why + f.fix for f in audit.run("https://site.fr/", client=client).findings)
    for name in ("Egyptours", "Oria", "ORIA", "TF Bank", "TFBANK"):
        assert name not in text
