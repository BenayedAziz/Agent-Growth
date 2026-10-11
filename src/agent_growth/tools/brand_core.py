"""Outil 1 — `brand-core` : construire la ligne éditoriale de la marque.

C'est le premier outil parce que c'est celui dont tous les autres dépendent. Il
lit le site de la marque et ceux de ses concurrents, puis produit un
`brand-core.json` : positionnement, ICP, ligne éditoriale, angles
différenciants, et des opportunités chiffrées par canal.

Aucun autre outil ne redécide du ton ou du positionnement : ils lisent ce
fichier. C'est ce qui garantit que le site, les réseaux, la fiche Google et les
pubs racontent la même histoire.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..crawl import Page, crawl_site, fetch_competitors
from ..llm import structured
from ..schemas import SCHEMA_VERSION, BrandCore, BrandCoreDocument, Source

#: Caractères de texte retenus par page. Au-delà, un site répète son message.
TEXT_BUDGET = 6_000

SYSTEM = """\
Tu es stratège de marque. Tu travailles pour des dirigeants de TPE et PME qui \
n'ont aucune formation en marketing et très peu de temps. Ton travail est jugé \
sur une seule chose : est-ce que cette personne peut agir demain matin.

Comment tu écris
- En français, à la deuxième personne du singulier, comme un associé qui \
explique, pas comme un consultant qui impressionne.
- Zéro jargon non expliqué. Si un terme technique est indispensable (SEO, CPC, \
ICP, tunnel), tu l'expliques dans la phrase même où tu l'emploies, une fois.
- Concret et spécifique à CETTE marque. Une phrase qui marcherait pour \
n'importe quel concurrent est une phrase à supprimer.

Honnêteté
- Tu ne t'appuies que sur les sources fournies. Tu n'inventes ni chiffre \
d'affaires, ni effectif, ni client, ni récompense.
- Ce que les sources ne disent pas va dans `open_questions`, sous forme de \
question posée à la marque. Une bonne question vaut mieux qu'une invention \
plausible.
- `confidence_note` dit franchement où l'analyse est solide et où elle est \
fragile.

Les chiffres
- Chaque `Estimate` est une fourchette, jamais un chiffre unique.
- `assumptions` liste les hypothèses sans lesquelles la fourchette ne tient \
pas (volume de recherche supposé, panier moyen, taux de conversion retenu).
- `basis` dit d'où ça vient : `donnees_site` si c'est lu sur le site, \
`benchmark_secteur` si c'est un ordre de grandeur usuel du secteur, \
`hypothese` sinon.
- Un ordre de grandeur assumé est utile. Un chiffre faussement précis détruit \
la confiance. En cas de doute, élargis la fourchette et baisse `confidence`.

La ligne éditoriale est la colonne vertébrale
- Elle doit être assez précise pour qu'un post Instagram, une page de site et \
une annonce Google écrits séparément sonnent comme la même marque.
- Les piliers couvrent ~100 % en `share_of_voice_pct`, et chacun est un \
territoire défendable, pas un thème générique.
- `vocabulary_avoid` et `do_not_say` sont aussi importants que le reste : ce \
sont eux qui empêchent la marque de redevenir banale.

Les opportunités
- Entre 6 et 10, réparties sur plusieurs canaux. Classe-les de la plus \
rentable à la moins rentable au regard de l'effort.
- Relie systématiquement ce que la marque publie (inbound : être trouvée) et \
qui elle va chercher (outbound : aller chercher). Les `search_intents` d'un \
persona alimentent le SEO ; son `where_to_find_them` alimente la prospection. \
Ce sont deux usages du même travail de ciblage.
- Quand tu proposes une création (annonce, visuel, accroche), propose de la \
tester en plusieurs variantes avant de dépenser : c'est moins cher de jeter \
trois accroches que de payer une campagne qui ne parle à personne.
- `first_step` est une action unique, faisable cette semaine, sans budget ni \
prestataire.
"""


def _page_block(page: Page) -> str:
    if page.error:
        return f"### {page.role} — {page.url}\n(non lisible : {page.error})\n"

    seo = page.seo
    lines = [f"### {page.role} — {page.url}"]
    if seo:
        lines += [
            f"- title ({seo.title_length} car.) : {seo.title or '(absent)'}",
            f"- meta description ({seo.meta_description_length} car.) : {seo.meta_description or '(absente)'}",
            f"- H1 : {' | '.join(seo.h1) or '(aucun)'}",
            f"- H2 : {' | '.join(seo.h2[:12]) or '(aucun)'}",
            f"- lang : {seo.lang or '(non déclarée)'} · canonical : {seo.canonical or '(absente)'}",
            f"- balises Open Graph : {', '.join(seo.og_tags) or '(aucune)'}",
            f"- données structurées JSON-LD : {'oui' if seo.has_structured_data else 'non'}",
            f"- volume : {seo.word_count} mots · {seo.internal_link_count} liens internes",
        ]
    lines.append(f"\nTexte de la page :\n{page.text[:TEXT_BUDGET]}\n")
    return "\n".join(lines)


def build_prompt(
    brand_url: str,
    pages: list[Page],
    competitor_pages: list[Page],
    notes: str = "",
) -> str:
    parts = [
        f"Marque à analyser : {brand_url}",
        "",
        "Voici tout ce qui a pu être lu. Les constats techniques (title, meta, "
        "H1, données structurées) sont bruts : à toi de dire ce qu'ils valent.",
        "",
        "## Pages du site",
        "",
    ]
    parts += [_page_block(p) for p in pages]

    if competitor_pages:
        parts += ["## Concurrents", ""]
        parts += [_page_block(p) for p in competitor_pages]
    else:
        parts += [
            "## Concurrents",
            "",
            "Aucun concurrent fourni. Déduis 2 à 4 concurrents plausibles à partir "
            "de la catégorie et du marché, et dis-le dans `confidence_note` : "
            "ces fiches sont des hypothèses, pas des observations.",
            "",
        ]

    if notes.strip():
        parts += [
            "## Ce que la marque nous a dit",
            "",
            "Ces informations viennent du dirigeant. Elles priment sur ce que "
            "laisse deviner le site.",
            "",
            notes.strip(),
            "",
        ]

    parts.append(
        "Produis le brand-core complet. Souviens-toi que la personne qui te lit "
        "n'y connaît rien et doit pouvoir agir demain matin."
    )
    return "\n".join(parts)


def run(
    brand_url: str,
    competitors: list[str] | None = None,
    max_pages: int = 6,
    notes: str = "",
) -> BrandCoreDocument:
    """Analyse la marque et renvoie son brand-core."""
    pages = crawl_site(brand_url, max_pages=max_pages)
    if pages and pages[0].error:
        raise RuntimeError(
            f"Impossible de lire {pages[0].url} ({pages[0].error}). "
            "Vérifie l'adresse, ou que le site est bien en ligne."
        )

    competitor_pages = fetch_competitors(competitors or [])

    core, served_by = structured(
        system=SYSTEM,
        prompt=build_prompt(brand_url, pages, competitor_pages, notes),
        output_model=BrandCore,
    )

    return BrandCoreDocument(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        model=served_by,
        brand_url=brand_url,
        sources=[
            Source(
                url=p.url,
                title=p.title,
                status=p.status,
                word_count=p.word_count,
                role=p.role,
            )
            for p in pages + competitor_pages
        ],
        core=core,
    )
