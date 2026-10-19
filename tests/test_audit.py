"""L'audit SEO / GEO, sur un faux site servi par une fausse API. Aucun réseau.

Les cas testés ici sont ceux qui ont produit de faux constats lors du premier
passage sur de vrais sites : une page comptée deux fois après redirection, une
coupure passagère prise pour un domaine mort, et des fichiers « absents »
vérifiés sur une adresse qui ne répondait pas.
"""

import json

import httpx2
import pytest

from agent_growth import audit, pagespeed, render, screamingfrog, store

HOME = """<html lang="fr"><head><title>Banque franco-tunisienne pour particuliers et pros</title>
<meta name="description" content="Comptes, crédits et transferts entre la France et la Tunisie, en agence ou en ligne.">
<meta name="viewport" content="width=device-width"><link rel="canonical" href="https://site.fr/">
<meta property="og:title" content="X"></head><body><h1>Votre banque des deux rives</h1>
<p>Crédits et comptes. {words}</p><a href="/contact">Contact</a><a href="/choisir-1/">c</a><a href="/credit-3/">c</a>
<a href="/accueil">accueil</a><a href="/vieux">vieux</a></body></html>"""

PAGE = """<html lang="fr"><head><title>{title}</title><meta name="viewport" content="x">
<link rel="canonical" href="https://site.fr{path}"><meta property="og:title" content="x"></head>
<body><h1>{h1}</h1><p>{words}</p></body></html>"""


def fake_site(*, www_dead=True, flaky=None, sitemap=False, all_dead=False, psi=None):
    calls = {}
    words = "mot " * 300

    def handler(request: httpx2.Request) -> httpx2.Response:
        url = str(request.url)
        host, path = request.url.host, request.url.path
        calls[url] = calls.get(url, 0) + 1
        if host == "www.googleapis.com":
            return httpx2.Response(200, json=psi) if psi else httpx2.Response(429, json={})
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
    # Jamais de vrai navigateur dans les tests, même si Lighthouse est installé.
    monkeypatch.setattr(pagespeed, "lighthouse_available", lambda: False)


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


def test_global_score_is_the_mean_of_the_three_pillars():
    """Le client lit trois notes : la note globale doit en être la moyenne."""
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    pillars = audit.pillar_scores(result.findings)
    assert set(pillars) == {"technique", "on-page", "eeat"}
    assert result.score == round(sum(pillars.values()) / 3)


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


# --------------------------------------------------------------------------- #
# Piliers
# --------------------------------------------------------------------------- #

def test_every_rule_belongs_to_a_pillar_and_says_what_passing_means():
    for pillar, label, codes in audit.CHECKS.values():
        assert pillar in audit.PILLARS
        assert label and codes
    client, _ = fake_site()
    for f in audit.run("https://site.fr/", client=client).findings:
        assert f.code in audit.CHECK_OF, f"{f.code} n'est rattaché à aucune vérification"
        assert f.pillar == audit.PILLAR_OF[f.code]


def test_pillar_subtitles_are_the_ones_shown_to_clients():
    assert audit.PILLARS["technique"]["subtitle"] == "Ce qui permet à Google de lire, comprendre et indexer le site"
    assert audit.PILLARS["on-page"]["subtitle"] == "Ce qui signale à Google de quoi parle chaque page"
    assert audit.PILLARS["eeat"]["subtitle"] == "Ce qui établit la crédibilité du site aux yeux de Google"


# --------------------------------------------------------------------------- #
# E-E-A-T
# --------------------------------------------------------------------------- #

def test_trust_pages_and_contact_details():
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    c = codes(result)
    assert "page-contact" not in c and "contact" in result.evaluated     # /contact existe
    for code in ("page-a-propos", "mentions-legales", "confidentialite", "coordonnees-absentes"):
        assert code in c and c[code].pillar == "eeat"


def test_trust_pages_are_found_by_link_label_too():
    from agent_growth.crawl import parse_html

    html = ('<html><body><a href="/a-proros-de-nous/">À propos de nous</a>'
            '<a href="/legal-x/">Mentions légales</a><a href="/p/">Politique de confidentialité</a>'
            '<footer>Appelez le +216 71 123 456</footer></body></html>')
    seo, text, links = parse_html("https://site.fr/", html)
    page = audit.Page(url="https://site.fr/", status=200, role="accueil", text=text, seo=seo, links=links)
    c = {f.code for f in audit.eeat_checks([page])}
    assert not c & {"page-a-propos", "mentions-legales", "confidentialite", "coordonnees-absentes"}


