-- Création de tables (si elles n'existent pas déjà)
-- Vous pouvez adapter ces schémas selon vos besoins

-- Table des règles de fidélité
CREATE TABLE IF NOT EXISTS regles_fidelite (
    regle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    type_regle TEXT NOT NULL,  -- 'nombre_achats', 'montant_cumule', 'produit_specifique', etc.
    condition_valeur TEXT NOT NULL,
    periode_jours INTEGER,
    recompense_id INTEGER,
    action_type TEXT,
    action_valeur TEXT,
    priorite INTEGER DEFAULT 0,
    est_active INTEGER DEFAULT 1,
    date_debut TEXT,  -- Format YYYY-MM-DD
    date_fin TEXT,    -- Format YYYY-MM-DD
    segments_cibles TEXT  -- Stocké en JSON: '["premium", "standard"]'
);

-- Table des offres client
CREATE TABLE IF NOT EXISTS offres_client (
    offre_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    regle_id INTEGER,
    recompense_id INTEGER,
    date_generation TEXT DEFAULT (datetime('now')),
    date_expiration TEXT,
    statut TEXT DEFAULT 'active',  -- 'active', 'utilisee', 'expiree'
    code_unique TEXT,
    utilisation_transaction_id INTEGER,
    commentaire TEXT
);

-- Table des cartes de fidélité
CREATE TABLE IF NOT EXISTS cartes_fidelite (
    carte_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE,
    points_actuels INTEGER DEFAULT 0,
    date_creation TEXT DEFAULT (datetime('now')),
    date_derniere_activite TEXT DEFAULT (datetime('now')),
    statut TEXT DEFAULT 'active'
);

-- Table historique des points
CREATE TABLE IF NOT EXISTS historique_points (
    historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    carte_id INTEGER NOT NULL,
    type_operation TEXT NOT NULL,  -- 'achat', 'bonus', 'utilisation'
    points INTEGER NOT NULL,
    date_operation TEXT DEFAULT (datetime('now')),
    transaction_id INTEGER,
    description TEXT,
    solde_apres INTEGER
);

-- Table des statistiques d'évaluation des règles
CREATE TABLE IF NOT EXISTS historique_evaluations_regles (
    historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
    regle_id INTEGER NOT NULL,
    date_evaluation TEXT DEFAULT (datetime('now')),
    nombre_clients_evalues INTEGER,
    nombre_offres_generees INTEGER,
    duree_execution_ms INTEGER,
    commentaire TEXT
);

-- Trigger pour générer un code unique après l'insertion d'une nouvelle offre
CREATE TRIGGER IF NOT EXISTS generate_unique_code AFTER INSERT ON offres_client
WHEN NEW.code_unique IS NULL
BEGIN
    UPDATE offres_client
    SET code_unique = 'OF-' || NEW.offre_id || '-' || substr(hex(randomblob(4)), 1, 8)
    WHERE offre_id = NEW.offre_id;
END;

-- Trigger pour mettre à jour les points après utilisation d'une offre
CREATE TRIGGER IF NOT EXISTS after_offer_used AFTER UPDATE ON offres_client
WHEN NEW.statut = 'utilisee' AND OLD.statut != 'utilisee'
BEGIN
    INSERT INTO historique_points (
        client_id,
        carte_id,
        type_operation,
        points,
        transaction_id,
        description,
        solde_apres
    )
    SELECT
        NEW.client_id,
        cf.carte_id,
        'bonus',
        CAST((SELECT action_valeur FROM regles_fidelite WHERE regle_id = NEW.regle_id) AS INTEGER),
        NEW.utilisation_transaction_id,
        'Points bonus de fidélité (offre ID: ' || NEW.offre_id || ')',
        cf.points_actuels + CAST((SELECT action_valeur FROM regles_fidelite WHERE regle_id = NEW.regle_id) AS INTEGER)
    FROM cartes_fidelite cf
    WHERE cf.client_id = NEW.client_id
    AND (SELECT action_type FROM regles_fidelite WHERE regle_id = NEW.regle_id) = 'offre_points';
    
    -- Mettre à jour le solde de points
    UPDATE cartes_fidelite
    SET points_actuels = points_actuels + CAST((SELECT action_valeur FROM regles_fidelite WHERE regle_id = NEW.regle_id) AS INTEGER),
        date_derniere_activite = datetime('now')
    WHERE client_id = NEW.client_id
    AND (SELECT action_type FROM regles_fidelite WHERE regle_id = NEW.regle_id) = 'offre_points';
END;
