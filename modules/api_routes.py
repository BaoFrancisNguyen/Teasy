"""
Routes d'API pour le programme de fidélité

Ce module définit les routes d'API pour le programme de fidélité,
permettant l'intégration avec d'autres systèmes et applications.
"""

from flask import Blueprint, request, jsonify
from loyalty_manager import LoyaltyManager, RewardManager
import logging

# Création du Blueprint pour les routes d'API de fidélité
loyalty_api = Blueprint('loyalty_api', __name__, url_prefix='/api/loyalty')

# Initialisation des gestionnaires
loyalty_manager = LoyaltyManager()
reward_manager = RewardManager()

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Routes des statistiques
@loyalty_api.route('/stats', methods=['GET'])
def api_loyalty_stats():
    """API pour récupérer les statistiques du programme de fidélité"""
    try:
        # Récupérer le paramètre de période
        period = request.args.get('period', 30, type=int)
        
        # Obtenir les statistiques
        stats = loyalty_manager.get_loyalty_stats(period)
        
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Routes des règles
@loyalty_api.route('/rules', methods=['GET'])
def api_get_rules():
    """API pour récupérer la liste des règles de fidélité"""
    try:
        conn = loyalty_manager._get_connection()
        
        # Paramètres de filtrage
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        rule_type = request.args.get('type', 'all')
        
        # Construire la requête SQL
        query = """
            SELECT r.*, rec.nom as recompense_nom
            FROM regles_fidelite r
            LEFT JOIN recompenses rec ON r.recompense_id = rec.recompense_id
            WHERE 1=1
        """
        params = []
        
        if active_only:
            query += " AND r.est_active = 1"
        
        if rule_type != 'all':
            query += " AND r.type_regle = ?"
            params.append(rule_type)
        
        query += " ORDER BY r.priorite DESC, r.est_active DESC"
        
        # Exécuter la requête
        rules = conn.execute(query, params).fetchall()
        
        # Convertir les résultats en liste de dictionnaires
        rules_list = []
        for rule in rules:
            rule_dict = dict(rule)
            
            # Convertir les segments_cibles de JSON à liste
            if rule_dict['segments_cibles']:
                try:
                    import json
                    rule_dict['segments_cibles'] = json.loads(rule_dict['segments_cibles'])
                except:
                    pass
            
            rules_list.append(rule_dict)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'rules': rules_list
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des règles: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/rules', methods=['POST'])
def api_create_rule():
    """API pour créer une nouvelle règle de fidélité"""
    try:
        # Récupérer les données de la requête
        data = request.json
        
        # Vérifier les champs obligatoires
        required_fields = ['nom', 'type_regle', 'condition_valeur', 'action_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f"Champ obligatoire manquant: {field}"
                })
        
        # Convertir les segments en JSON si fournis
        if 'segments_cibles' in data and isinstance(data['segments_cibles'], list):
            import json
            data['segments_cibles'] = json.dumps(data['segments_cibles'])
        
        # Préparation des champs pour l'insertion
        fields = [
            'nom', 'description', 'type_regle', 'condition_valeur', 
            'periode_jours', 'recompense_id', 'action_type', 'action_valeur',
            'segments_cibles', 'priorite', 'est_active', 'date_debut', 'date_fin'
        ]
        
        # Ne conserver que les champs présents dans la requête
        present_fields = [f for f in fields if f in data]
        
        # Construire la requête SQL
        placeholders = ', '.join(['?' for _ in present_fields])
        fields_str = ', '.join(present_fields)
        
        conn = loyalty_manager._get_connection()
        
        # Insérer la règle
        cursor = conn.execute(f"""
            INSERT INTO regles_fidelite ({fields_str})
            VALUES ({placeholders})
        """, [data[f] for f in present_fields])
        
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'rule_id': rule_id,
            'message': "Règle créée avec succès"
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la création de la règle: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/rules/<int:rule_id>', methods=['PUT'])
def api_update_rule(rule_id):
    """API pour mettre à jour une règle de fidélité existante"""
    try:
        # Récupérer les données de la requête
        data = request.json
        
        # Convertir les segments en JSON si fournis
        if 'segments_cibles' in data and isinstance(data['segments_cibles'], list):
            import json
            data['segments_cibles'] = json.dumps(data['segments_cibles'])
        
        # Préparation des champs pour la mise à jour
        fields = [
            'nom', 'description', 'type_regle', 'condition_valeur', 
            'periode_jours', 'recompense_id', 'action_type', 'action_valeur',
            'segments_cibles', 'priorite', 'est_active', 'date_debut', 'date_fin'
        ]
        
        # Ne conserver que les champs présents dans la requête
        present_fields = [f for f in fields if f in data]
        
        # S'il n'y a aucun champ à mettre à jour
        if not present_fields:
            return jsonify({
                'success': False,
                'error': "Aucun champ à mettre à jour"
            })
        
        # Construire la requête SQL
        set_clause = ', '.join([f"{f} = ?" for f in present_fields])
        
        conn = loyalty_manager._get_connection()
        
        # Vérifier si la règle existe
        rule = conn.execute("SELECT regle_id FROM regles_fidelite WHERE regle_id = ?", (rule_id,)).fetchone()
        
        if not rule:
            conn.close()
            return jsonify({
                'success': False,
                'error': f"Règle #{rule_id} non trouvée"
            })
        
        # Mettre à jour la règle
        params = [data[f] for f in present_fields] + [rule_id]
        conn.execute(f"""
            UPDATE regles_fidelite
            SET {set_clause}
            WHERE regle_id = ?
        """, params)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'rule_id': rule_id,
            'message': "Règle mise à jour avec succès"
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la règle: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/rules/<int:rule_id>', methods=['DELETE'])
def api_delete_rule(rule_id):
    """API pour supprimer une règle de fidélité"""
    try:
        conn = loyalty_manager._get_connection()
        
        # Vérifier si la règle existe
        rule = conn.execute("SELECT regle_id FROM regles_fidelite WHERE regle_id = ?", (rule_id,)).fetchone()
        
        if not rule:
            conn.close()
            return jsonify({
                'success': False,
                'error': f"Règle #{rule_id} non trouvée"
            })
        
        # Supprimer la règle
        conn.execute("DELETE FROM regles_fidelite WHERE regle_id = ?", (rule_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Règle #{rule_id} supprimée avec succès"
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la règle: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Routes des offres
@loyalty_api.route('/offers', methods=['GET'])
def api_get_offers():
    """API pour récupérer la liste des offres"""
    try:
        # Paramètres de filtrage
        status = request.args.get('status', 'all')
        client_id = request.args.get('client_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        conn = loyalty_manager._get_connection()
        
        # Construire la requête SQL
        query = """
            SELECT 
                oc.*, 
                c.prenom || ' ' || c.nom as client_nom,
                r.nom as regle_nom,
                rec.nom as recompense_nom
            FROM offres_client oc
            JOIN clients c ON oc.client_id = c.client_id
            JOIN regles_fidelite r ON oc.regle_id = r.regle_id
            LEFT JOIN recompenses rec ON oc.recompense_id = rec.recompense_id
            WHERE 1=1
        """
        params = []
        
        # Appliquer les filtres
        if status != 'all':
            query += " AND oc.statut = ?"
            params.append(status)
        
        if client_id:
            query += " AND oc.client_id = ?"
            params.append(client_id)
        
        if date_from:
            query += " AND oc.date_generation >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND oc.date_generation <= ?"
            params.append(date_to)
        
        # Ajouter le tri et la pagination
        query += " ORDER BY oc.date_generation DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Exécuter la requête
        offers = conn.execute(query, params).fetchall()
        
        # Convertir les résultats en liste de dictionnaires
        offers_list = [dict(offer) for offer in offers]
        
        # Compter le nombre total d'offres (sans pagination)
        count_query = f"""
            SELECT COUNT(*) as total
            FROM offres_client oc
            WHERE 1=1
        """
        count_params = []
        
        # Appliquer les mêmes filtres
        if status != 'all':
            count_query += " AND oc.statut = ?"
            count_params.append(status)
        
        if client_id:
            count_query += " AND oc.client_id = ?"
            count_params.append(client_id)
        
        if date_from:
            count_query += " AND oc.date_generation >= ?"
            count_params.append(date_from)
        
        if date_to:
            count_query += " AND oc.date_generation <= ?"
            count_params.append(date_to)
        
        total_count = conn.execute(count_query, count_params).fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'offers': offers_list,
            'total': total_count,
            'limit': limit,
            'offset': offset
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des offres: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/offers/send', methods=['POST'])
def api_send_offers():
    """API pour envoyer des offres aux clients"""
    try:
        # Récupérer les données de la requête
        data = request.json
        offer_ids = data.get('offer_ids')
        channel = data.get('channel', 'email')
        
        # Envoyer les offres
        result = loyalty_manager.send_offers(offer_ids, channel)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des offres: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/offers/use', methods=['POST'])
def api_use_offer():
    """API pour utiliser une offre"""
    try:
        # Récupérer les données de la requête
        data = request.json
        offer_code = data.get('offer_code')
        transaction_id = data.get('transaction_id')
        
        if not offer_code:
            return jsonify({
                'success': False,
                'error': "Code offre manquant"
            })
        
        # Utiliser l'offre
        result = loyalty_manager.use_offer(offer_code, transaction_id)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'utilisation de l'offre: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Routes des récompenses
@loyalty_api.route('/rewards', methods=['GET'])
def api_get_rewards():
    """API pour récupérer la liste des récompenses disponibles"""
    try:
        # Paramètre client_id optionnel pour filtrer par points du client
        client_id = request.args.get('client_id')
        
        # Récupérer les récompenses
        if client_id:
            result = reward_manager.get_available_rewards(int(client_id))
        else:
            result = reward_manager.get_available_rewards()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des récompenses: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/rewards/redeem', methods=['POST'])
def api_redeem_reward():
    """API pour échanger des points contre une récompense"""
    try:
        # Récupérer les données de la requête
        data = request.json
        client_id = data.get('client_id')
        reward_id = data.get('reward_id')
        transaction_id = data.get('transaction_id')
        
        if not client_id or not reward_id:
            return jsonify({
                'success': False,
                'error': "ID client et ID récompense requis"
            })
        
        # Échanger la récompense
        result = reward_manager.redeem_reward(client_id, reward_id, transaction_id)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'échange de récompense: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Routes des clients
@loyalty_api.route('/clients/<int:client_id>', methods=['GET'])
def api_get_client_loyalty(client_id):
    """API pour récupérer les informations de fidélité d'un client"""
    try:
        # Récupérer les informations de fidélité
        result = loyalty_manager.get_client_loyalty_info(client_id)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations de fidélité: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/clients/<int:client_id>/points/add', methods=['POST'])
def api_add_points(client_id):
    """API pour ajouter des points à un client"""
    try:
        # Récupérer les données de la requête
        data = request.json
        points = data.get('points')
        transaction_id = data.get('transaction_id')
        comment = data.get('comment')
        
        if not points:
            return jsonify({
                'success': False,
                'error': "Nombre de points requis"
            })
        
        # Vérifier que points est un nombre positif
        try:
            points = int(points)
            if points <= 0:
                raise ValueError("Le nombre de points doit être positif")
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': "Format de points invalide"
            })
        
        # Ajouter les points
        result = loyalty_manager.add_points(client_id, points, transaction_id, comment)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de points: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/clients/<int:client_id>/points/use', methods=['POST'])
def api_use_points(client_id):
    """API pour utiliser des points d'un client"""
    try:
        # Récupérer les données de la requête
        data = request.json
        points = data.get('points')
        transaction_id = data.get('transaction_id')
        comment = data.get('comment')
        
        if not points:
            return jsonify({
                'success': False,
                'error': "Nombre de points requis"
            })
        
        # Vérifier que points est un nombre positif
        try:
            points = int(points)
            if points <= 0:
                raise ValueError("Le nombre de points doit être positif")
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': "Format de points invalide"
            })
        
        # Utiliser les points
        result = loyalty_manager.use_points(client_id, points, transaction_id, comment)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'utilisation de points: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Routes d'exécution des règles (administrateur)
