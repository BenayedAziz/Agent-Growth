# Agent Growth — conventions du projet

## Ce qu'on construit

Un agent qui gère le marketing digital d'une marque — stratégie, SEO/GEO,
réseaux sociaux, publicité, prospection, mesure — avec **la ligne éditoriale
comme colonne vertébrale**. La cible est un dirigeant de TPE/PME sans formation
marketing. Vulgariser n'est donc pas de la mise en forme : c'est la
fonctionnalité.

**Produit et feuille de route : [docs/PLATEFORME.md](docs/PLATEFORME.md).**
Ambition et mécanisme de différenciation : [docs/VISION.md](docs/VISION.md).
Le produit est une console multi-marques ; les canaux (SEO, GEO, social, ads)
sont des modules (ADR-012). Catalogue des modules par canal :
[docs/FEATURES.md](docs/FEATURES.md).
Marché, concurrence, tarifs : [docs/ETUDE-MARCHE.md](docs/ETUDE-MARCHE.md).
Choix techniques : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) et
[docs/DECISIONS.md](docs/DECISIONS.md).

## La méthode de raisonnement

**On raisonne en premiers principes** : [docs/PREMIERS-PRINCIPES.md](docs/PREMIERS-PRINCIPES.md).
Avant de construire quoi que ce soit, cinq questions — et la plus coupante est
la première : *le client peut-il l'avoir gratuitement ailleurs ?* Si oui, c'est
une commodité, pas le produit.

Les deux conclusions qui commandent le code :

- **La rareté est passée de la production au jugement.** Produire est gratuit,
  donc produire ne vaut rien. Ce qui vaut : décider quoi produire, et prouver
  que ça a marché. Un module de contenu doit donc avoir un **taux de rejet
  élevé et assumé** — on produit beaucoup pour publier peu.
- **La mesure n'est pas un module, c'est le produit.** Le client peut écrire un
  post gratuitement ; il ne peut pas savoir si un euro dépensé en a rapporté
  plus d'un, tous canaux confondus. D'où : le résultat en haut des écrans,
  l'activité en dessous.

## Les règles qui ne se discutent pas

1. **Un outil ne redécide jamais du positionnement ou du ton.** Il lit
   `brands/<marque>/brand-core.json`. Si une information manque au schéma,
   on étend le schéma — on ne la devine pas dans un prompt.
2. **Aucun chiffre sans hypothèses.** Toute estimation passe par `Estimate`
   (fourchette + hypothèses + origine). Le schéma l'impose.
3. **Rien ne part sans validation humaine** : publier, dépenser, contacter,
   modifier un site. Tout passe par `store.request_approval()` ; décider passe
   par `store.decide()`. La validation automatique existe (`auto_rule`) mais
   s'active canal par canal, et une dépense automatique exige un plafond
   (ADR-015).
4. **Pas d'automatisation non officielle des réseaux sociaux.** API officielles
   uniquement. Le risque porte sur le compte du client (ADR-006).
5. **Ce qu'on ne sait pas devient une question**, pas une invention plausible.
   Le schéma a `open_questions` et `confidence_note` pour ça.
6. **Ne pas écrire ce qui existe déjà sous licence MIT.** Avant d'ouvrir un
   fichier, vérifier si une skill publique le fait déjà. Si oui : vendoriser
   (`scripts/vendor-skill.sh`) et écrire le pont. L'ingénierie se concentre sur
   les trois choses qu'aucune librairie ne fait — appliquer sur le vrai site,
   le reporting de livraison, la couche locale française (ADR-009).
7. **Chaque outil se juge en heures de livraison par client et par mois.**
   C'est la contrainte du modèle : le temps par client est la seule variable
   ajustable (ADR-008, ADR-010).
8. **Tout contenu généré qui part chez un client européen est signalé et marqué
   de façon lisible par machine.** L'article 50 de l'AI Act est en vigueur
   depuis le 2 août 2026. Ça vit dans le pipeline de publication, pas dans les
   CGV (ADR-011).
9. **On mène avec la preuve du retour, pas avec un canal.** Le GEO est mieux
   payé que le SEO (ADR-010), mais les deux restent des moyens. L'argument est
   « voilà ce qu'un euro a rapporté, tous canaux confondus » — la seule chose
   que le client ne peut pas obtenir gratuitement (ADR-014).
10. **Un écran montre le résultat avant l'activité.** Clients et coût par
   acquisition en haut ; clics, visites et abonnés en dessous, comme
   diagnostic. Et quand rien n'est mesuré, on le dit au lieu de remplir
   l'écran avec de l'activité.

## Structure

