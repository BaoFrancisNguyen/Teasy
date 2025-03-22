# Système de Fidélité Client - Documentation

## Table des matières
1. [Présentation générale](#présentation-générale)
2. [Structure de la base de données](#structure-de-la-base-de-données)
3. [Processus principaux](#processus-principaux)
4. [Protection anti-fraude](#protection-anti-fraude)
5. [Requêtes et vues analytiques](#requêtes-et-vues-analytiques)
6. [Installation et configuration](#installation-et-configuration)

## Présentation générale

Ce système de fidélité client est une solution complète pour gérer un programme de fidélisation dans un contexte commercial (retail). Il permet de suivre les achats des clients, attribuer des points, gérer des récompenses et des campagnes marketing, tout en offrant une protection robuste contre la fraude.

### Fonctionnalités principales
- Gestion des profils clients avec anonymisation pour les analyses
- Attribution de points via transactions en magasin ou par scan de tickets de caisse
- Système de niveaux de fidélité avec avantages progressifs
- Catalogue de récompenses et suivi de leur utilisation
- Campagnes marketing ciblées et mesure de leur efficacité
- Protection anti-fraude avancée, notamment pour les tickets de caisse
- Analyses RFM (Récence, Fréquence, Montant) et détection des risques d'attrition

## Structure de la base de données

### Tables principales

#### Gestion des clients
- **clients** - Informations personnelles des clients
  - `client_id` - Identifiant unique
  - `uuid` - Identifiant anonymisé
  - `nom`, `prenom`, `email`, etc. - Informations de contact
  - `niveau_confiance` - Score de 0 à 100 indiquant la fiabilité du client

- **clients_anonymized** - Version anonymisée pour les analystes
  - `client_id` - Clé étrangère vers clients
  - `uuid` - Identifiant anonymisé
  - `tranche_age`, `region`, etc. - Données démographiques agrégées

#### Fidélité et points
- **cartes_fidelite** - Cartes associées à chaque client
  - `carte_id` - Identifiant unique
  - `client_id` - Client associé
  - `points_actuels` - Points validés
  - `points_en_attente` - Points en cours de validation
  - `niveau_fidelite` - Niveau actuel (bronze, argent, or, platine)

- **niveaux_fidelite** - Définition des niveaux de fidélité
  - `niveau_id` - Identifiant unique
  - `nom` - Nom du niveau (bronze, argent, or, platine)
  - `points_minimum`, `points_maximum` - Seuils de points
  - `multiplicateur_points` - Bonus multiplicateur de points
  - `avantages` - Description des avantages

- **historique_points** - Journal de tous les mouvements de points
  - `historique_id` - Identifiant unique
  - `client_id`, `carte_id` - Références client et carte
  - `type_operation` - Type de mouvement (gain, utilisation, expiration, etc.)
  - `validation_status` - État de validation (pending, validated, rejected)

#### Transactions et achats
- **transactions** - Registre des achats
  - `transaction_id` - Identifiant unique
  - `client_id`, `carte_id` - Références client et carte
  - `montant_total` - Montant de la transaction
  - `points_gagnes` - Points attribués
  - `validation_source` - Source de validation (pos, ocr, manuel, api)

- **details_transactions** - Lignes des transactions
  - `detail_id` - Identifiant unique
  - `transaction_id` - Transaction parente
  - `produit_id` - Produit acheté
  - `quantite`, `prix_unitaire` - Détails de l'achat
  - `points_ligne` - Points générés par cette ligne

- **tickets_caisse** - Tickets soumis par les clients
  - `ticket_id` - Identifiant unique
  - `client_id` - Client ayant soumis le ticket
  - `ticket_hash` - Empreinte unique du ticket pour détecter les doublons
  - `validation_status` - État de validation
  - `quarantine_until` - Date jusqu'à laquelle les points sont en quarantaine

#### Produits et magasins
- **produits** - Catalogue des produits
  - `produit_id` - Identifiant unique
  - `reference`, `nom`, `prix_standard` - Informations produit
  - `multiplicateur_points` - Bonus spécifique au produit

- **categories_produits** - Catégories de produits
  - `categorie_id` - Identifiant unique
  - `nom`, `description` - Informations sur la catégorie
  - `multiplicateur_points` - Bonus spécifique à la catégorie

- **points_vente** - Magasins et points de vente
  - `magasin_id` - Identifiant unique
  - `nom`, `adresse`, `type` - Informations sur le magasin

#### Récompenses
- **recompenses** - Catalogue des récompenses disponibles
  - `recompense_id` - Identifiant unique
  - `nom`, `description` - Informations sur la récompense
  - `points_necessaires` - Coût en points
  - `quota_total`, `quota_restant` - Gestion des stocks

- **utilisation_recompenses** - Suivi des récompenses utilisées
  - `utilisation_id` - Identifiant unique
  - `client_id`, `carte_id` - Client concerné
  - `recompense_id` - Récompense choisie
  - `statut` - État d'utilisation (réservée, utilisée, annulée, expirée)

#### Marketing
- **campagnes_marketing** - Campagnes promotionnelles
  - `campagne_id` - Identifiant unique
  - `nom`, `description`, `type` - Informations sur la campagne
  - `date_debut`, `date_fin` - Période de validité
  - `public_cible`, `criteres_selection` - Ciblage clients

- **participation_campagnes** - Participation aux campagnes
  - `participation_id` - Identifiant unique
  - `campagne_id`, `client_id` - Campagne et client
  - `statut` - Suivi d'engagement (envoyé, ouvert, cliqué)
  - `conversion` - Indication de conversion

#### Protection anti-fraude
- **motifs_suspicion** - Raisons de suspicion sur les tickets
  - `motif_id` - Identifiant unique
  - `ticket_id` - Ticket concerné
  - `type_motif` - Type de suspicion (doublon, altération, délai, etc.)
  - `niveau_risque` - Score de gravité (1-5)

- **audit_tickets** - Journal des changements de statut des tickets
  - `audit_id` - Identifiant unique
  - `ticket_id` - Ticket concerné
  - `ancien_statut`, `nouveau_statut` - Changement de statut
  - `utilisateur` - Personne ayant effectué le changement

- **limites_points** - Configuration des plafonds de points
  - `limite_id` - Identifiant unique
  - `type_limite` - Type de limite (quotidien, hebdomadaire, etc.)
  - `valeur_limite` - Plafond de points

#### Traitement OCR des tickets
- **regles_ocr** - Règles d'extraction par OCR
  - `regle_id` - Identifiant unique
  - `pattern` - Expression régulière d'extraction
  - `champ_cible` - Champ à extraire (date, montant, etc.)

- **extractions_ocr** - Résultats d'extraction OCR
  - `extraction_id` - Identifiant unique
  - `ticket_id` - Ticket concerné
  - `champ`, `valeur` - Information extraite
  - `confiance` - Score de fiabilité (0-1)

#### Conformité et audit
- **logs_acces_donnees** - Journal d'accès aux données sensibles
  - `log_id` - Identifiant unique
  - `utilisateur`, `date_acces` - Qui et quand
  - `action`, `table_concernee` - Action effectuée
  - `details` - Description de l'action

## Processus principaux

### 1. Cycle de vie client

#### Inscription
1. Un nouveau client est enregistré dans la table `clients`
2. Le trigger `update_client_anonymized` crée automatiquement son entrée anonymisée
3. Une carte de fidélité lui est attribuée avec niveau initial "bronze"

#### Évolution des niveaux
1. À chaque mise à jour des points, le trigger `check_fidelity_level` vérifie si un changement de niveau est nécessaire
2. Les niveaux sont réévalués selon les seuils définis dans `niveaux_fidelite`
3. Un client peut monter ou descendre de niveau selon son activité

### 2. Attribution de points

#### Via transaction en magasin (POS)
1. Une transaction est enregistrée dans `transactions`
2. Les détails sont ajoutés dans `details_transactions`
3. Le trigger `calculate_points_earned` calcule les points pour chaque ligne
4. Le trigger `update_client_points` met à jour les points du client et l'historique

#### Via tickets de caisse (OCR)
1. Le client soumet un ticket via l'application
2. Le ticket est enregistré dans `tickets_caisse` avec statut "en_attente"
3. Le système OCR extrait les informations et les stocke dans `extractions_ocr`
4. Le trigger `set_points_quarantine` met les points en attente de validation
5. Après vérification, le trigger `audit_ticket_status_change` valide ou rejette les points

### 3. Gestion des récompenses

#### Disponibilité des récompenses
1. Les récompenses sont configurées dans `recompenses` avec quotas et dates
2. Le système vérifie la disponibilité avant de permettre une demande

#### Processus de rédemption
1. Le client demande une récompense, créant une entrée dans `utilisation_recompenses`
2. Les points sont débités de son compte
3. La récompense est utilisée et le statut passe à "utilisée"
4. L'opération est enregistrée dans l'historique des points

### 4. Campagnes marketing

#### Création d'une campagne
1. Une campagne est définie dans `campagnes_marketing` avec critères de ciblage
2. Le système identifie les clients correspondant aux critères

#### Suivi et mesure
1. Chaque envoi est enregistré dans `participation_campagnes`
2. Les interactions (ouverture, clic) sont suivies
3. Les conversions sont reliées aux transactions générées

## Protection anti-fraude

### Système de validation des tickets

#### Étapes de validation
1. **Soumission** : Le ticket est enregistré avec un hash unique
2. **Quarantaine** : Les points sont placés en attente pendant une période définie
3. **Vérification** : Contrôles automatiques et/ou manuels selon le profil de risque
4. **Validation/Rejet** : Attribution définitive ou rejet des points

#### Détection de fraude
1. **Doublons** : Le trigger `detect_duplicate_tickets` identifie les soumissions multiples
2. **Tickets anciens** : Le trigger `check_ticket_date_before_insert` bloque les tickets trop anciens
3. **Incohérences** : Analyse des montants, dates, et autres anomalies
4. **Motifs multiples** : Cumul des suspicions dans `motifs_suspicion`

#### Niveaux de risque
- Les tickets sont classés selon leur niveau de risque (1-5)
- Les tickets à risque élevé (≥4) sont automatiquement signalés
- Les tickets à risque moyen (2-3) peuvent nécessiter une vérification manuelle

#### Système de confiance client
- Chaque client a un score de confiance (0-100)
- Ce score est ajusté en fonction de l'historique des validations
- Les tickets des clients à haute confiance peuvent suivre un parcours de validation allégé

## Requêtes et vues analytiques

### Analyses RFM (Récence, Fréquence, Montant)
- `analyse_rfm` : Données brutes RFM par client
- `rfm_scores` : Scores calculés pour segmentation client

### Détection d'attrition
- `clients_risque_attrition` : Identifie les clients inactifs depuis plus de 60 jours

### Analyses comportementales
- `comportements_achat` : Habitudes d'achat (panier moyen, fréquence, etc.)
- `stats_achat_categories` : Préférences par catégorie de produits

### Surveillance anti-fraude
- `tickets_suspects` : Liste les tickets présentant des signes de fraude
- `anomalies_soumission_tickets` : Détecte les patterns anormaux de soumission
- `resume_tickets_client` : Synthèse de l'historique de tickets par client

## Installation et configuration

### Prérequis
- SQLite 3.x ou version supérieure
- Python 3.6+ pour les scripts d'initialisation

### Initialisation de la base
1. Créer la base de données:
   ```
   sqlite3 fidelity_db.sqlite < schema.sql
   ```

2. Initialiser les données de test:
   ```
   python python-db-init.py
   ```

### Configuration des paramètres anti-fraude
1. Ajuster les limites de points dans la table `limites_points`
2. Configurer la durée de quarantaine dans le trigger `set_points_quarantine`
3. Définir les seuils de risque pour la validation automatique/manuelle

### Intégration avec les systèmes existants
1. **Système de caisse (POS)** : API pour enregistrer les transactions
2. **Application mobile** : Interfaces pour soumission de tickets et consultation des points
3. **OCR** : Service d'extraction de texte pour les tickets
4. **CRM** : Synchronisation des données clients

---

## Notes de déploiement

Le système est conçu pour être évolutif et sécurisé. Les triggers et contraintes SQLite garantissent l'intégrité des données et la prévention de la fraude au niveau de la base de données.

Pour un environnement de production, il est recommandé de:
1. Mettre en place des sauvegardes régulières
2. Configurer des routines de purge pour les données anciennes
3. Définir des rôles d'accès différenciés pour les opérateurs
4. Mettre en place une surveillance active des tentatives de fraude

---

Documentation générée le: 18 mars 2025
