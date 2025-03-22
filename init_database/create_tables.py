import sqlite3
import os

# Chemin vers la base de données
db_path = "C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/modules/fidelity_db"  # Assurez-vous que c'est le même chemin que dans votre script evaluer_regles.py
print(f"Vérification de la base de données à : {db_path}")
print(f"Ce fichier existe : {os.path.exists(db_path)}")
# Connexion à la base de données
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Créez toutes les tables nécessaires
cursor.executescript("""
-- Table des règles de fidélité
CREATE TABLE IF NOT EXISTS regles_fidelite (
    regle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    type_regle TEXT NOT NULL,
    condition_valeur TEXT NOT NULL,
    periode_jours INTEGER,
    recompense_id INTEGER,
    action_type TEXT,
    action_valeur TEXT,
    priorite INTEGER DEFAULT 0,
    est_active INTEGER DEFAULT 1,
    date_debut TEXT,
    date_fin TEXT,
    segments_cibles TEXT
);

-- Table des offres client
CREATE TABLE IF NOT EXISTS offres_client (
    offre_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    regle_id INTEGER,
    recompense_id INTEGER,
    date_generation TEXT DEFAULT (datetime('now')),
    date_expiration TEXT,
    statut TEXT DEFAULT 'active',
    code_unique TEXT,
    utilisation_transaction_id INTEGER,
    commentaire TEXT
);

-- Autres tables de votre schéma...
-- Ajoutez ici le reste des tables nécessaires
CREATE TABLE IF NOT EXISTS clients (
    client_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT,
    prenom TEXT,
    email TEXT,
    date_naissance TEXT,
    date_inscription TEXT DEFAULT (datetime('now')),
    segment TEXT DEFAULT 'standard',
    statut TEXT DEFAULT 'actif'
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    date_transaction TEXT DEFAULT (datetime('now')),
    montant_total REAL,
    statut TEXT DEFAULT 'completee'
);

CREATE TABLE IF NOT EXISTS details_transactions (
    detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    produit_id INTEGER,
    quantite INTEGER,
    prix_unitaire REAL
);

CREATE TABLE IF NOT EXISTS produits (
    produit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT,
    categorie_id INTEGER,
    prix REAL
);

CREATE TABLE IF NOT EXISTS cartes_fidelite (
    carte_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE,
    points_actuels INTEGER DEFAULT 0,
    date_creation TEXT DEFAULT (datetime('now')),
    date_derniere_activite TEXT DEFAULT (datetime('now')),
    statut TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS historique_points (
    historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    carte_id INTEGER NOT NULL,
    type_operation TEXT NOT NULL,
    points INTEGER NOT NULL,
    date_operation TEXT DEFAULT (datetime('now')),
    transaction_id INTEGER,
    description TEXT,
    solde_apres INTEGER
);

CREATE TABLE IF NOT EXISTS historique_evaluations_regles (
    historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
    regle_id INTEGER NOT NULL,
    date_evaluation TEXT DEFAULT (datetime('now')),
    nombre_clients_evalues INTEGER,
    nombre_offres_generees INTEGER,
    duree_execution_ms INTEGER,
    commentaire TEXT
);
""")

# Créez également les triggers
cursor.executescript("""
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
""")

# Valider les changements et fermer la connexion
conn.commit()
conn.close()

print("Les tables ont été créées avec succès!")