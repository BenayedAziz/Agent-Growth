from agent_growth.render import to_markdown, to_voice


def test_markdown_opens_with_the_brand_and_its_sources(doc):
    md = to_markdown(doc)
    assert md.startswith("# Brand core — Salon Léa")
    assert "claude-opus-5-5" in md
    assert "[Salon Léa](https://salonlea.fr/)" in md


def test_markdown_shows_the_editorial_line_as_the_backbone(doc):
    md = to_markdown(doc)
    assert "## Ligne éditoriale" in md
    assert "Expert <-> Accessible" in md
    assert "●●●●●●●○○○" in md  # curseur de ton à 7/10
    assert "| **Avant / après** | 40 % |" in md
    assert "dompter" in md  # vocabulaire banni


def test_every_figure_carries_its_assumptions_and_origin(doc):
    md = to_markdown(doc)
    assert "40 à 120 visites/mois (ordre de grandeur du secteur)" in md
    assert "~300 recherches/mois sur l'agglomération" in md
    assert "confiance moyenne" in md


def test_markdown_links_inbound_and_outbound_targeting(doc):
    md = to_markdown(doc)
    assert "coiffeur boucles lyon" in md       # search_intents -> SEO
    assert "Groupes Facebook boucles Lyon" in md  # where_to_find_them -> outbound


def test_markdown_reports_what_is_missing(doc):
    md = to_markdown(doc)
    assert "## Ce qu'il nous manque" in md
    assert "Combien de coiffeuses sont formées" in md
    assert "## Fiabilité de cette analyse" in md


def test_voice_file_is_self_contained_for_writing_skills(doc):
    voice = to_voice(doc)
    assert voice.startswith("# Voix de la marque — Salon Léa")
    for section in ("## Qui je suis", "## À qui je parle", "## Comment j'écris",
                    "## De quoi je parle", "## Ce que je ne dis jamais"):
        assert section in voice
    assert "Le mot « dompter »" in voice
    assert "Ne pas éditer à la main" in voice


def test_zero_cost_is_written_in_words_not_as_a_range(doc):
    """« 0 à 0 EUR/mois » se lit mal et sonne comme un bug."""
    md = to_markdown(doc)
    assert "**Coût** : aucun coût en argent (hypothèse)" in md
    assert "0 à 0" not in md


def test_single_value_estimate_is_not_shown_as_a_range(doc):
    from agent_growth.render import _estimate
    from agent_growth.schemas import Estimate

    est = Estimate(metric="leads/mois", low=12, high=12, assumptions=["x"], basis="donnees_site")
    assert _estimate(est) == "12 leads/mois (lu sur le site)"
