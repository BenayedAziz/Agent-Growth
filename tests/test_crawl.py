from agent_growth.crawl import SKIP_PATTERNS, _rank_links, parse_html

HTML = """
<html lang="fr">
  <head>
    <title>Salon Léa — coiffeur boucles Lyon</title>
    <meta name="Description" content="Spécialiste du cheveu bouclé à Lyon.">
    <link rel="canonical" href="/">
    <meta property="og:title" content="Salon Léa">
    <script type="application/ld+json">{"@type":"HairSalon"}</script>
  </head>
  <body>
    <nav><a href="/panier">Panier</a></nav>
    <h1>Vos boucles, enfin comprises</h1>
    <h2>Coupe à sec</h2><h2>Tarifs</h2>
    <p>Nous coupons les boucles à sec.</p>
    <a href="/a-propos">À propos</a>
    <a href="/tarifs">Tarifs</a>
    <a href="/brochure.pdf">Brochure</a>
    <a href="https://autre-site.fr/x">Externe</a>
    <footer><a href="/mentions">Mentions</a></footer>
    <script>tracker();</script>
  </body>
</html>
"""


def test_extracts_seo_signals():
    seo, _, _ = parse_html("https://salonlea.fr/", HTML)
    assert seo.title == "Salon Léa — coiffeur boucles Lyon"
    assert seo.title_length == len(seo.title)
    assert seo.meta_description == "Spécialiste du cheveu bouclé à Lyon."
    assert seo.h1 == ["Vos boucles, enfin comprises"]
    assert seo.h2 == ["Coupe à sec", "Tarifs"]
    assert seo.lang == "fr"
    assert seo.canonical == "https://salonlea.fr/"
    assert seo.og_tags == ["og:title"]
    assert seo.has_structured_data is True


def test_keeps_only_internal_crawlable_links():
    _, _, links = parse_html("https://salonlea.fr/", HTML)
    assert "https://salonlea.fr/a-propos" in links
    assert "https://salonlea.fr/tarifs" in links
    # externe, PDF et panier sont écartés
    assert not any("autre-site.fr" in url or ".pdf" in url or "panier" in url for url in links)


def test_body_text_drops_scripts_and_chrome():
    _, text, _ = parse_html("https://salonlea.fr/", HTML)
    assert "Nous coupons les boucles à sec." in text
    assert "tracker" not in text
    assert "Panier" not in text  # <nav> retiré
    assert "Mentions" not in text  # <footer> retiré


def test_skip_patterns_cover_assets_and_private_areas():
    for url in ("https://x.fr/a.PDF", "https://x.fr/img.jpeg", "https://x.fr/wp-admin/", "https://x.fr/connexion"):
        assert SKIP_PATTERNS.search(url), url
    assert not SKIP_PATTERNS.search("https://x.fr/tarifs")


def test_rank_links_takes_one_page_per_role_in_priority_order():
    home = "https://salonlea.fr/"
    links = [
        "https://salonlea.fr/blog/boucles",
        "https://salonlea.fr/tarifs",
        "https://salonlea.fr/a-propos",
        "https://salonlea.fr/a-propos/equipe",  # même rôle : ignoré
    ]
    ranked = _rank_links(links, home)
    roles = [role for _, role in ranked]
    assert roles == ["à propos", "tarifs", "contenu"]  # ordre de PRIORITY_PATTERNS
    assert ("https://salonlea.fr/a-propos", "à propos") in ranked


def test_user_agent_stays_ascii():
    """Un en-tête HTTP non ASCII fait échouer la requête avant même le réseau."""
    from agent_growth.crawl import USER_AGENT

    USER_AGENT.encode("ascii")