@loyalty_api.route('/evaluate-rules', methods=['POST'])
def api_evaluate_rules():
    """API pour évaluer toutes les règles de fidélité"""
    try:
        # Vérifier l'authentification (à implémenter)
        
        # Évaluer les règles
        result = loyalty_manager.evaluate_all_rules()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation des règles: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@loyalty_api.route('/check-expired-offers', methods=['POST'])
def api_check_expired_offers():
    """API pour vérifier les offres expirées"""
    try:
        # Vérifier l'authentification (à implémenter)
        
        # Vérifier les offres expirées
        result = loyalty_manager.check_expired_offers()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des offres expirées: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Route pour initialiser les données de test
@loyalty_api.route('/init-test-data', methods=['POST'])
def api_init_test_data():
    """API pour initialiser des données de test (uniquement en développement)"""
    try:
        import os
        # Vérifier si nous sommes en environnement de développement
        if os.environ.get('FLASK_ENV') != 'development':
            return jsonify({
                'success': False,
                'error': "Cette API n'est disponible qu'en environnement de développement"
            })
        
        conn = loyalty_manager._get_connection()
        
        # Créer quelques règles de fidélité de test
        rules = [
            {
                'nom': 'Bienvenue',
                'description': 'Offre de bienvenue pour les nouveaux clients',
                'type_regle': 'premiere_visite',
                'condition_valeur': '30',
                'action_type': 'offre_points',
                'action_valeur': '100',
                'priorite': 10,
                'est_active': 1
            },
            {
                'nom': 'Fidélité Standard',
                'description': 'Récompense pour 5 achats',
                'type_regle': 'nombre_achats',
                'condition_valeur': '5',
                'periode_jours': 180,
                'action_type': 'reduction_pourcentage',
                'action_valeur': '10',
                'priorite': 5,
                'est_active': 1
            },
            {
                'nom': 'Grand Acheteur',
                'description': 'Récompense pour cumul d\'achats important',
                'type_regle': 'montant_cumule',
                'condition_valeur': '500',
                'periode_jours': 90,
                'action_type': 'offre_cadeau',
                'recompense_id': 6,
                'priorite': 8,
                'est_active': 1
            },
            {
                'nom': 'Anniversaire',
                'description': 'Offre pour l\'anniversaire du client',
                'type_regle': 'anniversaire',
                'condition_valeur': '7',
                'action_type': 'offre_points',
                'action_valeur': '200',
                'priorite': 15,
                'est_active': 1
            }
        ]
        
        # Insérer les règles
        for rule in rules:
            fields = list(rule.keys())
            placeholders = ', '.join(['?' for _ in fields])
            fields_str = ', '.join(fields)
            
            conn.execute(f"""
                INSERT OR IGNORE INTO regles_fidelite ({fields_str})
                VALUES ({placeholders})
            """, [rule[f] for f in fields])
        
        # Mettre à jour quelques cartes de fidélité pour les tests
        # (Supposons que nous avons déjà des clients dans la base de données)
        clients = conn.execute("SELECT client_id FROM clients LIMIT 10").fetchall()
        
        for i, client in enumerate(clients):
            client_id = client['client_id']
            # Vérifier si le client a déjà une carte
            existing_card = conn.execute(
                "SELECT carte_id FROM cartes_fidelite WHERE client_id = ?", 
                (client_id,)
            ).fetchone()
            
            points = (i + 1) * 100  # Points différents pour chaque client
            
            if existing_card:
                # Mettre à jour la carte existante
                conn.execute("""
                    UPDATE cartes_fidelite
                    SET points_actuels = ?,
                        niveau_fidelite = ?,
                        date_derniere_activite = CURRENT_TIMESTAMP
                    WHERE client_id = ?
                """, (points, loyalty_manager._calculate_loyalty_level(points), client_id))
            else:
                # Créer une nouvelle carte
                conn.execute("""
                    INSERT INTO cartes_fidelite (
                        client_id, points_actuels, niveau_fidelite,
                        date_creation, date_derniere_activite
                    ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (client_id, points, loyalty_manager._calculate_loyalty_level(points)))
        
        conn.commit()
        conn.close()
        
        # Exécuter l'évaluation des règles pour générer des offres
        loyalty_manager.evaluate_all_rules()
        
        return jsonify({
            'success': True,
            'message': "Données de test initialisées avec succès"
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation des données de test: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
