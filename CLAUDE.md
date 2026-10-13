# Agent Growth — conventions du projet

## Ce qu'on construit

Un agent qui gère le marketing digital d'une marque — stratégie, SEO/GEO,
réseaux sociaux, publicité, prospection, mesure — avec **la ligne éditoriale
comme colonne vertébrale**. La cible est un dirigeant de TPE/PME sans formation
marketing. Vulgariser n'est donc pas de la mise en forme : c'est la
fonctionnalité.

Périmètre et ordre des lots : [docs/FEATURES.md](docs/FEATURES.md).
Choix techniques : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) et
[docs/DECISIONS.md](docs/DECISIONS.md).

## Les règles qui ne se discutent pas

1. **Un outil ne redécide jamais du positionnement ou du ton.** Il lit
   `brands/<marque>/brand-core.json`. Si une information manque au schéma,
   on étend le schéma — on ne la devine pas dans un prompt.
2. **Aucun chiffre sans hypothèses.** Toute estimation passe par `Estimate`
   (fourchette + hypothèses + origine). Le schéma l'impose.
3. **Rien ne part sans validation humaine** : publier, dépenser, contacter.
4. **Pas d'automatisation non officielle des réseaux sociaux.** API officielles
   uniquement. Le risque porte sur le compte du client (ADR-006).
5. **Ce qu'on ne sait pas devient une question**, pas une invention plausible.
   Le schéma a `open_questions` et `confidence_note` pour ça.
6. **Ne pas écrire ce qui existe déjà sous licence MIT.** Avant d'ouvrir un
   fichier, vérifier si une skill publique le fait déjà. Si oui : vendoriser
   (`scripts/vendor-skill.sh`) et écrire le pont. L'ingénierie se concentre sur
   les trois choses qu'aucune librairie ne fait — appliquer sur le vrai site,
   le reporting de livraison, la couche locale française (ADR-009).
7. **Chaque outil se juge en heures de livraison par client et par mois.** Le
   modèle est un abonnement à prix bas avec un humain derrière : le prix ne peut
   pas monter, donc seul le temps est ajustable (ADR-008).

## Structure

| Chemin | Rôle |
| --- | --- |
| `src/agent_growth/schemas.py` | Le contrat `brand-core`. Le modifier impacte tous les outils → incrémenter `SCHEMA_VERSION`. |
| `src/agent_growth/llm.py` | **Seul** point d'accès à Claude. Modèle, effort, refus : ici et nulle part ailleurs. |
| `src/agent_growth/crawl.py` | Lecture des sites. Respecte `robots.txt`. En-têtes HTTP en ASCII strict. |
| `src/agent_growth/render.py` | JSON → documents lisibles. Aucune logique métier. |
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
utiliser le fixture `doc` de `tests/conftest.py`.

## Modèle

`claude-opus-5-5` par défaut, surchargeable par `AG_MODEL`. Structured outputs
via `client.messages.parse()` + schéma Pydantic : on reçoit un objet validé, pas
du JSON à parser. `effort: "high"` sur l'analyse stratégique — le défaut du
modèle (`medium`) est trop bas.
