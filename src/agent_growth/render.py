"""Du JSON vers des documents lisibles.

`brand-core.json` est le contrat machine. Mais personne ne lit du JSON, et une
ligne éditoriale que le dirigeant ne lit pas n'est pas appliquée. On produit
donc deux documents à partir de la même source :

- `brand-core.md` : le document de référence, en français clair ;
- `voice.md` : la fiche de voix, au format attendu par les skills de
  rédaction (Instagram, LinkedIn...), pour qu'ils héritent du ton sans
  configuration manuelle.
"""

from __future__ import annotations

from .schemas import BrandCoreDocument, Estimate

EFFORT_LABEL = {"faible": "effort faible", "moyen": "effort moyen", "eleve": "effort élevé"}
CONFIDENCE_LABEL = {"faible": "confiance faible", "moyenne": "confiance moyenne", "elevee": "confiance élevée"}
BASIS_LABEL = {
    "donnees_site": "lu sur le site",
    "benchmark_secteur": "ordre de grandeur du secteur",
    "hypothese": "hypothèse",
}
CHANNEL_LABEL = {
    "seo": "SEO (être trouvé sur Google)",
    "geo": "GEO (être cité par les IA)",
    "site": "Site",
    "social": "Réseaux sociaux",
    "ads": "Publicité payante",
    "influence": "Influence & partenariats",
    "outbound": "Prospection sortante",
    "gmb": "Fiche Google Business",
    "email": "E-mail",
}


