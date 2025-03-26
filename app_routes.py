from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, make_response
import pandas as pd
import numpy as np
import os
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import sqlite3
from dateutil.relativedelta import relativedelta
from functools import wraps
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from jinja2 import Environment, FileSystemLoader
from flask import render_template, request, redirect, url_for, flash, jsonify
from modules.loyalty_scheduler_controller import (
    load_config, save_config, update_task_config, start_scheduler, 
    stop_scheduler, restart_scheduler, run_specific_task, 
    get_scheduler_logs, get_scheduler_status, is_scheduler_running
)

# Importer nos modules personnalisés
from modules.db_connection import DatabaseManager
from modules.data_processor_module import DataProcessor
from modules.clustering_module import ClusteringProcessor
from modules.visualization_module import create_visualization, generate_report
from modules.history_manager_module import AnalysisHistory, PDFAnalysisHistory
from modules.transformations_persistence import TransformationManager
from modules.maps_module import create_sales_map, analyze_geographical_sales, generate_geographical_insights
from modules.store_locations import update_store_locations, verify_store_locations
from modules.loyalty_manager import LoyaltyManager, RewardManager
from modules.cluster_offers_routes import cluster_offers
from modules.settings_routes import settings_bp
# Ajoutez l'import nécessaire en haut du fichier
from modules.cluster_offers_routes import ClusterOfferGenerator


import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration de l'application
app = Flask(__name__)
app.secret_key = "milan_app_secret_key_2025"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite 16 Mo
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'txt', 'xlsx', 'pdf', 'wav', 'mp3'}
app.register_blueprint(cluster_offers)
app.register_blueprint(settings_bp)


# S'assurer que le dossier d'upload existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialisation des gestionnaires
db_manager = DatabaseManager('init_database/fidelity_db')
data_processor = DataProcessor()
transformation_manager = TransformationManager('uploads')
history_manager = AnalysisHistory('analysis_history')
pdf_history_manager = PDFAnalysisHistory('analysis_history/pdf')