| Chemin | Rôle |
| --- | --- |
| `src/agent_growth/schemas.py` | Le contrat `brand-core`. Le modifier impacte tous les outils → incrémenter `SCHEMA_VERSION`. |
| `src/agent_growth/llm.py` | **Seul** point d'accès à Claude. Modèle, effort, refus : ici et nulle part ailleurs. |
| `src/agent_growth/crawl.py` | Lecture des sites. Respecte `robots.txt`. En-têtes HTTP en ASCII strict. |
| `src/agent_growth/render.py` | JSON → documents lisibles. Aucune logique métier. |
| `src/agent_growth/audit.py` | Audit SEO / GEO : règles vérifiables rangées en 3 piliers (Technique, On-Page, E-E-A-T). Toute règle est déclarée dans `CHECKS`, avec ce qu'on écrit quand elle passe. Aucun appel au modèle. |
| `src/agent_growth/pagespeed.py` | Vitesse : API PageSpeed Insights, Lighthouse en secours. Jamais de « non mesuré ». |
| `src/agent_growth/semantics.py` | Mots-clés : ce que dit chaque page, couverture de la liste du consultant, export Search Console. |
| `src/agent_growth/dataforseo.py` | Volumes, positions, concurrents (DataForSEO, logique reprise d'OpenSEO — `THIRD_PARTY_NOTICES.md`). Pas de scraping de Google. |
| `src/agent_growth/screamingfrog.py` | Import de l'export « Internal: All » de Screaming Frog. |
| `src/agent_growth/templates/` | Rapports clients. Couleurs et polices en variables CSS : la charte graphique de l'outil les remplacera. |
| `src/agent_growth/schema.sql` | Les 13 tables de la console. Une colonne ajoutée après coup va aussi dans `_ADDED_COLUMNS` de `store.py`, sinon la base de production casse. |
| `src/agent_growth/store.py` | Seul accès à la base. **Aucun secret n'y entre** : `secret_ref` est un nom de variable, jamais une valeur. |
| `src/agent_growth/console/` | Les écrans. Rendu serveur, Jinja. Starlette 1.6 exige `TemplateResponse(request, nom, contexte)`. Mot de passe obligatoire en ligne, contrôle d'origine sur tout POST. |
| `src/agent_growth/autonomy/` | Le planificateur et le bot Telegram. **Seul `TELEGRAM_OWNER_ID` décide.** Une tâche = un nom, une cadence, une fonction ; chaque exécution va dans `job_run`. |
| `src/agent_growth/sites/` | Un adaptateur d'écriture par plateforme. Sans accès configuré, retombe en mode manuel. Le marquage IA (`AI_MARK_HTML`) est défini dans `base.py` et nulle part ailleurs. |
| `src/agent_growth/tools/` | Un fichier par outil. Le prompt système y vit — c'est l'actif principal. |
| `skills/<nom>/SKILL.md` | Quand lancer l'outil et quoi faire du résultat. Jamais de logique. |
| `skills/vendor/` | Skills externes copiées et épinglées. À relire avant activation. |
| `brands/` | Données clients. **Ignoré par Git.** |

## Ajouter un outil

1. Étendre `schemas.py` si l'outil produit un nouveau type de résultat.
2. Créer `src/agent_growth/tools/<nom>.py` avec un prompt système explicite et
   une fonction `run()` qui renvoie un objet Pydantic.
3. Ajouter la sous-commande dans `cli.py`.
4. Ajouter le rendu lisible dans `render.py` si le client doit lire le résultat.
5. Écrire `skills/<nom>/SKILL.md`.
6. Écrire des tests qui **ne requièrent pas l'API** : construction du prompt,
   parsing, rendu. Un fixture figé suffit (voir `tests/conftest.py`).

## Prompts

Le prompt système d'un outil est du code : il est relu, versionné, et modifié
avec intention. Les prompts de ce projet imposent systématiquement :

- le français clair, le tutoiement, zéro jargon non expliqué dans la phrase ;
- la spécificité — une phrase qui marcherait pour n'importe quel concurrent est
  une phrase à supprimer ;
- le refus d'inventer, et le renvoi vers `open_questions` ;
- des fourchettes avec hypothèses, jamais de chiffre seul ;
- une première action faisable cette semaine, sans budget ni prestataire.

## Tests

```bash
python3 -m pytest -q          # rapide, aucun appel API, aucun réseau
ag inspect https://unsite.fr  # vérifier le crawler en vrai
ag brand-core URL --dry-run   # vérifier le prompt sans dépenser
```

Les tests ne doivent jamais appeler l'API ni le réseau. Pour tester un rendu,
utiliser le fixture `doc` de `tests/conftest.py`. Pour une API externe
(Telegram, WordPress, Shopify, GitHub), `httpx2.MockTransport` — voir
`tests/test_sites.py`.

Les fichiers non Python (gabarits, `schema.sql`) doivent figurer dans
`[tool.setuptools.package-data]` de `pyproject.toml`, sinon le déploiement
plante alors que tout marche en local.

Mise en ligne : [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).

## Modèle

`claude-opus-5-5` par défaut, surchargeable par `AG_MODEL`. Structured outputs
via `client.messages.parse()` + schéma Pydantic : on reçoit un objet validé, pas
du JSON à parser. `effort: "high"` sur l'analyse stratégique — le défaut du
modèle (`medium`) est trop bas.
