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

    has_structured_data = bool(soup.find("script", attrs={"type": re.compile(r"ld\+json", re.I)}))

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
    )
    return signals, text, links


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