# Fonction pour obtenir une connexion à la base de données
def get_db_connection(db_path='fidelity_db.sqlite'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_app():
    app = Flask(__name__)
    app.secret_key = 'votre_clé_secrète_ici'  # Remplacez par une vraie clé secrète
    
    # Enregistrer le Blueprint
    app.register_blueprint(settings_bp)

# Routes principales
@app.route('/')
def index():
    """Page d'accueil de l'application"""
    return render_template('index.html')

# Modifie la route data_processing pour gérer correctement les filtres
@app.route('/data_processing', methods=['GET', 'POST'])
def data_processing():
    """
    Page de traitement de données CSV ou accès à la base de données
    Gère le chargement et le filtrage des transactions depuis SQLite
    """
    # Initialisation des variables de connexion et d'état
    db_connected = False
    db_info = ""
    db_error = "Base de données non initialisée."
    transactions_count = 0
    
    # Chemin de la base de données
    db_path = 'modules/fidelity_db.sqlite'
    
    # Variables pour stocker les données des listes déroulantes
    points_vente = []
    enseignes = []
    categories_produits = []
    villes = []
    produits = []
    moyens_paiement = []
    
    def decompose_transaction_with_articles(transaction_data):
        """
        Décompose un enregistrement de transaction avec ses articles.
        
        Args:
            transaction_data (dict): Dictionnaire contenant les détails de la transaction et ses articles
        
        Returns:
            list: Liste de dictionnaires, un pour chaque article de la transaction
        """
        # Extraire les détails de base de la transaction
        base_details = {
            'id': transaction_data['id'],
            'date_transaction': transaction_data['date_transaction'],
            'montant_total': transaction_data['montant_total'],
            'numero_facture': transaction_data['numero_facture'],
            'magasin': transaction_data['magasin'],
            'enseigne': transaction_data['enseigne'],
            'moyen_paiement': transaction_data['moyen_paiement'],
            'canal_vente': transaction_data['canal_vente'],
            'points_gagnes': transaction_data['points_gagnes']
        }
        
        # Ajouter les données démographiques client si disponibles
        # Ces clés seront présentes uniquement si include_demographics est vrai
        for key in ['client_id', 'genre', 'age', 'segment_client', 'niveau_fidelite']:
            if key in transaction_data:
                base_details[key] = transaction_data[key]
        
        # Si pas d'articles, retourner un seul enregistrement avec des détails d'article vides
        if not transaction_data.get('articles', []):
            base_details.update({
                'nom_article': None,
                'quantite': None,
                'prix_unitaire': None,
                'remise_pourcentage': None,
                'montant_ligne': None,
                'categorie': None
            })
            return [base_details]
        
        # Créer un enregistrement pour chaque article de la transaction
        decomposed_records = []
        for article in transaction_data['articles']:
            record = base_details.copy()
            record.update({
                'nom_article': article.get('nom_article'),
                'quantite': article.get('quantite'),
                'prix_unitaire': article.get('prix_unitaire'),
                'remise_pourcentage': article.get('remise_pourcentage'),
                'montant_ligne': article.get('montant_ligne'),
                'categorie': article.get('categorie')
            })
            decomposed_records.append(record)
        
        return decomposed_records

    # Bloc de connexion et récupération des données
    try:
        # Afficher le chemin complet de la base de données
        abs_db_path = os.path.abspath(db_path)
        
        # Vérifier si le fichier existe
        if os.path.exists(db_path):
            # Connexion à la base de données
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Tester la connexion en récupérant la liste des tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            table_count = len(table_names)
            
            # Vérifier si les tables nécessaires existent
            has_points_vente = 'points_vente' in table_names
            has_transactions = 'transactions' in table_names
            has_produits = 'produits' in table_names
            has_categories = 'categories_produits' in table_names
            has_clients = 'clients' in table_names
            
            # Récupérer des informations sur les transactions
            if has_transactions:
                try:
                    cursor.execute("SELECT COUNT(*) as count FROM transactions")
                    transactions_count = cursor.fetchone()[0]
                except Exception as e:
                    logger.error(f"Erreur lors du comptage des transactions: {e}")
                    transactions_count = 0
            
            db_connected = True
            db_info = f"Base de données connectée: {abs_db_path}. {table_count} tables trouvées. {transactions_count} transactions enregistrées."
            
            # Récupération des données pour les listes déroulantes
            if has_points_vente:
                try:
                    # Points de vente
                    cursor.execute("""
                        SELECT magasin_id, nom, ville, code_postal, type, email as enseigne
                        FROM points_vente
                        WHERE statut != 'fermé'
                        ORDER BY nom
                    """)
                    points_vente = [dict(row) for row in cursor.fetchall()]
                    
                    # Enseignes
                    cursor.execute("""
                        SELECT DISTINCT email as enseigne 
                        FROM points_vente 
                        WHERE email IS NOT NULL 
                        ORDER BY email
                    """)
                    enseignes = [row[0] for row in cursor.fetchall() if row[0]]
                    
                    # Villes
                    cursor.execute("""
                        SELECT DISTINCT ville 
                        FROM points_vente 
                        WHERE ville IS NOT NULL 
                        ORDER BY ville
                    """)
                    villes = [row[0] for row in cursor.fetchall() if row[0]]
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des points de vente: {e}")
            
            # Catégories de produits
            if has_categories:
                try:
                    cursor.execute("""
                        SELECT categorie_id, nom, description, categorie_parent_id
                        FROM categories_produits
                        ORDER BY nom
                    """)
                    categories_produits = [dict(row) for row in cursor.fetchall()]
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des catégories: {e}")
            
            # Produits
            if has_produits:
                try:
                    cursor.execute("""
                        SELECT produit_id, reference, nom, categorie_id, marque, prix_standard
                        FROM produits
                        WHERE statut = 'actif'
                        ORDER BY nom
                        LIMIT 100
                    """)
                    produits = [dict(row) for row in cursor.fetchall()]
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des produits: {e}")
            
            # Moyens de paiement
            if has_transactions:
                try:
                    cursor.execute("""
                        SELECT DISTINCT type_paiement
                        FROM transactions
                        WHERE type_paiement IS NOT NULL
                        ORDER BY type_paiement
                    """)
                    moyens_paiement = [row[0] for row in cursor.fetchall() if row[0]]
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des moyens de paiement: {e}")
            
            conn.close()
        else:
            logger.warning(f"Base de données non trouvée: {abs_db_path}")
            db_error = f"Base de données non trouvée: {abs_db_path}"
    
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
        db_error = f"Erreur de connexion: {str(e)}"
    
    # Traitement des requêtes POST
    if request.method == 'POST':
        # Vérifier le type de source de données
        data_source = request.form.get('data_source', '')
        
        # Traitement du fichier CSV
        if 'file' in request.files and data_source != 'sqlite':
            file = request.files['file']
            if file.filename == '':
                flash('Aucun fichier sélectionné', 'warning')
                return redirect(request.url)
            
            if file and allowed_file(file.filename):
                # TODO: Implémenter le traitement du fichier CSV
                # Code existant de traitement CSV
                pass
        
        # Traitement des données de la base de données SQLite
        elif data_source == 'sqlite' or (not 'file' in request.files and db_connected):
            try:
                # Récupérer les filtres du formulaire
                filters = {
                    'date_debut': request.form.get('date_debut', ''),
                    'date_fin': request.form.get('date_fin', ''),
                    'magasin_id': request.form.get('magasin_id', ''),
                    'enseigne': request.form.get('enseigne', ''),
                    'ville': request.form.get('ville', ''),
                    'categorie_id': request.form.get('categorie_id', ''),
                    'produit_id': request.form.get('produit_id', ''),
                    'moyen_paiement': request.form.get('moyen_paiement', ''),
                    'montant_min': request.form.get('montant_min', ''),
                    'montant_max': request.form.get('montant_max', ''),
                    'include_items': request.form.get('include_items') == 'true',
                    'include_demographics': request.form.get('include_demographics') == 'true'  # Nouveau filtre
                }
                
                logger.info(f"Filtres appliqués: {filters}")
                
                # Gestion des dates par défaut
                if not filters['date_debut'] or not filters['date_fin']:
                    today = datetime.now()
                    filters['date_fin'] = today.strftime('%Y-%m-%d') if not filters['date_fin'] else filters['date_fin']
                    filters['date_debut'] = (today - timedelta(days=90)).strftime('%Y-%m-%d') if not filters['date_debut'] else filters['date_debut']
                
                # Connexion à la base de données
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Construction de la requête de base
                query = """
                SELECT t.transaction_id as id, t.date_transaction, t.montant_total, 
                       t.numero_facture, pv.nom as magasin, pv.email as enseigne, 
                       t.type_paiement as moyen_paiement, t.canal_vente, t.points_gagnes
                """
                
                # Ajouter les champs démographiques si demandé
                if filters['include_demographics']:
                    query += """,
                       t.client_id, c.genre, 
                       (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) as age,
                       c.segment as segment_client, cf.niveau_fidelite
                    """
                
                query += """
                FROM transactions t
                LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
                """
                
                # Ajouter les jointures pour les données démographiques si demandé
                if filters['include_demographics']:
                    query += """
                    LEFT JOIN clients c ON t.client_id = c.client_id
                    LEFT JOIN cartes_fidelite cf ON t.carte_id = cf.carte_id
                    """
                
                # Ajout des jointures conditionnelles
                if filters['categorie_id'] or filters['produit_id']:
                    query += """
                    JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                    JOIN produits p ON dt.produit_id = p.produit_id
                    """
                
                # Initialisation des conditions WHERE
                query += " WHERE 1=1"
                params = []
                
                # Ajout des conditions de filtrage
                conditions_filtres = [
                    ('date_transaction', '>=', filters['date_debut']),
                    ('date_transaction', '<=', filters['date_fin']),
                    ('t.magasin_id', '=', filters['magasin_id']),
                    ('pv.email', '=', filters['enseigne']),
                    ('pv.ville', '=', filters['ville']),
                    ('p.categorie_id', '=', filters['categorie_id']),
                    ('dt.produit_id', '=', filters['produit_id']),
                    ('t.type_paiement', '=', filters['moyen_paiement'])
                ]
                
                for colonne, operateur, valeur in conditions_filtres:
                    if valeur:
                        query += f" AND {colonne} {operateur} ?"
                        params.append(valeur)
                
                # Filtres de montant
                if filters['montant_min']:
                    query += " AND t.montant_total >= ?"
                    params.append(float(filters['montant_min']))
                
                if filters['montant_max']:
                    query += " AND t.montant_total <= ?"
                    params.append(float(filters['montant_max']))
                
                # Gestion des doublons
                if filters['categorie_id'] or filters['produit_id']:
                    query += " GROUP BY t.transaction_id"
                
                # Tri et limitation
                query += " ORDER BY t.date_transaction DESC LIMIT 5000"
                
                logger.info(f"Requête SQL: {query}")
                logger.info(f"Paramètres: {params}")
                
                # Exécution de la requête
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                if not rows:
                    flash('Aucune donnée trouvée avec les filtres spécifiés', 'warning')
                    conn.close()
                    return redirect(request.url)
                
                # Conversion en DataFrame
                df = pd.DataFrame([dict(row) for row in rows])
                
                # Traitement des articles si demandé
                if filters['include_items']:
                    try:
                        # Récupération des articles
                        transaction_ids = df['id'].tolist()
                        transaction_ids_str = ','.join(['?' for _ in transaction_ids])
                        
                        items_query = f"""
                        SELECT dt.transaction_id, p.nom as nom_article, dt.quantite, dt.prix_unitaire, 
                               dt.remise_pourcentage, dt.montant_ligne, cp.nom as categorie
                        FROM details_transactions dt
                        JOIN produits p ON dt.produit_id = p.produit_id
                        LEFT JOIN categories_produits cp ON p.categorie_id = cp.categorie_id
                        WHERE dt.transaction_id IN ({transaction_ids_str})
                        """
                        
                        cursor.execute(items_query, transaction_ids)
                        items = [dict(row) for row in cursor.fetchall()]
                        
                        # Groupement des articles par transaction
                        items_by_transaction = {}
                        for item in items:
                            transaction_id = item['transaction_id']
                            if transaction_id not in items_by_transaction:
                                items_by_transaction[transaction_id] = []
                            items_by_transaction[transaction_id].append(item)
                        
                        # Décomposition des transactions
                        decomposed_transactions = []
                        for _, transaction in df.iterrows():
                            transaction_dict = transaction.to_dict()
                            transaction_dict['articles'] = items_by_transaction.get(transaction['id'], [])
                            decomposed_transaction = decompose_transaction_with_articles(transaction_dict)
                            decomposed_transactions.extend(decomposed_transaction)
                        
                        # Mise à jour du DataFrame
                        df = pd.DataFrame(decomposed_transactions)
                        
                        logger.info(f"Décomposition des transactions : {len(df)} lignes")
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de la décomposition des transactions : {e}")
                
                # Fermeture de la connexion
                conn.close()
                
                # Conversion des types de données
                if 'date_transaction' in df.columns:
                    df['date_transaction'] = pd.to_datetime(df['date_transaction'])
                
                if 'montant_total' in df.columns:
                    df['montant_total'] = pd.to_numeric(df['montant_total'])
                
                # Conversion de l'âge en numérique si présent
                if 'age' in df.columns:
                    df['age'] = pd.to_numeric(df['age'], errors='coerce')
                
                # Génération d'un identifiant unique pour le fichier
                file_id = f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Sauvegarde du DataFrame
                transformation_manager.save_original_dataframe(file_id, df)
                
                # Mise à jour de la session
                session['file_id'] = file_id
                session['filename'] = f"transactions_{datetime.now().strftime('%Y%m%d')}"
                
                # Redirection vers la page d'aperçu
                return redirect(url_for('data_preview'))
                
            except Exception as e:
                flash(f'Erreur lors du chargement des données: {str(e)}', 'danger')
                logger.error(f"Erreur lors du chargement des données SQL: {e}")
                return redirect(request.url)
    
    # Méthode GET : préparation du formulaire
    # Dates par défaut
    default_date_fin = datetime.now().strftime('%Y-%m-%d')
    default_date_debut = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    # Récupération des analyses récentes
    recent_analyses = []
    try:
        recent_analyses = history_manager.get_recent_analyses(5)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des analyses récentes: {e}")
    
    # Rendu du template
    return render_template('data_processing.html', 
                          magasins=points_vente, 
                          enseignes=enseignes,
                          villes=villes,
                          categories_produits=categories_produits,
                          produits=produits,
                          moyens_paiement=moyens_paiement,
                          recent_analyses=recent_analyses,
                          db_connected=db_connected,
                          db_info=db_info,
                          db_error=db_error,
                          tickets_count=transactions_count,
                          default_date_debut=default_date_debut,
                          default_date_fin=default_date_fin)

@app.route('/data_preview')
def data_preview():
    """Page d'aperçu des données"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame actuel
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Préparer les informations du DataFrame pour l'affichage
    df_info = {
        'shape': df.shape,
        'dtypes': df.dtypes.astype(str).to_dict(),
        'missing_values': df.isna().sum().sum(),
        'has_numeric': len(df.select_dtypes(include=['number']).columns) > 0,
        'numeric_count': len(df.select_dtypes(include=['number']).columns),
        'columns': df.columns.tolist()
    }
    
    # Créer un aperçu HTML des données (limité à 100 lignes)
    preview_data = df.head(100).to_html(classes='table table-striped table-hover', index=False)
    
    return render_template('data_preview.html',
                           df_info=df_info,
                           preview_data=preview_data,
                           filename=filename,
                           columns=df.columns.tolist())

# Dans app_routes.py

@app.route('/api/dataset_preview')
def api_dataset_preview():
    """API pour récupérer les données d'aperçu du dataset"""
    # Vérifier si un fichier est chargé
    file_id = session.get('file_id')
    if not file_id:
        return jsonify({"error": "Aucune donnée chargée"})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    if df is None:
        return jsonify({"error": "Erreur lors de la récupération des données"})
    
    # Limiter le nombre d'éléments à récupérer
    limit = int(request.args.get('limit', 10))
    
    # Vérifier si le DataFrame contient une colonne d'articles
    has_articles = 'articles' in df.columns
    
    try:
        if has_articles:
            # Extraire les tickets avec leurs articles (limité)
            tickets_data = []
            for _, row in df.head(limit).iterrows():
                ticket = {
                    'id': int(row['id']) if 'id' in row else None,
                    'date_transaction': row['date_transaction'].isoformat() if pd.notna(row.get('date_transaction')) else None,
                    'montant_total': float(row['montant_total']) if pd.notna(row.get('montant_total')) else 0,
                    'magasin': row.get('magasin', 'Inconnu'),
                    'enseigne': row.get('enseigne', None),
                    'moyen_paiement': row.get('moyen_paiement', None),
                    'articles': row.get('articles', [])
                }
                tickets_data.append(ticket)
            
            return jsonify({
                "success": True,
                "tickets": tickets_data,
                "has_articles": True
            })
        else:
            # Pour les DataFrames sans articles
            data = df.head(limit).to_dict('records')
            return jsonify({
                "success": True,
                "data": data,
                "has_articles": False
            })
    
    except Exception as e:
        app.logger.error(f"Erreur lors de la récupération de l'aperçu: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route('/data_transform', methods=['GET', 'POST'])
def data_transform():
    """Page de transformation des données"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame original
    df_original = transformation_manager.load_original_dataframe(file_id)
    
    if df_original is None:
        flash('Erreur lors de la récupération des données originales. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))

    # Pour l'analyse IA
    analysis_result = None
    analysis_pending = False
    
    if request.method == 'POST':
        # Récupérer les transformations demandées
        transformations = request.form.getlist('transformations[]')
        logger.info(f"Transformations demandées: {transformations}")
        
        # Vérifier si c'est une analyse IA
        is_ai_analysis = request.form.get('is_ai_analysis') == 'true'
        
        if is_ai_analysis:
            user_context = request.form.get('user_context', '')
            
            try:
                # Récupérer le DataFrame actuel après toutes les transformations
                current_df = transformation_manager.get_current_dataframe(file_id)
                
                # Importer le transformateur de données qui contient l'accès à l'IA
                from modules.data_transformer_module import DataTransformer
                
                # Créer le transformateur
                data_transformer = DataTransformer()
                
                # Générer l'analyse
                analysis_result = data_transformer.generate_dataset_analysis(current_df, user_context)
                
                # Sauvegarder l'analyse dans l'historique
                if request.form.get('save_history') == 'true':
                    history_manager.add_analysis(
                        dataset_name=filename,
                        dataset_description=f"Analyse IA - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        analysis_text=analysis_result,
                        metadata={
                            "user_context": user_context,
                            "dimensions": current_df.shape,
                            "columns": current_df.columns.tolist(),
                            "transformations": transformation_manager.get_transformations(file_id).get('history', [])
                        }
                    )
                    flash('Analyse IA sauvegardée dans l\'historique', 'success')
                
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse IA: {str(e)}")
                logger.error(traceback.format_exc())
                flash(f'Erreur lors de l\'analyse IA: {str(e)}', 'danger')
                analysis_pending = True
        else:
            # Construire le dictionnaire de transformations
            transform_dict = {}
            
            # Traitement des valeurs manquantes
            if 'missing_values' in transformations:
                strategy = request.form.get('missing_strategy', 'auto')
                transform_dict['missing_values'] = {
                    'strategy': strategy,
                    'threshold': float(request.form.get('missing_threshold', 0.5)),
                    'constant': request.form.get('missing_constant', '')
                }
            
            # Standardisation
            if 'standardization' in transformations:
                columns = request.form.getlist('columns_to_standardize[]')
                transform_dict['standardization'] = {
                    'columns': columns,
                    'method': request.form.get('standardization_method', 'zscore')
                }
            
            # Encodage
            if 'encoding' in transformations:
                columns = request.form.getlist('columns_to_encode[]')
                transform_dict['encoding'] = {
                    'columns': columns,
                    'method': request.form.get('encoding_method', 'one_hot'),
                    'drop_original': request.form.get('drop_original', 'true') == 'true'
                }
            
            # Valeurs aberrantes
            if 'outliers' in transformations:
                columns = request.form.getlist('columns_for_outliers[]')
                transform_dict['outliers'] = {
                    'columns': columns,
                    'method': request.form.get('outlier_detection_method', 'iqr'),
                    'treatment': request.form.get('outlier_treatment', 'tag')
                }
            
            # Ingénierie de caractéristiques
            if 'feature_engineering' in transformations:
                columns = request.form.getlist('interaction_columns[]') if 'interaction_columns[]' in request.form else None
                operations = request.form.getlist('interaction_operations[]') if 'interaction_operations[]' in request.form else None
                transform_dict['feature_engineering'] = {
                    'type_fe': request.form.get('feature_engineering_type', 'interaction'),
                    'columns': columns,
                    'operations': operations
                }
            
            # Suppression de colonnes
            if 'drop_columns' in transformations:
                columns_to_drop = request.form.getlist('columns_to_drop[]')
                transform_dict['drop_columns'] = {
                    'columns_to_drop': columns_to_drop
                }
            
            # Fusion de colonnes
            if 'merge_columns' in transformations:
                columns_to_merge = request.form.getlist('columns_to_merge[]')
                new_column = request.form.get('new_column_name', 'merged_column')
                transform_dict['merge_columns'] = {
                    'columns_to_merge': columns_to_merge,
                    'new_column': new_column,
                    'method': request.form.get('merge_method', 'concat'),
                    'separator': request.form.get('separator', ', '),
                    'drop_original': request.form.get('drop_original_columns', 'false') == 'true'
                }
            
            # Remplacement de valeurs
            if 'replace_values' in transformations:
                column = request.form.get('column_to_replace')
                original_values = request.form.getlist('original_values[]')
                new_values = request.form.getlist('new_values[]')
                
                replacements = {}
                for i in range(len(original_values)):
                    if i < len(new_values) and original_values[i]:
                        replacements[original_values[i]] = new_values[i]
                
                transform_dict['replace_values'] = {
                    'column': column,
                    'replacements': replacements,
                    'replace_all': request.form.get('replace_all_occurrences', 'true') == 'true'
                }
            
            # Appliquer les transformations
            if transform_dict:
                try:
                    # Récupérer le DataFrame actuel
                    current_df = transformation_manager.get_current_dataframe(file_id)
                    
                    # Log avant transformation
                    logger.info(f"DataFrame avant transformation: {current_df.shape}, colonnes: {current_df.columns.tolist()}")
                    
                    # Appliquer les transformations
                    df_transformed, metadata = data_processor.process_dataframe(current_df, transform_dict)
                    
                    # Log après transformation
                    logger.info(f"DataFrame après transformation: {df_transformed.shape}, colonnes: {df_transformed.columns.tolist()}")
                    
                    # Vérifier si la transformation a eu un effet
                    if df_transformed.equals(current_df):
                        logger.warning("ATTENTION: Le DataFrame transformé est identique à l'original. La transformation n'a pas eu d'effet.")
                    
                    # Sauvegarder le DataFrame transformé (copie profonde pour éviter les problèmes de référence)
                    import copy
                    df_to_save = copy.deepcopy(df_transformed)
                    success = transformation_manager.save_transformed_dataframe(file_id, df_to_save)
                    logger.info(f"Sauvegarde du DataFrame transformé: {'succès' if success else 'échec'}")
                    
                    # Vérifier que la sauvegarde a fonctionné
                    verification_df = transformation_manager.load_transformed_dataframe(file_id)
                    if verification_df is None:
                        logger.error("ERREUR CRITIQUE: Le DataFrame transformé n'a pas été correctement sauvegardé!")
                    elif verification_df.equals(df_transformed):
                        logger.info("VÉRIFICATION RÉUSSIE: Le DataFrame transformé a été correctement sauvegardé et rechargé.")
                    else:
                        logger.warning("ATTENTION: Le DataFrame rechargé après sauvegarde est différent de celui transformé!")
                    
                    # Ajouter la transformation à l'historique
                    for transform_type, params in transform_dict.items():
                        transform_success = transformation_manager.add_transformation(file_id, {
                            "type": transform_type,
                            "params": params,
                            "timestamp": datetime.now().isoformat(),
                            "applied_successfully": success
                        })
                        logger.info(f"Ajout de la transformation {transform_type} à l'historique: {transform_success}")
                    
                    flash('Transformations appliquées avec succès !', 'success')
                except Exception as e:
                    logger.error(f"Erreur lors de l'application des transformations: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash(f'Erreur lors de l\'application des transformations: {str(e)}', 'danger')
            
        return redirect(url_for('data_transform'))
    
    # Pour la méthode GET, récupérer le DataFrame courant pour préparer les informations
    current_df = transformation_manager.get_current_dataframe(file_id)
    
    df_info = {
        'shape': current_df.shape,
        'dtypes': current_df.dtypes.astype(str).to_dict(),
        'missing_values': current_df.isna().sum().sum(),
        'has_numeric': len(current_df.select_dtypes(include=['number']).columns) > 0,
        'numeric_count': len(current_df.select_dtypes(include=['number']).columns),
        'columns': current_df.columns.tolist()
    }
    
    # Colonnes numériques et catégorielles pour les formulaires
    numeric_columns = current_df.select_dtypes(include=['number']).columns.tolist()
    categorical_columns = current_df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Récupérer l'historique des transformations
    transform_history = transformation_manager.get_transformations(file_id)
    
    return render_template('data_transform.html',
                           df_info=df_info,
                           numeric_columns=numeric_columns,
                           categorical_columns=categorical_columns,
                           filename=filename,
                           analysis_result=analysis_result,
                           analysis_pending=analysis_pending,
                           transformations_history=transform_history.get('history', []))

@app.route('/visualizations')
def visualizations():
    """Page de visualisations"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame courant
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Colonnes numériques pour les visualisations
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    
    return render_template('visualizations.html',
                           columns=df.columns.tolist(),
                           numeric_columns=numeric_columns,
                           filename=filename)

@app.route('/clustering')
def clustering():
    """Page de clustering"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame courant
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Informations sur le DataFrame
    df_info = {
        'shape': df.shape
    }
    
    # Colonnes numériques pour le clustering
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    
    return render_template('clustering.html',
                           df_info=df_info,
                           numeric_columns=numeric_columns,
                           filename=filename)

@app.route('/run_clustering', methods=['POST'])
def run_clustering():
    """Exécute l'algorithme de clustering sélectionné et ajoute le formulaire d'offres par clusters"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame courant
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Récupérer les paramètres du formulaire
    algorithm = request.form.get('algorithm')
    columns = request.form.getlist('columns[]')
    
    # Paramètres spécifiques à l'algorithme
    params = {}
    
    if algorithm == 'kmeans':
        params['n_clusters'] = int(request.form.get('kmeans-n-clusters', 3))
        params['max_iter'] = int(request.form.get('kmeans-max-iter', 300))
        params['n_init'] = int(request.form.get('kmeans-n-init', 10))
    
    elif algorithm == 'dbscan':
        params['eps'] = float(request.form.get('dbscan-eps', 0.5))
        params['min_samples'] = int(request.form.get('dbscan-min-samples', 5))
    
    elif algorithm == 'hierarchical':
        params['n_clusters'] = int(request.form.get('hierarchical-n-clusters', 3))
        params['affinity'] = request.form.get('hierarchical-affinity', 'euclidean')
        params['linkage'] = request.form.get('hierarchical-linkage', 'ward')
    
    try:
        # Initialiser le processeur de clustering
        from modules.clustering_module import ClusteringProcessor
        clustering_processor = ClusteringProcessor()
        
        # Exécuter le clustering
        clustering_result = clustering_processor.cluster_data(df, algorithm, columns, params)
        
        if not clustering_result["success"]:
            flash(f'Erreur lors du clustering: {clustering_result.get("error", "Erreur inconnue")}', 'danger')
            return redirect(url_for('clustering'))
        
        # Générer un ID unique pour le clustering
        import uuid
        import pickle
        import os
        clustering_id = f"clustering_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # Stocker le DataFrame résultant séparément si présent
        if "result_df" in clustering_result:
            transformation_manager.save_transformed_dataframe(file_id, clustering_result["result_df"])
            # Faire une copie de result_df avant de le supprimer
            result_df_copy = clustering_result["result_df"].copy()
            # Supprimer le DataFrame du résultat avant de le sauvegarder
            del clustering_result["result_df"]
        
        # Créer le dossier pour les résultats de clustering s'il n'existe pas
        clustering_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'clustering_results')
        os.makedirs(clustering_folder, exist_ok=True)
        
        # Sauvegarder les résultats du clustering dans un fichier
        clustering_file = os.path.join(clustering_folder, f"{clustering_id}.pkl")
        with open(clustering_file, 'wb') as f:
            pickle.dump(clustering_result, f)
        
        # Stocker l'ID du clustering dans la session
        session['clustering_id'] = clustering_id
        
        # Générer un résumé textuel du clustering
        cluster_summary = clustering_processor.generate_cluster_summary(clustering_result)
        
        # Journaliser le succès du stockage
        logger.info(f"Résultats du clustering sauvegardés dans {clustering_file}")
        
        # Pour la page de résultats, nous avons besoin d'une copie sécurisée pour l'affichage
        # Créer une version simplifiée (sérialisable) pour le rendu de la page
        display_result = {
            "success": clustering_result["success"],
            "algorithm": clustering_result["algorithm"],
            "n_clusters": clustering_result["n_clusters"],
            "columns_used": clustering_result["columns_used"],
            "labels": clustering_result["labels"],
            "cluster_sizes": clustering_result["cluster_sizes"],
            "pca_result": clustering_result["pca_result"],
            "pca_explained_variance": clustering_result["pca_explained_variance"]
        }
        
        # Ajouter des éléments spécifiques à l'algorithme
        if algorithm == 'kmeans':
            display_result["inertia"] = clustering_result.get("inertia")
            display_result["silhouette_score"] = clustering_result.get("silhouette_score")
            display_result["calinski_harabasz_score"] = clustering_result.get("calinski_harabasz_score")
            display_result["cluster_stats"] = clustering_result.get("cluster_stats", [])
        elif algorithm == 'dbscan':
            display_result["noise_points"] = clustering_result.get("noise_points")
            display_result["silhouette_score"] = clustering_result.get("silhouette_score")
            display_result["calinski_harabasz_score"] = clustering_result.get("calinski_harabasz_score")
            display_result["cluster_stats"] = clustering_result.get("cluster_stats", {})
        elif algorithm == 'hierarchical':
            display_result["silhouette_score"] = clustering_result.get("silhouette_score")
            display_result["calinski_harabasz_score"] = clustering_result.get("calinski_harabasz_score")
            display_result["cluster_stats"] = clustering_result.get("cluster_stats", [])
        
        # Remettre le DataFrame de résultats si nécessaire pour l'affichage
        if "result_df_copy" in locals():
            transformation_manager.save_transformed_dataframe(file_id, result_df_copy)
        
        # NOUVEAU: Récupérer les récompenses disponibles pour les offres par cluster
        conn = get_db_connection()
        rewards = conn.execute('''
            SELECT recompense_id, nom, description, points_necessaires
            FROM recompenses
            WHERE statut = 'active'
            ORDER BY nom
        ''').fetchall()
        conn.close()
        
        # Convertir les objets Row en dictionnaires pour les récompenses
        rewards_dicts = [dict(reward) for reward in rewards]
        
        return render_template('clustering.html',
                           df_info={'shape': df.shape},
                           numeric_columns=df.select_dtypes(include=['number']).columns.tolist(),
                           filename=filename,
                           clustering_result=display_result,
                           cluster_summary=cluster_summary,
                           clustering_id=clustering_id,  # Nouveau: Passer l'ID du clustering
                           rewards=rewards_dicts)        # Nouveau: Passer les récompenses disponibles
    
    except Exception as e:
        app.logger.error(f"Erreur lors du clustering: {e}", exc_info=True)
        flash(f'Erreur lors du clustering: {str(e)}', 'danger')
        return redirect(url_for('clustering'))

@app.route('/save_clustering', methods=['POST'])
def save_clustering():
    """Sauvegarde les résultats du clustering dans le DataFrame"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame courant
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Récupérer les résultats du clustering de la session
    clustering_result = session.get('clustering_result')
    
    if not clustering_result:
        flash('Aucun résultat de clustering trouvé. Veuillez d\'abord exécuter le clustering.', 'warning')
        return redirect(url_for('clustering'))
    
    try:
        # Récupérer le nom de la colonne pour les clusters
        cluster_column_name = request.form.get('cluster_column_name', f"cluster_{clustering_result['algorithm']}")
        
        # Ajouter les clusters au DataFrame
        df_with_clusters = df.copy()
        
        # Créer une colonne pour les clusters
        df_with_clusters[cluster_column_name] = clustering_result['labels']
        
        # Sauvegarder le DataFrame mis à jour
        transformation_manager.save_transformed_dataframe(file_id, df_with_clusters)
        
        # Ajouter la transformation à l'historique
        transformation_manager.add_transformation(file_id, {
            "type": "clustering",
            "params": {
                "algorithm": clustering_result['algorithm'],
                "n_clusters": clustering_result['n_clusters'],
                "column_name": cluster_column_name
            },
            "timestamp": datetime.now().isoformat()
        })
        
        flash(f'Clusters sauvegardés dans la colonne "{cluster_column_name}"', 'success')
        return redirect(url_for('data_preview'))
    
    except Exception as e:
        flash(f'Erreur lors de la sauvegarde des clusters: {str(e)}', 'danger')
        return redirect(url_for('clustering'))

@app.route('/export_clusters', methods=['GET'])
def export_clusters():
    """Exporte les résultats du clustering au format spécifié"""
    # Vérifier que le fichier est bien chargé
    file_id = session.get('file_id')
    filename = session.get('filename')
    
    if not file_id or not filename:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return redirect(url_for('data_processing'))
    
    # Récupérer le DataFrame courant
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'danger')
        return redirect(url_for('data_processing'))
    
    # Récupérer les résultats du clustering de la session
    clustering_result = session.get('clustering_result')
    
    if not clustering_result:
        flash('Aucun résultat de clustering trouvé. Veuillez d\'abord exécuter le clustering.', 'warning')
        return redirect(url_for('clustering'))
    
    try:
        # Format d'exportation
        export_format = request.args.get('format', 'csv')
        
        # Ajouter les clusters au DataFrame
        df_with_clusters = df.copy()
        cluster_column_name = f"cluster_{clustering_result['algorithm']}"
        df_with_clusters[cluster_column_name] = clustering_result['labels']
        
        # Créer un fichier temporaire pour l'exportation
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{export_format}')
        
        if export_format == 'csv':
            df_with_clusters.to_csv(temp_file.name, index=False)
            mime_type = 'text/csv'
        elif export_format == 'xlsx':
            df_with_clusters.to_excel(temp_file.name, index=False)
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            temp_file.close()
            os.unlink(temp_file.name)
            flash(f'Format d\'exportation non pris en charge: {export_format}', 'danger')
            return redirect(url_for('clustering'))
        
        temp_file.close()
        
        # Renvoyer le fichier
        export_filename = f"{os.path.splitext(filename)[0]}_clusters.{export_format}"
        return send_file(temp_file.name, 
                         as_attachment=True, 
                         download_name=export_filename, 
                         mimetype=mime_type)
    
    except Exception as e:
        flash(f'Erreur lors de l\'exportation des clusters: {str(e)}', 'danger')
        return redirect(url_for('clustering'))

@app.route('/history')
def history():
    """Page d'historique des analyses"""
    try:
        # Récupérer les analyses CSV
        csv_analyses = history_manager.get_recent_analyses(20)
        
        # Récupérer les analyses PDF
        pdf_analyses = pdf_history_manager.get_recent_pdf_analyses(20)
        
        return render_template('history.html', csv_analyses=csv_analyses, pdf_analyses=pdf_analyses)
    
    except Exception as e:
        flash(f'Erreur lors de la récupération de l\'historique: {str(e)}', 'danger')
        return render_template('history.html', csv_analyses=[], pdf_analyses=[])


@app.route('/pdf_analysis')
def pdf_analysis():
    """Page d'analyse de documents PDF"""
    return render_template('pdf_analysis.html')

@app.route('/settings')
def settings():
    """Page des paramètres de l'application"""
    return render_template('settings.html')


# API Routes
@app.route('/api/generate_visualization', methods=['POST'])
def api_generate_visualization():
    """API pour générer une visualisation"""
    # Vérifier si des données sont disponibles
    file_id = session.get('file_id')
    
    if not file_id:
        return jsonify({"error": "Aucune donnée disponible"})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        return jsonify({"error": "Erreur lors de la récupération des données"})
    
    # Récupérer les paramètres de la requête
    data = request.json
    chart_type = data.get('chart_type')
    x_var = data.get('x_var')
    y_var = data.get('y_var')
    color_var = data.get('color_var')
    
    # Paramètres supplémentaires
    params = {k: v for k, v in data.items() if k not in ['chart_type', 'x_var', 'y_var', 'color_var']}
    
    try:
        # Utiliser la fonction du module de visualisation
        result = create_visualization(df, chart_type, x_var, y_var, color_var, **params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/elbow_method', methods=['POST'])
def api_elbow_method():
    """API pour calculer les données de la méthode du coude"""
    # Vérifier si des données sont disponibles
    file_id = session.get('file_id')
    
    if not file_id:
        return jsonify({"error": "Aucune donnée disponible", "success": False})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        return jsonify({"error": "Erreur lors de la récupération des données", "success": False})
    
    # Récupérer les colonnes sélectionnées
    data = request.json
    columns = data.get('columns', [])
    
    try:
        # Initialiser le processeur de clustering
        clustering_processor = ClusteringProcessor()
        
        # Calculer les données de la méthode du coude
        result = clustering_processor.get_elbow_method_data(df, columns)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/column_values', methods=['POST'])
def api_column_values():
    """API pour récupérer les valeurs uniques d'une colonne"""
    # Vérifier si des données sont disponibles
    file_id = session.get('file_id')
    
    if not file_id:
        return jsonify({"success": False, "error": "Aucune donnée disponible", "stats": {}})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        return jsonify({"success": False, "error": "Erreur lors de la récupération des données", "stats": {}})
    
    # Récupérer le nom de la colonne
    data = request.json
    column_name = data.get('column_name')
    
    if not column_name or column_name not in df.columns:
        return jsonify({
            "success": False, 
            "error": f"Colonne '{column_name}' non trouvée", 
            "stats": {"data_type": None, "total_rows": 0, "unique_values": 0, "missing_values": 0}
        })
    
    try:
        # Récupérer les valeurs uniques et leur fréquence
        value_counts = df[column_name].value_counts().reset_index()
        value_counts.columns = ['value', 'count']
        
        # Convertir en liste de dictionnaires
        values = []
        for _, row in value_counts.iterrows():
            # Convertir les valeurs en objets sérialisables
            value = row['value']
            if pd.isna(value):
                value = "null"  # Utiliser une chaîne pour représenter les valeurs nulles
            elif isinstance(value, (np.int64, np.int32)):
                value = int(value)
            elif isinstance(value, (np.float64, np.float32)):
                value = float(value)
            else:
                value = str(value)
                
            values.append({
                "value": value,
                "count": int(row['count'])
            })
        
        # Statistiques sur la colonne
        stats = {
            "total_rows": int(len(df)),
            "unique_values": int(df[column_name].nunique()),
            "missing_values": int(df[column_name].isna().sum()),
            "data_type": str(df[column_name].dtype)
        }
        
        return jsonify({
            "success": True, 
            "values": values, 
            "stats": stats
        })
    except Exception as e:
        import traceback
        logger.error(f"Erreur lors de la récupération des valeurs: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False, 
            "error": str(e),
            "stats": {"data_type": None, "total_rows": 0, "unique_values": 0, "missing_values": 0}
        })

@app.route('/api/analyze_clusters_with_ai', methods=['POST'])
def api_analyze_clusters_with_ai():
    """API pour analyser les clusters avec l'IA via Ollama"""
    import logging
    import traceback
    import pickle
    
    logger = logging.getLogger(__name__)
    logger.info("Début de l'analyse des clusters avec IA")
    
    # Récupérer l'ID du clustering
    clustering_id = session.get('clustering_id')
    
    if not clustering_id:
        logger.warning("Aucun ID de clustering trouvé dans la session")
        return jsonify({"success": False, "error": "Aucun résultat de clustering trouvé"}), 400
    
    # Chemin du fichier contenant les résultats du clustering
    # Corriger le chemin pour inclure le sous-dossier clustering_results
    clustering_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'clustering_results')
    clustering_file = os.path.join(clustering_folder, f"{clustering_id}.pkl")
    
    logger.info(f"Recherche du fichier de clustering: {clustering_file}")
    
    if not os.path.exists(clustering_file):
        logger.warning(f"Fichier de clustering non trouvé: {clustering_file}")
        return jsonify({"success": False, "error": "Résultats de clustering non disponibles"}), 400
    
    # Charger les résultats du clustering
    try:
        with open(clustering_file, 'rb') as f:
            clustering_result = pickle.load(f)
        
        logger.info(f"Fichier de clustering chargé avec succès: {clustering_id}")
    except Exception as e:
        logger.error(f"Erreur lors du chargement des résultats de clustering: {e}")
        return jsonify({"success": False, "error": f"Erreur lors du chargement des résultats: {str(e)}"}), 500
    
    # Récupérer le contexte utilisateur
    data = request.json or {}
    user_context = data.get('user_context', '')
    logger.info(f"Contexte utilisateur reçu: {user_context[:50]}...")
    
    try:
        # S'assurer que clustering_processor est disponible
        if 'clustering_processor' not in globals():
            from modules.clustering_module import ClusteringProcessor
            global clustering_processor
            clustering_processor = ClusteringProcessor()
            logger.info("Processeur de clustering initialisé")
        
        # Analyser les clusters
        logger.info("Démarrage de l'analyse des clusters avec IA...")
        analysis_result = clustering_processor.analyze_clusters_with_ai(clustering_result, user_context)
        
        if analysis_result.get("success", False):
            logger.info(f"Analyse réussie, {len(analysis_result.get('analysis', ''))} caractères générés")
            # Tronquer pour le log
            analysis_excerpt = analysis_result.get('analysis', '')[:100] + "..." if analysis_result.get('analysis') else ""
            logger.info(f"Extrait: {analysis_excerpt}")
        else:
            logger.warning(f"Échec de l'analyse: {analysis_result.get('error')}")
        
        return jsonify(analysis_result)
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Exception non gérée lors de l'analyse IA: {str(e)}\n{error_trace}")
        return jsonify({
            "success": False, 
            "error": str(e),
            "trace": error_trace
        }), 500

