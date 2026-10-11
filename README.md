# Agent Growth

Le marketing digital d'une marque, piloté par sa ligne éditoriale.

Stratégie, SEO/GEO, réseaux sociaux, publicité, prospection et mesure — pour des
dirigeants qui n'ont pas de formation marketing et pas de temps. Chaque
recommandation arrive en français clair, avec une fourchette chiffrée, ses
hypothèses, et une première action faisable cette semaine.

> **État du projet.** Le socle est livré : l'outil `brand-core`, qui construit
> la ligne éditoriale dont tout le reste dépend. Le périmètre complet et l'ordre
> des lots sont dans [docs/FEATURES.md](docs/FEATURES.md).

## L'idée en une image

```
                      ┌─────────────────────┐
                      │   brand-core.json   │
                      │  (ligne éditoriale) │
                      └──────────┬──────────┘
          ┌──────────────┬───────┴───────┬──────────────┐
          ▼              ▼               ▼              ▼
      SEO / GEO       Social           Ads          Outbound
       + Site        + Fiche Google   + Visuels    + Séquences
          └─────────────┴───────┬───────┴──────────────┘
                                ▼
                     Cohérence  +  Mesure
```

Un seul fichier porte le positionnement, le ton, les piliers de contenu et les
interdits. Tous les outils le lisent ; aucun ne le redécide. C'est ce qui fait
que le site, les réseaux, la fiche Google et les pubs racontent la même
histoire — mécaniquement, et pas par discipline.

## Installation

```bash
git clone https://github.com/BenayedAziz/Agent-Growth
cd Agent-Growth
pip install -e .

cp .env.example .env     # puis renseigne ANTHROPIC_API_KEY
```

## Démarrer

```bash
# 1. Voir ce que l'agent lit du site. Gratuit : aucun appel au modèle.
ag inspect https://lamarque.fr

# 2. Construire la ligne éditoriale.
ag brand-core https://lamarque.fr \
  --competitor https://concurrent-1.fr \
  --competitor https://concurrent-2.fr \
  --notes "On ne travaille que le cheveu bouclé, et on coupe à sec."

# 3. Lire le résultat.
open brands/lamarque-fr/brand-core.md
```

Trois fichiers sont écrits dans `brands/lamarque-fr/` :

| Fichier | Pour qui |
| --- | --- |
| `brand-core.json` | Les autres outils. C'est le contrat. |
| `brand-core.md` | Le client. C'est ce qu'on lui envoie. |
| `voice.md` | Les outils de rédaction. Ils héritent du ton sans réglage. |

Pas d'accord avec une conclusion ? Modifie le JSON, puis
`ag render brands/lamarque-fr/brand-core.json`. Un brand-core corrigé par le
client vaut mieux qu'un brand-core régénéré par le modèle.

### Ce que produit `brand-core`

- **Positionnement** et catégorie dans laquelle le client range la marque
- **Clients idéaux**, avec pour chacun ce qu'il tape sur Google *et* où il se
  trouve — les deux moitiés d'un même ciblage, l'une pour l'inbound, l'autre
  pour l'outbound
- **Analyse concurrentielle** et espace laissé libre
- **Ligne éditoriale** : mission, promesse, preuves, curseurs de ton, vocabulaire
  à employer et à bannir, piliers avec leur part de voix, formats signature,
  interdits
- **Angles différenciants**, avec la preuve à réunir et le risque
- **6 à 10 opportunités chiffrées** par canal, classées par rentabilité
- **Questions ouvertes** — ce qui n'a pas pu être déduit, plutôt qu'inventé

## Les principes

1. **La ligne éditoriale est un contrat, pas une suggestion.**
2. **Aucun chiffre sans ses hypothèses.** Fourchette, hypothèses, origine. Un
   ordre de grandeur assumé est utile ; un chiffre faussement précis détruit la
   confiance.
3. **Vulgariser est une fonctionnalité**, pas de la mise en forme.
4. **Rien ne part sans validation humaine** : publier, dépenser, contacter.
5. **Des fichiers, pas de base de données.** Relisibles, corrigeables,
   versionnables, envoyables au client.
6. **Pré-tester avant de dépenser.** Jeter trois accroches coûte moins cher
   qu'une campagne qui ne parle à personne.

Le détail et le pourquoi : [docs/DECISIONS.md](docs/DECISIONS.md).

## Réutiliser des skills existantes

Une bonne partie du savoir-faire rédactionnel par réseau existe déjà en open
source. On le réutilise plutôt que de le réécrire :

```bash
./scripts/vendor-skill.sh https://github.com/auteur/depot-skill ig
```

Le script copie la skill dans `skills/vendor/<nom>/` et épingle son commit. On
copie au lieu de dépendre : une skill est faite d'instructions que Claude suit
et de scripts qu'il exécute, donc une modification en amont changerait le
comportement du produit sans décision de notre part.

⚠ **Rien n'est activé automatiquement.** Chaque `SKILL.md` et chaque script se
lisent avant usage — procédure dans
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#brancher-une-skill-externe).

Ces skills font gagner la **couche création**. Elles ne font pas gagner l'agent :
la stratégie, le chiffrage, les corrections sur le site, le pilotage des
campagnes, la cohérence et la mesure restent le produit. Et elles ne publient
pas — la publication passe par les API officielles des réseaux
([ADR-004](docs/DECISIONS.md#adr-004--réutiliser-les-skills-de-rédaction-existantes)).

## Développer

```bash
pip install -e ".[dev]"
python3 -m pytest -q             # rapide, sans appel API ni réseau
ag brand-core URL --dry-run      # voir le prompt sans dépenser
```

Conventions et procédure d'ajout d'un outil : [CLAUDE.md](CLAUDE.md).

## Documentation

| Document | Contenu |
| --- | --- |
| [docs/FEATURES.md](docs/FEATURES.md) | Les fonctionnalités clés, par lot, avec leur état |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | L'infrastructure, et comment brancher des skills externes |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Les choix structurants et leur raison |
| [CLAUDE.md](CLAUDE.md) | Conventions de contribution |
