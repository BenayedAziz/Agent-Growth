"""Schéma du `brand-core` : l'ADN de la marque.

C'est la source de vérité du projet. Tous les autres outils (SEO, social, ads,
outbound) lisent ce fichier et ne réinventent jamais le positionnement, le ton
ou les piliers de contenu. Changer ce schéma, c'est changer le contrat entre
tous les outils — à faire en connaissance de cause, en incrémentant
`SCHEMA_VERSION`.

Note : les modèles envoyés au LLM n'ont volontairement **aucune valeur par
défaut**. Les structured outputs de l'API exigent que tous les champs soient
requis ; un défaut rendrait le champ optionnel et le modèle pourrait l'omettre.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

Channel = Literal[
    "seo",       # être trouvé sur Google
    "geo",       # être cité par les IA (ChatGPT, Claude, Perplexity, AI Overviews)
    "site",      # le site lui-même : structure, vitesse, conversion
    "social",    # Instagram, LinkedIn, TikTok...
    "ads",       # Google Ads, Meta Ads...
    "influence", # créateurs, partenariats
    "outbound",  # prospection sortante ciblée
    "gmb",       # fiche Google Business
    "email",     # newsletter, séquences
]

Effort = Literal["faible", "moyen", "eleve"]
Confidence = Literal["faible", "moyenne", "elevee"]


class ToneAxis(BaseModel):
    """Un curseur de ton, plus utile qu'une liste d'adjectifs."""

    axis: str = Field(description="Les deux extrêmes, ex. 'Expert <-> Accessible'")
    position: int = Field(description="0 = extrême gauche de l'axe, 10 = extrême droite")
    note: str = Field(description="Ce que ça implique concrètement à l'écriture")


class Persona(BaseModel):
    """Un client idéal (ICP). Sert autant l'inbound que l'outbound."""

    name: str = Field(description="Étiquette courte et mémorisable, ex. 'Léa, gérante de 2 salons'")
    description: str
    jobs_to_be_done: list[str] = Field(description="Ce qu'elle cherche à accomplir, dans ses mots")
    pains: list[str]
    triggers: list[str] = Field(description="Événements qui déclenchent la recherche d'une solution")
    objections: list[str]
    where_to_find_them: list[str] = Field(
        description="Endroits précis et vérifiables : groupes, salons, annuaires, sous-reddits, "
        "titres de poste LinkedIn. C'est la matière première de l'outbound."
    )
    search_intents: list[str] = Field(
        description="Requêtes qu'elle tape réellement, en langage naturel. Matière première du SEO/GEO."
    )


class Competitor(BaseModel):
    name: str
    url: str
    positioning: str
    main_angle: str = Field(description="L'argument qu'il met en avant partout")
    strengths: list[str]
    weaknesses: list[str]
    gap_to_exploit: str = Field(description="L'espace qu'il laisse vide et que la marque peut prendre")


class Pillar(BaseModel):
    """Un pilier de contenu : un territoire que la marque occupe durablement."""

    name: str
    share_of_voice_pct: int = Field(description="Part du contenu à consacrer à ce pilier (0-100)")
    why: str
    example_topics: list[str]


class Angle(BaseModel):
    """Un angle différenciant : ce que la marque peut dire et pas les autres."""

    angle: str
    why_it_differentiates: str
    proof_required: str = Field(description="La preuve à réunir pour que l'angle soit crédible")
    best_channels: list[Channel]
    risk: str


class Estimate(BaseModel):
    """Un chiffre avec sa fourchette, ses hypothèses et son origine.

    Règle du projet : aucun chiffre n'est affiché sans `assumptions` et `basis`.
    Un ordre de grandeur assumé est utile ; un chiffre faussement précis est
    nuisible.
    """

    metric: str = Field(description="Unité explicite, ex. 'visiteurs/mois', 'leads/mois', 'EUR/mois'")
    low: float
    high: float
    assumptions: list[str] = Field(description="Les hypothèses sans lesquelles le chiffre ne tient pas")
    basis: Literal["benchmark_secteur", "donnees_site", "hypothese"]


class Opportunity(BaseModel):
    """Une recommandation actionnable et chiffrée."""

    id: str = Field(description="Identifiant court en kebab-case, ex. 'seo-cluster-tarifs'")
    channel: Channel
    title: str
    plain_french: str = Field(
        description="Explication pour quelqu'un qui n'y connaît rien. Pas de jargon, "
        "ou alors expliqué dans la phrase. 2 phrases maximum."
    )
    rationale: str = Field(description="Pourquoi cette marque, maintenant — pas une généralité")
    first_step: str = Field(description="La toute première action, faisable cette semaine")
    effort: Effort
    monthly_cost: Estimate
    expected_result: Estimate
    confidence: Confidence


class EditorialLine(BaseModel):
    """La colonne vertébrale. Tout le reste s'y conforme."""

    mission: str = Field(description="Une phrase. Ce que la marque change pour ses clients.")
    promise: str = Field(description="La promesse centrale, répétable partout")
    proof_points: list[str] = Field(description="Les preuves factuelles qui soutiennent la promesse")
    tone_axes: list[ToneAxis]
    vocabulary_use: list[str] = Field(description="Mots et expressions à employer")
    vocabulary_avoid: list[str] = Field(description="Mots à bannir, y compris ceux du secteur")
    pillars: list[Pillar]
    signature_formats: list[str] = Field(description="Formats récurrents reconnaissables")
    do_not_say: list[str] = Field(description="Promesses interdites : juridique, crédibilité, marque")


class BrandCore(BaseModel):
    """Ce que le LLM produit."""

    brand_name: str
    one_liner: str = Field(description="La marque en une phrase, comme on la présenterait à un ami")
    category: str = Field(description="La catégorie dans laquelle le client la range mentalement")
    positioning_statement: str
    icp: list[Persona]
    competitors: list[Competitor]
    editorial_line: EditorialLine
    differentiating_angles: list[Angle]
    opportunities: list[Opportunity]
    quick_wins: list[str] = Field(description="Actions faisables en moins d'une heure, dès aujourd'hui")
    open_questions: list[str] = Field(
        description="Ce qui n'a pas pu être déduit des sources et qu'il faut demander à la marque. "
        "Préférer une question ouverte à une invention."
    )
    confidence_note: str = Field(description="Honnêtement : sur quoi cette analyse est solide, sur quoi elle est fragile")


class Source(BaseModel):
    """Une page réellement lue, pour que l'analyse soit auditable."""

    url: str
    title: str
    status: int
    word_count: int
    role: str = Field(description="Pourquoi cette page a été retenue, ex. 'accueil', 'concurrent'")


class BrandCoreDocument(BaseModel):
    """Le fichier `brand-core.json` tel qu'écrit sur disque."""

    schema_version: str
    generated_at: str
    model: str
    brand_url: str
    sources: list[Source]
    core: BrandCore