@app.route('/api/dataset_stats')
def api_dataset_stats():
    """API pour obtenir des statistiques sur le dataset"""
    # Vérifier si des données sont disponibles
    file_id = session.get('file_id')
    
    if not file_id:
        return jsonify({"error": "Aucune donnée disponible"})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        return jsonify({"error": "Erreur lors de la récupération des données"})
    
    try:
        # Statistiques générales
        stats = {
            "rows": len(df),
            "columns": len(df.columns),
            "missing_values": int(df.isna().sum().sum()),
            "missing_percentage": float(df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100)
        }
        
        # Statistiques sur les colonnes numériques
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            stats["numeric_stats"] = {
                "count": len(numeric_cols),
                "columns": numeric_cols.tolist()
            }
        
        # Statistiques sur les colonnes catégorielles
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(cat_cols) > 0:
            stats["categorical_stats"] = {
                "count": len(cat_cols),
                "columns": cat_cols.tolist()
            }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)})

# Fonctions utilitaires
def allowed_file(filename, allowed_extensions=None):
    """Vérifie si le fichier a une extension autorisée"""
    if allowed_extensions is None:
        allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions




@app.route('/pdf_analysis_results/<pdf_id>')
def pdf_analysis_results(pdf_id):
    """Page des résultats d'analyse PDF"""
    # Récupérer l'analyse PDF
    analysis = pdf_history_manager.get_pdf_analysis(pdf_id)
    
    if not analysis:
        flash('Analyse PDF non trouvée', 'warning')
        return redirect(url_for('pdf_analysis'))
    
    return render_template('pdf_analysis_results.html', analysis=analysis)


## --------------------------------- CALENDRIER ------------------------------------------------------------
# route pour la page du calendrier
@app.route('/api/calendar_data', methods=['POST'])
def api_calendar_data():
    """API pour obtenir les données du calendrier des achats avec filtres avancés"""
    try:
        # Récupérer les filtres depuis la requête
        data = request.json
        
        # Normaliser les valeurs des filtres
        brand_filter = data.get('brand', 'all')
        date_start = data.get('date_start', None)
        date_end = data.get('date_end', None)
        payment_method = data.get('payment_method', 'all')
        article_filter = data.get('article', 'all')
        
        # Normaliser le genre en minuscules pour éviter les problèmes de casse
        gender = data.get('gender', 'all')
        if gender != 'all':
            gender = gender.lower()
        
        age_range = data.get('age_range', 'all')
        
        # Log détaillé des filtres reçus
        logger.info(f"Filtres reçus: brand={brand_filter}, payment={payment_method}, article={article_filter}, gender={gender}, age={age_range}")
        logger.info(f"Requête complète: {data}")
        
        # Vérifier si on utilise un DataFrame chargé ou la base de données
        file_id = session.get('file_id')
        
        if not file_id:
            # Utiliser la base de données SQLite
            db_path = 'modules/fidelity_db.sqlite'
            
            # Vérifier que la base de données existe
            if not os.path.exists(db_path):
                logger.error(f"Base de données non trouvée: {db_path}")
                return jsonify({
                    'success': False,
                    'error': "Base de données non trouvée"
                })
            
            # Connexion à la base de données
            conn = sqlite3.connect(db_path)
            
            # Construction de la requête SQL de base
            query = """
            SELECT 
                date(t.date_transaction) as date_achat,
                COUNT(*) as nb_achats,
                m.nom as magasin,
                t.type_paiement as moyen_paiement,
                c.genre,
                CAST(strftime('%Y', 'now') - strftime('%Y', c.date_naissance) AS INTEGER) as age
            FROM transactions t
            JOIN points_vente m ON t.magasin_id = m.magasin_id
            JOIN clients c ON t.client_id = c.client_id
            """
            
            # Filtres article (avec jointures)
            if article_filter != 'all':
                query = query.replace("FROM transactions t", """
                FROM transactions t
                JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                JOIN produits p ON dt.produit_id = p.produit_id
                """)
            
            # Conditions WHERE
            conditions = []
            params = []
            
            # Filtre par magasin
            if brand_filter != 'all':
                conditions.append("m.nom = ?")
                params.append(brand_filter)
            
            # Filtre par moyen de paiement
            if payment_method != 'all':
                conditions.append("t.type_paiement = ?")
                params.append(payment_method)
            
            # Filtre par article
            if article_filter != 'all':
                conditions.append("p.nom LIKE ?")  # Recherche flexible avec LIKE
                params.append(f"%{article_filter}%")
                logger.info(f"Filtrage par article: {article_filter}")
            
            # Filtre par genre - insensible à la casse
            if gender != 'all':
                conditions.append("LOWER(c.genre) = ?")  # Conversion en minuscules pour comparaison insensible à la casse
                params.append(gender.lower())
                logger.info(f"Filtrage par genre: {gender}")
            
            # Filtre par tranche d'âge
            if age_range != 'all':
                logger.info(f"Filtrage par tranche d'âge: {age_range}")
                if age_range == "0-18":
                    conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) < 19")
                elif age_range == "19-25":
                    conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 19 AND 25")
                elif age_range == "26-35":
                    conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 26 AND 35")
                elif age_range == "36-50":
                    conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 36 AND 50")
                elif age_range == "51+":
                    conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) > 50")
            
            # Filtre par période
            if date_start:
                conditions.append("date(t.date_transaction) >= ?")
                params.append(date_start)
            if date_end:
                conditions.append("date(t.date_transaction) <= ?")
                params.append(date_end)
            
            # Ajouter les conditions à la requête
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # Grouper par date, magasin et moyen de paiement (sans inclure genre et âge)
            query += " GROUP BY date_achat, magasin, moyen_paiement"
            
            # Exécuter la requête
            logger.info(f"Requête SQL: {query}")
            logger.info(f"Paramètres: {params}")
            
            df = pd.read_sql_query(query, conn, params=params)
            
            # Récupérer les listes de valeurs pour les filtres
            # Magasins
            brands_query = "SELECT DISTINCT nom FROM points_vente ORDER BY nom"
            brands_df = pd.read_sql_query(brands_query, conn)
            brands = brands_df['nom'].tolist()
            
            # Moyens de paiement
            payment_query = "SELECT DISTINCT type_paiement FROM transactions WHERE type_paiement IS NOT NULL ORDER BY type_paiement"
            payment_df = pd.read_sql_query(payment_query, conn)
            payment_methods = payment_df['type_paiement'].tolist()
            
            # Articles (produits)
            products_query = """
            SELECT p.nom, COUNT(*) as count
            FROM details_transactions dt
            JOIN produits p ON dt.produit_id = p.produit_id
            GROUP BY p.nom
            ORDER BY count DESC
            LIMIT 30
            """
            products_df = pd.read_sql_query(products_query, conn)
            articles = products_df['nom'].tolist()
            
            # Genres disponibles
            genders_query = "SELECT DISTINCT genre FROM clients WHERE genre IS NOT NULL"
            genders_df = pd.read_sql_query(genders_query, conn)
            available_genders = genders_df['genre'].tolist()
            
            conn.close()
            
            # Vérifier que des données ont été récupérées
            if df.empty:
                return jsonify({
                    'success': True,
                    'dates': [],
                    'values': [],
                    'brands': brands,
                    'paymentInfo': [],
                    'magasins': [],
                    'payment_methods': payment_methods,
                    'articles': articles,
                    'genders': ['homme', 'femme'],
                    'age_ranges': ['0-18', '19-25', '26-35', '36-50', '51+']
                })
                
            # Préparer les données détaillées
            date_col = 'date_achat'
            value_col = 'nb_achats'
            payment_col = 'moyen_paiement'
            store_col = 'magasin'
            
        else:
            # Utiliser le DataFrame chargé en session
            df_original = transformation_manager.get_current_dataframe(file_id)
            # Faire une copie pour ne pas modifier l'original
            df = df_original.copy()
            
            # Log détaillé des colonnes disponibles
            logger.info(f"Colonnes disponibles dans le DataFrame: {df.columns.tolist()}")
            
            # Vérification de présence des colonnes de genre et âge
            if 'genre' in df.columns:
                unique_genres = df['genre'].dropna().unique()
                logger.info(f"Valeurs uniques de genre: {unique_genres}")
            else:
                logger.warning("Colonne 'genre' non trouvée dans le DataFrame")
                
            if 'age' in df.columns:
                logger.info(f"Statistiques d'âge: min={df['age'].min()}, max={df['age'].max()}, moyenne={df['age'].mean()}")
            else:
                logger.warning("Colonne 'age' non trouvée dans le DataFrame")
            
            # Déterminer les colonnes à utiliser en fonction de ce qui est disponible
            # Colonnes de date possibles
            date_columns = ['date_transaction', 'date_achat', 'date', 'date_operation']
            date_col = None
            for col in date_columns:
                if col in df.columns:
                    date_col = col
                    break
            
            if not date_col:
                return jsonify({
                    'success': False,
                    'error': f"Aucune colonne de date trouvée. Colonnes disponibles: {df.columns.tolist()}"
                })
            
            # Convertir la colonne de date en datetime
            try:
                df[date_col] = pd.to_datetime(df[date_col])
            except Exception as e:
                logger.error(f"Erreur de conversion de la date: {e}")
                try:
                    df[date_col] = pd.to_datetime(df[date_col].astype(str))
                except:
                    return jsonify({
                        'success': False,
                        'error': f"Impossible de convertir la colonne {date_col} en date"
                    })
            
            # Filtre par période
            if date_start:
                df = df[df[date_col] >= pd.to_datetime(date_start)]
            if date_end:
                df = df[df[date_col] <= pd.to_datetime(date_end)]
            
            # Appliquer la conversion à date (sans heure)
            df[date_col] = df[date_col].dt.date
            
            # Identifier les colonnes possibles
            store_columns = ['magasin', 'nom_magasin', 'enseigne', 'email']
            payment_columns = ['moyen_paiement', 'type_paiement', 'payment_method']
            gender_columns = ['genre', 'gender', 'sexe']
            age_columns = ['age', 'age_client']
            article_columns = ['nom_article', 'article', 'produit', 'nom_produit', 'nom']
            
            # Trouver les colonnes disponibles
            store_col = None
            for col in store_columns:
                if col in df.columns:
                    store_col = col
                    break
            
            payment_col = None  
            for col in payment_columns:
                if col in df.columns:
                    payment_col = col
                    break
            
            gender_col = None
            for col in gender_columns:
                if col in df.columns:
                    gender_col = col
                    break
            
            age_col = None
            for col in age_columns:
                if col in df.columns:
                    age_col = col
                    break
            
            article_col = None
            for col in article_columns:
                if col in df.columns:
                    article_col = col
                    break
            
            logger.info(f"Colonnes identifiées: date={date_col}, store={store_col}, payment={payment_col}, gender={gender_col}, age={age_col}, article={article_col}")
            
            # Appliquer les filtres
            # Par magasin
            if brand_filter != 'all' and store_col in df.columns:
                df = df[df[store_col] == brand_filter]
                logger.info(f"Après filtre magasin: {len(df)} lignes")
            
            # Par moyen de paiement
            if payment_method != 'all' and payment_col in df.columns:
                df = df[df[payment_col] == payment_method]
                logger.info(f"Après filtre paiement: {len(df)} lignes")
            
            # Par article
            if article_filter != 'all' and article_col in df.columns:
                df = df[df[article_col].str.contains(article_filter, case=False, na=False)]
                logger.info(f"Après filtre article: {len(df)} lignes")
            
            # Par genre - avec plusieurs techniques de correspondance
            if gender != 'all' and gender_col in df.columns:
                # Approche 1: Correspondance exacte
                mask1 = df[gender_col] == gender
                # Approche 2: Correspondance insensible à la casse
                mask2 = df[gender_col].str.lower() == gender.lower()
                # Approche 3: Correspondance partielle
                mask3 = df[gender_col].str.contains(gender, case=False, na=False)
                
                # Combiner les approches avec OU logique
                combined_mask = mask1 | mask2 | mask3
                
                # Filtrer
                df_filtered = df[combined_mask]
                
                if not df_filtered.empty:
                    df = df_filtered
                    logger.info(f"Filtrage genre réussi: {len(df)} lignes")
                else:
                    logger.warning(f"Aucune correspondance pour le genre '{gender}'. Valeurs disponibles: {df[gender_col].unique()}")
            
            # Par tranche d'âge
            if age_range != 'all' and age_col in df.columns:
                # Essayer de convertir en numérique s'il ne l'est pas déjà
                if not pd.api.types.is_numeric_dtype(df[age_col]):
                    try:
                        df[age_col] = pd.to_numeric(df[age_col], errors='coerce')
                        logger.info(f"Colonne d'âge '{age_col}' convertie en numérique")
                    except Exception as e:
                        logger.error(f"Impossible de convertir la colonne d'âge en numérique: {e}")
                
                # Appliquer le filtre d'âge
                original_count = len(df)
                
                if age_range == "0-18":
                    df = df[df[age_col] < 19]
                elif age_range == "19-25":
                    df = df[(df[age_col] >= 19) & (df[age_col] <= 25)]
                elif age_range == "26-35":
                    df = df[(df[age_col] >= 26) & (df[age_col] <= 35)]
                elif age_range == "36-50":
                    df = df[(df[age_col] >= 36) & (df[age_col] <= 50)]
                elif age_range == "51+":
                    df = df[df[age_col] > 50]
                
                logger.info(f"Filtre âge '{age_range}' appliqué: {len(df)}/{original_count} lignes")
            
            # Vérifier si on a encore des données après filtrage
            if df.empty:
                logger.warning("DataFrame vide après application des filtres")
                
                # Récupérer les articles disponibles du DataFrame original pour le menu déroulant
                articles = []
                if article_col and article_col in df_original.columns:
                    articles = df_original[article_col].dropna().unique().tolist()[:30]
                
                # Récupérer les genres disponibles
                available_genders = []
                if gender_col and gender_col in df_original.columns:
                    available_genders = df_original[gender_col].dropna().unique().tolist()
                else:
                    available_genders = ['homme', 'femme']
                
                return jsonify({
                    'success': True,
                    'dates': [],
                    'values': [],
                    'brands': [brand_filter] if brand_filter != 'all' else ['Tous les magasins'],
                    'paymentInfo': [],
                    'magasins': [],
                    'payment_methods': [payment_method] if payment_method != 'all' else [],
                    'articles': articles,
                    'genders': available_genders,
                    'age_ranges': ['0-18', '19-25', '26-35', '36-50', '51+']
                })
            
            # Grouper par les colonnes disponibles - EXCLURE genre et âge pour permettre le filtrage
            group_columns = [date_col]
            if store_col:
                group_columns.append(store_col)
            if payment_col:
                group_columns.append(payment_col)
            
            # Effectuer le groupement
            try:
                grouped = df.groupby(group_columns).size().reset_index(name='nb_achats')
                df = grouped
                value_col = 'nb_achats'
                logger.info(f"Groupement réussi: {len(df)} lignes de résultat")
            except Exception as e:
                logger.error(f"Erreur lors du groupement: {e}")
                return jsonify({
                    'success': False,
                    'error': f"Erreur lors du groupement des données: {e}"
                })
            
            # Récupérer les valeurs possibles pour les filtres
            brands = df[store_col].unique().tolist() if store_col in df.columns else ['Tous les magasins']
            payment_methods = df[payment_col].unique().tolist() if payment_col in df.columns else []
            
            # Pour les articles, récupérer depuis le DF original pour avoir toutes les options
            articles = []
            if article_col and article_col in df_original.columns:
                articles = df_original[article_col].dropna().unique().tolist()[:30]
            
            # Pour le genre, utiliser les valeurs du DataFrame original
            available_genders = []
            if gender_col and gender_col in df_original.columns:
                available_genders = df_original[gender_col].dropna().unique().tolist()
            else:
                available_genders = ['homme', 'femme']
        
        # Préparer les données pour la réponse JSON
        # Convertir les dates en strings
        if len(df) > 0:  # Vérifier que df n'est pas vide
            if hasattr(df[date_col].iloc[0], 'strftime'):
                dates = [d.strftime('%Y-%m-%d') for d in df[date_col]]
            else:
                dates = [str(d) for d in df[date_col]]
            
            values = df[value_col].tolist()
            
            # Informations supplémentaires si disponibles
            paymentInfo = df[payment_col].tolist() if payment_col in df.columns else [None] * len(dates)
            magasins = df[store_col].tolist() if store_col in df.columns else [None] * len(dates)
            
            # On ne renvoie pas les genres et âges dans ces listes car on a filtré avant
            genders_data = [gender] * len(dates) if gender != 'all' else [None] * len(dates)
            ages_data = [age_range] * len(dates) if age_range != 'all' else [None] * len(dates)
        else:
            dates = []
            values = []
            paymentInfo = []
            magasins = []
            genders_data = []
            ages_data = []
        
        # Ajouter les tranches d'âge standardisées
        age_ranges = ['0-18', '19-25', '26-35', '36-50', '51+']
        
        return jsonify({
            'success': True,
            'dates': dates,
            'values': values,
            'brands': brands,
            'paymentInfo': paymentInfo,
            'magasins': magasins,
            'genders': genders_data,
            'ages': ages_data,
            'payment_methods': payment_methods,
            'articles': articles,
            'available_genders': available_genders,
            'available_age_ranges': age_ranges
        })
    
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des données du calendrier: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/calendar')  # Changez le décorateur si nécessaire
def calendar_view():
    """Page de visualisation des achats en calendrier"""
    # Vérifiez que le fichier est bien chargé
    file_id = session.get('file_id')
    
    if not file_id:
        flash('Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.', 'warning')
        return render_template('calendar_view.html', has_data=False)
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        flash('Erreur lors de la récupération des données. Veuillez recharger le fichier.', 'warning')
        return render_template('calendar_view.html', has_data=False)
    
    return render_template('calendar_view.html', 
                           filename=session.get('filename'),
                           has_data=True)

