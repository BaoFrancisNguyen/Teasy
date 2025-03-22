"""
Module de cartographie avancé pour l'application MILAN
"""

import sqlite3
import pandas as pd
import json
import numpy as np
from colour import Color

def create_sales_map(conn=None, filters=None):
    """
    Crée une carte de ventes avec des marqueurs personnalisés.
    
    Args:
        conn (sqlite3.Connection, optional): Connexion à la base de données
        filters (dict, optional): Filtres à appliquer sur les données
    
    Returns:
        dict: Données de la carte au format JSON
    """
    # Gestion de la connexion à la base de données
    close_conn = False
    if conn is None:
        conn = sqlite3.connect('C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/fidelity_db.sqlite')
        close_conn = True
    
    try:
        # Construction de la requête SQL de base
        query = """
        SELECT 
            pv.magasin_id, 
            pv.nom, 
            pv.latitude, 
            pv.longitude, 
            COALESCE(SUM(t.montant_total), 0) as total_ventes,
            COUNT(t.transaction_id) as nb_transactions
        FROM points_vente pv
        LEFT JOIN transactions t ON pv.magasin_id = t.magasin_id
        WHERE pv.latitude IS NOT NULL AND pv.longitude IS NOT NULL
        """
        
        # Ajouter des filtres si nécessaire
        params = []
        if filters:
            conditions = []
            if filters.get('date_debut'):
                conditions.append("t.date_transaction >= ?")
                params.append(filters['date_debut'])
            if filters.get('date_fin'):
                conditions.append("t.date_transaction <= ?")
                params.append(filters['date_fin'])
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
        
        query += " GROUP BY pv.magasin_id, pv.nom, pv.latitude, pv.longitude"
        
        # Exécuter la requête
        df = pd.read_sql_query(query, conn, params=params)
        
        # Vérifier s'il y a des données
        if df.empty:
            return {
                'success': False,
                'error': 'Aucune donnée trouvée pour la période sélectionnée'
            }
        
        # Normalisation des ventes pour la visualisation
        df['sales_normalized'] = (df['total_ventes'] - df['total_ventes'].min()) / (df['total_ventes'].max() - df['total_ventes'].min())
        
        # Créer le dégradé de couleur
        green = Color("#2ecc71")  # Vert
        red = Color("#e74c3c")    # Rouge
        colors = list(green.range_to(red, len(df)))
        
        # Préparer les données pour le frontend
        markers = []
        for _, row in df.iterrows():
            # Sélectionner une couleur basée sur les ventes normalisées
            color_index = min(int(row['sales_normalized'] * (len(colors) - 1)), len(colors) - 1)
            color = colors[color_index].hex
            
            markers.append({
                'name': row['nom'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'sales': row['total_ventes'],
                'sales_normalized': row['sales_normalized'],
                'transactions': row['nb_transactions'],
                'color': color
            })
        
        # Fermer la connexion si nécessaire
        if close_conn:
            conn.close()
        
        return {
            'success': True,
            'map_data': json.dumps({
                'markers': markers,
                'total_sales': float(df['total_ventes'].sum()),
                'total_transactions': int(df['nb_transactions'].sum())
            })
        }
    
    except Exception as e:
        # Gérer les erreurs
        print(f"Erreur lors de la création de la carte : {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # S'assurer que la connexion est fermée
        if close_conn and 'conn' in locals():
            conn.close()

def analyze_geographical_sales(conn=None, filters=None):
    """
    Analyse géographique détaillée des ventes.
    
    Args:
        conn (sqlite3.Connection, optional): Connexion à la base de données
        filters (dict, optional): Filtres à appliquer sur les données
    
    Returns:
        dict: Statistiques géographiques détaillées
    """
    # Gestion de la connexion à la base de données
    close_conn = False
    if conn is None:
        conn = sqlite3.connect('C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/fidelity_db.sqlite')
        close_conn = True
    
    try:
        # Requête SQL pour obtenir les statistiques par ville
        query = """
        SELECT 
            COALESCE(pv.ville, 'Non spécifié') as ville,
            COUNT(DISTINCT pv.magasin_id) as nb_magasins,
            COALESCE(SUM(t.montant_total), 0) as total_ventes,
            COALESCE(AVG(t.montant_total), 0) as panier_moyen,
            COUNT(t.transaction_id) as nb_transactions
        FROM points_vente pv
        LEFT JOIN transactions t ON pv.magasin_id = t.magasin_id
        WHERE pv.ville IS NOT NULL
        """
        
        # Ajouter des filtres si nécessaire
        params = []
        if filters:
            conditions = []
            if filters.get('date_debut'):
                conditions.append("t.date_transaction >= ?")
                params.append(filters['date_debut'])
            if filters.get('date_fin'):
                conditions.append("t.date_transaction <= ?")
                params.append(filters['date_fin'])
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
        
        query += """
        GROUP BY ville
        ORDER BY total_ventes DESC
        """
        
        # Exécuter la requête
        df = pd.read_sql_query(query, conn, params=params)
        
        # Fermer la connexion si nécessaire
        if close_conn:
            conn.close()
        
        # Convertir les résultats en liste de dictionnaires
        stats = df.to_dict(orient='records')
        
        return {
            'success': True,
            'stats': stats,
            'total_cities': len(stats),
            'total_sales': float(df['total_ventes'].sum()),
            'total_transactions': int(df['nb_transactions'].sum())
        }
    
    except Exception as e:
        print(f"Erreur lors de l'analyse géographique : {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # S'assurer que la connexion est fermée
        if close_conn and 'conn' in locals():
            conn.close()

def generate_geographical_insights(sales_data):
    """
    Génère des insights à partir des données géographiques de ventes.
    
    Args:
        sales_data (dict): Données de ventes géographiques
    
    Returns:
        dict: Insights générés
    """
    insights = []
    
    if not sales_data.get('success', False):
        return {'insights': []}
    
    stats = sales_data.get('stats', [])
    
    # Top 3 des villes par ventes
    top_cities = sorted(stats, key=lambda x: x.get('total_ventes', 0), reverse=True)[:3]
    if top_cities:
        insights.append({
            'type': 'success',
            'message': f"Top 3 des villes : {', '.join([city['ville'] for city in top_cities])}"
        })
    
    # Ville avec le panier moyen le plus élevé
    top_basket_city = max(stats, key=lambda x: x.get('panier_moyen', 0)) if stats else None
    if top_basket_city:
        insights.append({
            'type': 'info',
            'message': f"Ville avec le panier moyen le plus élevé : {top_basket_city['ville']} ({top_basket_city['panier_moyen']:.2f} €)"
        })
    
    # Distribution des ventes
    total_sales = sales_data.get('total_sales', 0)
    total_transactions = sales_data.get('total_transactions', 0)
    
    if total_transactions > 0:
        avg_transaction = total_sales / total_transactions
        insights.append({
            'type': 'neutral',
            'message': f"Ventes totales : {total_sales:.2f} € sur {total_transactions} transactions"
        })
        
        insights.append({
            'type': 'neutral',
            'message': f"Panier moyen global : {avg_transaction:.2f} €"
        })
    
    return {'insights': insights}
