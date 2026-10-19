# Mise en ligne sur Railway

Compte une demi-heure. À la fin, le système tourne 24 h/24, t'envoie les
validations sur Telegram, et la console est protégée par un mot de passe.

## Ce qui tourne

Un seul service fait tout : la console, le planificateur et l'écoute Telegram.

| Tâche | Cadence | Ce qu'elle fait |
| --- | --- | --- |
| `notifier` | chaque minute | envoie sur Telegram les demandes pas encore notifiées |
| `expirer` | toutes les 15 min | clôt les demandes trop anciennes et libère leur objet |
| `appliquer-site` | toutes les 5 min | écrit sur les sites ce qui a été validé |
| `collecter` | chaque nuit, 3 h UTC | relève les chiffres des canaux connectés |
| `resume` | chaque matin, 6 h UTC | t'envoie le résultat du portefeuille |

L'état de chaque tâche est visible dans la console, page **Validations**.

## 1. Créer le bot Telegram (3 minutes)

1. Dans Telegram, ouvre **@BotFather** et envoie `/newbot`.
2. Donne un nom (« Agent Growth ») puis un identifiant qui finit par `bot`.
3. BotFather te donne un **jeton**. Garde-le pour l'étape 3 — c'est
   `TELEGRAM_BOT_TOKEN`. Ne le colle nulle part ailleurs.

Ton identifiant Telegram (`TELEGRAM_OWNER_ID`) s'obtient à l'étape 4.

## 2. Créer le service Railway

1. Railway → **New Project** → **Deploy from GitHub repo** → `Agent-Growth`.
2. Choisis la branche `claude/inspiring-keller-ls8hai` (ou `main` une fois
   fusionnée). Railway lit `railway.json` et construit le `Dockerfile`.
3. **Ajoute un volume** : clic droit sur le service → **Attach Volume**,
   point de montage **`/data`**.

   > Sans volume, la base est effacée à chaque déploiement : toutes tes
   > marques, tes mesures et ton historique disparaîtraient.

4. Laisse **une seule instance**. La base est SQLite : deux instances
   écriraient chacune de leur côté. `railway.json` le fixe déjà.

## 3. Les variables

Service → **Variables** :

| Variable | Valeur |
| --- | --- |
| `AG_CONSOLE_PASSWORD` | un mot de passe long. **Obligatoire** : sans lui, le service refuse de démarrer. |
| `ANTHROPIC_API_KEY` | ta clé sur console.anthropic.com |
| `TELEGRAM_BOT_TOKEN` | le jeton de l'étape 1 |

Ne mets pas encore `TELEGRAM_OWNER_ID`.

Puis **Settings → Networking → Generate Domain** pour obtenir l'adresse de la
console.

## 4. Te déclarer propriétaire du bot

1. Dans Telegram, ouvre ton bot et envoie `/start`.
2. Il répond avec ton identifiant. C'est le seul message qu'il enverra à
   quelqu'un tant qu'aucun propriétaire n'est déclaré.
3. Ajoute `TELEGRAM_OWNER_ID` dans Railway avec cette valeur. Le service
   redémarre.
4. Envoie `/aide` : il doit répondre.

À partir de là, **seul ton compte peut valider**. Un inconnu qui appuie sur un
bouton est ignoré en silence et la tentative est journalisée.

## 5. Ouvrir la console

L'adresse de l'étape 3, identifiant `admin`, ton mot de passe.

Les commandes `ag …` s'exécutent dans le service : Railway → ton service →
**Shell** (ou `railway run ag …` depuis ton ordinateur avec la CLI Railway).

```bash
ag brand add https://egyptours.fr --name Egyptours --channel instagram --channel gmb
ag brand-core https://egyptours.fr
```

## 6. Brancher les sites

Le principe est le même partout : **un accès par site, rangé dans une
variable Railway, dont on donne le NOM à la console — jamais la valeur.**

### WordPress

1. Dans l'administration du site : **Utilisateurs → Profil → Mots de passe
   d'application** → nom « Agent Growth » → **Ajouter**.
2. Railway : variable `WP_<MARQUE>` = le mot de passe affiché.
3. ```bash
   ag site add <marque> https://site.fr --platform wordpress \
     --secret-ref WP_<MARQUE> --config user=<ton-identifiant-wordpress>
   ```

Les pages sont créées **en brouillon** par défaut : tu les vois en place avant
qu'elles s'affichent. Pour publier directement, ajoute `--config status=publish`.

### Shopify

1. Shopify : **Paramètres → Applications → Développer des applications** →
   créer une application → droits **`read_content`** et **`write_content`** →
   installer → copier le jeton Admin API.
2. Railway : variable `SHOPIFY_<MARQUE>`.
3. ```bash
   ag site add <marque> https://boutique.fr --platform shopify \
     --secret-ref SHOPIFY_<MARQUE> --config shop=<boutique>.myshopify.com
   ```

Pages créées **non publiées** par défaut (`--config publish=true` pour changer).

### Site développé sur mesure (Oria)

On n'écrit jamais directement sur un site codé à la main : on ouvre une
**pull request** sur son dépôt GitHub. La mise en ligne a lieu à la fusion,
selon le déploiement du site.

1. GitHub → **Settings → Developer settings → Fine-grained tokens** →
   accès limité **au seul dépôt du site**, droits **Contents** et **Pull
   requests** en écriture.
2. Railway : variable `GITHUB_<MARQUE>`.
3. ```bash
   ag site add oria https://oria.fr --platform sur_mesure \
     --secret-ref GITHUB_ORIA --config repo=<propriétaire>/<dépôt> \
     --config dir=content/pages --config ext=.md
   ```

`dir` et `ext` dépendent de la façon dont le site range ses pages : à ajuster
avec le développeur.

### SpeedMedia (Egyptours)

SpeedMedia n'a pas d'API d'écriture publique connue. Le système prépare un
**dossier prêt à coller** — titre, adresse, texte, meta description — et te
prévient sur Telegram. Tu colles dans l'administration SpeedMedia.

```bash
ag site add egyptours https://egyptours.fr --platform speedmedia
```

## 7. Vérifier que tout marche

```bash
ag site propose <numéro-du-site> --title "Page d'essai" --body "<p>Essai</p>"
```

Dans la minute, Telegram te montre la demande avec **Valider / Refuser**.
Valide : dans les 5 minutes, la page est créée (en brouillon) ou le dossier est
prêt, et Telegram te le confirme.

## La validation automatique, plus tard

Quand un canal a fait ses preuves, on active la validation automatique pour ce
canal et cette marque seulement. **Une dépense automatique exige un plafond** —
la base refuse une règle sans plafond, et tout montant au-dessus revient vers
toi.

## Sécurité, en résumé

- La console refuse de démarrer en ligne sans mot de passe.
- Seul ton compte Telegram peut valider.
- Une action envoyée depuis un autre site que la console est refusée.
- Aucun secret en base : seulement le nom de la variable qui le porte.
- Une demande ne s'applique qu'une fois, même en appuyant deux fois.
- Une demande expirée libère son objet au lieu de l'appliquer en retard.