# ---------------------------------------------------------CLIENT ---------------------------------------------------

@app.route('/api/client_demographics')
def api_client_demographics():
    """API pour récupérer les données démographiques des clients"""
    # Vérifier si des données sont disponibles
    file_id = session.get('file_id')
    
    if not file_id:
        return jsonify({"success": False, "error": "Aucune donnée disponible"})
    
    # Récupérer le DataFrame
    df = transformation_manager.get_current_dataframe(file_id)
    
    if df is None:
        return jsonify({"success": False, "error": "Erreur lors de la récupération des données"})
    
    try:
        demographics_data = {}
        
        # Distribution par genre
        if 'genre' in df.columns:
            gender_counts = df['genre'].value_counts().to_dict()
            # Normaliser les clés en minuscules pour cohérence
            normalized_gender_counts = {}
            for key, value in gender_counts.items():
                if pd.notna(key):
                    normalized_key = key.lower() if isinstance(key, str) else key
                    normalized_gender_counts[normalized_key] = value
            demographics_data['gender_distribution'] = normalized_gender_counts
        
        # Distribution par âge
        if 'age' in df.columns:
            # Définir les tranches d'âge
            age_bins = [0, 18, 25, 35, 50, 100]
            age_labels = ['0-18', '19-25', '26-35', '36-50', '51+']
            
            # Créer une copie pour éviter les avertissements de modification avec pd.cut
            df_age = df.copy()
            
            # Convertir en numérique si pas déjà fait
            if not pd.api.types.is_numeric_dtype(df_age['age']):
                df_age['age'] = pd.to_numeric(df_age['age'], errors='coerce')
            
            # Catégoriser les âges
            df_age['age_group'] = pd.cut(df_age['age'], bins=age_bins, labels=age_labels, right=False)
            
            # Compter les occurrences par tranche d'âge
            age_counts = df_age['age_group'].value_counts().sort_index()
            
            # Formater pour le graphique
            demographics_data['age_distribution'] = {
                'categories': age_counts.index.tolist(),
                'values': age_counts.values.tolist()
            }
        
        # Distribution par segment client
        if 'segment_client' in df.columns:
            segment_counts = df['segment_client'].value_counts().to_dict()
            demographics_data['segment_distribution'] = segment_counts
            
            # Panier moyen par segment
            if 'montant_total' in df.columns:
                avg_basket = df.groupby('segment_client')['montant_total'].mean().round(2)
                
                demographics_data['avg_basket_by_segment'] = {
                    'categories': avg_basket.index.tolist(),
                    'values': avg_basket.values.tolist()
                }
        
        return jsonify({"success": True, **demographics_data})
        
    except Exception as e:
        app.logger.error(f"Erreur lors de la génération des statistiques démographiques: {e}")
        return jsonify({"success": False, "error": str(e)})

#----------------------------------------------------------DASHBOARD--------------------------------------------

@app.route('/dashboard')
def dashboard():
    """Page principale du tableau de bord"""
    
    # Définir des valeurs par défaut pour toutes les variables utilisées dans le template
    template_vars = {
        'magasins': [],
        'payment_methods': [],
        'kpi_ca': 0,
        'kpi_ca_trend': 0,
        'kpi_transactions': 0,
        'kpi_transactions_trend': 0,
        'kpi_panier_moyen': 0,
        'kpi_panier_moyen_trend': 0,
        'kpi_points': 0,
        'kpi_points_trend': 0,
        'recent_transactions': [],
        'error': None
    }
    
    # Vérifier la connexion à la base de données
    db_path = 'modules/fidelity_db.sqlite'
    if not os.path.exists(db_path):
        template_vars['error'] = "Base de données non trouvée."
        return render_template('dashboard.html', **template_vars)
    
    try:
        # Récupérer les options pour les filtres
        conn = get_db_connection(db_path)
        
        # Liste des magasins
        template_vars['magasins'] = conn.execute("""
            SELECT magasin_id, nom FROM points_vente ORDER BY nom
        """).fetchall()
        
        # Liste des moyens de paiement
        template_vars['payment_methods'] = [row[0] for row in conn.execute("""
            SELECT DISTINCT type_paiement FROM transactions 
            WHERE type_paiement IS NOT NULL
            ORDER BY type_paiement
        """).fetchall()]
        
        # Récupérer quelques KPIs de base pour l'affichage initial
        kpi_data = get_basic_kpis(conn)
        
        # Mettre à jour les variables de template avec les KPIs
        template_vars.update({
            'kpi_ca': kpi_data.get('ca', 0),
            'kpi_ca_trend': kpi_data.get('ca_trend', 0),
            'kpi_transactions': kpi_data.get('transactions', 0),
            'kpi_transactions_trend': kpi_data.get('transactions_trend', 0),
            'kpi_panier_moyen': kpi_data.get('panier_moyen', 0),
            'kpi_panier_moyen_trend': kpi_data.get('panier_moyen_trend', 0),
            'kpi_points': kpi_data.get('points', 0),
            'kpi_points_trend': kpi_data.get('points_trend', 0)
        })
        
        # Récupérer les transactions récentes
        recent_transactions = conn.execute("""
            SELECT t.transaction_id as id, t.date_transaction, t.montant_total, 
                   t.numero_facture, pv.nom as magasin, t.type_paiement as moyen_paiement, 
                   t.points_gagnes
            FROM transactions t
            LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
            ORDER BY t.date_transaction DESC
            LIMIT 10
        """).fetchall()
        
        # Convertir les transactions en liste de dictionnaires
        template_vars['recent_transactions'] = [dict(t) for t in recent_transactions]
        
        conn.close()
        
        return render_template('dashboard.html', **template_vars)
    
    except Exception as e:
        template_vars['error'] = f"Erreur de connexion à la base de données: {str(e)}"
        return render_template('dashboard.html', **template_vars)

def get_basic_kpis(conn):
    """Calcul des KPIs de base pour l'affichage initial"""
    
    # Période actuelle: 30 derniers jours
    from datetime import datetime, timedelta
    
    today = datetime.now()
    start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    # Période précédente: 30 jours avant la période actuelle
    prev_start_date = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    prev_end_date = (today - timedelta(days=31)).strftime("%Y-%m-%d")
    
    # Requête pour la période actuelle
    current_data = conn.execute("""
        SELECT 
            SUM(montant_total) as ca_total,
            COUNT(*) as nb_transactions,
            SUM(points_gagnes) as total_points
        FROM transactions
        WHERE date_transaction >= ? AND date_transaction <= ?
    """, (start_date, end_date)).fetchone()
    
    # Requête pour la période précédente
    previous_data = conn.execute("""
        SELECT 
            SUM(montant_total) as ca_total,
            COUNT(*) as nb_transactions,
            SUM(points_gagnes) as total_points
        FROM transactions
        WHERE date_transaction >= ? AND date_transaction <= ?
    """, (prev_start_date, prev_end_date)).fetchone()
    
    # Extraire les données
    ca_current = current_data['ca_total'] or 0
    transactions_current = current_data['nb_transactions'] or 0
    points_current = current_data['total_points'] or 0
    
    ca_previous = previous_data['ca_total'] or 0
    transactions_previous = previous_data['nb_transactions'] or 0
    points_previous = previous_data['total_points'] or 0
    
    # Calculer le panier moyen
    panier_moyen_current = ca_current / transactions_current if transactions_current > 0 else 0
    panier_moyen_previous = ca_previous / transactions_previous if transactions_previous > 0 else 0
    
    # Calculer les tendances (en pourcentage)
    ca_trend = ((ca_current - ca_previous) / ca_previous * 100) if ca_previous > 0 else 0
    transactions_trend = ((transactions_current - transactions_previous) / transactions_previous * 100) if transactions_previous > 0 else 0
    panier_moyen_trend = ((panier_moyen_current - panier_moyen_previous) / panier_moyen_previous * 100) if panier_moyen_previous > 0 else 0
    points_trend = ((points_current - points_previous) / points_previous * 100) if points_previous > 0 else 0
    
    return {
        'ca': ca_current,
        'ca_trend': ca_trend,
        'transactions': transactions_current,
        'transactions_trend': transactions_trend,
        'panier_moyen': panier_moyen_current,
        'panier_moyen_trend': panier_moyen_trend,
        'points': points_current,
        'points_trend': points_trend
    }

@app.route('/api/dashboard_data')
def api_dashboard_data():
    """API pour récupérer les données du tableau de bord avec filtres"""
    try:
        # Récupérer les paramètres de filtrage
        date_range = request.args.get('date_range', '30')
        store = request.args.get('store', 'all')
        payment = request.args.get('payment', 'all')
        segment = request.args.get('segment', 'all')
        
        # Déterminer les dates de début et fin
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        if date_range == 'custom':
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({
                    'success': False,
                    'error': 'Les dates de début et de fin sont requises pour une période personnalisée'
                })
        else:
            # Convertir date_range en nombre de jours
            days = int(date_range)
            start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        
        # Période précédente (pour calculer les tendances)
        days_diff = (datetime.strptime(end_date, "%Y-%m-%d") - 
                    datetime.strptime(start_date, "%Y-%m-%d")).days
        prev_end_date = (datetime.strptime(start_date, "%Y-%m-%d") - 
                         timedelta(days=1)).strftime("%Y-%m-%d")
        prev_start_date = (datetime.strptime(prev_end_date, "%Y-%m-%d") - 
                          timedelta(days=days_diff)).strftime("%Y-%m-%d")
        
        # Connexion à la base de données
        conn = get_db_connection()
        
        # Construire la requête SQL avec les filtres
        params = [start_date, end_date]
        query_filters = "WHERE t.date_transaction >= ? AND t.date_transaction <= ?"
        
        if store != 'all':
            query_filters += " AND t.magasin_id = ?"
            params.append(store)
        
        if payment != 'all':
            query_filters += " AND t.type_paiement = ?"
            params.append(payment)
        
        if segment != 'all':
            query_filters += " AND c.segment = ?"
            params.append(segment)
        
        # Requête pour les KPIs de la période actuelle
        current_kpis_query = f"""
            SELECT 
                SUM(t.montant_total) as ca_total,
                COUNT(*) as nb_transactions,
                SUM(t.points_gagnes) as total_points
            FROM transactions t
            LEFT JOIN clients c ON t.client_id = c.client_id
            {query_filters}
        """
        
        # Requête pour les KPIs de la période précédente
        prev_params = [prev_start_date, prev_end_date]
        prev_params.extend(params[2:])  # Ajouter les mêmes filtres que la période actuelle
        
        prev_kpis_query = f"""
            SELECT 
                SUM(t.montant_total) as ca_total,
                COUNT(*) as nb_transactions,
                SUM(t.points_gagnes) as total_points
            FROM transactions t
            LEFT JOIN clients c ON t.client_id = c.client_id
            {query_filters.replace('?', '?', 2)}
        """
        
        # Exécuter les requêtes pour les KPIs
        current_kpis = conn.execute(current_kpis_query, params).fetchone()
        prev_kpis = conn.execute(prev_kpis_query, prev_params).fetchone()
        
        # Calculer les KPIs et les tendances
        ca_current = current_kpis['ca_total'] or 0
        transactions_current = current_kpis['nb_transactions'] or 0
        points_current = current_kpis['total_points'] or 0
        
        ca_previous = prev_kpis['ca_total'] or 0
        transactions_previous = prev_kpis['nb_transactions'] or 0
        points_previous = prev_kpis['total_points'] or 0
        
        # Calculer le panier moyen
        panier_moyen_current = ca_current / transactions_current if transactions_current > 0 else 0
        panier_moyen_previous = ca_previous / transactions_previous if transactions_previous > 0 else 0
        
        # Calculer les tendances (en pourcentage)
        ca_trend = ((ca_current - ca_previous) / ca_previous * 100) if ca_previous > 0 else 0
        transactions_trend = ((transactions_current - transactions_previous) / transactions_previous * 100) if transactions_previous > 0 else 0
        panier_moyen_trend = ((panier_moyen_current - panier_moyen_previous) / panier_moyen_previous * 100) if panier_moyen_previous > 0 else 0
        points_trend = ((points_current - points_previous) / points_previous * 100) if points_previous > 0 else 0
        
        # Récupérer les données pour les graphiques
        charts_data = get_charts_data(conn, query_filters, params, start_date, end_date)
        
        # Récupérer les transactions récentes avec les filtres appliqués
        recent_transactions_query = f"""
            SELECT t.transaction_id as id, t.date_transaction, t.montant_total, 
                   t.numero_facture, pv.nom as magasin, t.type_paiement as moyen_paiement, 
                   t.points_gagnes
            FROM transactions t
            LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
            LEFT JOIN clients c ON t.client_id = c.client_id
            {query_filters}
            ORDER BY t.date_transaction DESC
            LIMIT 10
        """
        
        recent_transactions = conn.execute(recent_transactions_query, params).fetchall()
        recent_transactions = [dict(t) for t in recent_transactions]
        
        conn.close()
        
        # Construire la réponse JSON
        return jsonify({
            'success': True,
            'kpis': {
                'ca': ca_current,
                'ca_trend': ca_trend,
                'transactions': transactions_current,
                'transactions_trend': transactions_trend,
                'panier_moyen': panier_moyen_current,
                'panier_moyen_trend': panier_moyen_trend,
                'points': points_current,
                'points_trend': points_trend
            },
            'charts_data': charts_data,
            'recent_transactions': recent_transactions
        })
    
    except Exception as e:
        # Journaliser l'erreur
        app.logger.error(f"Erreur lors de la récupération des données du dashboard: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e)
        })

def get_charts_data(conn, query_filters, params, start_date, end_date):
    """Récupère les données pour les graphiques du tableau de bord"""
    
    # 1. Données pour les graphiques d'évolution des ventes
    daily_sales_query = f"""
        SELECT 
            date(t.date_transaction) as date,
            SUM(t.montant_total) as montant
        FROM transactions t
        LEFT JOIN clients c ON t.client_id = c.client_id
        {query_filters}
        GROUP BY date(t.date_transaction)
        ORDER BY date(t.date_transaction)
    """
    
    daily_sales = conn.execute(daily_sales_query, params).fetchall()
    daily_sales = [dict(row) for row in daily_sales]
    
    # Calculer les données hebdomadaires
    weekly_sales = []
    from datetime import datetime
    
    for row in daily_sales:
        date_obj = datetime.strptime(row['date'], "%Y-%m-%d")
        week_number = date_obj.isocalendar()[1]
        week_year = date_obj.year
        week_key = f"{week_year}-W{week_number:02d}"
        
        # Chercher si cette semaine existe déjà
        week_found = False
        for week in weekly_sales:
            if week['week'] == week_key:
                week['montant'] += row['montant']
                week_found = True
                break
        
        if not week_found:
            weekly_sales.append({
                'week': week_key,
                'montant': row['montant']
            })
    
    # Calculer les données mensuelles
    monthly_sales = []
    for row in daily_sales:
        date_obj = datetime.strptime(row['date'], "%Y-%m-%d")
        month_key = f"{date_obj.year}-{date_obj.month:02d}"
        
        # Chercher si ce mois existe déjà
        month_found = False
        for month in monthly_sales:
            if month['month'] == month_key:
                month['montant'] += row['montant']
                month_found = True
                break
        
        if not month_found:
            monthly_sales.append({
                'month': month_key,
                'montant': row['montant']
            })
    
    # 2. Données pour la répartition par magasin
    store_distribution_query = f"""
        SELECT 
            pv.nom as magasin,
            SUM(t.montant_total) as montant
        FROM transactions t
        LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
        LEFT JOIN clients c ON t.client_id = c.client_id
        {query_filters}
        GROUP BY pv.nom
        ORDER BY montant DESC
    """
    
    store_distribution = conn.execute(store_distribution_query, params).fetchall()
    store_distribution = [dict(row) for row in store_distribution]
    
    # 3. Données pour la répartition par moyen de paiement
    payment_distribution_query = f"""
        SELECT 
            t.type_paiement,
            SUM(t.montant_total) as montant
        FROM transactions t
        LEFT JOIN clients c ON t.client_id = c.client_id
        {query_filters}
        GROUP BY t.type_paiement
        ORDER BY montant DESC
    """
    
    payment_distribution = conn.execute(payment_distribution_query, params).fetchall()
    payment_distribution = [dict(row) for row in payment_distribution]
    
    # 4. Données pour la distribution par heure
    hourly_distribution_query = f"""
        SELECT 
            CAST(strftime('%H', t.date_transaction) AS INTEGER) as hour,
            COUNT(*) as count
        FROM transactions t
        LEFT JOIN clients c ON t.client_id = c.client_id
        {query_filters}
        GROUP BY hour
        ORDER BY hour
    """
    
    hourly_distribution = conn.execute(hourly_distribution_query, params).fetchall()
    hourly_distribution = [dict(row) for row in hourly_distribution]
    
    # Compléter les heures manquantes avec des valeurs nulles
    hourly_data = [0] * 24
    for row in hourly_distribution:
        hour = row['hour']
        if 0 <= hour < 24:
            hourly_data[hour] = row['count']
    
    # 5. Données pour les top produits
    top_products_query = f"""
        SELECT 
            p.nom as product_name,
            SUM(dt.quantite) as quantity
        FROM details_transactions dt
        JOIN transactions t ON dt.transaction_id = t.transaction_id
        JOIN produits p ON dt.produit_id = p.produit_id
        LEFT JOIN clients c ON t.client_id = c.client_id
        {query_filters}
        GROUP BY p.nom
        ORDER BY quantity DESC
        LIMIT 5
    """
    
    top_products = conn.execute(top_products_query, params).fetchall()
    top_products = [dict(row) for row in top_products]
    
    # S'assurer que top_products n'est pas vide pour éviter les erreurs
    if not top_products:
        top_products = [{'product_name': 'Aucun produit', 'quantity': 0}]
    
    # 6. Données pour la satisfaction client (simulées car il n'y a pas de table spécifique)
    # En production, vous utiliseriez les données réelles de la table feedback_clients
    satisfaction_categories = ["Produit", "Prix", "Service", "Livraison", "Application"]
    satisfaction_values = [4.2, 3.8, 4.5, 3.9, 4.1]  # Valeurs simulées
    
    # Valeurs par défaut si les listes sont vides
    if not daily_sales:
        daily_sales = [{'date': start_date, 'montant': 0}]
    
    if not weekly_sales:
        weekly_sales = [{'week': f"{datetime.now().year}-W01", 'montant': 0}]
    
    if not monthly_sales:
        monthly_sales = [{'month': f"{datetime.now().year}-01", 'montant': 0}]
    
    if not store_distribution:
        store_distribution = [{'magasin': 'Aucun magasin', 'montant': 0}]
    
    if not payment_distribution:
        payment_distribution = [{'type_paiement': 'Aucun paiement', 'montant': 0}]
    
    # S'assurer que toutes les listes sont bien définies pour éviter les erreurs dans les graphiques
    labels_stores = [row.get('magasin', 'Inconnu') for row in store_distribution]
    values_stores = [row.get('montant', 0) for row in store_distribution]
    
    labels_payments = [row.get('type_paiement', 'Inconnu') for row in payment_distribution]
    values_payments = [row.get('montant', 0) for row in payment_distribution]
    
    names_products = [row.get('product_name', 'Inconnu') for row in top_products]
    quantities_products = [row.get('quantity', 0) for row in top_products]
    
    # Formatage des données pour les graphiques
    return {
        'sales': {
            'daily': {
                'dates': [row.get('date', start_date) for row in daily_sales],
                'values': [row.get('montant', 0) for row in daily_sales],
                'total': sum(row.get('montant', 0) for row in daily_sales)
            },
            'weekly': {
                'dates': [row.get('week', 'Semaine 1') for row in weekly_sales],
                'values': [row.get('montant', 0) for row in weekly_sales],
                'total': sum(row.get('montant', 0) for row in weekly_sales)
            },
            'monthly': {
                'dates': [row.get('month', 'Mois 1') for row in monthly_sales],
                'values': [row.get('montant', 0) for row in monthly_sales],
                'total': sum(row.get('montant', 0) for row in monthly_sales)
            }
        },
        'distribution': {
            'stores': {
                'labels': labels_stores,
                'values': values_stores
            },
            'payments': {
                'labels': labels_payments,
                'values': values_payments
            }
        },
        'hourly': {
            'values': hourly_data
        },
        'top_products': {
            'names': names_products,
            'quantities': quantities_products
        },
        'satisfaction': {
            'categories': satisfaction_categories,
            'values': satisfaction_values
        }
    }

