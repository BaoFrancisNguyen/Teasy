"""
Gestion des données pour le module d'analyse de sentiments.
Stocke, récupère et formate les données de sentiments clients.
"""

import os
import json
import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SentimentDataManager:
    """Gestionnaire des données d'analyse de sentiments"""
    
    def __init__(self, db_path: str = 'modules/sentiment_scraper/data/sentiment_data.db'):
        """
        Initialise le gestionnaire de données.
        
        Args:
            db_path: Chemin vers la base de données SQLite
        """
        self.db_path = db_path
        self.ensure_data_directory()
        
    def ensure_data_directory(self):
        """S'assure que le répertoire de données existe"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def initialize_database(self):
        """Crée la structure de la base de données si elle n'existe pas déjà"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Création des tables principales
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_category TEXT NOT NULL,
            product_brand TEXT NOT NULL,
            review_text TEXT NOT NULL,
            rating REAL,
            review_date TIMESTAMP NOT NULL,
            reviewer_id TEXT,
            reviewer_name TEXT,
            verified_purchase BOOLEAN DEFAULT 0,
            scrape_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            sentiment_score REAL NOT NULL,
            sentiment_label TEXT NOT NULL,
            confidence REAL NOT NULL,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES reviews(review_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_segments (
            segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id TEXT NOT NULL,
            segment_name TEXT NOT NULL,
            segment_description TEXT,
            confidence REAL NOT NULL,
            assignment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS aspect_sentiments (
            aspect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            aspect_name TEXT NOT NULL,
            sentiment_score REAL NOT NULL,
            sentiment_label TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES reviews(review_id)
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Base de données d'analyse de sentiments initialisée avec succès")
    
    def _get_connection(self):
        """Établit une connexion à la base de données SQLite"""
        return sqlite3.connect(self.db_path)
    
    def save_reviews(self, reviews: List[Dict[str, Any]]):
        """
        Sauvegarde les avis récupérés dans la base de données.
        
        Args:
            reviews: Liste de dictionnaires contenant les avis
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for review in reviews:
            # Vérifier si l'avis existe déjà (en se basant sur l'ID source et la date)
            cursor.execute('''
            SELECT review_id FROM reviews 
            WHERE source = ? AND product_id = ? AND reviewer_id = ? AND review_date = ?
            ''', (
                review.get('source', ''),
                review.get('product_id', ''),
                review.get('reviewer_id', ''),
                review.get('review_date', '')
            ))
            
            existing_review = cursor.fetchone()
            
            if not existing_review:
                # Insérer le nouvel avis
                cursor.execute('''
                INSERT INTO reviews (
                    source, product_id, product_name, product_category, product_brand,
                    review_text, rating, review_date, reviewer_id, reviewer_name, verified_purchase
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    review.get('source', ''),
                    review.get('product_id', ''),
                    review.get('product_name', ''),
                    review.get('product_category', ''),
                    review.get('product_brand', ''),
                    review.get('review_text', ''),
                    review.get('rating', None),
                    review.get('review_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    review.get('reviewer_id', ''),
                    review.get('reviewer_name', ''),
                    review.get('verified_purchase', False)
                ))
                
        conn.commit()
        conn.close()
        logger.info(f"Sauvegarde de {len(reviews)} avis terminée")
    
    def save_sentiment_analysis(self, sentiments: List[Dict[str, Any]]):
        """
        Sauvegarde les résultats d'analyse de sentiments dans la base de données.
        
        Args:
            sentiments: Liste de dictionnaires contenant les analyses de sentiments
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for sentiment in sentiments:
            cursor.execute('''
            INSERT INTO sentiment_analysis (
                review_id, sentiment_score, sentiment_label, confidence
            ) VALUES (?, ?, ?, ?)
            ''', (
                sentiment.get('review_id', 0),
                sentiment.get('sentiment_score', 0),
                sentiment.get('sentiment_label', 'neutral'),
                sentiment.get('confidence', 0)
            ))
            
            # Si des aspects sont présents, les sauvegarder également
            if 'aspects' in sentiment and sentiment['aspects']:
                for aspect in sentiment['aspects']:
                    cursor.execute('''
                    INSERT INTO aspect_sentiments (
                        review_id, aspect_name, sentiment_score, sentiment_label
                    ) VALUES (?, ?, ?, ?)
                    ''', (
                        sentiment.get('review_id', 0),
                        aspect.get('name', ''),
                        aspect.get('sentiment_score', 0),
                        aspect.get('sentiment_label', 'neutral')
                    ))
        
        conn.commit()
        conn.close()
        logger.info(f"Sauvegarde de {len(sentiments)} analyses de sentiments terminée")
    
    def save_customer_segments(self, segments: List[Dict[str, Any]]):
        """
        Sauvegarde les segments clients dans la base de données.
        
        Args:
            segments: Liste de dictionnaires contenant les segments clients
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for segment in segments:
            # Vérifier si ce reviewer a déjà un segment assigné
            cursor.execute('''
            SELECT segment_id FROM customer_segments 
            WHERE reviewer_id = ?
            ''', (segment.get('reviewer_id', ''),))
            
            existing_segment = cursor.fetchone()
            
            if existing_segment:
                # Mettre à jour le segment existant
                cursor.execute('''
                UPDATE customer_segments 
                SET segment_name = ?, segment_description = ?, confidence = ?, assignment_date = CURRENT_TIMESTAMP
                WHERE reviewer_id = ?
                ''', (
                    segment.get('segment_name', ''),
                    segment.get('segment_description', ''),
                    segment.get('confidence', 0),
                    segment.get('reviewer_id', '')
                ))
            else:
                # Insérer un nouveau segment
                cursor.execute('''
                INSERT INTO customer_segments (
                    reviewer_id, segment_name, segment_description, confidence
                ) VALUES (?, ?, ?, ?)
                ''', (
                    segment.get('reviewer_id', ''),
                    segment.get('segment_name', ''),
                    segment.get('segment_description', ''),
                    segment.get('confidence', 0)
                ))
        
        conn.commit()
        conn.close()
        logger.info(f"Sauvegarde de {len(segments)} segments clients terminée")
    
    def get_reviews_for_analysis(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les avis qui n'ont pas encore été analysés.
        
        Args:
            limit: Nombre maximum d'avis à récupérer
            
        Returns:
            Liste d'avis à analyser
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT r.* FROM reviews r
        LEFT JOIN sentiment_analysis sa ON r.review_id = sa.review_id
        WHERE sa.analysis_id IS NULL
        LIMIT ?
        ''', (limit,))
        
        columns = [column[0] for column in cursor.description]
        reviews = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return reviews
    
    def get_formatted_sentiment_data(self, product_category=None, time_period=None, segment=None):
        """
        Récupère et formate les données d'analyse de sentiments pour l'affichage.
        
        Args:
            product_category: Catégorie de produit à filtrer
            time_period: Période temporelle (ex: '30d', '6m', '1y')
            segment: Segment client à filtrer
            
        Returns:
            Données formatées pour l'affichage dans l'interface
        """
        conn = self._get_connection()
        
        # Calculer la date de début en fonction de la période
        start_date = None
        if time_period:
            now = datetime.now()
            if time_period == '7d':
                start_date = now - timedelta(days=7)
            elif time_period == '30d':
                start_date = now - timedelta(days=30)
            elif time_period == '6m':
                start_date = now - timedelta(days=180)
            elif time_period == '1y':
                start_date = now - timedelta(days=365)
        
        # Construire la requête SQL
        query = '''
        SELECT 
            r.product_category,
            r.product_brand,
            r.product_name,
            AVG(sa.sentiment_score) as avg_sentiment,
            COUNT(*) as review_count,
            COUNT(CASE WHEN sa.sentiment_label = 'positive' THEN 1 END) as positive_count,
            COUNT(CASE WHEN sa.sentiment_label = 'neutral' THEN 1 END) as neutral_count,
            COUNT(CASE WHEN sa.sentiment_label = 'negative' THEN 1 END) as negative_count,
            cs.segment_name
        FROM reviews r
        JOIN sentiment_analysis sa ON r.review_id = sa.review_id
        LEFT JOIN customer_segments cs ON r.reviewer_id = cs.reviewer_id
        WHERE 1=1
        '''
        
        params = []
        
        # Ajouter les filtres
        if product_category:
            query += " AND r.product_category = ?"
            params.append(product_category)
        
        if start_date:
            query += " AND r.review_date >= ?"
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if segment:
            query += " AND cs.segment_name = ?"
            params.append(segment)
        
        # Grouper et ordonner les résultats
        query += '''
        GROUP BY r.product_category, r.product_brand, r.product_name, cs.segment_name
        ORDER BY r.product_category, avg_sentiment DESC
        '''
        
        # Exécuter la requête
        df = pd.read_sql_query(query, conn, params=params)
        
        # Créer le dictionnaire de résultats
        results = {
            'overall_sentiment': {
                'score': df['avg_sentiment'].mean() if not df.empty else 0,
                'review_count': df['review_count'].sum() if not df.empty else 0,
                'positive_percent': df['positive_count'].sum() / df['review_count'].sum() * 100 if not df.empty and df['review_count'].sum() > 0 else 0,
                'neutral_percent': df['neutral_count'].sum() / df['review_count'].sum() * 100 if not df.empty and df['review_count'].sum() > 0 else 0,
                'negative_percent': df['negative_count'].sum() / df['review_count'].sum() * 100 if not df.empty and df['review_count'].sum() > 0 else 0
            },
            'by_category': {},
            'by_brand': {},
            'by_segment': {}
        }
        
        # Traiter les données par catégorie
        for category, category_df in df.groupby('product_category'):
            results['by_category'][category] = {
                'score': category_df['avg_sentiment'].mean(),
                'review_count': category_df['review_count'].sum(),
                'positive_percent': category_df['positive_count'].sum() / category_df['review_count'].sum() * 100 if category_df['review_count'].sum() > 0 else 0,
                'neutral_percent': category_df['neutral_count'].sum() / category_df['review_count'].sum() * 100 if category_df['review_count'].sum() > 0 else 0,
                'negative_percent': category_df['negative_count'].sum() / category_df['review_count'].sum() * 100 if category_df['review_count'].sum() > 0 else 0
            }
        
        # Traiter les données par marque
        for brand, brand_df in df.groupby('product_brand'):
            results['by_brand'][brand] = {
                'score': brand_df['avg_sentiment'].mean(),
                'review_count': brand_df['review_count'].sum(),
                'positive_percent': brand_df['positive_count'].sum() / brand_df['review_count'].sum() * 100 if brand_df['review_count'].sum() > 0 else 0,
                'neutral_percent': brand_df['neutral_count'].sum() / brand_df['review_count'].sum() * 100 if brand_df['review_count'].sum() > 0 else 0,
                'negative_percent': brand_df['negative_count'].sum() / brand_df['review_count'].sum() * 100 if brand_df['review_count'].sum() > 0 else 0
            }
        
        # Traiter les données par segment
        for segment_name, segment_df in df.groupby('segment_name'):
            if pd.isna(segment_name):
                continue
                
            results['by_segment'][segment_name] = {
                'score': segment_df['avg_sentiment'].mean(),
                'review_count': segment_df['review_count'].sum(),
                'positive_percent': segment_df['positive_count'].sum() / segment_df['review_count'].sum() * 100 if segment_df['review_count'].sum() > 0 else 0,
                'neutral_percent': segment_df['neutral_count'].sum() / segment_df['review_count'].sum() * 100 if segment_df['review_count'].sum() > 0 else 0,
                'negative_percent': segment_df['negative_count'].sum() / segment_df['review_count'].sum() * 100 if segment_df['review_count'].sum() > 0 else 0
            }
        
        # Récupérer les aspects les plus mentionnés et leur sentiment
        aspect_query = '''
        SELECT 
            aspect_name,
            AVG(sentiment_score) as avg_sentiment,
            COUNT(*) as mention_count,
            COUNT(CASE WHEN sentiment_label = 'positive' THEN 1 END) as positive_count,
            COUNT(CASE WHEN sentiment_label = 'neutral' THEN 1 END) as neutral_count,
            COUNT(CASE WHEN sentiment_label = 'negative' THEN 1 END) as negative_count
        FROM aspect_sentiments a
        JOIN reviews r ON a.review_id = r.review_id
        WHERE 1=1
        '''
        
        # Ajouter les mêmes filtres que pour la requête principale
        if product_category:
            aspect_query += " AND r.product_category = ?"
        
        if start_date:
            aspect_query += " AND r.review_date >= ?"
        
        if segment:
            aspect_query += " AND r.reviewer_id IN (SELECT reviewer_id FROM customer_segments WHERE segment_name = ?)"
        
        aspect_query += '''
        GROUP BY aspect_name
        ORDER BY mention_count DESC
        LIMIT 10
        '''
        
        # Exécuter la requête des aspects
        aspect_df = pd.read_sql_query(aspect_query, conn, params=params)
        
        # Ajouter les aspects au résultat
        results['top_aspects'] = []
        for _, row in aspect_df.iterrows():
            results['top_aspects'].append({
                'name': row['aspect_name'],
                'score': row['avg_sentiment'],
                'mention_count': row['mention_count'],
                'positive_percent': row['positive_count'] / row['mention_count'] * 100 if row['mention_count'] > 0 else 0,
                'neutral_percent': row['neutral_count'] / row['mention_count'] * 100 if row['mention_count'] > 0 else 0,
                'negative_percent': row['negative_count'] / row['mention_count'] * 100 if row['mention_count'] > 0 else 0
            })
        
        conn.close()
        return results
