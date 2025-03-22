import sqlite3
import json
import time
import datetime
import uuid
import random

def evaluer_regles_fidelite(db_path):
    """
    Fonction qui évalue les règles de fidélité et génère les offres pour les clients éligibles
    
    Args:
        db_path (str): Chemin vers la base de données SQLite
    """
    conn = sqlite3.connect(db_path)
    # Activer le support pour les clés étrangères
    conn.execute("PRAGMA foreign_keys = ON")
    # Permettre d'accéder aux colonnes par nom
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Variables pour suivre les statistiques d'exécution
    debut_execution = datetime.datetime.now()
    nb_clients_traites = 0
    nb_offres_generees = 0
    
    # Récupérer toutes les règles actives
    cursor.execute("""
        SELECT * FROM regles_fidelite 
        WHERE est_active = 1
          AND (date_debut IS NULL OR date_debut <= date('now'))
          AND (date_fin IS NULL OR date_fin >= date('now'))
        ORDER BY priorite DESC
    """)
    
    regles_actives = cursor.fetchall()
    
    for regle in regles_actives:
        # Initialiser les compteurs pour cette règle
        nb_evaluations_regle = 0
        nb_offres_regle = 0
        
        # 1. Règle basée sur le nombre d'achats
        if regle['type_regle'] == 'nombre_achats':
            # Trouver les clients qui ont effectué le nombre d'achats requis
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre générée après ' || ? || ' achats'
                FROM clients c
                JOIN (
                    SELECT 
                        client_id, 
                        COUNT(DISTINCT transaction_id) as nb_achats
                    FROM transactions
                    WHERE date_transaction >= CASE 
                                             WHEN ? IS NOT NULL 
                                             THEN date('now', '-' || ? || ' days')
                                             ELSE '1900-01-01'
                                             END
                    GROUP BY client_id
                    HAVING nb_achats >= ?
                ) achats ON c.client_id = achats.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                WHERE oc.offre_id IS NULL
                  AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['condition_valeur'],
                regle['periode_jours'],
                regle['periode_jours'],
                int(regle['condition_valeur']),
                regle['regle_id'],
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 2. Règle basée sur le montant cumulé
        elif regle['type_regle'] == 'montant_cumule':
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre générée après ' || ? || '€ d''achats cumulés'
                FROM clients c
                JOIN (
                    SELECT 
                        client_id, 
                        SUM(montant_total) as montant_total
                    FROM transactions
                    WHERE date_transaction >= CASE 
                                             WHEN ? IS NOT NULL 
                                             THEN date('now', '-' || ? || ' days')
                                             ELSE '1900-01-01'
                                            END
                    GROUP BY client_id
                    HAVING montant_total >= ?
                ) achats ON c.client_id = achats.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                WHERE oc.offre_id IS NULL
                  AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['condition_valeur'],
                regle['periode_jours'],
                regle['periode_jours'],
                float(regle['condition_valeur']),
                regle['regle_id'],
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 3. Règle basée sur l'achat d'un produit spécifique
        elif regle['type_regle'] == 'produit_specifique':
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre générée après achat du produit ID ' || ?
                FROM clients c
                JOIN (
                    SELECT DISTINCT t.client_id
                    FROM transactions t
                    JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                    WHERE dt.produit_id = ?
                      AND t.date_transaction >= CASE 
                                                WHEN ? IS NOT NULL 
                                                THEN date('now', '-' || ? || ' days')
                                                ELSE '1900-01-01'
                                               END
                ) achats ON c.client_id = achats.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                WHERE oc.offre_id IS NULL
                  AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['condition_valeur'],
                int(regle['condition_valeur']),
                regle['periode_jours'],
                regle['periode_jours'],
                regle['regle_id'],
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 4. Règle basée sur l'achat dans une catégorie spécifique
        elif regle['type_regle'] == 'categorie_specifique':
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre générée après achat dans la catégorie ID ' || ?
                FROM clients c
                JOIN (
                    SELECT DISTINCT t.client_id
                    FROM transactions t
                    JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                    JOIN produits p ON dt.produit_id = p.produit_id
                    WHERE p.categorie_id = ?
                      AND t.date_transaction >= CASE 
                                                WHEN ? IS NOT NULL 
                                                THEN date('now', '-' || ? || ' days')
                                                ELSE '1900-01-01'
                                               END
                ) achats ON c.client_id = achats.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                WHERE oc.offre_id IS NULL
                  AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['condition_valeur'],
                int(regle['condition_valeur']),
                regle['periode_jours'],
                regle['periode_jours'],
                regle['regle_id'],
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 5. Règle basée sur la première visite
        elif regle['type_regle'] == 'premiere_visite':
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre de bienvenue après première visite'
                FROM clients c
                JOIN (
                    SELECT 
                        client_id,
                        MIN(date_transaction) as premiere_transaction
                    FROM transactions
                    GROUP BY client_id
                    HAVING premiere_transaction >= date('now', '-' || ? || ' days')
                ) prem ON c.client_id = prem.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                WHERE oc.offre_id IS NULL
                  AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                int(regle['condition_valeur']),
                regle['regle_id'],
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 6. Règle basée sur l'anniversaire
        elif regle['type_regle'] == 'anniversaire':
            # SQLite gère moins bien les fonctions de date que MySQL, nous devons adapter la requête
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre anniversaire'
                FROM clients c
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id 
                     AND oc.regle_id = ?
                     AND strftime('%Y', oc.date_generation) = strftime('%Y', 'now')
                WHERE strftime('%m-%d', c.date_naissance) BETWEEN strftime('%m-%d', 'now') 
                     AND strftime('%m-%d', date('now', '+' || ? || ' days'))
                AND oc.offre_id IS NULL
                AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['regle_id'],
                int(regle['condition_valeur']),
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # 7. Règle basée sur l'inactivité
        elif regle['type_regle'] == 'inactivite':
            cursor.execute("""
                INSERT INTO offres_client (client_id, regle_id, recompense_id, date_expiration, commentaire)
                SELECT 
                    c.client_id,
                    ?,
                    ?,
                    date('now', '+30 days'),
                    'Offre de réactivation après ' || ? || ' jours d''inactivité'
                FROM clients c
                LEFT JOIN (
                    SELECT 
                        client_id,
                        MAX(date_transaction) as derniere_transaction
                    FROM transactions
                    GROUP BY client_id
                ) dern ON c.client_id = dern.client_id
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id 
                     AND oc.regle_id = ?
                     AND (oc.date_generation >= COALESCE(dern.derniere_transaction, c.date_inscription))
                WHERE (
                    dern.derniere_transaction IS NULL OR
                    date(dern.derniere_transaction) <= date('now', '-' || ? || ' days')
                )
                AND oc.offre_id IS NULL
                AND c.statut = 'actif'
                AND (? IS NULL OR json_extract(?, '$') LIKE '%' || c.segment || '%')
            """, (
                regle['regle_id'],
                regle['recompense_id'],
                regle['condition_valeur'],
                regle['regle_id'],
                int(regle['condition_valeur']),
                regle['segments_cibles'],
                regle['segments_cibles']
            ))
            nb_offres_regle = cursor.rowcount
            
        # Mettre à jour les statistiques
        nb_offres_generees += nb_offres_regle
        
        # Enregistrer les statistiques d'évaluation pour cette règle
        cursor.execute("""
            INSERT INTO historique_evaluations_regles (
                regle_id, 
                nombre_clients_evalues, 
                nombre_offres_generees, 
                duree_execution_ms,
                commentaire
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            regle['regle_id'],
            nb_evaluations_regle,
            nb_offres_regle,
            int((datetime.datetime.now() - debut_execution).total_seconds() * 1000),
            f"Exécution du {datetime.datetime.now()}"
        ))
    
    fin_execution = datetime.datetime.now()
    duree_secondes = (fin_execution - debut_execution).total_seconds()
    
    # Commit des changements
    conn.commit()
    
    # Retourner les statistiques d'exécution
    resultat = {
        "clients_traites": nb_clients_traites,
        "offres_generees": nb_offres_generees,
        "duree_secondes": duree_secondes
    }
    
    # Fermer la connexion
    cursor.close()
    conn.close()
    
    return resultat


# Exemple d'utilisation
if __name__ == "__main__":
    # Chemin vers votre base de données SQLite
    db_path = "C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/modules/fidelity_db"
    
    # Exécuter l'évaluation des règles de fidélité
    stats = evaluer_regles_fidelite(db_path)
    
    # Afficher les statistiques
    print(f"Clients traités: {stats['clients_traites']}")
    print(f"Offres générées: {stats['offres_generees']}")
    print(f"Durée (secondes): {stats['duree_secondes']}")
