"""Lecture du site d'une marque.

Volontairement modeste : on lit l'accueil, puis quelques pages qui portent
presque toujours le positionnement (à propos, offre, tarifs, cas clients). Pas
de rendu JavaScript, pas de crawl exhaustif — l'objectif est de donner au
modèle de quoi comprendre la marque, pas de dresser l'inventaire du site.

`robots.txt` est respecté : ces outils tournent sur de vrais sites, parfois
ceux de concurrents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx2 as httpx
from bs4 import BeautifulSoup

# Les en-têtes HTTP doivent rester en ASCII : pas d'accent ici.
USER_AGENT = "AgentGrowthBot/0.1 (+marketing audit; identifies itself and respects robots.txt)"
TIMEOUT = 20.0

# Chemins qui portent le positionnement, par ordre de valeur décroissante.
PRIORITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"/(a-propos|about|qui-sommes-nous|notre-histoire|equipe|team)", "à propos"),
    (r"/(offre|offres|services|prestations|solutions|produit|produits)", "offre"),
    (r"/(tarif|tarifs|prix|pricing|abonnement)", "tarifs"),
    (r"/(cas-client|realisation|realisations|portfolio|temoignage|temoignages|clients)", "preuve sociale"),
    (r"/(blog|ressources|guides|articles|actualites)", "contenu"),
    (r"/(contact|devis|demo|rendez-vous)", "conversion"),
)

SKIP_PATTERNS = re.compile(
    r"\.(pdf|jpe?g|png|gif|svg|webp|zip|mp4|mp3|avi|docx?|xlsx?)$"
    r"|/(wp-admin|wp-json|cart|panier|checkout|compte|account|login|connexion)",
    re.IGNORECASE,
)

# Numéros français, marocains, tunisiens… : « +33 1 23 45 67 89 », « 01 23 45 67 89 ».
PHONE = re.compile(
    r"(?:\+\d{2,3}[\s.]?(?:\(0\))?\s?\d|\b0[1-9])(?:[\s.-]?\d{2}){4}\b"
    r"|\+216[\s.]?\d{2}[\s.]?\d{3}[\s.]?\d{3}\b"
)
# Mention imposée à toute publicité pour un crédit à la consommation
# (Code de la consommation, art. L312-5).
CREDIT_WARNING = re.compile(r"cr[ée]dit vous engage et doit [êe]tre rembours", re.I)

DROP_TAGS = ("head", "script", "style", "noscript", "nav", "footer", "header", "svg", "iframe", "form")


@dataclass
class SeoSignals:
    """Constats techniques bruts. Aucun jugement ici — c'est le rôle du modèle."""

    title: str
    title_length: int
    meta_description: str
    meta_description_length: int
    h1: list[str]
    h2: list[str]
    lang: str
    canonical: str
    og_tags: list[str]
    has_structured_data: bool
    word_count: int
    internal_link_count: int
    # Pour l'audit. Valeurs par défaut : les anciens appels restent valides.
    jsonld_types: list[str] = field(default_factory=list)
    images_total: int = 0
    images_missing_alt: int = 0
    noindex: bool = False
    has_viewport: bool = False
    # E-E-A-T : qui parle, comment le joindre, qui se porte garant.
    jsonld_keys: list[str] = field(default_factory=list)
    link_labels: list[str] = field(default_factory=list)
    has_tel: bool = False
    has_email: bool = False
    has_phone_text: bool = False
    has_author_meta: bool = False
    has_date_meta: bool = False
    credit_warning: bool = False


