-- Création de la base de données pour le système de fidélité client
-- SQLite version avec protection anti-fraude améliorée

PRAGMA foreign_keys = OFF;  -- Activer les contraintes de clé étrangère

-- Table des clients
CREATE TABLE clients (
    client_id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL,  -- Identifiant unique pour anonymisation
    nom TEXT,
    prenom TEXT,
    date_naissance DATE,
    genre TEXT,
    adresse TEXT,
    code_postal TEXT,
    ville TEXT,
    pays TEXT DEFAULT 'France',
    telephone TEXT,
    email TEXT UNIQUE,
    date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP,
    consentement_marketing BOOLEAN DEFAULT 0,
    consentement_data_processing BOOLEAN DEFAULT 0,
    date_consentement DATETIME,
    statut TEXT DEFAULT 'actif' CHECK (statut IN ('actif', 'inactif', 'suspendu', 'supprimé')),
    segment TEXT DEFAULT 'standard' CHECK (segment IN ('standard', 'premium', 'vip', 'inactif')),
    canal_acquisition TEXT,
    derniere_modification DATETIME DEFAULT CURRENT_TIMESTAMP,
    niveau_confiance INTEGER DEFAULT 100 CHECK (niveau_confiance BETWEEN 0 AND 100) -- Indicateur de confiance
);