@app.route('/api/export_dashboard')
def api_export_dashboard():
    """API pour exporter les données du tableau de bord avec option d'inclusion des données démographiques"""
    try:
        import io
        from datetime import datetime
        
        # Récupérer les paramètres
        export_format = request.args.get('format', 'csv')
        data_type = request.args.get('data_type', 'dashboard')
        
        # Nouvelle option pour inclure les données démographiques
        include_demographics = request.args.get('include_demographics') == 'true'
        
        # Récupérer les paramètres de filtrage
        date_range = request.args.get('date_range', '30')
        store = request.args.get('store', 'all')
        payment = request.args.get('payment', 'all')
        segment = request.args.get('segment', 'all')
        
        # Déterminer les dates de début et fin
        today = datetime.now()
        
        if date_range == 'custom':
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({
                    'success': False,
                    'error': 'Les dates de début et de fin sont requises pour une période personnalisée'
                })
        else:
            # Convertir date_range en nombre de jours
            from datetime import timedelta
            days = int(date_range)
            start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        
        # Connexion à la base de données
        conn = get_db_connection()
        
        # Construire la requête SQL avec les filtres
        params = [start_date, end_date]
        query_filters = "WHERE t.date_transaction >= ? AND t.date_transaction <= ?"
        
        if store != 'all':
            query_filters += " AND t.magasin_id = ?"
            params.append(store)
        
        if payment != 'all':
            query_filters += " AND t.type_paiement = ?"
            params.append(payment)
        
        if segment != 'all':
            query_filters += " AND c.segment = ?"
            params.append(segment)
        
        # Récupérer les données démographiques si demandé
        demographics_data = None
        if include_demographics:
            # Récupérer les données démographiques de la base de données
            # Distribution par genre
            gender_query = f"""
                SELECT c.genre, COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.genre IS NOT NULL
                GROUP BY c.genre
            """
            
            gender_data = conn.execute(gender_query, params).fetchall()
            gender_distribution = {row['genre']: row['count'] for row in gender_data}
            
            # Distribution par âge
            age_query = f"""
                SELECT 
                    CASE 
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) < 19 THEN '0-18'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 19 AND 25 THEN '19-25'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 26 AND 35 THEN '26-35'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 36 AND 50 THEN '36-50'
                        ELSE '51+'
                    END as age_group,
                    COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.date_naissance IS NOT NULL
                GROUP BY age_group
            """
            
            age_data = conn.execute(age_query, params).fetchall()
            
            # Distribution par segment client
            segment_query = f"""
                SELECT c.segment, COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.segment IS NOT NULL
                GROUP BY c.segment
            """
            
            segment_data = conn.execute(segment_query, params).fetchall()
            segment_distribution = {row['segment']: row['count'] for row in segment_data}
            
            # Panier moyen par segment
            avg_basket_query = f"""
                SELECT c.segment, AVG(t.montant_total) as avg_basket
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.segment IS NOT NULL
                GROUP BY c.segment
            """
            
            avg_basket_data = conn.execute(avg_basket_query, params).fetchall()
            
            # Organiser les données démographiques
            demographics_data = {
                'gender_distribution': gender_distribution,
                'age_distribution': {
                    'categories': [row['age_group'] for row in age_data],
                    'values': [row['count'] for row in age_data]
                },
                'segment_distribution': segment_distribution,
                'avg_basket_by_segment': {
                    'categories': [row['segment'] for row in avg_basket_data],
                    'values': [row['avg_basket'] for row in avg_basket_data]
                }
            }
        
        # Générer le contenu selon le type de données
        if data_type == 'transactions':
            # Exporter toutes les transactions
            transactions_query = f"""
                SELECT 
                    t.transaction_id as id,
                    t.date_transaction,
                    t.montant_total,
                    t.numero_facture,
                    pv.nom as magasin,
                    t.type_paiement as moyen_paiement,
                    t.canal_vente,
                    t.points_gagnes
                FROM transactions t
                LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
                LEFT JOIN clients c ON t.client_id = c.client_id
                {query_filters}
                ORDER BY t.date_transaction DESC
            """
            
            transactions = conn.execute(transactions_query, params).fetchall()
            df = pd.DataFrame([dict(t) for t in transactions])
            
            # Si on doit inclure les données démographiques, fusionner avec les données clientes
            if include_demographics and not df.empty:
                # Récupérer les infos démographiques par transaction
                demog_query = f"""
                    SELECT 
                        t.transaction_id as id,
                        c.genre,
                        (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) as age,
                        c.segment as segment_client
                    FROM transactions t
                    JOIN clients c ON t.client_id = c.client_id
                    {query_filters}
                """
                
                demog_data = conn.execute(demog_query, params).fetchall()
                demog_df = pd.DataFrame([dict(d) for d in demog_data])
                
                # Fusionner avec le DataFrame principal
                if not demog_df.empty:
                    df = pd.merge(df, demog_df, on='id', how='left')
            
        elif data_type == 'dashboard':
            # Exporter un résumé du tableau de bord
            # KPIs
            kpi_query = f"""
                SELECT 
                    SUM(t.montant_total) as ca_total,
                    COUNT(*) as nb_transactions,
                    SUM(t.points_gagnes) as total_points
                FROM transactions t
                LEFT JOIN clients c ON t.client_id = c.client_id
                {query_filters}
            """
            
            kpi_data = conn.execute(kpi_query, params).fetchone()
            
            # Ventes par magasin
            store_query = f"""
                SELECT 
                    pv.nom as magasin,
                    SUM(t.montant_total) as montant
                FROM transactions t
                LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
                LEFT JOIN clients c ON t.client_id = c.client_id
                {query_filters}
                GROUP BY pv.nom
                ORDER BY montant DESC
            """
            
            store_data = conn.execute(store_query, params).fetchall()
            
            # Ventes par moyen de paiement
            payment_query = f"""
                SELECT 
                    t.type_paiement,
                    SUM(t.montant_total) as montant
                FROM transactions t
                LEFT JOIN clients c ON t.client_id = c.client_id
                {query_filters}
                GROUP BY t.type_paiement
                ORDER BY montant DESC
            """
            
            payment_data = conn.execute(payment_query, params).fetchall()
            
            # Ventes par canal
            channel_query = f"""
                SELECT 
                    t.canal_vente,
                    SUM(t.montant_total) as montant
                FROM transactions t
                LEFT JOIN clients c ON t.client_id = c.client_id
                {query_filters}
                GROUP BY t.canal_vente
                ORDER BY montant DESC
            """
            
            channel_data = conn.execute(channel_query, params).fetchall()
            
            # Créer un DataFrame pour le résumé
            summary = {
                'Métrique': ['Période', 'Chiffre d\'affaires', 'Nombre de transactions', 'Panier moyen', 'Points de fidélité'],
                'Valeur': [
                    f"{start_date} au {end_date}",
                    f"{kpi_data['ca_total'] or 0:.2f} €",
                    kpi_data['nb_transactions'] or 0,
                    f"{(kpi_data['ca_total'] / kpi_data['nb_transactions'] if kpi_data['nb_transactions'] > 0 else 0):.2f} €",
                    kpi_data['total_points'] or 0
                ]
            }
            
            # Ajouter les distributions
            stores_dict = {
                'Magasin': [row['magasin'] for row in store_data],
                'Montant (€)': [row['montant'] for row in store_data]
            }
            
            payments_dict = {
                'Moyen de paiement': [row['type_paiement'] for row in payment_data],
                'Montant (€)': [row['montant'] for row in payment_data]
            }
            
            channels_dict = {
                'Canal de vente': [row['canal_vente'] for row in channel_data],
                'Montant (€)': [row['montant'] for row in channel_data]
            }
            
            # Créer plusieurs DataFrames
            df_summary = pd.DataFrame(summary)
            df_stores = pd.DataFrame(stores_dict)
            df_payments = pd.DataFrame(payments_dict)
            df_channels = pd.DataFrame(channels_dict)
            
            # Ajouter les données démographiques si demandées
            if include_demographics and demographics_data:
                # Créer des DataFrames pour chaque distribution démographique
                df_gender = pd.DataFrame({
                    'Genre': list(demographics_data['gender_distribution'].keys()),
                    'Nombre': list(demographics_data['gender_distribution'].values())
                })
                
                df_age = pd.DataFrame({
                    'Tranche d\'âge': demographics_data['age_distribution']['categories'],
                    'Nombre': demographics_data['age_distribution']['values']
                })
                
                df_segment = pd.DataFrame({
                    'Segment': list(demographics_data['segment_distribution'].keys()),
                    'Nombre': list(demographics_data['segment_distribution'].values())
                })
                
                df_basket = pd.DataFrame({
                    'Segment': demographics_data['avg_basket_by_segment']['categories'],
                    'Panier moyen (€)': demographics_data['avg_basket_by_segment']['values']
                })
            
            # Utiliser un writer Excel pour combiner plusieurs feuilles
            if export_format == 'excel':
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_summary.to_excel(writer, sheet_name='Résumé', index=False)
                    df_stores.to_excel(writer, sheet_name='Par magasin', index=False)
                    df_payments.to_excel(writer, sheet_name='Par moyen de paiement', index=False)
                    df_channels.to_excel(writer, sheet_name='Par canal', index=False)
                    
                    # Ajouter les feuilles démographiques si demandées
                    if include_demographics and demographics_data:
                        df_gender.to_excel(writer, sheet_name='Distribution par genre', index=False)
                        df_age.to_excel(writer, sheet_name='Distribution par âge', index=False)
                        df_segment.to_excel(writer, sheet_name='Distribution par segment', index=False)
                        df_basket.to_excel(writer, sheet_name='Panier moyen par segment', index=False)
                
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    download_name=f'dashboard_export_{today.strftime("%Y%m%d")}.xlsx',
                    as_attachment=True
                )
            
            # Pour CSV ou PDF, utiliser seulement le DataFrame du résumé
            df = df_summary
        
        else:
            return jsonify({
                'success': False,
                'error': f"Type de données non pris en charge: {data_type}"
            })
        
        conn.close()
        
        # Exporter selon le format demandé
        if export_format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False)
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                download_name=f'{data_type}_export_{today.strftime("%Y%m%d")}.csv',
                as_attachment=True
            )
        
        elif export_format == 'excel' and data_type == 'transactions':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Transactions', index=False)
                
                # Ajouter une feuille de données démographiques si demandé
                if include_demographics and demographics_data:
                    # Créer une feuille de synthèse démographique
                    demo_summary = pd.DataFrame({
                        'Catégorie': ['Distribution par genre', 'Distribution par âge', 'Distribution par segment'],
                        'Détails': [
                            ', '.join([f"{k}: {v}" for k, v in demographics_data['gender_distribution'].items()]),
                            ', '.join([f"{k}: {v}" for k, v in zip(
                                demographics_data['age_distribution']['categories'],
                                demographics_data['age_distribution']['values']
                            )]),
                            ', '.join([f"{k}: {v}" for k, v in demographics_data['segment_distribution'].items()])
                        ]
                    })
                    
                    demo_summary.to_excel(writer, sheet_name='Démographie', index=False)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                download_name=f'transactions_export_{today.strftime("%Y%m%d")}.xlsx',
                as_attachment=True
            )
        
        elif export_format == 'pdf':
            # Pour le PDF, nous aurions besoin d'une bibliothèque comme ReportLab ou WeasyPrint
            # C'est plus complexe et nécessiterait plus de code
            # Pour cet exemple, renvoyons une erreur
            return jsonify({
                'success': False,
                'error': "L'exportation en PDF n'est pas encore implémentée"
            })
        
        else:
            return jsonify({
                'success': False,
                'error': f"Format d'exportation non pris en charge: {export_format}"
            })
    
    except Exception as e:
        # Journaliser l'erreur
        app.logger.error(f"Erreur lors de l'exportation des données: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Route pour afficher les détails d'une transaction
@app.route('/transaction/<int:transaction_id>')
def transaction_details(transaction_id):
    """Page de détails d'une transaction spécifique"""
    try:
        # Définir des valeurs par défaut pour toutes les variables utilisées dans le template
        template_vars = {
            'transaction': {
                'id': transaction_id,
                'date_transaction': '',
                'montant_total': 0,
                'montant_ht': 0,
                'tva_montant': 0,
                'numero_facture': '',
                'magasin': '',
                'adresse_magasin': '',
                'ville_magasin': '',
                'code_postal_magasin': '',
                'moyen_paiement': '',
                'canal_vente': '',
                'points_gagnes': 0,
                'points_utilises': 0,
                'client_prenom': '',
                'client_nom': '',
                'client_email': '',
                'niveau_fidelite': ''
            },
            'articles': []
        }
        
        conn = get_db_connection()
        
        # Récupérer les informations de la transaction
        transaction = conn.execute("""
            SELECT 
                t.transaction_id as id,
                t.date_transaction,
                t.montant_total,
                t.montant_ht,
                t.tva_montant,
                t.numero_facture,
                pv.nom as magasin,
                pv.adresse as adresse_magasin,
                pv.ville as ville_magasin,
                pv.code_postal as code_postal_magasin,
                t.type_paiement as moyen_paiement,
                t.canal_vente,
                t.points_gagnes,
                t.points_utilises,
                c.prenom as client_prenom,
                c.nom as client_nom,
                c.email as client_email,
                cf.niveau_fidelite
            FROM transactions t
            LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
            LEFT JOIN clients c ON t.client_id = c.client_id
            LEFT JOIN cartes_fidelite cf ON t.carte_id = cf.carte_id
            WHERE t.transaction_id = ?
        """, (transaction_id,)).fetchone()
        
        if not transaction:
            return render_template('error.html', message=f"Transaction #{transaction_id} non trouvée")
        
        # Récupérer les détails des articles
        articles = conn.execute("""
            SELECT 
                dt.quantite,
                dt.prix_unitaire,
                dt.remise_pourcentage,
                dt.remise_montant,
                dt.montant_ligne,
                p.nom as produit_nom,
                p.reference as produit_reference,
                cp.nom as categorie
            FROM details_transactions dt
            JOIN produits p ON dt.produit_id = p.produit_id
            LEFT JOIN categories_produits cp ON p.categorie_id = cp.categorie_id
            WHERE dt.transaction_id = ?
            ORDER BY dt.montant_ligne DESC
        """, (transaction_id,)).fetchall()
        
        conn.close()
        
        # Convertir les objets Row en dictionnaires
        template_vars['transaction'] = dict(transaction)
        template_vars['articles'] = [dict(article) for article in articles]
        
        return render_template('transaction_details.html', **template_vars)
    
    except Exception as e:
        return render_template('error.html', message=f"Erreur: {str(e)}")
    
#-----------------------------------------EXPORT DASHBOARD PDF ----------------------------------------------------
@app.route('/api/export_dashboard_pdf')
def api_export_dashboard_pdf():
    """API pour exporter les données du tableau de bord en PDF avec option pour données démographiques"""
    try:
        # Récupérer les paramètres de filtrage
        date_range = request.args.get('date_range', '30')
        store = request.args.get('store', 'all')
        payment = request.args.get('payment', 'all')
        segment = request.args.get('segment', 'all')
        
        # Nouvelle option pour inclure les données démographiques
        include_demographics = request.args.get('include_demographics') == 'true'
        
        # Déterminer les dates de début et fin
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        if date_range == 'custom':
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({
                    'success': False,
                    'error': 'Les dates de début et de fin sont requises pour une période personnalisée'
                })
        else:
            # Convertir date_range en nombre de jours
            days = int(date_range)
            start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        
        # Connexion à la base de données
        conn = get_db_connection()
        
        # Construire la requête SQL avec les filtres
        params = [start_date, end_date]
        query_filters = "WHERE t.date_transaction >= ? AND t.date_transaction <= ?"
        
        if store != 'all':
            query_filters += " AND t.magasin_id = ?"
            params.append(store)
        
        if payment != 'all':
            query_filters += " AND t.type_paiement = ?"
            params.append(payment)
        
        if segment != 'all':
            query_filters += " AND c.segment = ?"
            params.append(segment)
        
        # Récupérer les KPIs
        kpi_query = f"""
            SELECT 
                SUM(t.montant_total) as ca_total,
                COUNT(*) as nb_transactions,
                SUM(t.points_gagnes) as total_points
            FROM transactions t
            LEFT JOIN clients c ON t.client_id = c.client_id
            {query_filters}
        """
        
        kpi_data = conn.execute(kpi_query, params).fetchone()
        
        # Calculer le panier moyen
        transactions_count = kpi_data['nb_transactions'] or 0
        ca_total = kpi_data['ca_total'] or 0
        panier_moyen = ca_total / transactions_count if transactions_count > 0 else 0
        
        # Récupérer les données démographiques si demandé
        demographics_data = None
        if include_demographics:
            # Distribution par genre
            gender_query = f"""
                SELECT c.genre, COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.genre IS NOT NULL
                GROUP BY c.genre
            """
            
            gender_data = conn.execute(gender_query, params).fetchall()
            gender_distribution = {row['genre']: row['count'] for row in gender_data}
            
            # Distribution par âge
            age_query = f"""
                SELECT 
                    CASE 
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) < 19 THEN '0-18'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 19 AND 25 THEN '19-25'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 26 AND 35 THEN '26-35'
                        WHEN (strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 36 AND 50 THEN '36-50'
                        ELSE '51+'
                    END as age_group,
                    COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.date_naissance IS NOT NULL
                GROUP BY age_group
            """
            
            age_data = conn.execute(age_query, params).fetchall()
            age_distribution = {row['age_group']: row['count'] for row in age_data}
            
            # Distribution par segment client
            segment_query = f"""
                SELECT c.segment, COUNT(*) as count
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.segment IS NOT NULL
                GROUP BY c.segment
            """
            
            segment_data = conn.execute(segment_query, params).fetchall()
            segment_distribution = {row['segment']: row['count'] for row in segment_data}
            
            # Panier moyen par segment
            avg_basket_query = f"""
                SELECT c.segment, AVG(t.montant_total) as avg_basket
                FROM clients c
                JOIN transactions t ON c.client_id = t.client_id
                {query_filters}
                WHERE c.segment IS NOT NULL
                GROUP BY c.segment
            """
            
            avg_basket_data = conn.execute(avg_basket_query, params).fetchall()
            avg_basket_by_segment = {row['segment']: row['avg_basket'] for row in avg_basket_data}
            
            demographics_data = {
                'gender_distribution': gender_distribution,
                'age_distribution': age_distribution,
                'segment_distribution': segment_distribution,
                'avg_basket_by_segment': avg_basket_by_segment
            }
        
        # Récupérer les transactions récentes
        recent_transactions_query = f"""
            SELECT t.transaction_id as id, t.date_transaction, t.montant_total, 
                   t.numero_facture, pv.nom as magasin, t.type_paiement as moyen_paiement, 
                   t.points_gagnes
            FROM transactions t
            LEFT JOIN points_vente pv ON t.magasin_id = pv.magasin_id
            LEFT JOIN clients c ON t.client_id = c.client_id
            {query_filters}
            ORDER BY t.date_transaction DESC
            LIMIT 10
        """
        
        recent_transactions = conn.execute(recent_transactions_query, params).fetchall()
        recent_transactions = [dict(t) for t in recent_transactions]
        
        # Récupération des données pour les graphiques
        charts_data = get_charts_data(conn, query_filters, params, start_date, end_date)
        
        # Fermer la connexion
        conn.close()
        
        # Créer un dictionnaire avec toutes les données pour le template
        template_data = {
            'title': 'Tableau de bord - Rapport PDF',
            'date_generation': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'period': f"{start_date} au {end_date}",
            'kpis': {
                'ca_total': ca_total,
                'transactions_count': transactions_count,
                'panier_moyen': panier_moyen,
                'points_total': kpi_data['total_points'] or 0
            },
            'filter_info': {
                'store': store,
                'payment': payment,
                'segment': segment
            },
            'recent_transactions': recent_transactions,
            'charts_data': charts_data,
            # Ajouter les données démographiques si demandées
            'include_demographics': include_demographics,
            'demographics_data': demographics_data
        }
        
        # Rendre le template HTML pour le PDF
        html_string = render_template('pdf_report.html', **template_data)
        
        # Configurer WeasyPrint
        font_config = FontConfiguration()
        html = HTML(string=html_string)
        
        # Créer un fichier temporaire pour le PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            html.write_pdf(
                target=tmp.name,
                font_config=font_config,
                # Vous pouvez ajouter des styles CSS personnalisés ici
                stylesheets=[CSS(string='@page { size: A4; margin: 1cm }')]
            )
            tmp_path = tmp.name
        
        # Lire le fichier PDF
        with open(tmp_path, 'rb') as f:
            pdf_data = f.read()
        
        # Supprimer le fichier temporaire
        os.unlink(tmp_path)
        
        # Créer une réponse avec le PDF
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=dashboard_report_{today.strftime("%Y%m%d")}.pdf'
        
        return response
        
    except Exception as e:
        # Journaliser l'erreur
        app.logger.error(f"Erreur lors de l'exportation en PDF: {e}")
    
