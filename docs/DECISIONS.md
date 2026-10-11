# Décisions

Les choix structurants, avec leur raison et leur date. Utile dans six mois,
quand on aura oublié pourquoi.

---

## ADR-001 — La ligne éditoriale est un fichier, pas un prompt

*2026-10-11 · adopté*

**Problème.** Un agent qui écrit un post lundi et une annonce mardi produit deux
marques différentes, parce que le positionnement est rédigé à neuf dans chaque
prompt.

**Décision.** Le positionnement, le ton, les piliers et les interdits vivent
dans `brand-core.json`. Tous les outils le lisent. Aucun ne le redécide.

**Conséquences.** La cohérence devient vérifiable au lieu d'être espérée. En
contrepartie, `schemas.py` devient un contrat : le modifier affecte tous les
outils, d'où le `SCHEMA_VERSION`.

---

## ADR-002 — Python, pas de framework d'agents

*2026-10-11 · adopté*

**Décision.** Python pur avec le SDK Anthropic. Pas de LangGraph, CrewAI ni
équivalent.

**Pourquoi.** Les outils sont séquentiels : lire des pages, analyser, écrire des
fichiers. Une fonction suffit. Un framework ajouterait une abstraction à
apprendre, à déboguer et à maintenir, sans rien résoudre. Python parce que le
crawl, le SEO et le scraping y sont les mieux outillés, et parce que les skills
de contenu disponibles sur GitHub y sont déjà écrites.

**À réexaminer si** on a besoin de véritable parallélisme sur des dizaines de
marques, ou de reprise sur incident en milieu de traitement.

---

## ADR-003 — Des fichiers, pas de base de données

*2026-10-11 · adopté*

**Décision.** Un dossier par marque dans `brands/<slug>/`.

**Pourquoi.** On peut relire, corriger à la main, versionner, envoyer au client.
Une base de données imposerait un schéma, des migrations et un serveur pour un
bénéfice nul à cette échelle.

**À réexaminer si** plusieurs personnes doivent travailler simultanément sur la
même marque, ou si l'historique des versions devient un besoin produit.

---

## ADR-004 — Réutiliser les skills de rédaction existantes

*2026-10-11 · adopté*

**Question posée.** Peut-on intégrer une skill Instagram publique
(`Jakeschincariol/instagram-agent-skill`) plutôt que développer l'agent ?

**Ce que ce dépôt contient réellement**, d'après son README (MIT, ~950 étoiles,
2 commits au moment de l'examen) :

- 13 skills Claude pour Instagram : scripts de Reels et notation d'accroches,
  légendes, recherche de contenus performants, audit de profil, planning
  hebdomadaire, nettoyage de textes ;
- des scripts Python locaux, sans dépendance et sans accès réseau ;
- **aucune authentification, aucune clé API, aucune publication.** Son README
  l'écrit explicitement : « rien n'est publié tant que vous ne dites pas oui »,
  et automatiser la publication, les commentaires, les abonnements ou les
  messages privés viole les conditions d'utilisation d'Instagram ;
- une honnêteté notable sur ses limites : l'auteur indique que son score
  d'accroche repère bien les accroches faibles (AUC 0,83) mais ne distingue pas
  les gagnantes parmi les bonnes (AUC 0,56, où 0,50 est le hasard).

**Décision.** Oui, le réutiliser — pour la **couche création**, copié et épinglé
dans `skills/vendor/`, après lecture de chaque fichier. Non, cela ne remplace
pas l'agent.

**Pourquoi.** Ce dépôt fait gagner du savoir-faire rédactionnel Instagram, ce
qui est réel et appréciable. Il ne fait rien de ce qui constitue le produit :
stratégie de marque, SEO et corrections sur le site, chiffrage des
opportunités, lancement et pilotage des campagnes, cohérence entre canaux,
mesure. Et il ne publie pas : « la gestion automatisée d'un compte Instagram »
reste à faire, et passe par la Content Publishing API de Meta — app
développeur, compte professionnel, Page liée, revue d'application.

**Précautions.** Une skill est composée d'instructions que Claude suit et de
scripts qu'il exécute. On ne dépend pas d'un dépôt tierce-partie par
sous-module : on copie, on épingle le commit, on relit. Procédure dans
[ARCHITECTURE.md](ARCHITECTURE.md#brancher-une-skill-externe). Les scores
produits par une skill externe sont présentés comme des indications, jamais
comme des vérités.

---

## ADR-005 — Aucun chiffre sans ses hypothèses

*2026-10-11 · adopté*

**Décision.** Toute estimation est un objet `Estimate` : une fourchette, la
liste des hypothèses, et l'origine du chiffre (`donnees_site`,
`benchmark_secteur`, `hypothese`). Le schéma l'impose ; ce n'est pas une
consigne de rédaction.

**Pourquoi.** La valeur promise est « des conseils avec des estimations
chiffrées » pour des gens qui ne peuvent pas vérifier ces chiffres eux-mêmes.
Un chiffre faussement précis est donc plus dangereux qu'une fourchette large.
Rendre les hypothèses obligatoires rend aussi l'estimation corrigible : quand
le réel diffère, on sait quelle hypothèse était fausse.

---

## ADR-006 — Pas d'automatisation non officielle des réseaux

*2026-10-11 · adopté*

**Décision.** Publication, commentaires, abonnements et messages privés passent
exclusivement par les API officielles. Pas de navigateur piloté, pas de client
non officiel, même si c'est plus rapide à construire.

**Pourquoi.** C'est une violation des conditions d'utilisation d'Instagram et
de LinkedIn, et le risque porte sur le compte du client. Un compte client fermé
n'est pas un incident technique, c'est une faute professionnelle.

**Conséquence.** Tant qu'un accès officiel n'est pas en place, les outils
préparent le contenu et le remettent à valider. C'est déjà l'essentiel du
travail, et c'est vendable tel quel.

---

## ADR-007 — Le pré-test comme réflexe, pas comme promesse

*2026-10-11 · adopté*

**Décision.** Tout outil qui produit une création produit des variantes et les
confronte avant diffusion.

**Pourquoi.** L'intérêt concret est de réduire le coût du raté créatif :
écarter trois accroches faibles coûte beaucoup moins cher qu'une campagne qui ne
parle à personne.

**Limite assumée.** Un pré-test écarte les ratés évidents ; il ne prédit pas les
succès. Les outils affichent cette limite au lieu de la masquer derrière un
score — c'est précisément ce que le dépôt Instagram examiné en ADR-004 mesure
sur ses propres accroches, et il a raison de le dire.
