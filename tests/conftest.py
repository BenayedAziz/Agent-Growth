"""Un brand-core complet et figé, pour tester le rendu sans appeler l'IA."""

from __future__ import annotations

import pytest

from agent_growth.schemas import (
    SCHEMA_VERSION,
    Angle,
    BrandCore,
    BrandCoreDocument,
    Competitor,
    EditorialLine,
    Estimate,
    Opportunity,
    Persona,
    Pillar,
    Source,
    ToneAxis,
)


@pytest.fixture
def doc() -> BrandCoreDocument:
    return BrandCoreDocument(
        schema_version=SCHEMA_VERSION,
        generated_at="2026-10-11T09:00:00+00:00",
        model="claude-opus-5-5",
        brand_url="https://salonlea.fr",
        sources=[
            Source(url="https://salonlea.fr/", title="Salon Léa", status=200, word_count=410, role="accueil"),
            Source(url="https://rival.fr/", title="Rival", status=200, word_count=250, role="concurrent"),
        ],
        core=BrandCore(
            brand_name="Salon Léa",
            one_liner="Deux salons de coiffure à Lyon, spécialisés dans le cheveu bouclé.",
            category="Coiffure de quartier spécialisée",
            positioning_statement="Le seul salon lyonnais qui ne coupe les boucles qu'à sec.",
            icp=[
                Persona(
                    name="Inès, cheveux bouclés, 29 ans",
                    description="Lassée des coiffeurs qui lissent ses boucles avant de couper.",
                    jobs_to_be_done=["Trouver un coiffeur qui comprend ses boucles"],
                    pains=["Coupes ratées", "Devoir tout réexpliquer"],
                    triggers=["Une coupe ratée ailleurs", "Un mariage"],
                    objections=["Trop cher", "Trop loin"],
                    where_to_find_them=["Groupes Facebook boucles Lyon", "Hashtag #curlylyon"],
                    search_intents=["coiffeur boucles lyon", "coupe à sec cheveux bouclés"],
                )
            ],
            competitors=[
                Competitor(
                    name="Rival",
                    url="https://rival.fr",
                    positioning="Salon généraliste pas cher",
                    main_angle="Le prix",
                    strengths=["Très visible sur Google"],
                    weaknesses=["Aucune spécialité affichée"],
                    gap_to_exploit="Personne ne revendique l'expertise boucles à Lyon.",
                )
            ],
            editorial_line=EditorialLine(
                mission="Rendre les boucles faciles à vivre au quotidien.",
                promise="Vos boucles, coupées à sec, par quelqu'un qui en a.",
                proof_points=["Formation Curly Method", "900 clientes bouclées depuis 2019"],
                tone_axes=[
                    ToneAxis(axis="Expert <-> Accessible", position=7, note="On explique, on ne récite pas."),
                    ToneAxis(axis="Sérieux <-> Complice", position=6, note="Tutoiement, zéro condescendance."),
                ],
                vocabulary_use=["boucles", "coupe à sec", "routine"],
                vocabulary_avoid=["discipliner", "dompter", "indomptable"],
                pillars=[
                    Pillar(name="Avant / après", share_of_voice_pct=40, why="La preuve visuelle convertit.",
                           example_topics=["Transformation sur boucles 3B", "Rattrapage de coupe ratée"]),
                    Pillar(name="Pédagogie boucles", share_of_voice_pct=35, why="Crée la confiance avant la visite.",
                           example_topics=["Pourquoi couper à sec", "Choisir son gel"]),
                    Pillar(name="Coulisses du salon", share_of_voice_pct=25, why="Humanise l'équipe.",
                           example_topics=["Une journée au salon"]),
                ],
                signature_formats=["Le avant/après du mardi", "La question boucles du vendredi"],
                do_not_say=["Promettre un résultat sans diagnostic", "Garantir une tenue de X jours"],
            ),
            differentiating_angles=[
                Angle(
                    angle="La seule coupe à sec de Lyon",
                    why_it_differentiates="Aucun concurrent local ne le revendique.",
                    proof_required="Photos avant/après et diplôme affichés.",
                    best_channels=["social", "seo", "gmb"],
                    risk="Tenable seulement si toutes les coiffeuses sont formées.",
                )
            ],
            opportunities=[
                Opportunity(
                    id="seo-coiffeur-boucles-lyon",
                    channel="seo",
                    title="Créer la page « coiffeur cheveux bouclés à Lyon »",
                    plain_french="Une page dédiée à cette recherche précise, pour apparaître sur Google "
                                 "quand quelqu'un la tape depuis Lyon.",
                    rationale="Le site n'a aucune page sur ce terme, et aucun concurrent lyonnais non plus.",
                    first_step="Écrire la page avec trois avant/après et l'adresse du salon.",
                    effort="faible",
                    monthly_cost=Estimate(metric="EUR/mois", low=0, high=0,
                                          assumptions=["Page écrite en interne"], basis="hypothese"),
                    expected_result=Estimate(metric="visites/mois", low=40, high=120,
                                             assumptions=["~300 recherches/mois sur l'agglomération",
                                                          "Position 3 à 6 atteinte en 4 mois"],
                                             basis="benchmark_secteur"),
                    confidence="moyenne",
                )
            ],
            quick_wins=["Ajouter « cheveux bouclés » au titre de la fiche Google Business"],
            open_questions=["Combien de coiffeuses sont formées à la coupe à sec ?"],
            confidence_note="Positionnement solide (lu sur le site). Volumes de recherche estimés.",
        ),
    )
