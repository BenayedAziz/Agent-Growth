import json

from agent_growth.cli import main, slugify
from agent_growth.tools.brand_core import build_prompt
from agent_growth.crawl import Page, parse_html


def test_slugify_normalises_hosts():
    assert slugify("https://www.salon-lea.fr/tarifs") == "salon-lea-fr"
    assert slugify("salonlea.fr") == "salonlea-fr"


def test_render_command_rebuilds_both_documents(tmp_path, doc):
    source = tmp_path / "brand-core.json"
    source.write_text(json.dumps(doc.model_dump(), ensure_ascii=False), encoding="utf-8")

    assert main(["render", str(source)]) == 0
    assert "Salon Léa" in (tmp_path / "brand-core.md").read_text(encoding="utf-8")
    assert "Voix de la marque" in (tmp_path / "voice.md").read_text(encoding="utf-8")


def _page(html: str) -> Page:
    seo, text, links = parse_html("https://salonlea.fr/", html)
    return Page(url="https://salonlea.fr/", status=200, role="accueil", text=text, seo=seo, links=links)


def test_prompt_includes_raw_technical_findings():
    page = _page("<html lang=fr><head><title>T</title></head><body><h1>H</h1><p>Texte</p></body></html>")
    prompt = build_prompt("https://salonlea.fr", [page], [])
    assert "title (1 car.) : T" in prompt
    assert "meta description (0 car.) : (absente)" in prompt
    assert "données structurées JSON-LD : non" in prompt


def test_prompt_flags_absent_competitors_as_hypotheses():
    page = _page("<html><body><p>x</p></body></html>")
    prompt = build_prompt("https://salonlea.fr", [page], [])
    assert "Aucun concurrent fourni" in prompt
    assert "hypothèses, pas des observations" in prompt


def test_owner_notes_outrank_the_website():
    page = _page("<html><body><p>x</p></body></html>")
    prompt = build_prompt("https://salonlea.fr", [page], [], notes="On ne fait que du bouclé.")
    assert "On ne fait que du bouclé." in prompt
    assert "Elles priment sur ce que laisse deviner le site." in prompt
