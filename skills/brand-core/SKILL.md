---
name: brand-core
description: >
  Construire ou relire la ligne éditoriale d'une marque : positionnement, clients
  idéaux, analyse concurrentielle, ton, piliers de contenu, angles différenciants
  et opportunités chiffrées par canal. À utiliser au démarrage de toute marque,
  et avant tout travail de SEO, de réseaux sociaux, de publicité ou de
  prospection — ces outils lisent le brand-core et ne redécident pas du
  positionnement. Se déclenche sur : nouvelle marque, nouveau client, « quelle
  est notre ligne éditoriale », « analyse ce site », « qui sont nos concurrents »,
  « par où commencer », « sur quoi communiquer », ou toute demande de contenu
  pour une marque dont le brand-core n'existe pas encore.
---

# Brand core — la ligne éditoriale de la marque

## Pourquoi cet outil passe avant les autres

Sans ligne éditoriale écrite, chaque contenu réinvente la marque. Le post
Instagram, la page du site et l'annonce Google finissent par raconter trois
histoires différentes. Cet outil écrit cette ligne une fois, dans un fichier
que tous les autres lisent.

## Avant de lancer quoi que ce soit

Vérifie si le brand-core existe déjà :

```bash
ls brands/*/brand-core.json
```

- **Il existe** → lis-le. Ne le régénère pas sans raison : il a pu être corrigé
  à la main par le client, et ces corrections sont plus fiables que ce qu'une
  nouvelle analyse déduira du site.
- **Il n'existe pas** → continue ci-dessous.

## Lancer l'analyse

```bash
# Voir d'abord ce que l'agent lit du site — gratuit, aucun appel au modèle
ag inspect https://lamarque.fr

# Puis l'analyse complète
ag brand-core https://lamarque.fr \
  --competitor https://concurrent-1.fr \
  --competitor https://concurrent-2.fr \
  --notes "Ce que le dirigeant nous a dit, en vrac."
```

| Option | Quand s'en servir |
| --- | --- |
| `--competitor URL` | Dès que possible, 2 à 4 fois. Sans concurrents, l'analyse concurrentielle n'est qu'une hypothèse, et le dit. |
| `--notes` / `--notes-file` | Tout ce que le dirigeant a dit et que le site ne dit pas. Ces notes priment sur le site. |
| `--max-pages N` | Défaut 6. Monter jusqu'à 10 pour un gros site, descendre à 3 pour un site d'une page. |
| `--dry-run` | Afficher le prompt sans appeler le modèle. À utiliser pour vérifier que les bonnes pages ont été lues avant de dépenser. |

Trois fichiers sont écrits dans `brands/<nom-de-domaine>/` :

| Fichier | Pour qui |
| --- | --- |
| `brand-core.json` | Les autres outils. C'est le contrat. |
| `brand-core.md` | Le client. C'est ce qu'on lui envoie. |
| `voice.md` | Les outils de rédaction (Instagram, LinkedIn…). Ils héritent du ton sans réglage. |

## Après l'analyse

1. **Ouvre `brand-core.md` et lis `## Ce qu'il nous manque`.** Ces questions sont
   là parce que le site ne répondait pas. Pose-les au client : y répondre vaut
   plus que relancer l'analyse.
2. **Lis `## Fiabilité de cette analyse`** et répète-la au client. Ne présente
   pas une déduction comme une observation.
3. **Présente les opportunités dans l'ordre**, de la plus rentable à la moins
   rentable. Pour chacune, donne la version en français clair et la première
   action — pas le tableau complet.
4. **Chaque fourchette se cite avec ses hypothèses.** « 40 à 120 visites par
   mois, si on part de 300 recherches mensuelles et d'une position 3 à 6 au bout
   de quatre mois » — jamais « 120 visites par mois ».

## Corriger plutôt que régénérer

Si le client n'est pas d'accord avec une conclusion, **modifie
`brands/<marque>/brand-core.json`**, puis :

```bash
ag render brands/<marque>/brand-core.json
```

Les documents sont reconstruits. Un brand-core corrigé par le client vaut
toujours mieux qu'un brand-core régénéré par le modèle.

## Ce que cet outil ne fait pas

- Il ne lit pas les réseaux sociaux de la marque, seulement son site.
- Il n'exécute pas de JavaScript : un site entièrement rendu côté client
  donnera peu de matière. `ag inspect` le montre tout de suite — si le nombre de
  mots est très faible, demande les textes au client.
- Il n'invente pas de chiffre d'affaires, de récompense ou de référence client.
  Ce qu'il ne sait pas, il le met en question ouverte.