#-----------------------------------------------------------------CARTOGRAPHIE--------------------------------------------------------------


@app.route('/maps')
def maps_view():
    """Page de visualisation cartographique"""
    # Récupérer des métadonnées pour les filtres
    conn = get_db_connection()
    
    # Récupérer les villes disponibles
    villes = conn.execute("""
        SELECT DISTINCT ville 
        FROM points_vente 
        WHERE ville IS NOT NULL 
        ORDER BY ville
    """).fetchall()
    
    # Récupérer les types de points de vente
    types_magasin = conn.execute("""
        SELECT DISTINCT type 
        FROM points_vente 
        WHERE type IS NOT NULL 
        ORDER BY type
    """).fetchall()
    
    conn.close()
    
    return render_template('maps.html', 
                           villes=[v[0] for v in villes],
                           types_magasin=[t[0] for t in types_magasin])

@app.route('/api/generate_sales_map', methods=['POST'])
def api_generate_sales_map():
    """API pour générer une carte des ventes"""
    try:
        # Récupérer les filtres de la requête
        data = request.json or {}
        filters = {
            'date_debut': data.get('date_debut'),
            'date_fin': data.get('date_fin')
        }
        
        # Créer la carte
        map_result = create_sales_map(filters=filters)
        
        return jsonify(map_result)
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la carte : {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/geographical_sales_analysis', methods=['POST'])
def api_geographical_sales_analysis():
    """API pour obtenir une analyse géographique des ventes"""
    try:
        # Récupérer les filtres de la requête
        data = request.json or {}
        filters = {
            'date_debut': data.get('date_debut'),
            'date_fin': data.get('date_fin')
        }
        
        # Obtenir l'analyse géographique
        sales_data = analyze_geographical_sales(filters=filters)
        
        # Générer des insights
        insights = generate_geographical_insights(sales_data)
        
        # Combiner les données
        result = {
            'success': sales_data['success'],
            'stats': sales_data.get('stats', []),
            'total_sales': sales_data.get('total_sales', 0),
            'total_transactions': sales_data.get('total_transactions', 0),
            'insights': insights.get('insights', [])
        }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse géographique : {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/export_map_data', methods=['POST'])
def api_export_map_data():
    """API pour exporter les données de la carte"""
    try:
        # Récupérer les filtres de la requête
        data = request.json or {}
        filters = {
            'date_debut': data.get('date_debut'),
            'date_fin': data.get('date_fin')
        }
        
        # Format d'export
        export_format = data.get('format', 'csv')
        
        # Obtenir l'analyse géographique
        sales_data = analyze_geographical_sales(filters=filters)
        
        if not sales_data['success']:
            return jsonify({
                'success': False,
                'error': 'Impossible de récupérer les données'
            })
        
        # Convertir en DataFrame
        df = pd.DataFrame(sales_data['stats'])
        
        # Exporter selon le format
        if export_format == 'csv':
            # Créer un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                df.to_csv(tmp.name, index=False)
            
            return send_file(
                tmp.name, 
                mimetype='text/csv',
                download_name='geographical_sales_analysis.csv',
                as_attachment=True
            )
        
        elif export_format == 'excel':
            # Créer un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                df.to_excel(tmp.name, index=False)
            
            return send_file(
                tmp.name, 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                download_name='geographical_sales_analysis.xlsx',
                as_attachment=True
            )
        
        else:
            return jsonify({
                'success': False,
                'error': f'Format non supporté : {export_format}'
            })
    
    except Exception as e:
        logger.error(f"Erreur lors de l'export des données de la carte : {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
@app.route('/api/update_store_locations', methods=['POST'])
def api_update_store_locations():
    """
    API pour mettre à jour les localisations des points de vente
    depuis le DataFrame actuel
    """
    # Vérifier si un fichier est chargé
    file_id = session.get('file_id')
    if not file_id:
        return jsonify({
            'success': False,
            'error': "Aucune donnée chargée. Veuillez d'abord charger un fichier."
        })
    
    try:
        # Récupérer le DataFrame courant
        df = transformation_manager.get_current_dataframe(file_id)
        
        if df is None:
            return jsonify({
                'success': False,
                'error': "Impossible de récupérer le DataFrame"
            })
        
        # Vérification initiale
        initial_verification = verify_store_locations()
        
        # Mettre à jour les localisations
        update_result = update_store_locations(df)
        
        # Vérification finale
        final_verification = verify_store_locations()
        
        # Préparer la réponse
        response = {
            'success': update_result['success'],
            'initial_locations': initial_verification['stores_with_location'],
            'final_locations': final_verification['stores_with_location']
        }
        
        # Ajouter les statistiques de mise à jour si disponibles
        if 'stats' in update_result:
            response['update_stats'] = update_result['stats']
        
        # Ajouter un message si l'opération a échoué
        if not update_result['success']:
            response['error'] = update_result.get('message', 'Erreur inconnue')
        
        # Ajouter la transformation à l'historique
        if update_result['success']:
            transformation_manager.add_transformation(file_id, {
                "type": "store_geolocation",
                "params": {
                    "initial_locations": initial_verification['stores_with_location'],
                    "final_locations": final_verification['stores_with_location']
                },
                "timestamp": datetime.now().isoformat()
            })
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des localisations : {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/verify_store_locations', methods=['GET'])
def api_verify_store_locations():
    """
    API pour vérifier les localisations des points de vente
    """
    try:
        # Vérifier les localisations
        verification = verify_store_locations()
        
        return jsonify({
            'success': True,
            'total_stores': verification['total_stores'],
            'stores_with_location': verification['stores_with_location'],
            'stores_without_location': verification['stores_without_location']
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des localisations : {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
@app.route('/api/export_data')
def api_export_data():
    """API pour exporter les données chargées avec option d'inclusion des données démographiques"""
    try:
        import io
        from datetime import datetime
        
        # Vérifier que le fichier est bien chargé
        file_id = session.get('file_id')
        filename = session.get('filename')
        
        if not file_id or not filename:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée chargée. Veuillez d\'abord charger un fichier CSV ou accéder à la base de données.'
            })
        
        # Récupérer le DataFrame actuel
        df = transformation_manager.get_current_dataframe(file_id)
        
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erreur lors de la récupération des données. Veuillez recharger le fichier.'
            })
        
        # Récupérer les paramètres d'export
        export_format = request.args.get('format', 'csv')
        include_demographics = request.args.get('include_demographics') == 'true'
        
        # Si on doit inclure les données démographiques, les récupérer
        demographics_df = None
        if include_demographics:
            # Vérifier quelles colonnes démographiques sont disponibles dans le DataFrame
            demographic_columns = ['genre', 'gender', 'sexe', 'age', 'tranche_age', 'segment', 'segment_client']
            available_columns = [col for col in demographic_columns if col in df.columns]
            
            # Si nous avons des colonnes démographiques, les extraire
            if available_columns:
                # Regrouper par colonnes démographiques pertinentes
                group_cols = available_columns.copy()
                
                # Calculer les agrégations par groupe
                try:
                    # Vérifier si on a une colonne de montant pour calculer le panier moyen
                    if 'montant_total' in df.columns:
                        demographics_df = df.groupby(group_cols, as_index=False).agg({
                            'montant_total': ['count', 'mean']
                        })
                        
                        # Renommer les colonnes
                        demographics_df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in demographics_df.columns]
                        
                        # Renommer les colonnes de manière plus explicite
                        demographics_df = demographics_df.rename(columns={
                            'montant_total_count': 'nombre_transactions',
                            'montant_total_mean': 'panier_moyen'
                        })
                    else:
                        # Simpler sans montant
                        demographics_df = df.groupby(group_cols, as_index=False).size()
                        demographics_df = demographics_df.rename(columns={'size': 'nombre'})
                except Exception as e:
                    app.logger.error(f"Erreur lors de l'agrégation des données démographiques: {e}")
                    demographics_df = None
        
        # Exporter selon le format demandé
        today = datetime.now().strftime("%Y%m%d")
        
        if export_format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False)
            
            # Si on a des données démographiques, les ajouter dans un second CSV
            if include_demographics and demographics_df is not None:
                # Pour CSV, nous ne pouvons pas ajouter un second DataFrame, alors informer l'utilisateur
                flash('Les données démographiques ne peuvent pas être incluses dans un export CSV. Utilisez Excel pour ce type d\'export.', 'warning')
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                download_name=f'{filename}_{today}.csv',
                as_attachment=True
            )
        
        elif export_format == 'excel':
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Données', index=False)
                
                # Ajouter les données démographiques si disponibles
                if include_demographics and demographics_df is not None:
                    demographics_df.to_excel(writer, sheet_name='Démographiques', index=False)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                download_name=f'{filename}_{today}.xlsx',
                as_attachment=True
            )
        
        else:
            return jsonify({
                'success': False,
                'error': f"Format d'exportation non pris en charge: {export_format}"
            })
    
    except Exception as e:
        # Journaliser l'erreur
        app.logger.error(f"Erreur lors de l'exportation des données: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e)
        })
#--------------------------------------------------SCRAP SENTIMENT-----------------------------------------

