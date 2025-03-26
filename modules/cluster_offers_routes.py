# Routes pour les offres par clusters

from flask import request, render_template, redirect, url_for, flash, jsonify, session
import json
import os
import pickle
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
from modules.loyalty_manager import LoyaltyManager, RewardManager
import logging

# Classe ClusterOfferGenerator qui utilise le modèle d'intelligence artificielle
class ClusterOfferGenerator:
    """
    Classe pour générer des offres personnalisées basées sur les caractéristiques d'un cluster
    à l'aide d'un modèle d'IA (Ollama/Mistral local ou autre service IA)
    """
    
    def __init__(self):
        """Initialisation du générateur d'offres"""
        self.logger = logging.getLogger(__name__)
        
    def generate_offer(self, cluster_id, cluster_stats, context=""):
        """
        Génère une offre personnalisée pour un cluster spécifique
        
        Args:
            cluster_id: Identifiant du cluster
            cluster_stats: Statistiques des caractéristiques du cluster
            context: Contexte utilisateur supplémentaire
            
        Returns:
            dict: Description de l'offre suggérée
        """
        import requests
        import json
        
        try:
            # Préparer le prompt pour le modèle
            prompt = f"""
            Je suis un expert en marketing et fidélisation client. J'ai besoin de suggérer une offre personnalisée 
            pour un segment de clients identifié par clustering.

            CARACTÉRISTIQUES DU CLUSTER {cluster_id}:
            """
            
            # Ajouter les statistiques du cluster
            for feature, values in cluster_stats.items():
                prompt += f"- {feature}: {values}\n"
            
            prompt += f"""
            CONTEXTE ADDITIONNEL:
            {context}
            
            TÂCHE:
            Suggère une offre marketing pertinente pour ce segment de clients. L'offre doit être l'une des suivantes:
            1. offre_points - Offrir des points de fidélité
            2. reduction_pourcentage - Réduction en pourcentage
            3. reduction_montant - Réduction en montant (euros)
            4. offre_cadeau - Offrir un cadeau
            5. notification - Notification spéciale sans remise

            FORMAT DE RÉPONSE (JSON uniquement):
            {{
                "offer_type": "type de l'offre (un des cinq types ci-dessus)",
                "offer_value": "valeur numérique de l'offre (ex: '10' pour 10 points, '15' pour 15% de réduction, '5' pour 5€)",
                "offer_description": "description marketing de l'offre",
                "offer_message": "message court à inclure dans l'email de l'offre"
            }}
            
            Ne réponds qu'avec un objet JSON valide sans autres explications.
            """
            
            self.logger.info(f"Génération d'offre pour le cluster {cluster_id}")
            
            # Tenter d'abord avec Ollama (modèle local)
            try:
                # Tester la connexion Ollama
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    # Utiliser Ollama
                    payload = {
                        "model": "mistral",
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                    
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json=payload,
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result.get('response', '')
                        
                        # Extraire le JSON de la réponse
                        try:
                            # Essayer d'extraire d'abord le JSON proprement formaté
                            offer_data = json.loads(response_text)
                            
                            # Valider les champs requis
                            required_fields = ['offer_type', 'offer_value', 'offer_description']
                            if not all(field in offer_data for field in required_fields):
                                raise ValueError("Réponse incomplète")
                                
                            return offer_data
                        except json.JSONDecodeError:
                            self.logger.warning("Impossible de parser directement le JSON de la réponse Ollama")
                            
                            # Essayer d'extraire le JSON de la réponse avec des regex
                            import re
                            json_match = re.search(r'\{[\s\S]*\}', response_text)
                            if json_match:
                                try:
                                    offer_data = json.loads(json_match.group(0))
                                    return offer_data
                                except:
                                    self.logger.error("Échec de l'extraction du JSON avec regex")
            except requests.exceptions.RequestException:
                self.logger.warning("Ollama n'est pas disponible, utilisation de la logique de repli")
            
            # Logique de repli si Ollama échoue ou n'est pas disponible
            self.logger.info("Utilisation de la logique de repli pour la génération d'offre")
            
            # Analyser les statistiques du cluster pour déterminer l'offre appropriée
            average_values = {}
            for feature, values in cluster_stats.items():
                # Essayer d'extraire les valeurs moyennes
                try:
                    # Format attendu: "Moyenne: X.XX, Médiane: Y.YY"
                    parts = values.split(',')
                    for part in parts:
                        if 'moyenne' in part.lower():
                            value_str = part.split(':')[1].strip()
                            average_values[feature] = float(value_str)
                            break
                except:
                    continue
            
            # Logique simple basée sur les caractéristiques disponibles
            # Noter que cette logique est basique et serait remplacée par un modèle plus sophistiqué
            
            # Déterminer le type d'offre
            offer_types = ['offre_points', 'reduction_pourcentage', 'reduction_montant']
            offer_type = offer_types[cluster_id % len(offer_types)]
            
            # Déterminer la valeur de l'offre
            if offer_type == 'offre_points':
                offer_value = str(100 + (cluster_id * 50))
            elif offer_type == 'reduction_pourcentage':
                offer_value = str(5 + (cluster_id * 2))
            elif offer_type == 'reduction_montant':
                offer_value = str(5 + (cluster_id * 3))
            
            # Construire une description
            offer_description = f"Offre spéciale pour les clients du groupe {cluster_id}"
            if 'montant_total' in average_values:
                if average_values['montant_total'] > 100:
                    offer_description += " qui sont de grands acheteurs"
                elif average_values['montant_total'] < 50:
                    offer_description += " pour encourager vos achats"
            
            # Construire un message
            offer_message = f"Merci de votre fidélité! Voici une offre spéciale juste pour vous."
            
            # Construire la réponse
            offer_message = f"Merci de votre fidélité! Voici une offre spéciale juste pour vous."
            
            # Construire la réponse
            offer_data = {
                "offer_type": offer_type,
                "offer_value": offer_value,
                "offer_description": offer_description,
                "offer_message": offer_message
            }
            
            return offer_data
        
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération d'offre: {e}", exc_info=True)
            return {
                "offer_type": "offre_points",
                "offer_value": "100",
                "offer_description": f"Offre standard pour le cluster {cluster_id}",
                "offer_message": "Nous vous remercions de votre fidélité!"
            }
        
from flask import request, render_template, redirect, url_for, flash, jsonify, session, Blueprint

# Créer un Blueprint pour les routes liées aux offres par cluster
cluster_offers = Blueprint('cluster_offers', __name__)

# Instancier le générateur d'offres
offer_generator = ClusterOfferGenerator()

# Fonction utilitaire pour se connecter à la base de données
def get_db_connection(db_path='modules/fidelity_db.sqlite'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@cluster_offers.route('/api/generate_cluster_offer', methods=['POST'])
def api_generate_cluster_offer():
    """API pour générer une offre pour un cluster spécifique"""
    try:
        # Récupérer les données de la requête
        data = request.json
        cluster_id = data.get('cluster_id')
        cluster_stats = data.get('cluster_stats', {})
        context = data.get('context', '')
        
        if not cluster_id:
            return jsonify({"success": False, "error": "ID de cluster manquant"})
        
        # Générer l'offre
        offer = offer_generator.generate_offer(cluster_id, cluster_stats, context)
        
        # Ajouter l'information de succès
        offer['success'] = True
        
        return jsonify(offer)
    except Exception as e:
        logging.error(f"Erreur lors de la génération d'offre: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        })

@cluster_offers.route('/api/preview_cluster_offers', methods=['POST'])
def api_preview_cluster_offers():
    """API pour prévisualiser les offres par cluster avant envoi"""
    try:
        # Récupérer l'ID du clustering
        clustering_id = request.form.get('clustering_id')
        
        if not clustering_id:
            return jsonify({"success": False, "error": "ID de clustering manquant"})
        
        # Charger les résultats du clustering
        clustering_folder = os.path.join('uploads', 'clustering_results')
        clustering_file = os.path.join(clustering_folder, f"{clustering_id}.pkl")
        
        if not os.path.exists(clustering_file):
            return jsonify({"success": False, "error": "Résultats de clustering non trouvés"})
            
        with open(clustering_file, 'rb') as f:
            clustering_result = pickle.load(f)
        
        # Prévisualiser les offres pour chaque cluster
        offers = []
        
        for cluster_id in clustering_result.get('cluster_sizes', {}).keys():
            # Ignorer le cluster de bruit (-1) pour DBSCAN
            if cluster_id == -1:
                continue
                
            # Vérifier si cette offre est activée
            if not request.form.get(f'enable_offer_{cluster_id}'):
                continue
                
            # Vérifier le type d'offre
            offer_type = request.form.get(f'offer_type_{cluster_id}')
            
            if offer_type == 'manual':
                # Récupérer les paramètres manuels
                action_type = request.form.get(f'action_type_{cluster_id}')
                action_value = request.form.get(f'action_value_{cluster_id}')
                gift_id = request.form.get(f'gift_id_{cluster_id}')
                
                # Définir l'étiquette du type d'action
                action_type_label = {
                    'offre_points': 'Points de fidélité',
                    'reduction_pourcentage': 'Réduction %',
                    'reduction_montant': 'Réduction €',
                    'offre_cadeau': 'Cadeau',
                    'notification': 'Notification'
                }.get(action_type, action_type)
                
                # Définir la description de l'offre
                if action_type == 'offre_points':
                    description = f"Offre de {action_value} points de fidélité"
                elif action_type == 'reduction_pourcentage':
                    description = f"Réduction de {action_value}% sur votre prochaine commande"
                elif action_type == 'reduction_montant':
                    description = f"Réduction de {action_value}€ sur votre prochaine commande"
                elif action_type == 'offre_cadeau':
                    # Récupérer le nom du cadeau
                    conn = get_db_connection()
                    reward = conn.execute('SELECT nom FROM recompenses WHERE recompense_id = ?', (gift_id,)).fetchone()
                    conn.close()
                    
                    reward_name = reward['nom'] if reward else "cadeau"
                    description = f"Offre d'un {reward_name}"
                else:
                    description = "Notification spéciale"
            else:
                # Utiliser le contexte pour générer une offre
                context = request.form.get(f'generation_context_{cluster_id}', '')
                
                # Récupérer les statistiques du cluster
                if clustering_result['algorithm'] == 'dbscan':
                    if cluster_id in clustering_result.get('cluster_stats', {}):
                        cluster_stats = {
                            col: {
                                "mean": values['mean'], 
                                "median": values['median']
                            }
                            for col, values in clustering_result['cluster_stats'][cluster_id].items()
                        }
                    else:
                        cluster_stats = {}
                else:
                    cluster_stats = {
                        col: {
                            "mean": values['mean'], 
                            "median": values['median']
                        }
                        for col, values in clustering_result['cluster_stats'][int(cluster_id)].items()
                    }
                
                # Formater les statistiques pour le générateur
                formatted_stats = {}
                for col, values in cluster_stats.items():
                    formatted_stats[col] = f"Moyenne: {values['mean']:.2f}, Médiane: {values['median']:.2f}"
                
                # Générer l'offre
                generated = offer_generator.generate_offer(cluster_id, formatted_stats, context)
                
                action_type = generated['offer_type']
                action_value = generated['offer_value']
                description = generated['offer_description']
                message = generated['offer_message']
                
                # Définir l'étiquette du type d'action
                action_type_label = {
                    'offre_points': 'Points de fidélité',
                    'reduction_pourcentage': 'Réduction %',
                    'reduction_montant': 'Réduction €',
                    'offre_cadeau': 'Cadeau',
                    'notification': 'Notification'
                }.get(action_type, action_type)
            
            # Déterminer le nombre de clients dans ce cluster
            clients_count = clustering_result['cluster_sizes'].get(cluster_id, 0)
            
            # Estimer le coût
            if action_type == 'offre_points':
                try:
                    estimated_cost = f"{clients_count} × {action_value} points"
                except:
                    estimated_cost = "N/A"
            elif action_type == 'reduction_pourcentage':
                try:
                    estimated_cost = f"~{clients_count} × (panier moyen × {action_value}%)"
                except:
                    estimated_cost = "N/A"
            elif action_type == 'reduction_montant':
                try:
                    estimated_cost = f"{clients_count} × {action_value}€"
                except:
                    estimated_cost = "N/A"
            else:
                estimated_cost = "Variable"
            
            # Calculer la date d'expiration
            expiration_days = int(request.form.get('expiration_days', 30))
            expiration_date = (datetime.now() + timedelta(days=expiration_days)).strftime('%Y-%m-%d')
            
            # Récupérer le message personnalisé
            message = request.form.get(f'offer_message_{cluster_id}', '')
            
            # Ajouter à la liste des offres
            offers.append({
                'cluster_id': cluster_id,
                'action_type': action_type,
                'action_type_label': action_type_label,
                'action_value': action_value,
                'description': description,
                'message': message,
                'clients_count': clients_count,
                'estimated_cost': estimated_cost,
                'expiration_date': expiration_date
            })
        
        return jsonify({
            "success": True,
            "offers": offers
        })
    except Exception as e:
        logging.error(f"Erreur lors de la prévisualisation des offres: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        })

@cluster_offers.route('/create_cluster_offers', methods=['POST'])
def create_cluster_offers():
    """Créer des offres basées sur les clusters et les envoyer aux clients"""
    try:
        # Récupérer l'ID du clustering
        clustering_id = request.form.get('clustering_id')
        
        if not clustering_id:
            flash('ID de clustering manquant', 'danger')
            return redirect(url_for('clustering'))
        
        # Charger les résultats du clustering
        clustering_folder = os.path.join('uploads', 'clustering_results')
        clustering_file = os.path.join(clustering_folder, f"{clustering_id}.pkl")
        
        if not os.path.exists(clustering_file):
            flash('Résultats de clustering non trouvés', 'danger')
            return redirect(url_for('clustering'))
            
        with open(clustering_file, 'rb') as f:
            clustering_result = pickle.load(f)
        
        # Vérifier si le résultat contient un DataFrame avec les clusters
        if 'result_df' not in clustering_result:
            flash('Le résultat du clustering ne contient pas de données client', 'danger')
            return redirect(url_for('clustering'))
        
        # Récupérer le DataFrame
        df = clustering_result['result_df']
        
        # Vérifier si le DataFrame a une colonne client_id
        if 'client_id' not in df.columns:
            flash('Les données du clustering ne contiennent pas d\'ID client', 'danger')
            return redirect(url_for('clustering'))
        
        # Déterminer la colonne de cluster
        cluster_col = None
        for col in df.columns:
            if col.startswith('cluster_'):
                cluster_col = col
                break
        
        if not cluster_col:
            flash('Colonne de cluster non trouvée dans les données', 'danger')
            return redirect(url_for('clustering'))
        
        # Initialiser les gestionnaires de fidélité
        loyalty_manager = LoyaltyManager()
        reward_manager = RewardManager()
        
        # Récupérer le délai d'expiration
        expiration_days = int(request.form.get('expiration_days', 30))
        expiration_date = (datetime.now() + timedelta(days=expiration_days)).strftime('%Y-%m-%d')
        
        # Pour chaque cluster, créer une règle et des offres
        offers_created = 0
        clusters_processed = 0
        
        for cluster_id in clustering_result.get('cluster_sizes', {}).keys():
            # Ignorer le cluster de bruit (-1) pour DBSCAN
            if cluster_id == -1:
                continue
            
            # Vérifier si cette offre est activée
            if not request.form.get(f'enable_offer_{cluster_id}'):
                continue
            
            clusters_processed += 1
            
            # Vérifier le type d'offre
            offer_type = request.form.get(f'offer_type_{cluster_id}')
            
            if offer_type == 'manual':
                # Récupérer les paramètres manuels
                action_type = request.form.get(f'action_type_{cluster_id}')
                action_value = request.form.get(f'action_value_{cluster_id}')
                gift_id = request.form.get(f'gift_id_{cluster_id}')
            else:
                # Utiliser le contexte pour générer une offre
                context = request.form.get(f'generation_context_{cluster_id}', '')
                
                # Récupérer les statistiques du cluster
                if clustering_result['algorithm'] == 'dbscan':
                    if cluster_id in clustering_result.get('cluster_stats', {}):
                        cluster_stats = {
                            col: {
                                "mean": values['mean'], 
                                "median": values['median']
                            }
                            for col, values in clustering_result['cluster_stats'][cluster_id].items()
                        }
                    else:
                        cluster_stats = {}
                else:
                    cluster_stats = {
                        col: {
                            "mean": values['mean'], 
                            "median": values['median']
                        }
                        for col, values in clustering_result['cluster_stats'][int(cluster_id)].items()
                    }
                
                # Formater les statistiques pour le générateur
                formatted_stats = {}
                for col, values in cluster_stats.items():
                    formatted_stats[col] = f"Moyenne: {values['mean']:.2f}, Médiane: {values['median']:.2f}"
                
                # Générer l'offre
                generated = offer_generator.generate_offer(cluster_id, formatted_stats, context)
                
                action_type = generated['offer_type']
                action_value = generated['offer_value']
                description = generated['offer_description']
                message = generated['offer_message']
            
            # Récupérer le message personnalisé
            message = request.form.get(f'offer_message_{cluster_id}', '')
            
            # Créer une règle de fidélité temporaire pour ce cluster
            conn = get_db_connection()
            
            # Préparer les paramètres de la règle
            regle_nom = f"Offre cluster {cluster_id} - {datetime.now().strftime('%Y-%m-%d')}"
            regle_description = f"Règle générée automatiquement pour le cluster {cluster_id} du clustering {clustering_id}"
            
            # Insérer la règle
            cursor = conn.execute('''
                INSERT INTO regles_fidelite (
                    nom, description, type_regle, condition_valeur, 
                    action_type, action_value, recompense_id,
                    est_active, priorite, date_creation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                regle_nom,
                regle_description,
                'cluster_specific',  # Type spécifique pour les règles de cluster
                str(cluster_id),     # L'ID du cluster comme valeur de condition
                action_type,
                action_value,
                gift_id if action_type == 'offre_cadeau' else None,
                1,  # Règle active
                10  # Priorité moyenne
            ))
            
            regle_id = cursor.lastrowid
            
            # Récupérer les clients de ce cluster
            clients = df[df[cluster_col] == cluster_id]['client_id'].unique()
            
            # Créer une offre pour chaque client
            for client_id in clients:
                conn.execute('''
                    INSERT INTO offres_client (
                        client_id, regle_id, recompense_id, date_generation,
                        date_expiration, statut, commentaire
                    ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 'generee', ?)
                ''', (
                    client_id,
                    regle_id,
                    gift_id if action_type == 'offre_cadeau' else None,
                    expiration_date,
                    message if message else f"Offre spéciale basée sur votre profil client"
                ))
                
                offers_created += 1
            
            # Générer des codes uniques pour toutes les nouvelles offres
            conn.execute('''
                UPDATE offres_client
                SET code_unique = 'OF-' || offre_id || '-' || substr(hex(randomblob(4)), 1, 8)
                WHERE code_unique IS NULL
            ''')
            
            conn.commit()
            conn.close()
        
        # Message de succès
        flash(f'{offers_created} offres créées pour {clusters_processed} clusters', 'success')
        
        # Rediriger vers la page des offres
        return redirect(url_for('loyalty_offers'))
        
    except Exception as e:
        logging.error(f"Erreur lors de la création des offres: {e}", exc_info=True)
        flash(f'Erreur lors de la création des offres: {str(e)}', 'danger')
        return redirect(url_for('clustering'))