def _num(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") if abs(value) >= 10 else f"{value:.2f}".rstrip("0").rstrip(".")


def _estimate(est: Estimate) -> str:
    """« 40 à 120 visites/mois (…) » — ou un seul chiffre quand la fourchette est nulle."""
    origin = BASIS_LABEL.get(est.basis, est.basis)
    if est.low == est.high == 0:
        return f"aucun coût en argent ({origin})"
    if est.low == est.high:
        return f"{_num(est.low)} {est.metric} ({origin})"
    return f"{_num(est.low)} à {_num(est.high)} {est.metric} ({origin})"


def to_markdown(doc: BrandCoreDocument) -> str:
    core = doc.core
    line = core.editorial_line
    out: list[str] = []
    add = out.append

    add(f"# Brand core — {core.brand_name}\n")
    add(f"> {core.one_liner}\n")
    add(
        f"*Généré le {doc.generated_at[:10]} · modèle `{doc.model}` · "
        f"schéma v{doc.schema_version} · {len(doc.sources)} sources lues*\n"
    )
    add("**À lire avant tout le reste.** Chaque post, chaque page et chaque annonce "
        "produits par Agent Growth découlent de ce document.\n")

    add("## En une minute\n")
    add(f"- **Catégorie** : {core.category}")
    add(f"- **Positionnement** : {core.positioning_statement}")
    add(f"- **Promesse** : {line.promise}")
    add(f"- **Mission** : {line.mission}\n")

    if core.quick_wins:
        add("## À faire aujourd'hui\n")
        add("Des actions de moins d'une heure, sans budget.\n")
        for item in core.quick_wins:
            add(f"- [ ] {item}")
        add("")

    add("## Ligne éditoriale\n")
    add("### Ton\n")
    for axis in line.tone_axes:
        filled = max(0, min(10, axis.position))
        add(f"- **{axis.axis}** — `{'●' * filled}{'○' * (10 - filled)}` {filled}/10 · {axis.note}")
    add("")
    add("### Mots\n")
    add(f"- **À employer** : {', '.join(line.vocabulary_use) or '—'}")
    add(f"- **À bannir** : {', '.join(line.vocabulary_avoid) or '—'}\n")

    add("### Piliers de contenu\n")
    add("| Pilier | Part | Pourquoi | Exemples de sujets |")
    add("| --- | --- | --- | --- |")
    for pillar in line.pillars:
        topics = " · ".join(pillar.example_topics[:3])
        add(f"| **{pillar.name}** | {pillar.share_of_voice_pct} % | {pillar.why} | {topics} |")
    add("")

    if line.signature_formats:
        add("### Formats signature\n")
        for fmt in line.signature_formats:
            add(f"- {fmt}")
        add("")

    add("### Preuves à l'appui\n")
    for proof in line.proof_points:
        add(f"- {proof}")
    add("")

    if line.do_not_say:
        add("### À ne jamais dire\n")
        for item in line.do_not_say:
            add(f"- {item}")
        add("")

    add("## À qui on parle\n")
    for persona in core.icp:
        add(f"### {persona.name}\n")
        add(f"{persona.description}\n")
        add(f"- **Ce qu'elle cherche à faire** : {' · '.join(persona.jobs_to_be_done)}")
        add(f"- **Ce qui la bloque** : {' · '.join(persona.pains)}")
        add(f"- **Ce qui la fait bouger** : {' · '.join(persona.triggers)}")
        add(f"- **Ce qu'elle objecte** : {' · '.join(persona.objections)}")
        add(f"- **Ce qu'elle tape sur Google** : {' · '.join(persona.search_intents)}")
        add(f"- **Où la trouver** : {' · '.join(persona.where_to_find_them)}\n")
    add(
        "> Les deux dernières lignes sont les deux moitiés d'un même travail : "
        "ce qu'elle tape nourrit le contenu qui la fait venir, où elle se trouve "
        "nourrit la prospection qui va la chercher.\n"
    )

    add("## Angles différenciants\n")
    for angle in core.differentiating_angles:
        add(f"### {angle.angle}\n")
        add(f"- **Pourquoi ça nous distingue** : {angle.why_it_differentiates}")
        add(f"- **Preuve à réunir** : {angle.proof_required}")
        add(f"- **Canaux** : {', '.join(CHANNEL_LABEL.get(c, c) for c in angle.best_channels)}")
        add(f"- **Risque** : {angle.risk}\n")

    add("## Concurrents\n")
    for comp in core.competitors:
        add(f"### {comp.name} — <{comp.url}>\n")
        add(f"- **Positionnement** : {comp.positioning}")
        add(f"- **Son argument** : {comp.main_angle}")
        add(f"- **Ses forces** : {' · '.join(comp.strengths)}")
        add(f"- **Ses faiblesses** : {' · '.join(comp.weaknesses)}")
        add(f"- **L'espace à prendre** : {comp.gap_to_exploit}\n")

    add("## Opportunités chiffrées\n")
    add(
        "Les fourchettes sont des ordres de grandeur, pas des promesses. "
        "Chaque ligne indique d'où vient le chiffre et à quelles conditions il tient.\n"
    )
    for i, opp in enumerate(core.opportunities, 1):
        add(f"### {i}. {opp.title}\n")
        add(f"**{CHANNEL_LABEL.get(opp.channel, opp.channel)}** · "
            f"{EFFORT_LABEL.get(opp.effort, opp.effort)} · "
            f"{CONFIDENCE_LABEL.get(opp.confidence, opp.confidence)}\n")
        add(f"{opp.plain_french}\n")
        add(f"- **Pourquoi nous, maintenant** : {opp.rationale}")
        add(f"- **Coût** : {_estimate(opp.monthly_cost)}")
        add(f"- **Résultat attendu** : {_estimate(opp.expected_result)}")
        add("- **Hypothèses retenues** :")
        for assumption in dict.fromkeys(opp.monthly_cost.assumptions + opp.expected_result.assumptions):
            add(f"  - {assumption}")
        add(f"- **Première action** : {opp.first_step}\n")

    if core.open_questions:
        add("## Ce qu'il nous manque\n")
        add("Réponds à ces questions et l'analyse gagnera en précision.\n")
        for question in core.open_questions:
            add(f"- {question}")
        add("")

    add("## Fiabilité de cette analyse\n")
    add(f"{core.confidence_note}\n")

    add("## Sources lues\n")
    add("| Rôle | Page | Statut | Mots |")
    add("| --- | --- | --- | --- |")
    for src in doc.sources:
        label = src.title or "(sans titre)"
        add(f"| {src.role} | [{label}]({src.url}) | {src.status or 'erreur'} | {src.word_count} |")
    add("")

    return "\n".join(out)


def to_voice(doc: BrandCoreDocument) -> str:
    """Fiche de voix destinée aux skills de rédaction.

    Format aligné sur la convention `templates/voice.md` des skills de contenu
    (Instagram, LinkedIn...) : les brancher sur cette marque ne demande aucune
    saisie manuelle.
    """
    core = doc.core
    line = core.editorial_line
    out: list[str] = []
    add = out.append

    add(f"# Voix de la marque — {core.brand_name}\n")
    add("<!-- Généré par Agent Growth depuis brand-core.json. Ne pas éditer à la main : -->")
    add("<!-- relancer `ag brand-core` ou modifier brand-core.json. -->\n")

    add("## Qui je suis\n")
    add(f"{core.one_liner}\n")
    add(f"Catégorie : {core.category}")
    add(f"Promesse : {line.promise}\n")

    add("## À qui je parle\n")
    for persona in core.icp:
        add(f"- **{persona.name}** — {persona.description}")
        add(f"  - Ce qui la bloque : {' · '.join(persona.pains)}")
        add(f"  - Ce qui la fait bouger : {' · '.join(persona.triggers)}")
    add("")

    add("## Comment j'écris\n")
    for axis in line.tone_axes:
        add(f"- {axis.axis} → {axis.position}/10. {axis.note}")
    add("")
    add(f"Mots à employer : {', '.join(line.vocabulary_use) or '—'}")
    add(f"Mots à bannir : {', '.join(line.vocabulary_avoid) or '—'}\n")

    add("## De quoi je parle\n")
    for pillar in line.pillars:
        add(f"- **{pillar.name}** ({pillar.share_of_voice_pct} %) — {' · '.join(pillar.example_topics[:4])}")
    add("")

    if line.signature_formats:
        add("## Mes formats récurrents\n")
        for fmt in line.signature_formats:
            add(f"- {fmt}")
        add("")

    add("## Ce que je peux prouver\n")
    for proof in line.proof_points:
        add(f"- {proof}")
    add("")

    add("## Ce que je ne dis jamais\n")
    for item in line.do_not_say:
        add(f"- {item}")
    for item in line.vocabulary_avoid:
        add(f"- Le mot « {item} »")
    add("")

    add("## Mes angles\n")
    for angle in core.differentiating_angles:
        add(f"- {angle.angle} — {angle.why_it_differentiates}")
    add("")

    return "\n".join(out)


def audit_html(report: dict) -> str:
    """Rapport d'audit client, une page HTML autonome et imprimable.

    `report` sort de `audit.report()` : toute la mise en ordre est faite là-bas,
    le gabarit ne fait que poser le texte.
    """
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(loader=PackageLoader("agent_growth", "templates"),
                      autoescape=select_autoescape(["html"]))
    return env.get_template("audit_report.html").render(r=report)