@dataclass
class Page:
    url: str
    status: int
    role: str
    text: str
    seo: SeoSignals | None = None
    links: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def title(self) -> str:
        return self.seo.title if self.seo else ""

    @property
    def word_count(self) -> int:
        return self.seo.word_count if self.seo else 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_html(url: str, html: str) -> tuple[SeoSignals, str, list[str]]:
    """Extrait les signaux SEO, le texte lisible et les liens internes.

    Séparé de la récupération réseau pour pouvoir être testé sur du HTML figé.
    """
    soup = BeautifulSoup(html, "lxml")

    title = _clean(soup.title.get_text()) if soup.title else ""

    meta_desc = ""
    tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if tag and tag.get("content"):
        meta_desc = _clean(tag["content"])

    canonical = ""
    link = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
    if link and link.get("href"):
        canonical = urljoin(url, link["href"])

    og_tags = sorted(
        {
            m["property"]
            for m in soup.find_all("meta", attrs={"property": True})
            if str(m["property"]).startswith("og:")
        }
    )

    html_tag = soup.find("html")
    lang = str(html_tag.get("lang", "")) if html_tag else ""

    jsonld_blocks = soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)})
    has_structured_data = bool(jsonld_blocks)
    jsonld_types, jsonld_keys = _jsonld_walk(jsonld_blocks)

    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not (img.get("alt") or "").strip())
    robots_meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    noindex = bool(robots_meta and "noindex" in str(robots_meta.get("content", "")).lower())
    has_viewport = bool(soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    hrefs = [str(a["href"]).strip().lower() for a in soup.find_all("a", href=True)]
    has_tel = any(h.startswith("tel:") for h in hrefs)
    has_email = any(h.startswith("mailto:") for h in hrefs)
    has_author_meta = bool(
        soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
        or soup.find(attrs={"rel": re.compile("author", re.I)})
    )
    has_date_meta = bool(
        soup.find("meta", attrs={"property": re.compile(r"^article:(published|modified)_time$", re.I)})
        or soup.find("time", attrs={"datetime": True})
    )
    link_labels: list[str] = []
    for anchor in soup.find_all("a", href=True):
        label = _clean(anchor.get_text()).lower()
        if label and len(label) < 80 and label not in link_labels:
            link_labels.append(label)
    # Coordonnées et mentions légales vivent dans le pied de page : on les
    # cherche dans la page entière, avant d'en retirer l'habillage.
    full_text = _clean(soup.get_text(separator=" "))
    has_phone_text = bool(PHONE.search(full_text))
    credit_warning = bool(CREDIT_WARNING.search(full_text))

    h1 = [_clean(h.get_text()) for h in soup.find_all("h1")][:10]
    h2 = [_clean(h.get_text()) for h in soup.find_all("h2")][:25]

    host = urlparse(url).netloc
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(url, anchor["href"]).split("#")[0]
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https") and parsed.netloc == host:
            if not SKIP_PATTERNS.search(absolute) and absolute not in links:
                links.append(absolute)

    for node in soup(list(DROP_TAGS)):
        node.decompose()
    text = _clean(soup.get_text(separator=" "))

    signals = SeoSignals(
        title=title,
        title_length=len(title),
        meta_description=meta_desc,
        meta_description_length=len(meta_desc),
        h1=h1,
        h2=h2,
        lang=lang,
        canonical=canonical,
        og_tags=og_tags,
        has_structured_data=has_structured_data,
        word_count=len(text.split()),
        internal_link_count=len(links),
        jsonld_types=jsonld_types,
        images_total=len(images),
        images_missing_alt=images_missing_alt,
        noindex=noindex,
        has_viewport=has_viewport,
        jsonld_keys=jsonld_keys,
        link_labels=link_labels[:300],
        has_tel=has_tel,
        has_email=has_email,
        has_phone_text=has_phone_text,
        has_author_meta=has_author_meta,
        has_date_meta=has_date_meta,
        credit_warning=credit_warning,
    )
    return signals, text, links


def _jsonld_types(blocks: list) -> list[str]:
    """Les types Schema.org déclarés (Organization, FAQPage…), dédoublonnés."""
    return _jsonld_walk(blocks)[0]


def _jsonld_walk(blocks: list) -> tuple[list[str], list[str]]:
    """Les types Schema.org déclarés et les propriétés renseignées
    (author, sameAs, reviewedBy…), dédoublonnés."""
    import json

    found: list[str] = []
    keys: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            kind = node.get("@type")
            for k in (kind if isinstance(kind, list) else [kind]):
                if isinstance(k, str) and k not in found:
                    found.append(k)
            for key, value in node.items():
                if not key.startswith("@") and value not in (None, "", [], {}) and key not in keys:
                    keys.append(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for block in blocks:
        try:
            walk(json.loads(block.string or block.get_text() or "{}"))
        except (ValueError, TypeError):
            if "JSON-LD invalide" not in found:
                found.append("JSON-LD invalide")
    return found, keys


def _robots(client: httpx.Client, base: str) -> RobotFileParser:
    parser = RobotFileParser()
    try:
        response = client.get(urljoin(base, "/robots.txt"))
        parser.parse(response.text.splitlines() if response.status_code == 200 else [])
    except httpx.HTTPError:
        parser.parse([])  # robots illisible : on reste prudent mais on n'échoue pas
    return parser


def _rank_links(links: list[str], home: str) -> list[tuple[str, str]]:
    """Classe les liens internes par valeur éditoriale, un seul par catégorie."""
    taken: dict[str, tuple[str, str]] = {}
    for pattern, role in PRIORITY_PATTERNS:
        for url in links:
            if url == home or role in taken:
                continue
            if re.search(pattern, urlparse(url).path, re.IGNORECASE):
                taken[role] = (url, role)
    return list(taken.values())


def fetch_page(client: httpx.Client, url: str, role: str) -> Page:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return Page(url=url, status=0, role=role, text="", error=f"{type(exc).__name__}: {exc}")

    if response.status_code >= 400:
        return Page(url=url, status=response.status_code, role=role, text="", error="HTTP error")
    if "html" not in response.headers.get("content-type", ""):
        return Page(url=url, status=response.status_code, role=role, text="", error="not HTML")

    seo, text, links = parse_html(str(response.url), response.text)
    return Page(url=str(response.url), status=response.status_code, role=role, text=text, seo=seo, links=links)


def crawl_site(url: str, max_pages: int = 6) -> list[Page]:
    """Lit l'accueil puis jusqu'à `max_pages - 1` pages à forte valeur."""
    if not urlparse(url).scheme:
        url = f"https://{url}"

    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    ) as client:
        robots = _robots(client, url)

        def allowed(target: str) -> bool:
            return robots.can_fetch(USER_AGENT, target)

        if not allowed(url):
            return [Page(url=url, status=0, role="accueil", text="", error="interdit par robots.txt")]

        home = fetch_page(client, url, "accueil")
        pages = [home]
        if home.error:
            return pages

        for target, role in _rank_links(home.links, home.url):
            if len(pages) >= max_pages:
                break
            if allowed(target):
                pages.append(fetch_page(client, target, role))

    return pages


def fetch_competitors(urls: list[str]) -> list[Page]:
    """Un seul appel par concurrent : l'accueil suffit à lire un positionnement."""
    pages: list[Page] = []
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for raw in urls:
            target = raw if urlparse(raw).scheme else f"https://{raw}"
            if _robots(client, target).can_fetch(USER_AGENT, target):
                pages.append(fetch_page(client, target, "concurrent"))
            else:
                pages.append(
                    Page(url=target, status=0, role="concurrent", text="", error="interdit par robots.txt")
                )
    return pages
