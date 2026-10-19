-- Modèle de la console multi-marques (ADR-012).
--
-- Cinq objets portent tout : marque, site, canal, contenu, campagne.
-- Et une seule table porte toute l'intelligence de reporting : `measure`.
-- Tous les écrans et tous les rapports se calculent dessus, ce qui évite
-- d'avoir un écran spécifique par plateforme.
--
-- SQLite pour commencer. Le SQL reste volontairement portable vers PostgreSQL :
-- pas de type exotique, dates en texte ISO 8601, pas de trigger.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS brand (
    id              INTEGER PRIMARY KEY,
    slug            TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    -- 'interne' = une marque à soi (Egyptours, Oria), pas un client facturé.
    kind            TEXT    NOT NULL DEFAULT 'interne'
                            CHECK (kind IN ('interne', 'client')),
    status          TEXT    NOT NULL DEFAULT 'actif'
                            CHECK (status IN ('actif', 'pause', 'archive')),
    plan            TEXT,
    monthly_fee_eur REAL,
    notes           TEXT    NOT NULL DEFAULT '',
    -- Où vit la ligne éditoriale de cette marque. La console lit ce chemin
    -- au lieu de le deviner : elle doit fonctionner depuis n'importe où.
    core_path       TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS site (
    id           INTEGER PRIMARY KEY,
    brand_id     INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    url          TEXT    NOT NULL,
    -- Détermine l'adaptateur d'écriture (sites/). La liste des valeurs vit
    -- dans store.PLATFORMS : un CHECK SQLite ne peut pas évoluer sans recréer
    -- la table, et de nouvelles plateformes arriveront.
    platform     TEXT    NOT NULL DEFAULT 'inconnue',
    page_count   INTEGER,
    write_access TEXT    NOT NULL DEFAULT 'aucun'
                         CHECK (write_access IN ('aucun', 'api', 'git', 'manuel')),
    -- Nom de la variable d'environnement qui porte l'accès. Jamais la valeur.
    secret_ref   TEXT    NOT NULL DEFAULT '',
    -- Réglages propres à l'adaptateur : utilisateur WordPress, boutique
    -- Shopify, dépôt GitHub et dossier de contenu…
    config       TEXT    NOT NULL DEFAULT '{}',
    UNIQUE (brand_id, url)
);

CREATE TABLE IF NOT EXISTS channel (
    id       INTEGER PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    kind     TEXT    NOT NULL,
    handle   TEXT    NOT NULL DEFAULT '',
    state    TEXT    NOT NULL DEFAULT 'a_connecter'
                     CHECK (state IN ('a_connecter', 'connecte', 'erreur', 'desactive')),
    UNIQUE (brand_id, kind)
);

-- Les jetons vivent à part, et on n'y stocke JAMAIS le secret lui-même :
-- seulement une référence vers le coffre (variable d'environnement, gestionnaire
-- de secrets). Une base volée ne doit pas donner accès aux comptes clients.
CREATE TABLE IF NOT EXISTS connected_account (
    id           INTEGER PRIMARY KEY,
    channel_id   INTEGER NOT NULL UNIQUE REFERENCES channel(id) ON DELETE CASCADE,
    external_id  TEXT    NOT NULL DEFAULT '',
    secret_ref   TEXT    NOT NULL DEFAULT '',
    expires_at   TEXT,
    connected_at TEXT,
    last_error   TEXT    NOT NULL DEFAULT ''
);

-- Le cœur du reporting. Une ligne = une valeur, un jour, un canal, une marque.
CREATE TABLE IF NOT EXISTS measure (
    brand_id INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    channel  TEXT    NOT NULL,
    metric   TEXT    NOT NULL,
    day      TEXT    NOT NULL,   -- AAAA-MM-JJ
    value    REAL    NOT NULL,
    PRIMARY KEY (brand_id, channel, metric, day)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS measure_by_day ON measure (day);
CREATE INDEX IF NOT EXISTS measure_by_brand_metric ON measure (brand_id, metric, day);

CREATE TABLE IF NOT EXISTS content (
    id            INTEGER PRIMARY KEY,
    brand_id      INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    channel       TEXT    NOT NULL,
    pillar        TEXT    NOT NULL DEFAULT '',
    scheduled_for TEXT,
    state         TEXT    NOT NULL DEFAULT 'prevu'
                          CHECK (state IN ('prevu', 'genere', 'a_valider',
                                           'valide', 'publie', 'rejete')),
    title         TEXT    NOT NULL DEFAULT '',
    body          TEXT    NOT NULL DEFAULT '',
    media_ref     TEXT    NOT NULL DEFAULT '',
    -- Article 50 de l'AI Act, en vigueur depuis le 2 août 2026 (ADR-011) :
    -- rien de généré ne part sans être signalé et marqué.
    ai_generated  INTEGER NOT NULL DEFAULT 1 CHECK (ai_generated IN (0, 1)),
    ai_marked     INTEGER NOT NULL DEFAULT 0 CHECK (ai_marked IN (0, 1)),
    published_at  TEXT,
    external_url  TEXT    NOT NULL DEFAULT '',
    -- Brief visuel, tendance exploitée, raison d'un rejet.
    notes         TEXT    NOT NULL DEFAULT '',
    -- Note donnée à la proposition. On en produit beaucoup, on en garde peu.
    score         REAL,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS content_queue ON content (state, scheduled_for);

CREATE TABLE IF NOT EXISTS campaign (
    id               INTEGER PRIMARY KEY,
    brand_id         INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    channel          TEXT    NOT NULL,
    name             TEXT    NOT NULL,
    objective        TEXT    NOT NULL DEFAULT '',
    daily_budget_eur REAL,
    -- Plafond non négociable. NOT NULL par choix : aucune campagne ne peut
    -- exister sans limite de dépense, même en brouillon.
    hard_cap_eur     REAL    NOT NULL,
    state            TEXT    NOT NULL DEFAULT 'brouillon'
                             CHECK (state IN ('brouillon', 'a_valider', 'active',
                                              'pause', 'terminee')),
    external_id      TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL
);

-- Journal des décisions prises par l'agent. Sert à répondre « pourquoi as-tu
-- fait ça ? » six mois plus tard, et à tracer toute dépense engagée.
CREATE TABLE IF NOT EXISTS decision_log (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER REFERENCES brand(id) ON DELETE CASCADE,
    at         TEXT    NOT NULL,
    actor      TEXT    NOT NULL,   -- 'agent' ou 'humain'
    action     TEXT    NOT NULL,
    rationale  TEXT    NOT NULL DEFAULT '',
    payload    TEXT    NOT NULL DEFAULT ''
);

-- --------------------------------------------------------------------------
-- Outils branchés
-- --------------------------------------------------------------------------
-- Un seul registre pour tout ce qu'on connecte : analytics, régies, réseaux,
-- CRM, envoi d'e-mails, enrichissement, sourcing. Chaque outil est une ligne,
-- jamais une colonne — ajouter un outil ne touche pas au schéma.
CREATE TABLE IF NOT EXISTS integration (
    id           INTEGER PRIMARY KEY,
    slug         TEXT    NOT NULL UNIQUE,
    name         TEXT    NOT NULL,
    category     TEXT    NOT NULL
                         CHECK (category IN ('analytics', 'ads', 'social', 'crm',
                                             'email', 'enrichment', 'sourcing',
                                             'site', 'media')),
    state        TEXT    NOT NULL DEFAULT 'disponible'
                         CHECK (state IN ('disponible', 'connecte', 'erreur', 'desactive')),
    -- Référence vers le coffre. Jamais le secret lui-même.
    secret_ref   TEXT    NOT NULL DEFAULT '',
    config       TEXT    NOT NULL DEFAULT '{}',
    connected_at TEXT,
    last_error   TEXT    NOT NULL DEFAULT ''
);

-- --------------------------------------------------------------------------
-- Prospection sortante
-- --------------------------------------------------------------------------
-- Le RGPD est dans le schéma, pas dans une note de bas de page : l'origine de
-- chaque contact est tracée, la base légale est obligatoire, et l'opposition
-- est un champ qu'aucune requête d'envoi ne peut ignorer.
CREATE TABLE IF NOT EXISTS prospect (
    id            INTEGER PRIMARY KEY,
    brand_id      INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    company       TEXT    NOT NULL,
    website       TEXT    NOT NULL DEFAULT '',
    contact_name  TEXT    NOT NULL DEFAULT '',
    role          TEXT    NOT NULL DEFAULT '',
    email         TEXT    NOT NULL DEFAULT '',
    phone         TEXT    NOT NULL DEFAULT '',
    linkedin      TEXT    NOT NULL DEFAULT '',
    -- D'où vient ce contact. Obligatoire : sans origine, pas d'envoi.
    source        TEXT    NOT NULL,
    source_detail TEXT    NOT NULL DEFAULT '',
    -- Score de correspondance à l'ICP du brand-core, et sa justification.
    icp_fit       REAL,
    icp_rationale TEXT    NOT NULL DEFAULT '',
    state         TEXT    NOT NULL DEFAULT 'trouve'
                          CHECK (state IN ('trouve', 'enrichi', 'qualifie', 'contacte',
                                           'repondu', 'rdv', 'gagne', 'perdu', 'exclu')),
    gdpr_basis    TEXT    NOT NULL DEFAULT 'interet_legitime'
                          CHECK (gdpr_basis IN ('interet_legitime', 'consentement', 'contrat')),
    opted_out     INTEGER NOT NULL DEFAULT 0 CHECK (opted_out IN (0, 1)),
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS prospect_pipeline ON prospect (brand_id, state);
CREATE UNIQUE INDEX IF NOT EXISTS prospect_unique_email
    ON prospect (brand_id, email) WHERE email != '';

CREATE TABLE IF NOT EXISTS sequence (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    channel    TEXT    NOT NULL DEFAULT 'email',
    state      TEXT    NOT NULL DEFAULT 'brouillon'
                       CHECK (state IN ('brouillon', 'a_valider', 'active', 'pause', 'terminee')),
    -- L'outil qui enverra réellement. Vide = envoi par nos propres moyens.
    sent_via   TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sequence_step (
    id          INTEGER PRIMARY KEY,
    sequence_id INTEGER NOT NULL REFERENCES sequence(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    wait_days   INTEGER NOT NULL DEFAULT 0,
    subject     TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL DEFAULT '',
    UNIQUE (sequence_id, position)
);

CREATE TABLE IF NOT EXISTS outreach (
    id            INTEGER PRIMARY KEY,
    prospect_id   INTEGER NOT NULL REFERENCES prospect(id) ON DELETE CASCADE,
    sequence_id   INTEGER REFERENCES sequence(id) ON DELETE SET NULL,
    step_id       INTEGER REFERENCES sequence_step(id) ON DELETE SET NULL,
    channel       TEXT    NOT NULL DEFAULT 'email',
    state         TEXT    NOT NULL DEFAULT 'prevu'
                          CHECK (state IN ('prevu', 'a_valider', 'envoye', 'ouvert',
                                           'repondu', 'rebond', 'desabonne', 'annule')),
    scheduled_for TEXT,
    sent_at       TEXT,
    external_id   TEXT    NOT NULL DEFAULT '',
    ai_generated  INTEGER NOT NULL DEFAULT 1 CHECK (ai_generated IN (0, 1)),
    ai_marked     INTEGER NOT NULL DEFAULT 0 CHECK (ai_marked IN (0, 1)),
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS outreach_queue ON outreach (state, scheduled_for);

-- --------------------------------------------------------------------------
-- Autonomie : la file de validation
-- --------------------------------------------------------------------------
-- Tout ce qui publie, dépense, contacte ou modifie un site passe par ici.
-- Le système prépare ; l'humain valide en un geste (Telegram ou console).
-- Une demande est liée à son objet (`subject_table`, `subject_id`), et décider
-- fait avancer l'objet — jamais l'inverse.
CREATE TABLE IF NOT EXISTS approval (
    id            INTEGER PRIMARY KEY,
    brand_id      INTEGER REFERENCES brand(id) ON DELETE CASCADE,
    kind          TEXT    NOT NULL
                          CHECK (kind IN ('publication', 'depense', 'contact', 'site')),
    subject_table TEXT    NOT NULL
                          CHECK (subject_table IN ('content', 'campaign', 'outreach', 'site_change')),
    subject_id    INTEGER NOT NULL,
    summary       TEXT    NOT NULL,
    detail        TEXT    NOT NULL DEFAULT '',
    -- Montant engagé si on valide. Affiché en clair dans la notification.
    amount_eur    REAL,
    state         TEXT    NOT NULL DEFAULT 'en_attente'
                          CHECK (state IN ('en_attente', 'approuve', 'refuse', 'expire')),
    requested_at  TEXT    NOT NULL,
    -- Une dépense validée trois jours trop tard n'a plus de sens : elle expire.
    expires_at    TEXT,
    decided_at    TEXT,
    decided_by    TEXT    NOT NULL DEFAULT '',
    -- Identifiant du message de notification, pour le mettre à jour.
    notified_ref  TEXT    NOT NULL DEFAULT ''
);

-- Jamais deux demandes en attente pour le même objet.
CREATE UNIQUE INDEX IF NOT EXISTS approval_one_pending
    ON approval (subject_table, subject_id) WHERE state = 'en_attente';
CREATE INDEX IF NOT EXISTS approval_queue ON approval (state, requested_at);

-- Validation automatique, activée canal par canal, marque par marque, quand la
-- confiance est établie. Une dépense automatique exige un plafond : c'est le
-- schéma qui l'impose.
CREATE TABLE IF NOT EXISTS auto_rule (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    kind       TEXT    NOT NULL CHECK (kind IN ('publication', 'depense', 'contact', 'site')),
    channel    TEXT    NOT NULL DEFAULT '*',
    max_eur    REAL,
    enabled    INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT    NOT NULL,
    CHECK (kind != 'depense' OR max_eur IS NOT NULL),
    UNIQUE (brand_id, kind, channel)
);

-- --------------------------------------------------------------------------
-- Modifications de site
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS site_change (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    site_id    INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    kind       TEXT    NOT NULL CHECK (kind IN ('page_create', 'page_update')),
    -- Identifiant ou chemin de la page visée ; vide pour une création.
    target     TEXT    NOT NULL DEFAULT '',
    title      TEXT    NOT NULL DEFAULT '',
    body       TEXT    NOT NULL DEFAULT '',
    slug       TEXT    NOT NULL DEFAULT '',
    meta       TEXT    NOT NULL DEFAULT '{}',
    state      TEXT    NOT NULL DEFAULT 'propose'
                       CHECK (state IN ('propose', 'a_valider', 'approuve', 'applique',
                                        'manuel', 'echec', 'refuse')),
    ai_generated INTEGER NOT NULL DEFAULT 1 CHECK (ai_generated IN (0, 1)),
    result     TEXT    NOT NULL DEFAULT '',
    applied_at TEXT,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS site_change_queue ON site_change (state);

-- --------------------------------------------------------------------------
-- Planificateur
-- --------------------------------------------------------------------------
-- Une ligne par exécution. Sert à savoir quand une tâche a tourné pour la
-- dernière fois — donc à ne jamais la lancer deux fois — et à afficher les
-- échecs au lieu de les avaler.
CREATE TABLE IF NOT EXISTS job_run (
    id          INTEGER PRIMARY KEY,
    job         TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    finished_at TEXT,
    ok          INTEGER CHECK (ok IN (0, 1)),
    detail      TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS job_run_last ON job_run (job, started_at);

-- --------------------------------------------------------------------------
-- Comptes : le consultant pilote, le client suit
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_user (
    id            INTEGER PRIMARY KEY,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT    NOT NULL DEFAULT '',
    -- consultant : voit et pilote tout. client : voit ses marques, ne pilote rien.
    role          TEXT    NOT NULL CHECK (role IN ('consultant', 'client')),
    -- scrypt, sel compris. Jamais le mot de passe.
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    last_login_at TEXT
);

-- Les marques qu'un client a le droit de voir. Un consultant n'en a pas besoin.
CREATE TABLE IF NOT EXISTS user_brand (
    user_id  INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    brand_id INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, brand_id)
);

-- La conversation avec l'agent, pour la reprendre où on l'a laissée.
CREATE TABLE IF NOT EXISTS chat_message (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    brand_id   INTEGER REFERENCES brand(id) ON DELETE SET NULL,
    role       TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    text       TEXT    NOT NULL,
    -- Les actions faites pendant ce tour, pour les afficher sous la réponse.
    actions    TEXT    NOT NULL DEFAULT '[]',
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS chat_by_user ON chat_message (user_id, created_at);

-- --------------------------------------------------------------------------
-- Travaux longs lancés depuis l'interface
-- --------------------------------------------------------------------------
-- Une analyse de marque ou une série de publications prend une à trois
-- minutes : on ne fait pas attendre l'écran, on affiche l'avancement.
CREATE TABLE IF NOT EXISTS task (
    id          INTEGER PRIMARY KEY,
    brand_id    INTEGER REFERENCES brand(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,
    label       TEXT    NOT NULL,
    state       TEXT    NOT NULL DEFAULT 'en_cours'
                        CHECK (state IN ('en_cours', 'termine', 'echec')),
    detail      TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    finished_at TEXT
);

-- --------------------------------------------------------------------------
-- Audits SEO / GEO
-- --------------------------------------------------------------------------
-- Gardés dans le temps : un audit seul est une photo, une suite d'audits
-- montre si le travail fait remonter la note.
CREATE TABLE IF NOT EXISTS audit (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER REFERENCES brand(id) ON DELETE CASCADE,
    url        TEXT    NOT NULL,
    score      INTEGER NOT NULL,
    pages      INTEGER NOT NULL,
    critique   INTEGER NOT NULL DEFAULT 0,
    important  INTEGER NOT NULL DEFAULT 0,
    amelioration INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_by_url ON audit (url, created_at);

CREATE TABLE IF NOT EXISTS audit_finding (
    id        INTEGER PRIMARY KEY,
    audit_id  INTEGER NOT NULL REFERENCES audit(id) ON DELETE CASCADE,
    code      TEXT    NOT NULL,
    severity  TEXT    NOT NULL CHECK (severity IN ('critique', 'important', 'amelioration')),
    category  TEXT    NOT NULL,
    title     TEXT    NOT NULL,
    why       TEXT    NOT NULL,
    fix       TEXT    NOT NULL,
    urls      TEXT    NOT NULL DEFAULT '[]'
);