def test_finance_site_is_checked_for_the_consumer_credit_mention():
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    assert result.sector == "finance"
    assert codes(result)["mention-credit"].urls == ["https://site.fr/credit-3/"]


def test_the_exact_credit_mention_passes_and_a_paraphrase_does_not():
    from agent_growth.crawl import parse_html

    def page(body, path="/credit-perso/"):
        seo, text, links = parse_html(f"https://b.fr{path}", f"<html><body><h1>Crédit</h1>{body}</body></html>")
        return audit.Page(url=f"https://b.fr{path}", status=200, role="page", text=text, seo=seo, links=links)

    exact = page("<footer>Un crédit vous engage et doit être remboursé. Vérifiez vos capacités…</footer>")
    paraphrase = page("<p>Un crédit est un engagement et doit être remboursé.</p>", "/credit-auto/")
    mortgage = page("<p>Rien</p>", "/credit-logement/")
    found = {f.code: f for f in audit.eeat_checks([exact, paraphrase, mortgage], sector_name="finance")}
    assert found["mention-credit"].urls == ["https://b.fr/credit-auto/"]


def test_sector_needs_several_mentions():
    from agent_growth.crawl import parse_html

    seo, text, _ = parse_html("https://c.fr/", "<html><title>Chirurgie esthétique</title><body>"
                                              "<h1>Clinique</h1><p>Nos médecins</p></body></html>")
    assert audit.sector([audit.Page("https://c.fr/", 200, "accueil", text, seo)]) == "sante"
    seo, text, _ = parse_html("https://d.fr/", "<html><title>Boulangerie</title><body><p>Pain et crédit</p></body></html>")
    assert audit.sector([audit.Page("https://d.fr/", 200, "accueil", text, seo)]) == ""


# --------------------------------------------------------------------------- #
# Vitesse
# --------------------------------------------------------------------------- #

def psi_response(score=0.42, category="SLOW", origin_only=False):
    field = {"metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 4100, "category": "SLOW"},
                         "INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"},
                         "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5, "category": "FAST"}},
             "overall_category": category}
    return {
        "loadingExperience": {"origin_fallback": True, **field} if origin_only else field,
        "originLoadingExperience": field,
        "lighthouseResult": {
            "categories": {"performance": {"score": score}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 3800.4},
                "cumulative-layout-shift": {"numericValue": 0.02},
                "total-blocking-time": {"numericValue": 310},
                "uses-text-compression": {"title": "Activez la compression de texte",
                                          "details": {"type": "opportunity", "overallSavingsMs": 1200}},
                "unused-javascript": {"title": "Réduisez le JavaScript inutilisé", "metricSavings": {"LCP": 450},
                                      "details": {"type": "opportunity"}},
                "tiny": {"title": "Négligeable", "details": {"type": "opportunity", "overallSavingsMs": 20}},
            },
        },
    }


def test_pagespeed_response_is_parsed():
    s = pagespeed.parse("https://a.fr/", "mobile", psi_response())
    assert (s.score, s.lcp_ms, s.cls, s.tbt_ms) == (42, 3800.4, 0.02, 310)
    assert s.field_data == {"lcp_ms": 4100.0, "inp_ms": 180.0, "cls": 0.05, "category": "SLOW"}
    assert s.field_scope == "page" and s.cwv_passed is False
    assert [o["title"] for o in s.opportunities] == ["Activez la compression de texte", "Réduisez le JavaScript inutilisé"]
    assert s.source == "pagespeed"
    assert pagespeed.parse("https://a.fr/", "mobile", psi_response(origin_only=True)).field_scope == "site"


def test_quota_refusal_falls_back_to_lighthouse():
    client = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(429, json={})))
    alone = pagespeed.measure("https://a.fr/", "mobile", client=client)
    assert "PAGESPEED_API_KEY" in alone.error

    seen = []

    def lighthouse(url, strategy):
        seen.append((url, strategy))
        return psi_response(score=0.91)["lighthouseResult"]

    speeds = pagespeed.measure_all([("https://a.fr/", "mobile")], client=client, api_key="", runner=lighthouse)
    assert seen == [("https://a.fr/", "mobile")]
    assert speeds[0].source == "lighthouse" and speeds[0].score == 91 and not speeds[0].error
    assert speeds[0].field_data == {}        # le terrain n'existe que chez Google