-- Table pour anonymisation des clients (pour les data analysts)
CREATE TABLE clients_anonymized (
    client_id INTEGER PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL,  -- Lien vers le client réel
    age INTEGER,                -- Calculé à partir de la date de naissance
    tranche_age TEXT,           -- Ex: "18-25", "26-35", etc.
    genre TEXT,
    region TEXT,                -- Dérivé du code postal
    segment TEXT,
    date_inscription DATE,      -- Sans l'heure pour réduire la précision
    statut TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Table des cartes de fidélité
CREATE TABLE cartes_fidelite (
    carte_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    numero_carte TEXT UNIQUE NOT NULL,
    date_emission DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_expiration DATETIME,
    statut TEXT DEFAULT 'active' CHECK (statut IN ('active', 'inactive', 'perdue', 'remplacée', 'expirée')),
    niveau_fidelite TEXT DEFAULT 'bronze' CHECK (niveau_fidelite IN ('bronze', 'argent', 'or', 'platine')),
    points_actuels INTEGER DEFAULT 0,
    points_en_attente INTEGER DEFAULT 0, -- Points qui attendent validation
    date_derniere_activite DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Table des niveaux de fidélité
CREATE TABLE niveaux_fidelite (
    niveau_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL,
    points_minimum INTEGER NOT NULL,
    points_maximum INTEGER,
    multiplicateur_points REAL DEFAULT 1.0,
    avantages TEXT,
    duree_validite INTEGER,  -- en jours
    seuil_maintien INTEGER,  -- points nécessaires pour maintenir le niveau
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    modification_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table des magasins / points de vente
CREATE TABLE points_vente (
    magasin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    type TEXT CHECK (type IN ('flagship', 'franchise', 'corner', 'pop-up', 'online')),
    adresse TEXT,
    code_postal TEXT,
    ville TEXT,
    pays TEXT DEFAULT 'France',
    telephone TEXT,
    email TEXT,
    horaires TEXT,
    latitude REAL,
    longitude REAL,
    date_ouverture DATE,
    statut TEXT DEFAULT 'actif' CHECK (statut IN ('actif', 'inactif', 'fermé', 'temporaire'))
);

-- Table des catégories de produits
CREATE TABLE categories_produits (
    categorie_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT,
    categorie_parent_id INTEGER,
    multiplicateur_points REAL DEFAULT 1.0,
    image_url TEXT,
    FOREIGN KEY (categorie_parent_id) REFERENCES categories_produits(categorie_id)
);

-- Table des produits
CREATE TABLE produits (
    produit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT UNIQUE NOT NULL,
    code_barres TEXT,
    nom TEXT NOT NULL,
    description TEXT,
    categorie_id INTEGER,
    sous_categorie_id INTEGER,
    marque TEXT,
    prix_standard REAL,
    multiplicateur_points REAL DEFAULT 1.0,
    statut TEXT DEFAULT 'actif' CHECK (statut IN ('actif', 'inactif', 'épuisé', 'abandonné')),
    image_url TEXT,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    modification_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (categorie_id) REFERENCES categories_produits(categorie_id),
    FOREIGN KEY (sous_categorie_id) REFERENCES categories_produits(categorie_id)
);

-- Table des transactions
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    carte_id INTEGER,
    magasin_id INTEGER,
    employe_id INTEGER,
    date_transaction DATETIME DEFAULT CURRENT_TIMESTAMP,
    montant_total REAL NOT NULL,
    montant_ht REAL,
    tva_montant REAL,
    type_paiement TEXT CHECK (type_paiement IN ('cb', 'espèces', 'chèque', 'mobile', 'mixte')),
    numero_facture TEXT,
    canal_vente TEXT DEFAULT 'magasin' CHECK (canal_vente IN ('magasin', 'en_ligne', 'application', 'telephone')),
    points_gagnes INTEGER DEFAULT 0,
    points_utilises INTEGER DEFAULT 0,
    commentaire TEXT,
    validation_source TEXT DEFAULT 'pos' CHECK (validation_source IN ('pos', 'ocr', 'manuel', 'api')),
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (carte_id) REFERENCES cartes_fidelite(carte_id),
    FOREIGN KEY (magasin_id) REFERENCES points_vente(magasin_id)
);

-- Table des détails des transactions
CREATE TABLE details_transactions (
    detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL,
    produit_id INTEGER NOT NULL,
    quantite INTEGER NOT NULL DEFAULT 1,
    prix_unitaire REAL NOT NULL,
    remise_pourcentage REAL DEFAULT 0,
    remise_montant REAL DEFAULT 0,
    montant_ligne REAL NOT NULL,
    points_ligne INTEGER DEFAULT 0,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (produit_id) REFERENCES produits(produit_id)
);

-- Table pour les tickets de caisse (OCR) avec protections anti-fraude
CREATE TABLE tickets_caisse (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    transaction_id INTEGER,
    date_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_transaction DATETIME,
    magasin_id INTEGER,
    numero_facture TEXT,
    montant_total REAL,
    image_path TEXT NOT NULL,
    ticket_hash VARCHAR(64) UNIQUE, -- Empreinte unique du ticket pour détecter les doublons
    statut_traitement TEXT DEFAULT 'en_attente' CHECK (statut_traitement IN ('en_attente', 'en_cours', 'traité', 'erreur', 'vérifié')),
    validation_status TEXT DEFAULT 'pending_validation' CHECK (validation_status IN ('pending_validation', 'validated', 'rejected', 'suspicious', 'requires_manual_review')),
    texte_ocr TEXT,  -- Le texte extrait par OCR
    metadonnees JSON,  -- Stockage de métadonnées additionnelles (format JSON)
    date_traitement DATETIME,
    verified_with_transaction BOOLEAN DEFAULT 0, -- Flag de vérification croisée avec la transaction
    verification_method TEXT, -- Méthode utilisée pour la vérification
    verification_date DATETIME,
    verification_user TEXT,   -- Utilisateur ayant vérifié le ticket
    quarantine_until DATETIME, -- Date jusqu'à laquelle les points sont en quarantaine
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (magasin_id) REFERENCES points_vente(magasin_id)
);

-- Index unique pour éviter les doublons de factures par client
CREATE UNIQUE INDEX idx_unique_facture_client ON tickets_caisse(client_id, numero_facture, montant_total) WHERE validation_status != 'rejected';

-- Table pour l'audit des tickets
CREATE TABLE audit_tickets (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    date_audit DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,
    ancien_statut TEXT,
    nouveau_statut TEXT,
    utilisateur TEXT,
    details TEXT,
    ip_address TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets_caisse(ticket_id)
);

-- Table pour les motifs de suspicion de fraude
CREATE TABLE motifs_suspicion (
    motif_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    type_motif TEXT NOT NULL CHECK (type_motif IN ('doublon', 'alteration', 'delai_suspect', 'incohérence', 'autre')),
    description TEXT,
    niveau_risque INTEGER CHECK (niveau_risque BETWEEN 1 AND 5),
    date_detection DATETIME DEFAULT CURRENT_TIMESTAMP,
    traite BOOLEAN DEFAULT 0,
    action_prise TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets_caisse(ticket_id)
);

-- Table pour gérer les règles d'extraction OCR
CREATE TABLE regles_ocr (
    regle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    pattern TEXT NOT NULL,  -- Expression régulière pour extraire des données
    champ_cible TEXT NOT NULL,  -- Nom du champ à extraire (ex: "montant_total", "date")
    priorite INTEGER DEFAULT 0,  -- Plus le chiffre est élevé, plus la règle est prioritaire
    est_active BOOLEAN DEFAULT 1,
    description TEXT
);

-- Table pour les résultats d'extraction OCR
CREATE TABLE extractions_ocr (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    champ TEXT NOT NULL,  -- Ex: "montant_total", "date", "magasin", etc.
    valeur TEXT,
    confiance REAL,       -- Score de confiance de l'extraction (0-1)
    regle_id INTEGER,     -- Référence à la règle qui a permis l'extraction
    verifie BOOLEAN DEFAULT 0,
    FOREIGN KEY (ticket_id) REFERENCES tickets_caisse(ticket_id),
    FOREIGN KEY (regle_id) REFERENCES regles_ocr(regle_id)
);

-- Table pour l'historique des points
CREATE TABLE historique_points (
    historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    carte_id INTEGER NOT NULL,
    date_operation DATETIME DEFAULT CURRENT_TIMESTAMP,
    type_operation TEXT NOT NULL CHECK (type_operation IN ('gain', 'gain_pending', 'gain_validated', 'gain_rejected', 'utilisation', 'expiration', 'ajustement', 'bonus')),
    points INTEGER NOT NULL,
    transaction_id INTEGER,
    ticket_id INTEGER,  -- Lien avec le ticket source si applicable
    recompense_id INTEGER,
    description TEXT,
    solde_apres INTEGER NOT NULL,
    validation_status TEXT DEFAULT 'validated' CHECK (validation_status IN ('pending', 'validated', 'rejected')),
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (carte_id) REFERENCES cartes_fidelite(carte_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (ticket_id) REFERENCES tickets_caisse(ticket_id)
);

-- Table des récompenses disponibles
CREATE TABLE recompenses (
    recompense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT,
    categorie TEXT CHECK (categorie IN ('remise', 'produit', 'experience', 'service', 'partenaire')),
    points_necessaires INTEGER NOT NULL,
    valeur_monetaire REAL,
    date_debut DATETIME,
    date_fin DATETIME,
    statut TEXT DEFAULT 'active' CHECK (statut IN ('active', 'inactive', 'épuisée')),
    quota_total INTEGER,
    quota_restant INTEGER,
    image_url TEXT,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    modification_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table pour l'utilisation des récompenses par les clients
CREATE TABLE utilisation_recompenses (
    utilisation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    carte_id INTEGER NOT NULL,
    recompense_id INTEGER NOT NULL,
    date_demande DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_utilisation DATETIME,
    points_depenses INTEGER NOT NULL,
    code_unique TEXT,
    statut TEXT DEFAULT 'réservée' CHECK (statut IN ('réservée', 'utilisée', 'annulée', 'expirée')),
    transaction_id INTEGER,
    commentaire TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (carte_id) REFERENCES cartes_fidelite(carte_id),
    FOREIGN KEY (recompense_id) REFERENCES recompenses(recompense_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

-- Table des campagnes marketing
CREATE TABLE campagnes_marketing (
    campagne_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT,
    type TEXT CHECK (type IN ('email', 'sms', 'notification', 'courrier', 'mixte')),
    date_debut DATETIME NOT NULL,
    date_fin DATETIME NOT NULL,
    public_cible TEXT,  -- Description du segment ciblé
    criteres_selection TEXT,  -- Critères SQL ou JSON pour la sélection des clients
    offre TEXT,
    multiplicateur_points REAL DEFAULT 1.0,
    budget REAL,
    statut TEXT DEFAULT 'planifiée' CHECK (statut IN ('planifiée', 'active', 'terminée', 'annulée')),
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    creation_user TEXT
);

-- Table pour la participation aux campagnes
CREATE TABLE participation_campagnes (
    participation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campagne_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    date_envoi DATETIME,
    canal TEXT,
    statut TEXT DEFAULT 'envoyé' CHECK (statut IN ('envoyé', 'erreur', 'ouvert', 'cliqué')),
    date_reponse DATETIME,
    conversion BOOLEAN DEFAULT 0,
    transaction_id INTEGER,
    FOREIGN KEY (campagne_id) REFERENCES campagnes_marketing(campagne_id),
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

-- Table pour le feedback des clients
CREATE TABLE feedback_clients (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    transaction_id INTEGER,
    date_feedback DATETIME DEFAULT CURRENT_TIMESTAMP,
    canal TEXT CHECK (canal IN ('email', 'app', 'web', 'sms', 'en_magasin', 'telephone')),
    score_nps INTEGER CHECK (score_nps BETWEEN 0 AND 10),
    score_satisfaction INTEGER CHECK (score_satisfaction BETWEEN 1 AND 5),
    commentaire TEXT,
    domaines TEXT,  -- JSON array: ["produit", "service", "prix", ...]
    contacts_souhaites BOOLEAN DEFAULT 0,
    traite BOOLEAN DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

-- Table pour les limites et quotas de points
CREATE TABLE limites_points (
    limite_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_limite TEXT CHECK (type_limite IN ('quotidien', 'hebdomadaire', 'mensuel', 'transaction')),
    valeur_limite INTEGER NOT NULL,
    description TEXT,
    est_active BOOLEAN DEFAULT 1,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    modification_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table de logs d'accès aux données (pour conformité RGPD et audit)
CREATE TABLE logs_acces_donnees (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur TEXT NOT NULL,
    date_acces DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,  -- "lecture", "modification", "suppression", "export"
    table_concernee TEXT NOT NULL,
    identifiant INTEGER,  -- ID de l'enregistrement concerné
    details TEXT,         -- Détails supplémentaires sur l'accès
    ip_address TEXT
);

-- -----------------------------------------------
-- VUES
-- -----------------------------------------------

-- Vue pour l'analyse RFM (Récence, Fréquence, Montant)
CREATE VIEW analyse_rfm AS
SELECT 
    c.client_id,
    c.uuid,
    JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(MAX(t.date_transaction)) AS recence_jours,
    COUNT(t.transaction_id) AS frequence_achats,
    SUM(t.montant_total) AS montant_total,
    AVG(t.montant_total) AS panier_moyen
FROM 
    clients_anonymized c
LEFT JOIN 
    transactions t ON c.client_id = t.client_id
WHERE 
    t.date_transaction >= date('now', '-1 year')
    AND c.statut = 'actif'
GROUP BY 
    c.client_id, c.uuid;

-- Vue pour les statistiques d'achat par catégorie (anonymisées)
CREATE VIEW stats_achat_categories AS
SELECT 
    ca.uuid,
    ca.tranche_age,
    ca.genre,
    ca.region,
    cp.nom AS categorie,
    COUNT(DISTINCT t.transaction_id) AS nb_transactions,
    SUM(dt.quantite) AS quantite_totale,
    SUM(dt.montant_ligne) AS montant_total,
    AVG(dt.prix_unitaire) AS prix_moyen
FROM 
    clients_anonymized ca
JOIN 
    transactions t ON ca.client_id = t.client_id
JOIN 
    details_transactions dt ON t.transaction_id = dt.transaction_id
JOIN 
    produits p ON dt.produit_id = p.produit_id
JOIN 
    categories_produits cp ON p.categorie_id = cp.categorie_id
WHERE 
    t.date_transaction >= date('now', '-6 month')
GROUP BY 
    ca.uuid, ca.tranche_age, ca.genre, ca.region, cp.nom;

-- Vue pour l'identification des tickets suspects
CREATE VIEW tickets_suspects AS
SELECT 
    c.client_id, 
    c.uuid,
    COUNT(t.ticket_id) AS nombre_tickets,
    AVG(julianday(t.date_upload) - julianday(t.date_transaction)) AS delai_moyen_upload,
    SUM(CASE WHEN t.validation_status = 'rejected' THEN 1 ELSE 0 END) AS tickets_rejetes,
    SUM(CASE WHEN m.niveau_risque >= 4 THEN 1 ELSE 0 END) AS tickets_haut_risque,
    c.niveau_confiance
FROM 
    clients c
JOIN 
    tickets_caisse t ON c.client_id = t.client_id
LEFT JOIN 
    motifs_suspicion m ON t.ticket_id = m.ticket_id
GROUP BY 
    c.client_id, c.uuid
HAVING 
    tickets_rejetes > 0 OR 
    tickets_haut_risque > 0 OR
    nombre_tickets > 20 OR
    delai_moyen_upload > 15;

-- Vue pour identifier les soumissions de tickets anormales
CREATE VIEW anomalies_soumission_tickets AS
SELECT 
    t.ticket_id,
    t.client_id,
    c.uuid,
    t.date_transaction,
    t.date_upload,
    JULIANDAY(t.date_upload) - JULIANDAY(t.date_transaction) AS delai_soumission,
    t.montant_total,
    pv.nom AS magasin,
    t.validation_status,
    CASE 
        WHEN JULIANDAY(t.date_upload) - JULIANDAY(t.date_transaction) > 30 THEN 'Délai excessif'
        WHEN EXISTS (
            SELECT 1 FROM tickets_caisse t2 
            WHERE t2.ticket_id != t.ticket_id 
              AND t2.client_id = t.client_id 
              AND t2.montant_total = t.montant_total 
              AND abs(julianday(t2.date_transaction) - julianday(t.date_transaction)) < 1
        ) THEN 'Doublon potentiel'
        WHEN t.montant_total > 1000 THEN 'Montant élevé'
        ELSE NULL
    END AS raison_anomalie
FROM 
    tickets_caisse t
JOIN 
    clients c ON t.client_id = c.client_id
JOIN 
    points_vente pv ON t.magasin_id = pv.magasin_id
WHERE 
    (JULIANDAY(t.date_upload) - JULIANDAY(t.date_transaction) > 30) OR
    EXISTS (
        SELECT 1 FROM tickets_caisse t2 
        WHERE t2.ticket_id != t.ticket_id 
          AND t2.client_id = t.client_id 
          AND t2.montant_total = t.montant_total 
          AND abs(julianday(t2.date_transaction) - julianday(t.date_transaction)) < 1
    ) OR
    t.montant_total > 1000;

-- -----------------------------------------------
-- DÉCLENCHEURS (TRIGGERS)
-- -----------------------------------------------

-- Déclencheur pour mettre à jour la table clients_anonymized
CREATE TRIGGER update_client_anonymized AFTER INSERT ON clients
BEGIN
    INSERT INTO clients_anonymized (
        client_id, 
        uuid, 
        age, 
        tranche_age, 
        genre, 
        region, 
        segment, 
        date_inscription, 
        statut
    )
    VALUES (
        NEW.client_id,
        NEW.uuid,
        (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)),
        CASE 
            WHEN (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)) < 18 THEN '<18'
            WHEN (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)) BETWEEN 18 AND 25 THEN '18-25'
            WHEN (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)) BETWEEN 26 AND 35 THEN '26-35'
            WHEN (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)) BETWEEN 36 AND 50 THEN '36-50'
            WHEN (strftime('%Y', 'now') - strftime('%Y', NEW.date_naissance)) BETWEEN 51 AND 65 THEN '51-65'
            ELSE '65+'
        END,
        NEW.genre,
        SUBSTR(NEW.code_postal, 1, 2),
        NEW.segment,
        date(NEW.date_inscription),
        NEW.statut
    );
END;

-- Déclencheur pour calculer automatiquement les points gagnés lors d'une transaction
CREATE TRIGGER calculate_points_earned AFTER INSERT ON details_transactions
BEGIN
    UPDATE details_transactions
    SET points_ligne = ROUND(montant_ligne * 
        (SELECT COALESCE(p.multiplicateur_points, 1.0) * 
         COALESCE(cp.multiplicateur_points, 1.0) * 
         COALESCE(
            (SELECT multiplicateur_points FROM niveaux_fidelite nf 
             JOIN cartes_fidelite cf ON nf.nom = cf.niveau_fidelite 
             JOIN transactions t ON cf.carte_id = t.carte_id 
             WHERE t.transaction_id = NEW.transaction_id), 
            1.0
         )
        FROM produits p
        LEFT JOIN categories_produits cp ON p.categorie_id = cp.categorie_id
        WHERE p.produit_id = NEW.produit_id))
    WHERE detail_id = NEW.detail_id;
    
    -- Mettre à jour le total des points pour la transaction
    UPDATE transactions 
    SET points_gagnes = (
        SELECT COALESCE(SUM(points_ligne), 0) 
        FROM details_transactions 
        WHERE transaction_id = NEW.transaction_id
    )
    WHERE transaction_id = NEW.transaction_id;
END;

-- Déclencheur pour mettre à jour les points du client après une transaction
CREATE TRIGGER update_client_points AFTER UPDATE OF points_gagnes ON transactions
WHEN NEW.points_gagnes > 0
BEGIN
    -- Mettre à jour les points de la carte de fidélité
    UPDATE cartes_fidelite
    SET points_actuels = points_actuels + NEW.points_gagnes,
        date_derniere_activite = CURRENT_TIMESTAMP
    WHERE carte_id = NEW.carte_id;
    
    -- Enregistrer dans l'historique des points
    INSERT INTO historique_points (
        client_id, 
        carte_id, 
        type_operation, 
        points, 
        transaction_id, 
        description, 
        solde_apres,
        validation_status
    )
    VALUES (
        NEW.client_id,
        NEW.carte_id,
        'gain',
        NEW.points_gagnes,
        NEW.transaction_id,
        'Points gagnés lors d''un achat',
        (SELECT points_actuels FROM cartes_fidelite WHERE carte_id = NEW.carte_id),
        'validated'
    );
END;

-- Déclencheur pour vérifier et mettre à jour le niveau de fidélité
CREATE TRIGGER check_fidelity_level AFTER UPDATE OF points_actuels ON cartes_fidelite
BEGIN
    UPDATE cartes_fidelite
    SET niveau_fidelite = (
        SELECT nom
        FROM niveaux_fidelite
        WHERE points_minimum <= NEW.points_actuels
        AND (points_maximum IS NULL OR points_maximum >= NEW.points_actuels)
        ORDER BY points_minimum DESC
        LIMIT 1
    )
    WHERE carte_id = NEW.carte_id
    AND niveau_fidelite != (
        SELECT nom
        FROM niveaux_fidelite
        WHERE points_minimum <= NEW.points_actuels
        AND (points_maximum IS NULL OR points_maximum >= NEW.points_actuels)
        ORDER BY points_minimum DESC
        LIMIT 1
    );
END;

-- Déclencheur pour calculer le hash du ticket lors de l'insertion
CREATE TRIGGER generate_ticket_hash BEFORE INSERT ON tickets_caisse
WHEN NEW.ticket_hash IS NULL
BEGIN
    UPDATE tickets_caisse
    SET ticket_hash = lower(hex(
        randomblob(4) || 
        cast(NEW.client_id as blob) || 
        cast(NEW.montant_total as blob) || 
        cast(NEW.date_transaction as blob) ||
        cast(NEW.numero_facture as blob)
    ))
    WHERE rowid = NEW.rowid;
END;

-- Déclencheur pour détecter les doublons potentiels - Corrigé pour SQLite
CREATE TRIGGER detect_duplicate_tickets AFTER INSERT ON tickets_caisse
BEGIN
    -- Recherche de tickets similaires (même montant, même date, même magasin)
    INSERT INTO motifs_suspicion (
        ticket_id,
        type_motif,
        description,
        niveau_risque
    )
    SELECT 
        NEW.ticket_id,
        'doublon',
        'Ticket similaire à ' || t.ticket_id,
        4
    FROM tickets_caisse t
    WHERE t.ticket_id != NEW.ticket_id
      AND t.client_id = NEW.client_id
      AND t.montant_total = NEW.montant_total
      AND t.magasin_id = NEW.magasin_id
      AND abs(julianday(t.date_transaction) - julianday(NEW.date_transaction)) < 1
    LIMIT 1;
    
    -- Marquer le ticket comme suspect s'il y a un doublon
    UPDATE tickets_caisse
    SET validation_status = 'suspicious'
    WHERE ticket_id = NEW.ticket_id
    AND EXISTS (SELECT 1 FROM motifs_suspicion WHERE ticket_id = NEW.ticket_id AND type_motif = 'doublon');
    
    -- Détecter les soumissions tardives
    INSERT INTO motifs_suspicion (
        ticket_id,
        type_motif,
        description,
        niveau_risque
    )
    SELECT
        NEW.ticket_id,
        'delai_suspect',
        'Ticket soumis ' || CAST(round(julianday(NEW.date_upload) - julianday(NEW.date_transaction)) AS TEXT) || ' jours après la date de transaction',
        3
    WHERE julianday(NEW.date_upload) - julianday(NEW.date_transaction) > 15;
    
    -- Détecter les montants anormalement élevés
    INSERT INTO motifs_suspicion (
        ticket_id,
        type_motif,
        description,
        niveau_risque
    )
    SELECT
        NEW.ticket_id,
        'montant_eleve',
        'Montant de ticket anormalement élevé: ' || NEW.montant_total,
        2
    WHERE NEW.montant_total > 1000;
    
    -- Nécessite une revue manuelle pour les montants élevés
    UPDATE tickets_caisse
    SET validation_status = 'requires_manual_review'
    WHERE ticket_id = NEW.ticket_id 
    AND validation_status = 'pending_validation'
    AND NEW.montant_total > 1000;


END;

PRAGMA foreign_keys = ON;