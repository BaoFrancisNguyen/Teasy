"""
Module de gestion du programme de fidélité

Ce module contient les classes et fonctions nécessaires pour gérer le programme de fidélité,
notamment l'évaluation des règles, la génération d'offres, et la gestion des points.
"""

import sqlite3
import json
import logging
import uuid
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LoyaltyManager:
    """
    Classe principale pour la gestion du programme de fidélité.
    Gère l'évaluation des règles, la génération et l'envoi d'offres, et la gestion des points.
    """
    
    def __init__(self, db_path='modules/fidelity_db.sqlite'):
        """
        Initialise le gestionnaire de fidélité.
        
        Args:
            db_path (str): Chemin vers la base de données SQLite
        """
        self.db_path = db_path
    
    def _get_connection(self):
        """
        Établit et retourne une connexion à la base de données.
        
        Returns:
            sqlite3.Connection: Connexion à la base de données
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def evaluate_all_rules(self):
        """
        Évalue toutes les règles de fidélité actives et génère des offres pour les clients éligibles.
        
        Returns:
            dict: Résultat de l'évaluation avec des statistiques
        """
        try:
            conn = self._get_connection()
            
            # Récupérer les règles actives
            rules = conn.execute('''
                SELECT * FROM regles_fidelite 
                WHERE est_active = 1
                AND (date_debut IS NULL OR date_debut <= date('now'))
                AND (date_fin IS NULL OR date_fin >= date('now'))
                ORDER BY priorite DESC
            ''').fetchall()
            
            stats = {
                'total_rules_evaluated': len(rules),
                'total_clients_evaluated': 0,
                'total_offers_generated': 0,
                'rules_details': []
            }
            
            # Pour chaque règle, exécuter la logique appropriée
            for rule in rules:
                rule_dict = dict(rule)
                offers_for_rule = 0
                clients_evaluated = 0
                
                # Appeler la méthode spécifique selon le type de règle
                if rule['type_regle'] == 'nombre_achats':
                    result = self._evaluate_purchase_count_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'montant_cumule':
                    result = self._evaluate_cumulative_amount_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'produit_specifique':
                    result = self._evaluate_specific_product_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'categorie_specifique':
                    result = self._evaluate_specific_category_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'premiere_visite':
                    result = self._evaluate_first_visit_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'anniversaire':
                    result = self._evaluate_birthday_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                elif rule['type_regle'] == 'inactivite':
                    result = self._evaluate_inactivity_rule(conn, rule_dict)
                    offers_for_rule = result['offers_generated']
                    clients_evaluated = result['clients_evaluated']
                
                # Enregistrer les statistiques d'évaluation
                conn.execute('''
                    INSERT INTO historique_evaluations_regles (
                        regle_id, nombre_clients_evalues, nombre_offres_generees, commentaire
                    ) VALUES (?, ?, ?, ?)
                ''', (
                    rule['regle_id'],
                    clients_evaluated,
                    offers_for_rule,
                    f"Évaluation automatique le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ))
                
                # Ajouter les statistiques de cette règle au résultat global
                stats['total_clients_evaluated'] += clients_evaluated
                stats['total_offers_generated'] += offers_for_rule
                stats['rules_details'].append({
                    'rule_id': rule['regle_id'],
                    'rule_name': rule['nom'],
                    'clients_evaluated': clients_evaluated,
                    'offers_generated': offers_for_rule
                })
            
            # Générer des codes uniques pour toutes les nouvelles offres
            conn.execute('''
                UPDATE offres_client
                SET code_unique = 'OF-' || offre_id || '-' || substr(hex(randomblob(4)), 1, 8)
                WHERE code_unique IS NULL
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Évaluation des règles terminée: {stats['total_offers_generated']} offres générées")
            return {'success': True, 'stats': stats}
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation des règles: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _evaluate_purchase_count_rule(self, conn, rule):
        """
        Évalue une règle basée sur le nombre d'achats.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Préparer la condition de période
        period_condition = ''
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients éligibles
        query = f'''
            SELECT 
                c.client_id
            FROM clients c
            JOIN (
                SELECT 
                    client_id, 
                    COUNT(DISTINCT transaction_id) as nb_achats
                FROM transactions
                WHERE 1=1 {period_condition}
                GROUP BY client_id
                HAVING nb_achats >= ?
            ) achats ON c.client_id = achats.client_id
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE oc.offre_id IS NULL
            AND c.statut = 'actif'
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['condition_valeur'], rule['regle_id'])).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                f"Offre générée après {rule['condition_valeur']} achats"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_cumulative_amount_rule(self, conn, rule):
        """
        Évalue une règle basée sur le montant cumulé d'achats.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Préparer la condition de période
        period_condition = ''
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients éligibles
        query = f'''
            SELECT 
                c.client_id
            FROM clients c
            JOIN (
                SELECT 
                    client_id, 
                    SUM(montant_total) as montant_cumule
                FROM transactions
                WHERE 1=1 {period_condition}
                GROUP BY client_id
                HAVING montant_cumule >= ?
            ) achats ON c.client_id = achats.client_id
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE oc.offre_id IS NULL
            AND c.statut = 'actif'
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['condition_valeur'], rule['regle_id'])).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                f"Offre générée après {rule['condition_valeur']}€ d'achats cumulés"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_specific_product_rule(self, conn, rule):
        """
        Évalue une règle basée sur l'achat d'un produit spécifique.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Préparer la condition de période
        period_condition = ''
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients éligibles
        query = f'''
            SELECT DISTINCT
                c.client_id
            FROM clients c
            JOIN transactions t ON c.client_id = t.client_id
            JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE dt.produit_id = ?
            {period_condition}
            AND oc.offre_id IS NULL
            AND c.statut = 'actif'
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                f"Offre générée après achat du produit #{rule['condition_valeur']}"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_specific_category_rule(self, conn, rule):
        """
        Évalue une règle basée sur l'achat dans une catégorie spécifique.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Préparer la condition de période
        period_condition = ''
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients éligibles
        query = f'''
            SELECT DISTINCT
                c.client_id
            FROM clients c
            JOIN transactions t ON c.client_id = t.client_id
            JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
            JOIN produits p ON dt.produit_id = p.produit_id
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE p.categorie_id = ?
            {period_condition}
            AND oc.offre_id IS NULL
            AND c.statut = 'actif'
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                f"Offre générée après achat dans catégorie #{rule['condition_valeur']}"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_first_visit_rule(self, conn, rule):
        """
        Évalue une règle basée sur la première visite d'un client.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients éligibles (nouveaux clients dans les X jours)
        # Utilisation de date_creation au lieu de première transaction
        query = f'''
            SELECT 
                c.client_id
            FROM clients c
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE c.date_creation >= date('now', '-{rule['condition_valeur']} days')
            AND c.date_creation <= date('now')
            AND c.statut = 'actif'
            AND c.marketing_consent = 1
            AND oc.offre_id IS NULL
            {segment_condition}
        '''
        
        # Logs pour le débogage
        logger.info(f"Requête SQL pour première visite: {query}")
        logger.info(f"Paramètres: {(rule['regle_id'],)}")
        
        eligible_clients = conn.execute(query, (rule['regle_id'],)).fetchall()
        
        logger.info(f"Nombre de clients éligibles pour première visite: {len(eligible_clients)}")
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                "Offre de bienvenue"
            ))
            offers_generated += 1
        
        logger.info(f"Nombre d'offres générées pour première visite: {offers_generated}")
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_birthday_rule(self, conn, rule):
        """
        Évalue une règle basée sur l'anniversaire des clients.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients dont l'anniversaire approche
        query = f'''
            SELECT 
                c.client_id
            FROM clients c
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE 
                strftime('%m-%d', c.date_naissance) BETWEEN 
                strftime('%m-%d', date('now')) AND 
                strftime('%m-%d', date('now', '+{rule['condition_valeur']} days'))
            AND oc.offre_id IS NULL
            AND c.statut = 'actif'
            AND c.date_naissance IS NOT NULL
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['regle_id'],)).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours après l'anniversaire)
            # Trouver l'anniversaire cette année
            current_year = datetime.now().year
            client_data = conn.execute('SELECT date_naissance FROM clients WHERE client_id = ?', 
                                     (client['client_id'],)).fetchone()
            
            birthday_date = client_data['date_naissance']
            birthday_parts = birthday_date.split('-')
            
            if len(birthday_parts) >= 3:
                month = int(birthday_parts[1])
                day = int(birthday_parts[2])
                
                this_year_birthday = datetime(current_year, month, day)
                if this_year_birthday < datetime.now():
                    this_year_birthday = datetime(current_year + 1, month, day)
                
                expiration_date = (this_year_birthday + timedelta(days=30)).strftime('%Y-%m-%d')
            else:
                # Fallback si le format de date est incorrect
                expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                "Offre d'anniversaire"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def _evaluate_inactivity_rule(self, conn, rule):
        """
        Évalue une règle basée sur l'inactivité des clients.
        
        Args:
            conn (sqlite3.Connection): Connexion à la base de données
            rule (dict): Informations sur la règle à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Vérifier les restrictions de segment si spécifiées
        segment_condition = ''
        if rule['segments_cibles']:
            try:
                segments = json.loads(rule['segments_cibles'])
                if segments:
                    segments_str = ','.join([f"'{s}'" for s in segments])
                    segment_condition = f"AND c.segment IN ({segments_str})"
            except:
                pass
        
        # Trouver les clients inactifs
        query = f'''
            SELECT 
                c.client_id
            FROM clients c
            JOIN (
                SELECT 
                    client_id,
                    MAX(date_transaction) as derniere_visite
                FROM transactions
                GROUP BY client_id
                HAVING derniere_visite <= date('now', '-{rule['condition_valeur']} days')
            ) dv ON c.client_id = dv.client_id
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
            WHERE oc.offre_id IS NULL
            AND c.statut = 'actif'
            {segment_condition}
        '''
        
        eligible_clients = conn.execute(query, (rule['regle_id'],)).fetchall()
        
        # Générer des offres pour chaque client éligible
        offers_generated = 0
        for client in eligible_clients:
            # Déterminer la date d'expiration (par défaut 30 jours)
            expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Créer l'offre
            conn.execute('''
                INSERT INTO offres_client (
                    client_id, regle_id, recompense_id, date_generation, date_expiration, 
                    statut, commentaire
                ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
            ''', (
                client['client_id'],
                rule['regle_id'],
                rule['recompense_id'],
                expiration_date,
                "Offre pour client inactif"
            ))
            offers_generated += 1
        
        return {
            'clients_evaluated': len(eligible_clients),
            'offers_generated': offers_generated
        }
    
    def evaluate_rules_for_client(self, client_id):
        """
        Évalue les règles de fidélité pour un client spécifique
        
        Args:
            client_id: ID du client à évaluer
            
        Returns:
            dict: Résultat de l'évaluation
        """
        try:
            conn = self._get_connection()
            
            # Récupérer les règles actives
            rules = conn.execute('''
                SELECT * FROM regles_fidelite 
                WHERE est_active = 1
                AND (date_debut IS NULL OR date_debut <= date('now'))
                AND (date_fin IS NULL OR date_fin >= date('now'))
                ORDER BY priorite DESC
            ''').fetchall()
            
            offers_generated = 0
            rules_applied = []
            
            # Pour chaque règle, vérifier si le client est éligible
            for rule in rules:
                rule_dict = dict(rule)
                
                # Appeler la méthode spécifique selon le type de règle
                eligible = False
                
                if rule['type_regle'] == 'nombre_achats':
                    eligible = self._check_purchase_count_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'montant_cumule':
                    eligible = self._check_cumulative_amount_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'produit_specifique':
                    eligible = self._check_specific_product_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'categorie_specifique':
                    eligible = self._check_specific_category_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'premiere_visite':
                    eligible = self._check_first_visit_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'anniversaire':
                    eligible = self._check_birthday_eligibility(conn, client_id, rule_dict)
                
                elif rule['type_regle'] == 'inactivite':
                    eligible = self._check_inactivity_eligibility(conn, client_id, rule_dict)
                
                # Si le client est éligible, créer l'offre
                if eligible:
                    # Vérifier que le client n'a pas déjà cette offre
                    existing_offer = conn.execute('''
                        SELECT offre_id FROM offres_client 
                        WHERE client_id = ? AND regle_id = ?
                    ''', (client_id, rule['regle_id'])).fetchone()
                    
                    if not existing_offer:
                        # Créer l'offre
                        expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        conn.execute('''
                            INSERT INTO offres_client (
                                client_id, regle_id, recompense_id, date_generation, date_expiration, 
                                statut, commentaire
                            ) VALUES (?, ?, ?, date('now'), ?, 'generee', ?)
                        ''', (
                            client_id,
                            rule['regle_id'],
                            rule['recompense_id'],
                            expiration_date,
                            f"Offre générée après scan de ticket"
                        ))
                        
                        # Récupérer le nom de la règle
                        rule_name = rule['nom']
                        
                        # Ajouter aux statistiques
                        offers_generated += 1
                        rules_applied.append({
                            'rule_id': rule['regle_id'],
                            'rule_name': rule_name,
                            'rule_type': rule['type_regle']
                        })
                        
                        logger.info(f"Offre créée pour le client {client_id} selon la règle '{rule_name}'")
            
            # Générer des codes uniques pour les nouvelles offres
            conn.execute('''
                UPDATE offres_client
                SET code_unique = 'OF-' || offre_id || '-' || substr(hex(randomblob(4)), 1, 8)
                WHERE code_unique IS NULL OR code_unique = ''
            ''')
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'offers_generated': offers_generated,
                'rules_applied': rules_applied
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation des règles pour le client {client_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'offers_generated': 0,
                'rules_applied': []
            }
        
    def _check_purchase_count_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon le nombre d'achats"""
        period_condition = ""
        if rule['periode_jours']:
            period_condition = f"AND date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        query = f'''
            SELECT COUNT(DISTINCT transaction_id) as nb_achats
            FROM transactions
            WHERE client_id = ?
            {period_condition}
        '''
        
        result = conn.execute(query, (client_id,)).fetchone()
        return result and result['nb_achats'] >= rule['condition_valeur']

    def _check_cumulative_amount_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon le montant cumulé"""
        period_condition = ""
        if rule['periode_jours']:
            period_condition = f"AND date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        query = f'''
            SELECT SUM(montant_total) as montant_cumule
            FROM transactions
            WHERE client_id = ?
            {period_condition}
        '''
        
        result = conn.execute(query, (client_id,)).fetchone()
        return result and result['montant_cumule'] and result['montant_cumule'] >= rule['condition_valeur']

    def _check_specific_product_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon l'achat d'un produit spécifique"""
        period_condition = ""
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        query = f'''
            SELECT COUNT(*) as count
            FROM transactions t
            JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
            WHERE t.client_id = ?
            AND dt.produit_id = ?
            {period_condition}
        '''
        
        result = conn.execute(query, (client_id, rule['condition_valeur'])).fetchone()
        return result and result['count'] > 0

    def _check_specific_category_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon l'achat dans une catégorie spécifique"""
        period_condition = ""
        if rule['periode_jours']:
            period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
        
        query = f'''
            SELECT COUNT(*) as count
            FROM transactions t
            JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
            JOIN produits p ON dt.produit_id = p.produit_id
            WHERE t.client_id = ?
            AND p.categorie_id = ?
            {period_condition}
        '''
        
        result = conn.execute(query, (client_id, rule['condition_valeur'])).fetchone()
        return result and result['count'] > 0

    def _check_first_visit_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon sa première visite"""
        query = '''
            SELECT MIN(date_transaction) as premiere_visite
            FROM transactions
            WHERE client_id = ?
        '''
        
        result = conn.execute(query, (client_id,)).fetchone()
        if not result or not result['premiere_visite']:
            return False
        
        # Calculer le nombre de jours depuis la première visite
        first_visit_date = datetime.strptime(result['premiere_visite'], '%Y-%m-%d')
        days_since_first_visit = (datetime.now() - first_visit_date).days
        
        return days_since_first_visit <= rule['condition_valeur']

    def _check_birthday_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon son anniversaire"""
        # Récupérer la date de naissance
        query = '''
            SELECT date_naissance
            FROM clients
            WHERE client_id = ?
        '''
        
        result = conn.execute(query, (client_id,)).fetchone()
        if not result or not result['date_naissance']:
            return False
        
        # Calculer les jours jusqu'au prochain anniversaire
        birth_date = datetime.strptime(result['date_naissance'], '%Y-%m-%d')
        today = datetime.now()
        
        # Prochain anniversaire cette année
        next_birthday = datetime(today.year, birth_date.month, birth_date.day)
        
        # Si l'anniversaire est déjà passé cette année, prendre celui de l'année prochaine
        if next_birthday < today:
            next_birthday = datetime(today.year + 1, birth_date.month, birth_date.day)
        
        days_until_birthday = (next_birthday - today).days
        
        return days_until_birthday <= rule['condition_valeur']

    def _check_inactivity_eligibility(self, conn, client_id, rule):
        """Vérifie si le client est éligible selon son inactivité"""
        query = '''
            SELECT MAX(date_transaction) as derniere_transaction
            FROM transactions
            WHERE client_id = ?
        '''
        
        result = conn.execute(query, (client_id,)).fetchone()
        if not result or not result['derniere_transaction']:
            return False
        
        # Calculer le nombre de jours depuis la dernière transaction
        last_transaction_date = datetime.strptime(result['derniere_transaction'], '%Y-%m-%d')
        days_since_last_transaction = (datetime.now() - last_transaction_date).days
        
        return days_since_last_transaction >= rule['condition_valeur']
    
    def send_offers(self, offer_ids=None, channel='email'):
        """
        Envoie les offres générées aux clients.
        
        Args:
            offer_ids (list, optional): Liste des IDs d'offres à envoyer. Si None, toutes les offres générées seront envoyées.
            channel (str): Canal d'envoi (email, sms, push, etc.)
            
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Préparer la requête SQL
            if offer_ids:
                placeholders = ','.join(['?' for _ in offer_ids])
                query = f'''
                    UPDATE offres_client
                    SET statut = 'envoyee', 
                        date_envoi = CURRENT_TIMESTAMP,
                        canal_envoi = ?
                    WHERE offre_id IN ({placeholders})
                    AND statut = 'generee'
                '''
                params = [channel] + offer_ids
            else:
                query = '''
                    UPDATE offres_client
                    SET statut = 'envoyee', 
                        date_envoi = CURRENT_TIMESTAMP,
                        canal_envoi = ?
                    WHERE statut = 'generee'
                '''
                params = [channel]
            
            # Exécuter la mise à jour
            cursor = conn.execute(query, params)
            
            # Récupérer le nombre d'offres envoyées
            offers_sent = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"{offers_sent} offres envoyées via {channel}")
            return {'success': True, 'offers_sent': offers_sent}
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des offres: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def use_offer(self, offer_code, transaction_id=None):
        """
        Marque une offre comme utilisée et applique la récompense.
        
        Args:
            offer_code (str): Code unique de l'offre
            transaction_id (int, optional): ID de la transaction liée à l'utilisation de l'offre
            
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Vérifier si l'offre existe et est valide
            offer = conn.execute('''
                SELECT 
                    oc.*, r.action_type, r.action_valeur, r.recompense_id
                FROM offres_client oc
                JOIN regles_fidelite r ON oc.regle_id = r.regle_id
                WHERE oc.code_unique = ?
                AND oc.statut IN ('generee', 'envoyee')
                AND oc.date_expiration >= date('now')
            ''', (offer_code,)).fetchone()
            
            if not offer:
                return {
                    'success': False, 
                    'error': 'Code offre invalide, expiré ou déjà utilisé'
                }
            
            # Mettre à jour le statut de l'offre
            conn.execute('''
                UPDATE offres_client
                SET statut = 'utilisee', 
                    date_utilisation = CURRENT_TIMESTAMP,
                    transaction_utilisation_id = ?
                WHERE offre_id = ?
            ''', (transaction_id, offer['offre_id']))
            
            # Appliquer la récompense selon le type d'action
            if offer['action_type'] == 'offre_points':
                # Ajouter les points au client
                points_to_add = int(offer['action_valeur'])
                
                # Récupérer les points actuels
                client_points = conn.execute('''
                    SELECT points_actuels FROM cartes_fidelite WHERE client_id = ?
                ''', (offer['client_id'],)).fetchone()
                
                if client_points:
                    new_points = client_points['points_actuels'] + points_to_add
                    
                    # Mettre à jour les points
                    conn.execute('''
                        UPDATE cartes_fidelite
                        SET points_actuels = ?,
                            date_derniere_activite = CURRENT_TIMESTAMP
                        WHERE client_id = ?
                    ''', (new_points, offer['client_id']))
                    
                    # Ajouter à l'historique des points
                    conn.execute('''
                        INSERT INTO historique_points (
                            client_id, date_operation, type_operation, points, 
                            transaction_id, commentaire
                        ) VALUES (?, CURRENT_TIMESTAMP, 'ajout', ?, ?, ?)
                    ''', (
                        offer['client_id'],
                        points_to_add,
                        transaction_id,
                        f"Points offerts via programme de fidélité (offre #{offer['offre_id']})"
                    ))
                else:
                    return {
                        'success': False,
                        'error': 'Carte de fidélité non trouvée pour le client'
                    }
            
            elif offer['action_type'] in ['reduction_pourcentage', 'reduction_montant']:
                # Pour les réductions, rien à faire ici car elles sont appliquées 
                # directement au moment de la transaction
                pass
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'offer_id': offer['offre_id'],
                'action_type': offer['action_type'],
                'action_value': offer['action_valeur']
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'utilisation de l'offre: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def check_expired_offers(self):
        """
        Vérifie et marque les offres expirées.
        
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Marquer les offres expirées
            cursor = conn.execute('''
                UPDATE offres_client
                SET statut = 'expiree'
                WHERE date_expiration < date('now')
                AND statut IN ('generee', 'envoyee')
            ''')
            
            # Récupérer le nombre d'offres expirées
            offers_expired = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"{offers_expired} offres marquées comme expirées")
            return {'success': True, 'offers_expired': offers_expired}
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des offres expirées: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def add_points(self, client_id, points, transaction_id=None, comment=None):
        """
        Ajoute des points à un client.
        
        Args:
            client_id (int): ID du client
            points (int): Nombre de points à ajouter
            transaction_id (int, optional): ID de la transaction liée
            comment (str, optional): Commentaire
            
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Vérifier si le client a une carte de fidélité
            carte = conn.execute('''
                SELECT carte_id, points_actuels, niveau_fidelite 
                FROM cartes_fidelite 
                WHERE client_id = ?
            ''', (client_id,)).fetchone()
            
            if not carte:
                # Créer une nouvelle carte de fidélité
                conn.execute('''
                    INSERT INTO cartes_fidelite (
                        client_id, points_actuels, points_en_attente, niveau_fidelite,
                        date_creation, date_derniere_activite
                    ) VALUES (?, ?, 0, 'standard', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (client_id, points))
                
                new_points = points
                old_level = 'standard'
                new_level = 'standard'
            else:
                # Mettre à jour les points
                new_points = carte['points_actuels'] + points
                old_level = carte['niveau_fidelite']
                
                # Déterminer le nouveau niveau de fidélité
                new_level = self._calculate_loyalty_level(new_points)
                
                conn.execute('''
                    UPDATE cartes_fidelite
                    SET points_actuels = ?,
                        niveau_fidelite = ?,
                        date_derniere_activite = CURRENT_TIMESTAMP
                    WHERE client_id = ?
                ''', (new_points, new_level, client_id))
            
            # Ajouter à l'historique des points
            conn.execute('''
                INSERT INTO historique_points (
                    client_id, date_operation, type_operation, points, 
                    transaction_id, commentaire
                ) VALUES (?, CURRENT_TIMESTAMP, 'ajout', ?, ?, ?)
            ''', (
                client_id,
                points,
                transaction_id,
                comment or "Ajout de points"
            ))
            
            # Si le niveau a changé, enregistrer l'événement
            if old_level != new_level:
                conn.execute('''
                    INSERT INTO evenements_client (
                        client_id, type_evenement, date_evenement, details
                    ) VALUES (?, 'changement_niveau', CURRENT_TIMESTAMP, ?)
                ''', (
                    client_id,
                    json.dumps({
                        'ancien_niveau': old_level,
                        'nouveau_niveau': new_level,
                        'points': new_points
                    })
                ))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'client_id': client_id,
                'points_added': points,
                'new_total': new_points,
                'loyalty_level': new_level
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de points: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def use_points(self, client_id, points, transaction_id=None, comment=None):
        """
        Utilise des points d'un client.
        
        Args:
            client_id (int): ID du client
            points (int): Nombre de points à utiliser
            transaction_id (int, optional): ID de la transaction liée
            comment (str, optional): Commentaire
            
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Vérifier si le client a suffisamment de points
            carte = conn.execute('''
                SELECT carte_id, points_actuels, niveau_fidelite 
                FROM cartes_fidelite 
                WHERE client_id = ?
            ''', (client_id,)).fetchone()
            
            if not carte:
                return {
                    'success': False,
                    'error': 'Carte de fidélité non trouvée pour le client'
                }
            
            if carte['points_actuels'] < points:
                return {
                    'success': False,
                    'error': 'Points insuffisants'
                }
            
            # Mettre à jour les points
            new_points = carte['points_actuels'] - points
            old_level = carte['niveau_fidelite']
            
            # Déterminer le nouveau niveau de fidélité
            new_level = self._calculate_loyalty_level(new_points)
            
            conn.execute('''
                UPDATE cartes_fidelite
                SET points_actuels = ?,
                    niveau_fidelite = ?,
                    date_derniere_activite = CURRENT_TIMESTAMP
                WHERE client_id = ?
            ''', (new_points, new_level, client_id))
            
            # Ajouter à l'historique des points
            conn.execute('''
                INSERT INTO historique_points (
                    client_id, date_operation, type_operation, points, 
                    transaction_id, commentaire
                ) VALUES (?, CURRENT_TIMESTAMP, 'utilisation', ?, ?, ?)
            ''', (
                client_id,
                points,
                transaction_id,
                comment or "Utilisation de points"
            ))
            
            # Si le niveau a changé, enregistrer l'événement
            if old_level != new_level:
                conn.execute('''
                    INSERT INTO evenements_client (
                        client_id, type_evenement, date_evenement, details
                    ) VALUES (?, 'changement_niveau', CURRENT_TIMESTAMP, ?)
                ''', (
                    client_id,
                    json.dumps({
                        'ancien_niveau': old_level,
                        'nouveau_niveau': new_level,
                        'points': new_points
                    })
                ))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'client_id': client_id,
                'points_used': points,
                'new_total': new_points,
                'loyalty_level': new_level
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'utilisation de points: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_loyalty_level(self, points):
            """
            Calcule le niveau de fidélité en fonction du nombre de points.
            
            Args:
                points (int): Nombre de points
                
            Returns:
                str: Niveau de fidélité
            """
            try:
                conn = self._get_connection()
                
                # Récupérer le niveau correspondant aux points
                level = conn.execute("""
                    SELECT nom
                    FROM niveaux_fidelite
                    WHERE points_minimum <= ? AND (points_maximum >= ? OR points_maximum IS NULL)
                    ORDER BY points_minimum DESC
                    LIMIT 1
                """, (points, points)).fetchone()
                
                conn.close()
                
                # Retourner le niveau trouvé ou le niveau par défaut
                if level:
                    return level['nom']
                else:
                    return 'Standard'  # Niveau par défaut
                    
            except Exception as e:
                logger.error(f"Erreur lors du calcul du niveau de fidélité: {str(e)}")
                return 'Standard'  # En cas d'erreur, utiliser le niveau par défaut
    
    def get_client_loyalty_info(self, client_id):
        """
        Récupère les informations de fidélité d'un client.
        
        Args:
            client_id (int): ID du client
            
        Returns:
            dict: Informations de fidélité
        """
        try:
            conn = self._get_connection()
            
            # Récupérer les informations de base du client
            client = conn.execute('''
                SELECT 
                    c.client_id, c.prenom, c.nom, c.email, c.telephone, 
                    c.date_naissance, c.date_creation, c.segment,
                    cf.carte_id, cf.points_actuels, cf.points_en_attente, 
                    cf.niveau_fidelite, cf.date_derniere_activite
                FROM clients c
                LEFT JOIN cartes_fidelite cf ON c.client_id = cf.client_id
                WHERE c.client_id = ?
            ''', (client_id,)).fetchone()
            
            if not client:
                return {
                    'success': False,
                    'error': 'Client non trouvé'
                }
            
            # Convertir en dictionnaire
            client_info = dict(client)
            
            # Récupérer les offres du client
            offres = conn.execute('''
                SELECT 
                    oc.offre_id, oc.regle_id, oc.recompense_id, 
                    oc.date_generation, oc.date_envoi, oc.date_utilisation, 
                    oc.date_expiration, oc.statut, oc.code_unique,
                    r.nom as nom_regle, r.action_type, r.action_valeur,
                    rec.nom as nom_recompense
                FROM offres_client oc
                JOIN regles_fidelite r ON oc.regle_id = r.regle_id
                LEFT JOIN recompenses rec ON oc.recompense_id = rec.recompense_id
                WHERE oc.client_id = ?
                ORDER BY oc.date_generation DESC
            ''', (client_id,)).fetchall()
            
            client_info['offres'] = [dict(offre) for offre in offres]
            
            # Récupérer l'historique des points
            historique = conn.execute('''
                SELECT 
                    hp.historique_id, hp.date_operation, hp.type_operation, 
                    hp.points, hp.transaction_id, hp.commentaire,
                    t.montant_total, t.date_transaction
                FROM historique_points hp
                LEFT JOIN transactions t ON hp.transaction_id = t.transaction_id
                WHERE hp.client_id = ?
                ORDER BY hp.date_operation DESC
                LIMIT 20
            ''', (client_id,)).fetchall()
            
            client_info['historique_points'] = [dict(h) for h in historique]
            
            # Récupérer les événements client
            evenements = conn.execute('''
                SELECT 
                    evenement_id, type_evenement, date_evenement, details
                FROM evenements_client
                WHERE client_id = ?
                ORDER BY date_evenement DESC
                LIMIT 10
            ''', (client_id,)).fetchall()
            
            client_info['evenements'] = []
            for evt in evenements:
                evt_dict = dict(evt)
                if evt_dict['details']:
                    try:
                        evt_dict['details'] = json.loads(evt_dict['details'])
                    except:
                        pass
                client_info['evenements'].append(evt_dict)
            
            # Statistiques supplémentaires
            stats = conn.execute('''
                SELECT 
                    COUNT(t.transaction_id) as nb_transactions,
                    SUM(t.montant_total) as montant_total,
                    AVG(t.montant_total) as panier_moyen,
                    SUM(t.points_gagnes) as points_gagnes_total,
                    MAX(t.date_transaction) as derniere_transaction
                FROM transactions t
                WHERE t.client_id = ?
            ''', (client_id,)).fetchone()
            
            client_info['statistiques'] = dict(stats) if stats else {}
            
            conn.close()
            
            return {
                'success': True,
                'client_info': client_info
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations de fidélité: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_loyalty_stats(self, period=30):
        """
        Récupère les statistiques du programme de fidélité.
        
        Args:
            period (int): Période en jours pour les statistiques
            
        Returns:
            dict: Statistiques du programme
        """
        try:
            conn = self._get_connection()
            
            # Statistiques générales
            stats = conn.execute('''
                SELECT 
                    COUNT(DISTINCT c.client_id) as total_clients,
                    COUNT(DISTINCT oc.offre_id) as total_offres,
                    SUM(CASE WHEN oc.statut = 'utilisee' THEN 1 ELSE 0 END) as offres_utilisees,
                    AVG(CASE WHEN oc.statut = 'utilisee' THEN 1.0 ELSE 0.0 END) * 100 as taux_utilisation,
                    COUNT(DISTINCT cf.carte_id) as total_cartes,
                    AVG(cf.points_actuels) as points_moyens
                FROM clients c
                LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.date_generation >= date('now', '-' || ? || ' days')
                LEFT JOIN cartes_fidelite cf ON c.client_id = cf.client_id
                WHERE c.statut = 'actif'
            ''', (period,)).fetchone()
            
            # Statistiques par niveau de fidélité
            stats_niveaux = conn.execute('''
                SELECT 
                    cf.niveau_fidelite,
                    COUNT(cf.client_id) as nb_clients,
                    AVG(cf.points_actuels) as points_moyens
                FROM cartes_fidelite cf
                JOIN clients c ON cf.client_id = c.client_id
                WHERE c.statut = 'actif'
                GROUP BY cf.niveau_fidelite
            ''').fetchall()
            
            # Statistiques par statut d'offre
            stats_statuts = conn.execute('''
                SELECT 
                    statut,
                    COUNT(*) as nb_offres
                FROM offres_client
                WHERE date_generation >= date('now', '-' || ? || ' days')
                GROUP BY statut
            ''', (period,)).fetchall()
            
            # Nombre d'offres par mois (dernière année)
            offres_par_mois = conn.execute('''
                SELECT 
                    strftime('%Y-%m', date_generation) as mois,
                    COUNT(*) as nb_offres
                FROM offres_client
                WHERE date_generation >= date('now', '-1 year')
                GROUP BY mois
                ORDER BY mois
            ''').fetchall()
            
            # Règles les plus efficaces (taux d'utilisation)
            regles_efficaces = conn.execute('''
                SELECT 
                    r.regle_id, r.nom, r.type_regle,
                    COUNT(oc.offre_id) as offres_generees,
                    SUM(CASE WHEN oc.statut = 'utilisee' THEN 1 ELSE 0 END) as offres_utilisees,
                    CAST(SUM(CASE WHEN oc.statut = 'utilisee' THEN 1 ELSE 0 END) AS FLOAT) / 
                    CAST(COUNT(oc.offre_id) AS FLOAT) * 100 as taux_utilisation
                FROM regles_fidelite r
                JOIN offres_client oc ON r.regle_id = oc.regle_id
                WHERE oc.date_generation >= date('now', '-' || ? || ' days')
                GROUP BY r.regle_id
                HAVING offres_generees > 0
                ORDER BY taux_utilisation DESC
                LIMIT 5
            ''', (period,)).fetchall()
            
            conn.close()
            
            return {
                'success': True,
                'stats': dict(stats),
                'stats_niveaux': [dict(x) for x in stats_niveaux],
                'stats_statuts': [dict(x) for x in stats_statuts],
                'offres_par_mois': [dict(x) for x in offres_par_mois],
                'regles_efficaces': [dict(x) for x in regles_efficaces]
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques de fidélité: {str(e)}")
            return {'success': False, 'error': str(e)}


class RewardManager:
    """
    Classe pour gérer les récompenses du programme de fidélité.
    """
    
    def __init__(self, db_path='modules/fidelity_db.sqlite'):
        """
        Initialise le gestionnaire de récompenses.
        
        Args:
            db_path (str): Chemin vers la base de données SQLite
        """
        self.db_path = db_path
    
    def _get_connection(self):
        """
        Établit et retourne une connexion à la base de données.
        
        Returns:
            sqlite3.Connection: Connexion à la base de données
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_available_rewards(self, client_id=None):
        """
        Récupère les récompenses disponibles, éventuellement filtrées par les points d'un client.
        
        Args:
            client_id (int, optional): ID du client pour filtrer les récompenses par points
            
        Returns:
            dict: Liste des récompenses disponibles
        """
        try:
            conn = self._get_connection()
            
            # Points actuels du client si client_id est fourni
            client_points = 0
            if client_id:
                client_card = conn.execute('''
                    SELECT points_actuels 
                    FROM cartes_fidelite 
                    WHERE client_id = ?
                ''', (client_id,)).fetchone()
                
                if client_card:
                    client_points = client_card['points_actuels']
            
            # Récupérer toutes les récompenses actives
            rewards = conn.execute('''
                SELECT 
                    recompense_id, nom, description, type_recompense, 
                    valeur, points_necessaires, image_url, statut
                FROM recompenses
                WHERE statut = 'active'
                ORDER BY points_necessaires ASC
            ''').fetchall()
            
            # Convertir en liste de dictionnaires et ajouter des infos
            reward_list = []
            for reward in rewards:
                reward_dict = dict(reward)
                
                if client_id:
                    reward_dict['available'] = reward_dict['points_necessaires'] <= client_points
                    reward_dict['points_missing'] = max(0, reward_dict['points_necessaires'] - client_points)
                
                reward_list.append(reward_dict)
            
            conn.close()
            
            return {
                'success': True,
                'rewards': reward_list,
                'client_points': client_points if client_id else None
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def redeem_reward(self, client_id, reward_id, transaction_id=None):
        """
        Permet à un client d'échanger ses points contre une récompense.
        
        Args:
            client_id (int): ID du client
            reward_id (int): ID de la récompense
            transaction_id (int, optional): ID de la transaction liée
            
        Returns:
            dict: Résultat de l'opération
        """
        try:
            conn = self._get_connection()
            
            # Vérifier si la récompense existe et est active
            reward = conn.execute('''
                SELECT * 
                FROM recompenses 
                WHERE recompense_id = ? AND statut = 'active'
            ''', (reward_id,)).fetchone()
            
            if not reward:
                return {
                    'success': False,
                    'error': 'Récompense non disponible'
                }
            
            # Vérifier si le client a suffisamment de points
            client_card = conn.execute('''
                SELECT carte_id, points_actuels, niveau_fidelite
                FROM cartes_fidelite 
                WHERE client_id = ?
            ''', (client_id,)).fetchone()
            
            if not client_card:
                return {
                    'success': False,
                    'error': 'Carte de fidélité non trouvée pour ce client'
                }
            
            if client_card['points_actuels'] < reward['points_necessaires']:
                return {
                    'success': False,
                    'error': 'Points insuffisants',
                    'points_missing': reward['points_necessaires'] - client_card['points_actuels']
                }
            
            # Débiter les points du client
            new_points = client_card['points_actuels'] - reward['points_necessaires']
            
            # Déterminer le nouveau niveau de fidélité
            old_level = client_card['niveau_fidelite']
            # On réutilise la méthode de LoyaltyManager
            loyalty_manager = LoyaltyManager(self.db_path)
            new_level = loyalty_manager._calculate_loyalty_level(new_points)
            
            # Mettre à jour les points et le niveau du client
            conn.execute('''
                UPDATE cartes_fidelite
                SET points_actuels = ?,
                    niveau_fidelite = ?,
                    date_derniere_activite = CURRENT_TIMESTAMP
                WHERE client_id = ?
            ''', (new_points, new_level, client_id))
            
            # Ajouter l'historique des points
            conn.execute('''
                INSERT INTO historique_points (
                    client_id, date_operation, type_operation, points, 
                    transaction_id, commentaire
                ) VALUES (?, CURRENT_TIMESTAMP, 'utilisation', ?, ?, ?)
            ''', (
                client_id,
                reward['points_necessaires'],
                transaction_id,
                f"Échange contre récompense: {reward['nom']}"
            ))
            
            # Créer une utilisation de récompense
            conn.execute('''
                INSERT INTO utilisations_recompenses (
                    client_id, recompense_id, date_utilisation, 
                    transaction_id, points_utilises, statut
                ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, 'validee')
            ''', (
                client_id,
                reward_id,
                transaction_id,
                reward['points_necessaires']
            ))
            
            # Si le niveau a changé, enregistrer l'événement
            if old_level != new_level:
                conn.execute('''
                    INSERT INTO evenements_client (
                        client_id, type_evenement, date_evenement, details
                    ) VALUES (?, 'changement_niveau', CURRENT_TIMESTAMP, ?)
                ''', (
                    client_id,
                    json.dumps({
                        'ancien_niveau': old_level,
                        'nouveau_niveau': new_level,
                        'points': new_points
                    })
                ))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'client_id': client_id,
                'reward_id': reward_id,
                'reward_name': reward['nom'],
                'points_used': reward['points_necessaires'],
                'new_points_total': new_points,
                'new_loyalty_level': new_level
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'échange de récompense: {str(e)}")
            return {'success': False, 'error': str(e)}