def test_api_key_is_sent_when_configured(monkeypatch):
    sent = []
    client = httpx2.Client(transport=httpx2.MockTransport(
        lambda r: sent.append(r.url.params.get("key")) or httpx2.Response(200, json=psi_response())))
    monkeypatch.setenv("PAGESPEED_API_KEY", "cle-test")
    pagespeed.measure_all([("https://a.fr/", "mobile")], client=client)
    assert sent == ["cle-test"]


def test_speed_rules():
    slow = pagespeed.parse("https://a.fr/", "mobile", psi_response(score=0.42))
    fine = pagespeed.parse("https://a.fr/b", "mobile", psi_response(score=0.75, category="FAST"))
    failed = pagespeed.Speed("https://a.fr/c", "mobile", error="quota")
    evaluated = set()
    c = {f.code: f for f in audit.speed_checks([slow, fine, failed], evaluated)}
    assert c["vitesse-mobile-lente"].urls == ["https://a.fr/"]
    assert c["vitesse-mobile-moyenne"].urls == ["https://a.fr/b"]
    assert c["cwv-echec"].urls == ["https://a.fr/"]
    assert evaluated == {"vitesse", "cwv"}
    nothing = set()
    assert audit.speed_checks([failed], nothing) == [] and nothing == set()


def test_audit_measures_the_home_and_selling_pages():
    client, _ = fake_site(psi=psi_response(score=0.95, category="FAST"))
    result = audit.run("https://site.fr/", client=client)
    targets = {(s.url, s.strategy) for s in result.speed}
    assert ("https://site.fr/", "mobile") in targets and ("https://site.fr/", "desktop") in targets
    assert ("https://site.fr/contact", "mobile") in targets
    assert {"vitesse", "cwv"} <= result.evaluated
    assert not {"vitesse-mobile-lente", "cwv-echec"} & set(codes(result))


# --------------------------------------------------------------------------- #
# Screaming Frog
# --------------------------------------------------------------------------- #

SF_EXPORT = (
    '"Internal - All"\n'
    '"Address","Content Type","Status Code","Status","Indexability","Title 1","Meta Description 1",'
    '"H1-1","H1-2","Canonical Link Element 1","Word Count","Meta Robots 1"\n'
    '"https://site.fr/","text/html; charset=UTF-8","200","OK","Indexable","Banque franco-tunisienne pour particuliers",'
    '"Comptes et crédits.","Votre banque","","https://site.fr/","420",""\n'
    '"https://site.fr/agences/","text/html","200","OK","Indexable","Agences","","Nos agences","Paris",'
    '"https://site.fr/agences/","90",""\n'
    '"https://site.fr/test-2/","text/html","200","OK","Non-Indexable","Page de test pour le moteur interne",'
    '"x","Test","","","300","noindex, follow"\n'
    '"https://site.fr/ancien","text/html","301","Moved Permanently","Non-Indexable","","","","","","0",""\n'
    '"https://site.fr/perdu","text/html","404","Not Found","Non-Indexable","","","","","","0",""\n'
    '"https://site.fr/logo.png","image/png","200","OK","Indexable","","","","","","0",""\n'
)


def test_screaming_frog_export_is_read(tmp_path):
    path = tmp_path / "internal_all.csv"
    path.write_text(SF_EXPORT, encoding="utf-8")
    pages = screamingfrog.load(tmp_path)          # un dossier suffit
    assert [p.url for p in pages] == ["https://site.fr/", "https://site.fr/agences/",
                                      "https://site.fr/test-2/", "https://site.fr/perdu"]
    agences = pages[1]
    assert agences.seo.title == "Agences" and agences.seo.h1 == ["Nos agences", "Paris"]
    assert agences.seo.word_count == 90
    assert pages[2].seo.noindex and pages[3].error