@app.route('/api/reviews')
def api_reviews():
    """API pour récupérer plus d'avis"""
    # Récupérer les paramètres
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 5))
    product_category = request.args.get('product_category', 'all')
    segment = request.args.get('segment', 'all')
    time_period = request.args.get('time_period', '30d')
    sentiment_filter = request.args.get('sentiment', 'all')
    
    try:
        # Connexion à la base de données
        conn = data_manager._get_connection()
        cursor = conn.cursor()
        
        # Construire la requête avec les filtres
        query = """
            SELECT r.review_id, r.product_name, r.product_category, r.product_brand, 
                   r.reviewer_name, r.review_text, r.review_date, r.rating,
                   sa.sentiment_score, sa.sentiment_label, cs.segment_name as segment
            FROM reviews r
            JOIN sentiment_analysis sa ON r.review_id = sa.review_id
            LEFT JOIN customer_segments cs ON r.reviewer_id = cs.reviewer_id
            WHERE 1=1
        """
        params = []
        
        # Appliquer les filtres
        if product_category != 'all':
            query += " AND r.product_category = ?"
            params.append(product_category)
        
        if segment != 'all':
            query += " AND cs.segment_name = ?"
            params.append(segment)
        
        if sentiment_filter != 'all':
            query += " AND sa.sentiment_label = ?"
            params.append(sentiment_filter)
        
        if time_period != 'all':
            # Calculer la date de début en fonction de la période
            now = datetime.now()
            if time_period == '7d':
                start_date = now - timedelta(days=7)
            elif time_period == '30d':
                start_date = now - timedelta(days=30)
            elif time_period == '6m':
                start_date = now - timedelta(days=180)
            elif time_period == '1y':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
                
            if start_date:
                query += " AND r.review_date >= ?"
                params.append(start_date.strftime('%Y-%m-%d'))
        
        # Ajouter les paramètres de pagination
        query += " ORDER BY r.review_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Exécuter la requête
        cursor.execute(query, params)
        
        # Formater les résultats
        reviews = []
        for row in cursor.fetchall():
            reviews.append({
                'review_id': row[0],
                'product_name': row[1],
                'product_category': row[2],
                'product_brand': row[3],
                'reviewer_name': row[4],
                'review_text': row[5],
                'review_date': row[6],
                'rating': row[7],
                'sentiment_score': row[8],
                'sentiment_label': row[9],
                'segment': row[10] or 'unknown'
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'reviews': reviews,
            'count': len(reviews),
            'offset': offset,
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des avis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/segment_comparison')
def segment_comparison():
    """Page de comparaison des segments clients"""
    try:
        # Récupérer les données des segments
        customer_segmenter = CustomerSegmenter()
        
        # Récupérer les données de base des segments
        conn = data_manager._get_connection()
        cursor = conn.cursor()
        
        # Récupérer la liste des segments
        cursor.execute("""
            SELECT segment_name, COUNT(*) as count
            FROM customer_segments
            GROUP BY segment_name
            ORDER BY count DESC
        """)
        
        segments_raw = cursor.fetchall()
        total_customers = sum(row[1] for row in segments_raw)
        
        # Formater les données des segments
        segments = []
        segment_colors = {
            'tech_enthusiast': '#3b82f6',
            'practical_user': '#9333ea',
            'budget_conscious': '#f59e0b',
            'quality_seeker': '#10b981',
            'brand_loyal': '#ef4444',
            'eco_conscious': '#0ea5e9',
            'unknown': '#6b7280'
        }
        
        for segment_name, count in segments_raw:
            if not segment_name:
                segment_name = 'unknown'
                
            segment_id = segment_name.lower().replace(' ', '_')
            percentage = (count / total_customers * 100) if total_customers > 0 else 0
            
            segments.append({
                'id': segment_id,
                'name': segment_name,
                'count': count,
                'percentage': percentage,
                'color': segment_colors.get(segment_id, '#6b7280'),
                'description': customer_segmenter.get_segment_description(segment_name),
                'features': customer_segmenter.get_segment_features(segment_name),
                'preferences': customer_segmenter.get_segment_preferences(segment_name)
            })
        
        # Récupérer les aspects pour le graphique radar
        cursor.execute("""
            SELECT aspect_name, COUNT(*) as count
            FROM aspect_sentiments
            GROUP BY aspect_name
            ORDER BY count DESC
            LIMIT 10
        """)
        
        radar_aspects = [row[0] for row in cursor.fetchall()]
        
        # Récupérer les marques les plus populaires
        cursor.execute("""
            SELECT product_brand, COUNT(*) as count
            FROM reviews
            GROUP BY product_brand
            ORDER BY count DESC
            LIMIT 10
        """)
        
        top_brands = [row[0] for row in cursor.fetchall()]
        
        # Préparer les données pour les graphiques
        segment_data = {
            'segments': segments,
            'radar_aspects': radar_aspects,
            'top_brands': top_brands
        }
        
        conn.close()
        
        return render_template('segment_comparison.html', 
                              segments=segments,
                              segment_data=segment_data)
    
    except Exception as e:
        logger.error(f"Erreur lors de la préparation des données de segments: {e}")
        return render_template('error.html', message=f"Erreur: {str(e)}")

@app.route('/all_reviews')
def all_reviews():
    """Page affichant tous les avis avec filtres"""
    # Récupérer les paramètres de filtre
    product_category = request.args.get('product_category', 'all')
    segment = request.args.get('segment', 'all')
    time_period = request.args.get('time_period', '30d')
    sentiment_filter = request.args.get('sentiment', 'all')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    try:
        # Connexion à la base de données
        conn = data_manager._get_connection()
        cursor = conn.cursor()
        
        # Construire la requête avec les filtres
        query = """
            SELECT r.review_id, r.product_name, r.product_category, r.product_brand, 
                   r.reviewer_name, r.review_text, r.review_date, r.rating,
                   sa.sentiment_score, sa.sentiment_label, cs.segment_name as segment,
                   COUNT(*) OVER() as total_count
            FROM reviews r
            JOIN sentiment_analysis sa ON r.review_id = sa.review_id
            LEFT JOIN customer_segments cs ON r.reviewer_id = cs.reviewer_id
            WHERE 1=1
        """
        params = []
        count_query = """
            SELECT COUNT(*)
            FROM reviews r
            JOIN sentiment_analysis sa ON r.review_id = sa.review_id
            LEFT JOIN customer_segments cs ON r.reviewer_id = cs.reviewer_id
            WHERE 1=1
        """
        count_params = []
        
        # Appliquer les filtres
        if product_category != 'all':
            filter_sql = " AND r.product_category = ?"
            query += filter_sql
            count_query += filter_sql
            params.append(product_category)
            count_params.append(product_category)
        
        if segment != 'all':
            filter_sql = " AND cs.segment_name = ?"
            query += filter_sql
            count_query += filter_sql
            params.append(segment)
            count_params.append(segment)
        
        if sentiment_filter != 'all':
            filter_sql = " AND sa.sentiment_label = ?"
            query += filter_sql
            count_query += filter_sql
            params.append(sentiment_filter)
            count_params.append(sentiment_filter)
        
        if time_period != 'all':
            # Calculer la date de début en fonction de la période
            now = datetime.now()
            if time_period == '7d':
                start_date = now - timedelta(days=7)
            elif time_period == '30d':
                start_date = now - timedelta(days=30)
            elif time_period == '6m':
                start_date = now - timedelta(days=180)
            elif time_period == '1y':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
                
            if start_date:
                filter_sql = " AND r.review_date >= ?"
                query += filter_sql
                count_query += filter_sql
                params.append(start_date.strftime('%Y-%m-%d'))
                count_params.append(start_date.strftime('%Y-%m-%d'))
        
        # Récupérer le nombre total d'avis
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        # Calculer la pagination
        offset = (page - 1) * per_page
        total_pages = (total_count + per_page - 1) // per_page
        
        # Ajouter les paramètres de pagination
        query += " ORDER BY r.review_date DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        # Exécuter la requête
        cursor.execute(query, params)
        
        # Formater les résultats
        reviews = []
        for row in cursor.fetchall():
            reviews.append({
                'review_id': row[0],
                'product_name': row[1],
                'product_category': row[2],
                'product_brand': row[3],
                'reviewer_name': row[4],
                'review_text': row[5],
                'review_date': row[6],
                'rating': row[7],
                'sentiment_score': row[8],
                'sentiment_label': row[9],
                'segment': row[10] or 'unknown'
            })
        
        # Récupérer les options de filtre
        cursor.execute("SELECT DISTINCT product_category FROM reviews WHERE product_category IS NOT NULL ORDER BY product_category")
        categories = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT segment_name FROM customer_segments WHERE segment_name IS NOT NULL ORDER BY segment_name")
        segments = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return render_template('all_reviews.html',
                              reviews=reviews,
                              categories=categories,
                              segments=segments,
                              current_page=page,
                              total_pages=total_pages,
                              total_count=total_count,
                              per_page=per_page,
                              product_category=product_category,
                              segment=segment,
                              time_period=time_period,
                              sentiment=sentiment_filter)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des avis: {e}")
        return render_template('error.html', message=f"Erreur: {str(e)}")
    
#----------------------------------------------------PROGRAMME FIDELITE --------------------------------------------------------

"""
Routes et contrôleurs pour la gestion du programme de fidélité
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd
import uuid
import logging

# Fonction pour obtenir une connexion à la base de données
def get_db_connection(db_path='C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/fidelity_db.sqlite'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Routes pour le programme de fidélité
@app.route('/loyalty/dashboard')
def loyalty_dashboard():
    """Page principale du programme de fidélité (avec données client anonymisées)"""
    try:
        conn = get_db_connection()
        
        # Récupérer les règles de fidélité actives
        regles = conn.execute('''
            SELECT 
                r.regle_id, r.nom, r.description, r.type_regle, 
                r.condition_valeur, r.periode_jours, r.action_type, 
                r.action_valeur, r.est_active,
                rec.nom as recompense_nom
            FROM regles_fidelite r
            LEFT JOIN recompenses rec ON r.recompense_id = rec.recompense_id
            WHERE r.est_active = 1
            ORDER BY r.priorite DESC
        ''').fetchall()
        
        # Récupérer les statistiques des offres 
        stats_offres = conn.execute('''
            SELECT 
                COUNT(*) as total_offres,
                SUM(CASE WHEN statut = 'generee' THEN 1 ELSE 0 END) as offres_generees,
                SUM(CASE WHEN statut = 'envoyee' THEN 1 ELSE 0 END) as offres_envoyees,
                SUM(CASE WHEN statut = 'utilisee' THEN 1 ELSE 0 END) as offres_utilisees,
                SUM(CASE WHEN statut = 'expiree' THEN 1 ELSE 0 END) as offres_expirees
            FROM offres_client
            WHERE date_generation >= date('now', '-30 days')
        ''').fetchone()
        
        # Récupérer les offres récentes (anonymisées)
        offres_recentes = conn.execute('''
            SELECT 
                oc.offre_id, oc.client_id, oc.date_generation, oc.statut,
                r.nom as regle_nom,
                rec.nom as recompense_nom
            FROM offres_client oc
            JOIN regles_fidelite r ON oc.regle_id = r.regle_id
            LEFT JOIN recompenses rec ON oc.recompense_id = rec.recompense_id
            ORDER BY oc.date_generation DESC
            LIMIT 10
        ''').fetchall()
        
        # Récupérer les historiques d'évaluation récents
        historiques = conn.execute('''
            SELECT 
                h.evaluation_id, h.regle_id, h.date_evaluation,
                h.nombre_clients_evalues, h.nombre_offres_generees,
                r.nom as regle_nom
            FROM historique_evaluations_regles h
            JOIN regles_fidelite r ON h.regle_id = r.regle_id
            ORDER BY h.date_evaluation DESC
            LIMIT 10
        ''').fetchall()
        
        conn.close()
        
        return render_template(
            'loyalty/dashboard.html',
            regles=regles,
            stats_offres=stats_offres,
            offres_recentes=offres_recentes,
            historiques=historiques
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement du tableau de bord de fidélité: {str(e)}', 'danger')
        return render_template('loyalty/dashboard.html')

@app.route('/loyalty/rules')
def loyalty_rules():
    """Liste des règles de fidélité"""
    try:
        conn = get_db_connection()
        
        # Récupérer toutes les règles
        regles = conn.execute('''
            SELECT 
                r.*, rec.nom as recompense_nom
            FROM regles_fidelite r
            LEFT JOIN recompenses rec ON r.recompense_id = rec.recompense_id
            ORDER BY r.priorite DESC, r.est_active DESC
        ''').fetchall()
        
        # Récupérer les récompenses disponibles pour le formulaire
        recompenses = conn.execute('''
            SELECT recompense_id, nom, points_necessaires
            FROM recompenses
            WHERE statut = 'active'
            ORDER BY nom
        ''').fetchall()
        
        conn.close()
        
        return render_template(
            'loyalty/rules.html',
            regles=regles,
            recompenses=recompenses
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement des règles de fidélité: {str(e)}', 'danger')
        return render_template('loyalty/rules.html')

@app.route('/loyalty/rules/add', methods=['GET', 'POST'])
def add_loyalty_rule():
    """Ajouter une nouvelle règle de fidélité"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            nom = request.form.get('nom')
            description = request.form.get('description')
            type_regle = request.form.get('type_regle')
            condition_valeur = request.form.get('condition_valeur')
            periode_jours = request.form.get('periode_jours') or None
            recompense_id = request.form.get('recompense_id') or None
            action_type = request.form.get('action_type')
            action_valeur = request.form.get('action_valeur')
            segments_cibles = request.form.get('segments_cibles') or None
            priorite = request.form.get('priorite') or 0
            est_active = 1 if request.form.get('est_active') else 0
            date_debut = request.form.get('date_debut') or None
            date_fin = request.form.get('date_fin') or None
            
            # Convertir les segments en JSON si nécessaire
            if segments_cibles and segments_cibles != '[]':
                segments_list = [s.strip() for s in segments_cibles.split(',')]
                segments_cibles = json.dumps(segments_list)
            
            conn = get_db_connection()
            
            # Insérer la nouvelle règle
            cursor = conn.execute('''
                INSERT INTO regles_fidelite (
                    nom, description, type_regle, condition_valeur, 
                    periode_jours, recompense_id, action_type, action_valeur,
                    segments_cibles, priorite, est_active, date_debut, date_fin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nom, description, type_regle, condition_valeur,
                periode_jours, recompense_id, action_type, action_valeur,
                segments_cibles, priorite, est_active, date_debut, date_fin
            ))
            
            conn.commit()
            conn.close()
            
            flash('Règle de fidélité ajoutée avec succès !', 'success')
            return redirect(url_for('loyalty_rules'))
            
        except Exception as e:
            flash(f'Erreur lors de l\'ajout de la règle: {str(e)}', 'danger')
            return redirect(url_for('add_loyalty_rule'))
    
    # GET: Afficher le formulaire
    try:
        conn = get_db_connection()
        
        # Récupérer les récompenses disponibles pour le formulaire
        recompenses = conn.execute('''
            SELECT recompense_id, nom, points_necessaires, description
            FROM recompenses
            WHERE statut = 'active'
            ORDER BY nom
        ''').fetchall()
        
        conn.close()
        
        return render_template(
            'loyalty/add_rule.html',
            recompenses=recompenses
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement du formulaire: {str(e)}', 'danger')
        return render_template('loyalty/add_rule.html')

@app.route('/loyalty/rules/edit/<int:regle_id>', methods=['GET', 'POST'])
def edit_loyalty_rule(regle_id):
    """Modifier une règle de fidélité existante"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            nom = request.form.get('nom')
            description = request.form.get('description')
            type_regle = request.form.get('type_regle')
            condition_valeur = request.form.get('condition_valeur')
            periode_jours = request.form.get('periode_jours') or None
            recompense_id = request.form.get('recompense_id') or None
            action_type = request.form.get('action_type')
            action_valeur = request.form.get('action_valeur')
            segments_cibles = request.form.get('segments_cibles') or None
            priorite = request.form.get('priorite') or 0
            est_active = 1 if request.form.get('est_active') else 0
            date_debut = request.form.get('date_debut') or None
            date_fin = request.form.get('date_fin') or None
            
            # Convertir les segments en JSON si nécessaire
            if segments_cibles and segments_cibles != '[]':
                segments_list = [s.strip() for s in segments_cibles.split(',')]
                segments_cibles = json.dumps(segments_list)
            
            conn = get_db_connection()
            
            # Mettre à jour la règle
            conn.execute('''
                UPDATE regles_fidelite SET
                    nom = ?, description = ?, type_regle = ?, condition_valeur = ?,
                    periode_jours = ?, recompense_id = ?, action_type = ?, action_valeur = ?,
                    segments_cibles = ?, priorite = ?, est_active = ?, date_debut = ?, date_fin = ?,
                    modification_date = CURRENT_TIMESTAMP
                WHERE regle_id = ?
            ''', (
                nom, description, type_regle, condition_valeur,
                periode_jours, recompense_id, action_type, action_valeur,
                segments_cibles, priorite, est_active, date_debut, date_fin,
                regle_id
            ))
            
            conn.commit()
            conn.close()
            
            flash('Règle de fidélité mise à jour avec succès !', 'success')
            return redirect(url_for('loyalty_rules'))
            
        except Exception as e:
            flash(f'Erreur lors de la mise à jour de la règle: {str(e)}', 'danger')
            return redirect(url_for('edit_loyalty_rule', regle_id=regle_id))
    
    # GET: Afficher le formulaire avec les données actuelles
    try:
        conn = get_db_connection()
        
        # Récupérer la règle à modifier
        regle = conn.execute('''
            SELECT * FROM regles_fidelite WHERE regle_id = ?
        ''', (regle_id,)).fetchone()
        
        if not regle:
            flash('Règle de fidélité non trouvée', 'warning')
            return redirect(url_for('loyalty_rules'))
        
        # Récupérer les récompenses disponibles pour le formulaire
        recompenses = conn.execute('''
            SELECT recompense_id, nom, points_necessaires, description
            FROM recompenses
            WHERE statut = 'active'
            ORDER BY nom
        ''').fetchall()
        
        conn.close()
        
        # Convertir segments_cibles de JSON à liste pour l'affichage
        segments_cibles = []
        if regle['segments_cibles']:
            try:
                segments_cibles = json.loads(regle['segments_cibles'])
                segments_cibles = ', '.join(segments_cibles)
            except:
                segments_cibles = regle['segments_cibles']
        
        return render_template(
            'loyalty/edit_rule.html',
            regle=regle,
            recompenses=recompenses,
            segments_cibles=segments_cibles
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement de la règle: {str(e)}', 'danger')
        return redirect(url_for('loyalty_rules'))

@app.route('/loyalty/rules/delete/<int:regle_id>', methods=['POST'])
def delete_loyalty_rule(regle_id):
    """Supprimer une règle de fidélité"""
    try:
        conn = get_db_connection()
        
        # Vérifier si la règle existe
        regle = conn.execute('SELECT regle_id FROM regles_fidelite WHERE regle_id = ?', 
                           (regle_id,)).fetchone()
        
        if not regle:
            flash('Règle de fidélité non trouvée', 'warning')
            return redirect(url_for('loyalty_rules'))
        
        # Supprimer la règle
        conn.execute('DELETE FROM regles_fidelite WHERE regle_id = ?', (regle_id,))
        conn.commit()
        conn.close()
        
        flash('Règle de fidélité supprimée avec succès', 'success')
        
    except Exception as e:
        flash(f'Erreur lors de la suppression de la règle: {str(e)}', 'danger')
    
    return redirect(url_for('loyalty_rules'))

@app.route('/loyalty/offers')
def loyalty_offers():
    """Liste des offres générées (avec données client anonymisées)"""
    try:
        # Récupérer les paramètres de filtrage
        status_filter = request.args.get('status', 'all')
        date_from = request.args.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))
        
        conn = get_db_connection()
        
        # Construire la requête avec les filtres
        query = '''
            SELECT 
                oc.offre_id, oc.client_id, oc.date_generation, oc.date_envoi, oc.date_expiration,
                oc.statut, oc.code_unique,
                r.regle_id, r.nom as regle_nom,
                rec.recompense_id, rec.nom as recompense_nom
            FROM offres_client oc
            JOIN regles_fidelite r ON oc.regle_id = r.regle_id
            LEFT JOIN recompenses rec ON oc.recompense_id = rec.recompense_id
            WHERE oc.date_generation BETWEEN ? AND ?
        '''
        
        params = [date_from, date_to]
        
        # Appliquer le filtre de statut
        if status_filter != 'all':
            query += ' AND oc.statut = ?'
            params.append(status_filter)
        
        query += ' ORDER BY oc.date_generation DESC'
        
        offres = conn.execute(query, params).fetchall()
        
        # Récupérer les statistiques par statut
        stats = conn.execute('''
            SELECT 
                statut,
                COUNT(*) as count
            FROM offres_client
            WHERE date_generation BETWEEN ? AND ?
            GROUP BY statut
        ''', [date_from, date_to]).fetchall()
        
        conn.close()
        
        return render_template(
            'loyalty/offers.html',
            offres=offres,
            stats=stats,
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement des offres: {str(e)}', 'danger')
        return render_template('loyalty/offers.html')

@app.route('/loyalty/offers/send', methods=['POST'])
def send_loyalty_offers():
    """Envoyer des offres aux clients (simulé)"""
    try:
        offer_ids = request.form.getlist('offer_ids')
        
        if not offer_ids:
            flash('Aucune offre sélectionnée', 'warning')
            return redirect(url_for('loyalty_offers'))
        
        conn = get_db_connection()
        
        # Mettre à jour les offres sélectionnées
        for offer_id in offer_ids:
            conn.execute('''
                UPDATE offres_client
                SET statut = 'envoyee', 
                    date_envoi = CURRENT_TIMESTAMP,
                    canal_envoi = 'email'
                WHERE offre_id = ? AND statut = 'generee'
            ''', (offer_id,))
        
        conn.commit()
        conn.close()
        
        flash(f'{len(offer_ids)} offres ont été envoyées avec succès', 'success')
        
    except Exception as e:
        flash(f'Erreur lors de l\'envoi des offres: {str(e)}', 'danger')
    
    return redirect(url_for('loyalty_offers'))

@app.route('/loyalty/run-rules', methods=['POST'])
def run_loyalty_rules():
    """Exécution des règles de fidélité avec génération d'offres"""
    try:
        conn = get_db_connection()
        
        # Récupérer les règles actives
        rules = conn.execute('''
            SELECT * FROM regles_fidelite 
            WHERE est_active = 1
            AND (date_debut IS NULL OR date_debut <= date('now'))
            AND (date_fin IS NULL OR date_fin >= date('now'))
            ORDER BY priorite DESC
        ''').fetchall()
        
        total_offers_generated = 0
        
        # Pour chaque règle, exécuter la logique appropriée
        for rule in rules:
            rule_dict = dict(rule)
            offers_for_rule = 0
            eligible_clients = []
            
            # Logique par type de règle
            if rule['type_regle'] == 'nombre_achats':
                # Construire les conditions de période et segment
                period_condition = ""
                if rule['periode_jours']:
                    period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
                
                segment_condition = ""
                if rule['segments_cibles'] and rule['segments_cibles'] != '[]':
                    try:
                        segments = json.loads(rule['segments_cibles'])
                        if segments:
                            segments_str = ','.join([f"'{s.strip()}'" for s in segments])
                            segment_condition = f"AND c.segment IN ({segments_str})"
                    except Exception as e:
                        print(f"Erreur de traitement segments: {e}")
                
                # Requête optimisée pour trouver les clients éligibles en une seule étape
                clients_query = f'''
                    SELECT 
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom,
                        COUNT(DISTINCT t.transaction_id) as nb_achats
                    FROM clients c
                    JOIN transactions t ON c.client_id = t.client_id
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                    {period_condition}
                    {segment_condition}
                    GROUP BY c.client_id
                    HAVING nb_achats >= ?
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (nombre_achats): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'montant_cumule':
                # Construire les conditions de période et segment
                period_condition = ""
                if rule['periode_jours']:
                    period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
                
                segment_condition = ""
                if rule['segments_cibles'] and rule['segments_cibles'] != '[]':
                    try:
                        segments = json.loads(rule['segments_cibles'])
                        if segments:
                            segments_str = ','.join([f"'{s.strip()}'" for s in segments])
                            segment_condition = f"AND c.segment IN ({segments_str})"
                    except Exception as e:
                        print(f"Erreur de traitement segments: {e}")
                
                # Requête optimisée pour trouver les clients éligibles en une seule étape
                clients_query = f'''
                    SELECT 
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom,
                        SUM(t.montant_total) as montant_cumule
                    FROM clients c
                    JOIN transactions t ON c.client_id = t.client_id
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                    {period_condition}
                    {segment_condition}
                    GROUP BY c.client_id
                    HAVING montant_cumule >= ?
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (montant_cumule): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'produit_specifique':
                # Construire les conditions de période et segment
                period_condition = ""
                if rule['periode_jours']:
                    period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
                
                segment_condition = ""
                if rule['segments_cibles'] and rule['segments_cibles'] != '[]':
                    try:
                        segments = json.loads(rule['segments_cibles'])
                        if segments:
                            segments_str = ','.join([f"'{s.strip()}'" for s in segments])
                            segment_condition = f"AND c.segment IN ({segments_str})"
                    except Exception as e:
                        print(f"Erreur de traitement segments: {e}")
                
                # Trouver les clients qui ont acheté le produit spécifique
                clients_query = f'''
                    SELECT DISTINCT
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom
                    FROM clients c
                    JOIN transactions t ON c.client_id = t.client_id
                    JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND dt.produit_id = ?
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                    {period_condition}
                    {segment_condition}
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (produit_specifique): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'categorie_specifique':
                # Construire les conditions de période et segment
                period_condition = ""
                if rule['periode_jours']:
                    period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
                
                segment_condition = ""
                if rule['segments_cibles'] and rule['segments_cibles'] != '[]':
                    try:
                        segments = json.loads(rule['segments_cibles'])
                        if segments:
                            segments_str = ','.join([f"'{s.strip()}'" for s in segments])
                            segment_condition = f"AND c.segment IN ({segments_str})"
                    except Exception as e:
                        print(f"Erreur de traitement segments: {e}")
                
                # Trouver les clients qui ont acheté dans la catégorie spécifiée
                clients_query = f'''
                    SELECT DISTINCT
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom
                    FROM clients c
                    JOIN transactions t ON c.client_id = t.client_id
                    JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
                    JOIN produits p ON dt.produit_id = p.produit_id
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND p.categorie_id = ?
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                    {period_condition}
                    {segment_condition}
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'], rule['condition_valeur'])).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (categorie_specifique): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'premiere_visite':
                # Trouver les clients dont la première visite est dans la période spécifiée
                clients_query = f'''
                    SELECT 
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom
                    FROM clients c
                    JOIN (
                        SELECT 
                            client_id,
                            MIN(date_transaction) as premiere_visite
                        FROM transactions
                        GROUP BY client_id
                        HAVING premiere_visite >= date('now', '-{rule['condition_valeur']} days')
                        AND premiere_visite <= date('now')
                    ) pv ON c.client_id = pv.client_id
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'],)).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (premiere_visite): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'anniversaire':
                # Trouver les clients dont l'anniversaire approche
                clients_query = f'''
                    SELECT 
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom
                    FROM clients c
                    LEFT JOIN offres_client oc ON c.client_id = oc.client_id AND oc.regle_id = ?
                    WHERE c.statut = 'actif'
                    AND strftime('%m-%d', c.date_naissance) BETWEEN 
                        strftime('%m-%d', date('now')) AND 
                        strftime('%m-%d', date('now', '+{rule['condition_valeur']} days'))
                    AND c.date_naissance IS NOT NULL
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'],)).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (anniversaire): {len(eligible_clients)}")
                
            elif rule['type_regle'] == 'inactivite':
                # Trouver les clients inactifs pendant la période spécifiée
                clients_query = f'''
                    SELECT 
                        c.client_id,
                        c.prenom || ' ' || c.nom as client_nom
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
                    WHERE c.statut = 'actif'
                    AND (oc.offre_id IS NULL OR oc.statut = 'expiree')
                '''
                
                eligible_clients = conn.execute(clients_query, (rule['regle_id'],)).fetchall()
                
                print(f"Clients éligibles pour la règle '{rule['nom']}' (inactivite): {len(eligible_clients)}")
            
            # Créer des offres pour tous les clients éligibles
            for client in eligible_clients:
                # Déterminer la date d'expiration (par défaut 30 jours)
                expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                
                # Préparer le commentaire en fonction du type de règle
                if rule['type_regle'] == 'nombre_achats':
                    commentaire = f"Offre générée après {rule['condition_valeur']} achats"
                elif rule['type_regle'] == 'montant_cumule':
                    commentaire = f"Offre générée après {rule['condition_valeur']}€ d'achats cumulés"
                elif rule['type_regle'] == 'produit_specifique':
                    # Rechercher le nom du produit pour le commentaire
                    produit_info = conn.execute('SELECT nom FROM produits WHERE produit_id = ?', 
                                             (rule['condition_valeur'],)).fetchone()
                    produit_nom = produit_info['nom'] if produit_info else f"produit #{rule['condition_valeur']}"
                    commentaire = f"Offre générée pour l'achat de {produit_nom}"
                elif rule['type_regle'] == 'categorie_specifique':
                    # Rechercher le nom de la catégorie pour le commentaire
                    categorie_info = conn.execute('SELECT nom FROM categories_produits WHERE categorie_id = ?', 
                                               (rule['condition_valeur'],)).fetchone()
                    categorie_nom = categorie_info['nom'] if categorie_info else f"catégorie #{rule['condition_valeur']}"
                    commentaire = f"Offre générée pour achat dans {categorie_nom}"
                elif rule['type_regle'] == 'premiere_visite':
                    commentaire = "Offre de bienvenue pour nouveau client"
                elif rule['type_regle'] == 'anniversaire':
                    commentaire = "Offre d'anniversaire"
                elif rule['type_regle'] == 'inactivite':
                    commentaire = "Offre pour client inactif"
                else:
                    commentaire = "Offre programme de fidélité"
                
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
                    commentaire
                ))
                
                offers_for_rule += 1
                # Accéder au nom du client de manière sécurisée avec sqlite3.Row
                client_nom = client['client_nom'] if 'client_nom' in client else 'Inconnu'
                print(f"Offre créée pour client ID={client['client_id']}, nom={client_nom}")
            
            # Enregistrer les statistiques d'évaluation
            conn.execute('''
                INSERT INTO historique_evaluations_regles (
                    regle_id, nombre_clients_evalues, nombre_offres_generees, commentaire
                ) VALUES (?, ?, ?, ?)
            ''', (
                rule['regle_id'],
                len(eligible_clients),
                offers_for_rule,
                f"Exécution manuelle le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ))
            
            total_offers_generated += offers_for_rule
        
        # Générer des codes uniques pour toutes les nouvelles offres
        conn.execute('''
            UPDATE offres_client
            SET code_unique = 'OF-' || offre_id || '-' || substr(hex(randomblob(4)), 1, 8)
            WHERE code_unique IS NULL OR code_unique = ''
        ''')
        
        conn.commit()
        conn.close()
        
        flash(f'Évaluation des règles terminée. {total_offers_generated} offres générées.', 'success')
        
    except Exception as e:
        flash(f'Erreur lors de l\'exécution des règles: {str(e)}', 'danger')
        import traceback
        print(traceback.format_exc())
    
    return redirect(url_for('loyalty_dashboard'))

@app.route('/loyalty/client/<int:client_id>')
def client_loyalty(client_id):
    """Afficher les informations de fidélité d'un client spécifique"""
    try:
        conn = get_db_connection()
        
        # Récupérer les informations du client
        client = conn.execute('''
            SELECT 
                c.*,
                cf.niveau_fidelite,
                cf.points_actuels,
                cf.points_en_attente,
                cf.date_derniere_activite
            FROM clients c
            LEFT JOIN cartes_fidelite cf ON c.client_id = cf.client_id
            WHERE c.client_id = ?
        ''', (client_id,)).fetchone()
        
        if not client:
            flash('Client non trouvé', 'warning')
            return redirect(url_for('loyalty_dashboard'))
        
        # Récupérer les offres du client
        offres = conn.execute('''
            SELECT 
                oc.*,
                r.nom as nom_regle,
                rec.nom as nom_recompense
            FROM offres_client oc
            JOIN regles_fidelite r ON oc.regle_id = r.regle_id
            LEFT JOIN recompenses rec ON oc.recompense_id = rec.recompense_id
            WHERE oc.client_id = ?
            ORDER BY oc.date_generation DESC
        ''', (client_id,)).fetchall()
        
        # Récupérer l'historique des points
        historique_points = conn.execute('''
            SELECT 
                hp.*,
                t.date_transaction,
                t.montant_total
            FROM historique_points hp
            LEFT JOIN transactions t ON hp.transaction_id = t.transaction_id
            WHERE hp.client_id = ?
            ORDER BY hp.date_operation DESC
            LIMIT 20
        ''', (client_id,)).fetchall()
        
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
        
        conn.close()
        
        # Créer l'objet client_info avec les statistiques
        client_info = {
            'statistiques': dict(stats) if stats else {
                'nb_transactions': 0,
                'montant_total': 0,
                'panier_moyen': 0,
                'points_gagnes_total': 0,
                'derniere_transaction': None
            }
        }
        
        return render_template(
            'loyalty/client_loyalty.html',
            client=dict(client),
            offres=offres,
            historique_points=historique_points,
            client_info=client_info  # Assurez-vous de passer cette variable au template
        )
        
    except Exception as e:
        flash(f'Erreur lors du chargement des données de fidélité: {str(e)}', 'danger')
        return redirect(url_for('loyalty_dashboard'))

@app.route('/api/loyalty/stats')
def api_loyalty_stats():
    """API pour récupérer les statistiques du programme de fidélité"""
    try:
        conn = get_db_connection()
        
        # Statistiques générales
        stats = conn.execute('''
            SELECT 
                COUNT(DISTINCT c.client_id) as total_clients,
                COUNT(DISTINCT oc.offre_id) as total_offres,
                SUM(CASE WHEN oc.statut = 'utilisee' THEN 1 ELSE 0 END) as offres_utilisees,
                AVG(CASE WHEN oc.statut = 'utilisee' THEN 1.0 ELSE 0.0 END) as taux_utilisation
            FROM clients c
            LEFT JOIN offres_client oc ON c.client_id = oc.client_id
            WHERE c.statut = 'actif'
        ''').fetchone()
        
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
        
        # Statistiques par type de règle
        stats_regles = conn.execute('''
            SELECT 
                r.type_regle,
                COUNT(DISTINCT oc.offre_id) as nb_offres,
                SUM(CASE WHEN oc.statut = 'utilisee' THEN 1 ELSE 0 END) as offres_utilisees
            FROM offres_client oc
            JOIN regles_fidelite r ON oc.regle_id = r.regle_id
            GROUP BY r.type_regle
        ''').fetchall()
        
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
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': dict(stats),
            'stats_niveaux': [dict(x) for x in stats_niveaux],
            'stats_regles': [dict(x) for x in stats_regles],
            'offres_par_mois': [dict(x) for x in offres_par_mois]
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
@app.route('/loyalty/db-diagnosis')
def loyalty_db_diagnosis():
    """Page de diagnostic de la base de données du programme de fidélité"""
    try:
        # Connexion à la base de données
        conn = get_db_connection()
        
        # Dictionnaire pour stocker les résultats du diagnostic
        diagnosis = {
            'tables': {},
            'rules': [],
            'transactions_sample': [],
            'clients_sample': [],
            'eligible_clients': [],
            'errors': []
        }
        
        # 1. Vérifier les tables principales et leur nombre d'enregistrements
        for table_name in ['clients', 'transactions', 'regles_fidelite', 'offres_client', 
                          'cartes_fidelite', 'details_transactions', 'historique_points']:
            try:
                result = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchone()
                count = result['count'] if result else 0
                diagnosis['tables'][table_name] = count
            except Exception as e:
                diagnosis['errors'].append(f"Erreur lors du comptage de {table_name}: {str(e)}")
        
        # 2. Récupérer les règles actives avec leurs détails
        try:
            rules_query = '''
                SELECT 
                    r.regle_id, r.nom, r.type_regle, r.condition_valeur, r.periode_jours,
                    r.est_active, r.date_debut, r.date_fin, r.priorite, r.segments_cibles,
                    COUNT(o.offre_id) as offres_existantes
                FROM regles_fidelite r
                LEFT JOIN offres_client o ON r.regle_id = o.regle_id
                GROUP BY r.regle_id
                ORDER BY r.est_active DESC, r.priorite DESC
            '''
            rules = conn.execute(rules_query).fetchall()
            diagnosis['rules'] = [dict(rule) for rule in rules]
        except Exception as e:
            diagnosis['errors'].append(f"Erreur lors de la récupération des règles: {str(e)}")
        
        # 3. Échantillon de transactions récentes
        try:
            transactions_query = '''
                SELECT 
                    t.transaction_id, t.client_id, t.date_transaction, t.montant_total,
                    c.prenom || ' ' || c.nom as client_nom,
                    c.statut as client_statut,
                    c.segment as client_segment
                FROM transactions t
                JOIN clients c ON t.client_id = c.client_id
                ORDER BY t.date_transaction DESC
                LIMIT 10
            '''
            transactions = conn.execute(transactions_query).fetchall()
            diagnosis['transactions_sample'] = [dict(tx) for tx in transactions]
        except Exception as e:
            diagnosis['errors'].append(f"Erreur lors de la récupération des transactions: {str(e)}")
        
        # 4. Échantillon de clients
        try:
            clients_query = '''
                SELECT 
                    c.client_id, c.prenom, c.nom, c.email, c.statut, c.segment,
                    cf.points_actuels, cf.niveau_fidelite,
                    COUNT(DISTINCT t.transaction_id) as nb_transactions,
                    COUNT(DISTINCT o.offre_id) as nb_offres
                FROM clients c
                LEFT JOIN cartes_fidelite cf ON c.client_id = cf.client_id
                LEFT JOIN transactions t ON c.client_id = t.client_id
                LEFT JOIN offres_client o ON c.client_id = o.client_id
                WHERE c.statut = 'actif'
                GROUP BY c.client_id
                ORDER BY nb_transactions DESC
                LIMIT 10
            '''
            clients = conn.execute(clients_query).fetchall()
            diagnosis['clients_sample'] = [dict(client) for client in clients]
        except Exception as e:
            diagnosis['errors'].append(f"Erreur lors de la récupération des clients: {str(e)}")
        
        # 5. Pour chaque règle active, trouver des clients potentiellement éligibles
        try:
            active_rules = [r for r in diagnosis['rules'] if r['est_active']]
            
            for rule in active_rules[:3]:  # Limitons à 3 règles pour ne pas surcharger
                if rule['type_regle'] == 'nombre_achats':
                    # Requête spécifique pour les règles par nombre d'achats
                    period_condition = ""
                    if rule['periode_jours']:
                        period_condition = f"AND t.date_transaction >= date('now', '-{rule['periode_jours']} days')"
                    
                    eligible_query = f'''
                        SELECT 
                            c.client_id, c.prenom || ' ' || c.nom as client_nom, 
                            c.segment, c.statut,
                            COUNT(DISTINCT t.transaction_id) as nb_achats,
                            (SELECT COUNT(*) FROM offres_client 
                             WHERE client_id = c.client_id AND regle_id = ?) as offres_recues
                        FROM clients c
                        JOIN transactions t ON c.client_id = t.client_id
                        WHERE c.statut = 'actif'
                        {period_condition}
                        GROUP BY c.client_id
                        HAVING nb_achats >= ? AND offres_recues = 0
                        LIMIT 5
                    '''
                    eligible_clients = conn.execute(eligible_query, 
                                                  (rule['regle_id'], rule['condition_valeur'])).fetchall()
                    
                    diagnosis['eligible_clients'].append({
                        'rule_id': rule['regle_id'],
                        'rule_name': rule['nom'],
                        'rule_type': rule['type_regle'],
                        'condition': rule['condition_valeur'],
                        'clients': [dict(c) for c in eligible_clients]
                    })
                
                # Ajouter des requêtes similaires pour d'autres types de règles...
        except Exception as e:
            diagnosis['errors'].append(f"Erreur lors de la recherche des clients éligibles: {str(e)}")
        
        conn.close()
        
        # Conversion des données pour l'affichage
        import json
        diagnosis_json = json.dumps(diagnosis, indent=2, default=str)
        
        return render_template('loyalty/db_diagnosis.html', 
                              diagnosis=diagnosis,
                              diagnosis_json=diagnosis_json)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return render_template('error.html', 
                              message=f"Erreur lors du diagnostic: {str(e)}",
                              details=error_trace)
    
@app.route('/loyalty/debug-insert', methods=['GET', 'POST'])
def debug_insert_offer():
    """Page pour déboguer l'insertion d'offres"""
    try:
        if request.method == 'POST':
            # Tenter d'insérer une offre de test
            conn = get_db_connection()
            
            # 1. Récupérer un client et une règle valides
            client = conn.execute("SELECT client_id FROM clients WHERE statut = 'actif' LIMIT 1").fetchone()
            rule = conn.execute("SELECT regle_id FROM regles_fidelite WHERE est_active = 1 LIMIT 1").fetchone()
            
            if not client or not rule:
                return "Erreur: Impossible de trouver un client actif ou une règle active"
            
            # 2. Tenter d'insérer l'offre avec un try-except explicite
            try:
                cursor = conn.execute('''
                    INSERT INTO offres_client (
                        client_id, regle_id, date_generation, date_expiration, 
                        statut, commentaire
                    ) VALUES (?, ?, date('now'), date('now', '+30 days'), 'generee', ?)
                ''', (
                    client['client_id'],
                    rule['regle_id'],
                    "Offre de test pour débogage"
                ))
                
                # Vérifier si l'insertion a fonctionné
                if cursor.rowcount > 0:
                    # Récupérer l'ID de l'offre insérée
                    last_id = cursor.lastrowid
                    
                    # Valider la transaction
                    conn.commit()
                    
                    return f"Insertion réussie! Offre ID: {last_id}"
                else:
                    return "Échec de l'insertion: aucune ligne affectée."
                
            except sqlite3.Error as e:
                return f"Erreur SQLite lors de l'insertion: {e}"
            
        # Page de formulaire simple en GET
        return '''
        <html>
            <body>
                <h1>Déboguer l'insertion d'offres</h1>
                <form method="post">
                    <button type="submit">Tester l'insertion d'une offre</button>
                </form>
            </body>
        </html>
        '''
    
    except Exception as e:
        import traceback
        return f"Erreur: {str(e)}<br><pre>{traceback.format_exc()}</pre>"


# ---------------------------------------------------SCHEDULER --------------------------------------------------

@app.route('/loyalty/scheduler')
def loyalty_scheduler_config():
    """Page de configuration du planificateur de fidélité"""
    try:
        # Charger la configuration
        config = load_config()
        
        # Vérifier l'état actuel du planificateur
        is_running = is_scheduler_running()
        
        # Mettre à jour le statut si nécessaire
        if is_running != config['status']['is_running']:
            config['status']['is_running'] = is_running
            if not is_running:
                config['status']['pid'] = None
            save_config(config)
        
        # Récupérer les logs récents
        scheduler_logs = get_scheduler_logs(10)
        
        return render_template(
            'scheduler_config.html',
            scheduler_tasks=config['tasks'],
            scheduler_status=config['status'],
            scheduler_logs=scheduler_logs
        )
    
    except Exception as e:
        flash(f'Erreur lors du chargement de la configuration du planificateur: {str(e)}', 'danger')
        return redirect(url_for('loyalty_dashboard'))

# Sauvegarder la configuration du planificateur
@app.route('/loyalty/scheduler/save', methods=['POST'])
def loyalty_scheduler_config_save():
    """Sauvegarde les modifications de la configuration du planificateur"""
    try:
        # Mettre à jour la configuration avec les données du formulaire
        update_task_config(request.form)
        
        flash('Configuration du planificateur sauvegardée avec succès', 'success')
        
        # Si le planificateur est en cours d'exécution, proposer de le redémarrer
        if is_scheduler_running():
            flash('Le planificateur est en cours d\'exécution. Les modifications prendront effet après un redémarrage.', 'warning')
    
    except Exception as e:
        flash(f'Erreur lors de la sauvegarde de la configuration: {str(e)}', 'danger')
    
    return redirect(url_for('loyalty_scheduler_config'))

# Contrôle du planificateur (démarrage, arrêt, redémarrage)
@app.route('/loyalty/scheduler/control/<action>', methods=['POST'])
def loyalty_scheduler_control(action):
    """Contrôle l'état du planificateur (démarrage, arrêt, redémarrage)"""
    try:
        result = {'success': False, 'message': 'Action non reconnue'}
        
        if action == 'start':
            result = start_scheduler()
            if result['success']:
                flash('Planificateur démarré avec succès', 'success')
            else:
                flash(f'Échec du démarrage du planificateur: {result["message"]}', 'danger')
                
        elif action == 'stop':
            result = stop_scheduler()
            if result['success']:
                flash('Planificateur arrêté avec succès', 'success')
            else:
                flash(f'Échec de l\'arrêt du planificateur: {result["message"]}', 'danger')
                
        elif action == 'restart':
            result = restart_scheduler()
            if result['success']:
                flash('Planificateur redémarré avec succès', 'success')
            else:
                flash(f'Échec du redémarrage du planificateur: {result["message"]}', 'danger')
        
        else:
            flash(f'Action non reconnue: {action}', 'warning')
    
    except Exception as e:
        flash(f'Erreur lors de l\'exécution de l\'action: {str(e)}', 'danger')
    
    return redirect(url_for('loyalty_scheduler_config'))

# Exécution manuelle d'une tâche
@app.route('/loyalty/scheduler/run-task/<task_id>', methods=['POST'])
def loyalty_scheduler_run_task(task_id):
    """Exécute manuellement une tâche spécifique"""
    try:
        result = run_specific_task(task_id)
        
        if result['success']:
            flash(f'Tâche exécutée avec succès: {result["message"]}', 'success')
        else:
            flash(f'Échec de l\'exécution de la tâche: {result["message"]}', 'danger')
    
    except Exception as e:
        flash(f'Erreur lors de l\'exécution de la tâche: {str(e)}', 'danger')
    
    return redirect(url_for('loyalty_scheduler_config'))

# Page des logs complets
@app.route('/loyalty/scheduler/logs')
def loyalty_scheduler_logs():
    """Affiche les logs complets du planificateur"""
    try:
        # Récupérer tous les logs disponibles (limités à 200 lignes pour des raisons de performance)
        scheduler_logs = get_scheduler_logs(200)
        
        return render_template(
            'scheduler_logs.html',
            scheduler_logs=scheduler_logs
        )
    
    except Exception as e:
        flash(f'Erreur lors de la récupération des logs: {str(e)}', 'danger')
        return redirect(url_for('loyalty_scheduler_config'))

# API pour récupérer le statut du planificateur
@app.route('/api/loyalty/scheduler/status')
def api_scheduler_status():
    """API pour récupérer le statut actuel du planificateur"""
    try:
        status = get_scheduler_status()
        return jsonify({
            'success': True,
            'is_running': status['is_running'],
            'active_since': status['active_since'],
            'last_run': status['last_run'],
            'pid': status['pid']
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
#---------------------------------------------OFFRES CLUSTERS------------------------------------------------------

# Routes pour les offres par clusters

        
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


print("\n=== ROUTES DISPONIBLES ===")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule}")
    
if __name__ == '__main__':
    app.run(debug=True)