def test_unknown_export_is_refused_with_instructions(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text('"Adresse","Code"\n"https://a.fr/","200"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Internal"):
        screamingfrog.load(path)


def test_audit_uses_screaming_frog_for_what_it_covers(tmp_path):
    path = tmp_path / "internal_all.csv"
    path.write_text(SF_EXPORT, encoding="utf-8")
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client, screaming_frog=str(path))
    c = codes(result)
    assert result.crawler == "screaming-frog" and result.pages_crawled == 4
    assert c["title-court"].urls == ["https://site.fr/agences/"]        # vu par Screaming Frog
    assert c["h1-multiple"].urls == ["https://site.fr/agences/"]
    assert c["noindex"].urls == ["https://site.fr/test-2/"]
    assert c["pages-cassees"].urls == ["https://site.fr/perdu"]
    assert "jsonld-absent" in c                                         # vu par notre crawl
    assert "https://site.fr/contact" not in c["title-court"].urls       # notre crawl ne double pas


# --------------------------------------------------------------------------- #
# Rapport client
# --------------------------------------------------------------------------- #

def test_report_is_a_draft_until_the_manual_search_is_done():
    client, _ = fake_site()
    data = audit.run("https://site.fr/", client=client).to_dict()
    report = audit.report(data, brand="Banque Test")
    assert report["draft"] and len(report["pending"]) == len(audit.manual_checklist("https://site.fr/"))

    manual = audit.manual_checklist("https://site.fr/", brand="Banque Test")
    for m in manual:
        m["status"], m["constat"] = "ok", f"Vérifié : {m['id']}."
    manual[1]["status"], manual[1]["constat"] = "probleme", "Un avis <script>alert(1)</script> négatif sort en 2ᵉ."
    report = audit.report(data, manual, brand="Banque Test")
    assert not report["draft"]
    eeat = next(p for p in report["pillars"] if p["key"] == "eeat")
    assert any(m["id"] == "requete-marque" and m["status_label"] == "Problème" for m in eeat["manual"])


def test_manual_checklist_links_point_to_google_searches():
    items = {m["id"]: m for m in audit.manual_checklist("https://www.site.fr/", brand="Site")}
    assert "site%3Asite.fr" in items["indexation"]["links"][0]["url"]
    assert all(m["pillar"] in audit.PILLARS and m["status"] == "" for m in items.values())


def test_report_html_follows_the_three_pillar_structure():
    client, _ = fake_site(psi=psi_response())
    data = audit.run("https://site.fr/", client=client).to_dict()
    manual = audit.manual_checklist("https://site.fr/")
    for m in manual:
        m["status"], m["constat"] = "a-ameliorer", "<script>alert(1)</script>"
    html = render.audit_html(audit.report(data, manual, brand="Banque Test"))
    for meta in audit.PILLARS.values():
        assert meta["subtitle"] in html
    assert "Outils utilisés" in html and "Google PageSpeed Insights" in html
    assert "Recherche Google manuelle" in html and "Crawl complet du site" in html
    assert "Version de travail" not in html
    assert "<script>alert(1)</script>" not in html                     # échappé
    assert "Semrush" not in html
    assert "Ce qui est déjà en place" in html and "Vitesse de chargement" in html


def test_report_html_warns_when_manual_checks_are_missing():
    client, _ = fake_site()
    html = render.audit_html(audit.report(audit.run("https://site.fr/", client=client).to_dict()))
    assert "Version de travail" in html


def test_report_can_be_rebuilt_from_the_database(tmp_path):
    client, _ = fake_site()
    result = audit.run("https://site.fr/", client=client)
    conn = store.connect(tmp_path / "c.db")
    audit_id = store.save_audit(conn, result)
    data = store.audit_details(conn, audit_id)
    assert data["score"] == result.score and data["findings"][0]["pillar"]
    assert {f["pillar"] for f in store.audit_findings(conn, audit_id)} <= set(audit.PILLARS)
    assert audit.report(data)["score"] == result.score


def test_cli_rebuilds_the_report_after_manual_search(tmp_path, capsys):
    from agent_growth.cli import main

    client, _ = fake_site()
    data = audit.run("https://site.fr/", client=client).to_dict()
    (tmp_path / "audit.json").write_text(json.dumps(data), encoding="utf-8")
    manual = audit.manual_checklist("https://site.fr/")
    for m in manual:
        m["status"], m["constat"] = "ok", "Vérifié."
    (tmp_path / "recherche-manuelle.json").write_text(json.dumps(manual), encoding="utf-8")
    assert main(["audit-report", str(tmp_path)]) == 0
    assert "Prêt à envoyer" in capsys.readouterr().out
    assert "Outils utilisés" in (tmp_path / "rapport.html").read_text(encoding="utf-8")
