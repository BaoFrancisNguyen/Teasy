"""
Module d'analyse de sentiments pour les avis clients.
Utilise des techniques de NLP pour extraire le sentiment et les aspects des avis.
"""

import re
import json
import nltk
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

import pandas as pd
import numpy as np
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Analyseur de sentiments pour les avis clients"""
    
    def __init__(self, language: str = 'english'):
        """
        Initialise l'analyseur de sentiments.
        
        Args:
            language: Langue des textes à analyser ('english' ou 'french')
        """
        self.language = language
        self.initialize_nltk()
        
        # Initialiser les outils NLTK
        self.sid = SentimentIntensityAnalyzer()
        self.lemmatizer = WordNetLemmatizer()
        
        # Aspects pertinents pour les produits électroménagers/high-tech
        self.aspects = {
            'price': ['price', 'cost', 'expensive', 'cheap', 'affordable', 'value', 'worth', 'money', 'budget', 'priced'],
            'quality': ['quality', 'build', 'sturdy', 'solid', 'durable', 'construction', 'material', 'finish', 'craftsmanship', 'made'],
            'design': ['design', 'look', 'style', 'appearance', 'aesthetic', 'size', 'color', 'sleek', 'modern', 'bulky', 'slim', 'weight'],
            'usability': ['easy', 'simple', 'intuitive', 'user-friendly', 'ergonomic', 'comfortable', 'convenient', 'handy', 'practical', 'setup', 'instructions'],
            'performance': ['performance', 'fast', 'slow', 'speed', 'efficient', 'powerful', 'responsive', 'quick', 'effective', 'reliable'],
            'battery': ['battery', 'charge', 'runtime', 'power', 'last', 'hours', 'duration', 'battery life'],
            'features': ['feature', 'function', 'functionality', 'capability', 'option', 'setting', 'control', 'mode'],
            'noise': ['noise', 'quiet', 'silent', 'loud', 'sound', 'noisy', 'volume', 'decibel'],
            'service': ['service', 'support', 'customer service', 'warranty', 'return', 'repair', 'replacement', 'customer support', 'help'],
            'durability': ['durability', 'durable', 'lasting', 'robust', 'break', 'broken', 'fragile', 'strong', 'weak', 'long-lasting', 'lifespan']
        }
        
        # Traduire les aspects si la langue est le français
        if language == 'french':
            self.aspects = {
                'prix': ['prix', 'coût', 'cher', 'abordable', 'valeur', 'vaut', 'argent', 'budget', 'tarif'],
                'qualité': ['qualité', 'construction', 'solide', 'durable', 'matériau', 'finition', 'fabrication', 'fabriqué'],
                'design': ['design', 'look', 'style', 'apparence', 'esthétique', 'taille', 'couleur', 'élégant', 'moderne', 'encombrant', 'mince', 'poids'],
                'utilisation': ['facile', 'simple', 'intuitif', 'ergonomique', 'confortable', 'pratique', 'commode', 'installation', 'notice'],
                'performance': ['performance', 'rapide', 'lent', 'vitesse', 'efficace', 'puissant', 'réactif', 'fiable'],
                'batterie': ['batterie', 'charge', 'autonomie', 'énergie', 'durer', 'heures', 'durée'],
                'fonctionnalités': ['fonctionnalité', 'fonction', 'caractéristique', 'capacité', 'option', 'paramètre', 'contrôle', 'mode'],
                'bruit': ['bruit', 'silencieux', 'sonore', 'fort', 'son', 'bruyant', 'volume', 'décibel'],
                'service': ['service', 'support', 'service client', 'garantie', 'retour', 'réparation', 'remplacement', 'aide'],
                'durabilité': ['durabilité', 'durable', 'robuste', 'casser', 'cassé', 'fragile', 'solide', 'faible', 'longue durée', 'durée de vie']
            }
    
    def initialize_nltk(self):
        """Télécharge les ressources NLTK nécessaires"""
        resources = ['vader_lexicon', 'punkt', 'stopwords', 'wordnet']
        
        for resource in resources:
            try:
                nltk.data.find(f'tokenizers/{resource}' if resource == 'punkt' else resource)
            except LookupError:
                nltk.download(resource)
                
        logger.info("Ressources NLTK initialisées avec succès")
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyse le sentiment d'un texte.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Dictionnaire contenant le score de sentiment et le label
        """
        # Si le texte est vide, retourner un sentiment neutre
        if not text or len(text.strip()) == 0:
            return {
                'sentiment_score': 0,
                'sentiment_label': 'neutral',
                'confidence': 1.0
            }
        
        # Utiliser VADER pour analyser le sentiment
        scores = self.sid.polarity_scores(text)
        
        # Déterminer le label de sentiment
        # Déterminer le label de sentiment
        compound_score = scores['compound']
        
        if compound_score >= 0.05:
            sentiment_label = 'positive'
        elif compound_score <= -0.05:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        # Calculer un indice de confiance basé sur l'intensité du score
        confidence = abs(compound_score) if compound_score != 0 else 0.5
        
        return {
            'sentiment_score': compound_score,
            'sentiment_label': sentiment_label,
            'confidence': confidence
        }
    
    def extract_aspects(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait les aspects mentionnés dans le texte et leurs sentiments.
        
        Args:
            text: Texte de l'avis
            
        Returns:
            Liste d'aspects avec leurs scores de sentiment
        """
        if not text or len(text.strip()) == 0:
            return []
        
        # Tokeniser le texte par phrases pour une analyse plus précise
        sentences = sent_tokenize(text)
        
        # Analyser chaque phrase pour extraire les aspects
        aspect_sentiments = []
        
        for sentence in sentences:
            # Analyser le sentiment de la phrase
            sentence_sentiment = self.analyze_sentiment(sentence)
            
            # Tokeniser la phrase en mots
            words = word_tokenize(sentence.lower())
            
            # Supprimer les stop words
            stop_words = set(stopwords.words(self.language))
            filtered_words = [word for word in words if word not in stop_words and word.isalnum()]
            
            # Lemmatiser les mots
            lemmatized_words = [self.lemmatizer.lemmatize(word) for word in filtered_words]
            
            # Identifier les aspects mentionnés
            found_aspects = set()
            
            for aspect_category, aspect_keywords in self.aspects.items():
                # Vérifier si l'un des mots-clés d'aspect est présent dans la phrase lemmatisée
                if any(keyword in sentence.lower() for keyword in aspect_keywords):
                    found_aspects.add(aspect_category)
                    continue
                
                # Vérifier si l'un des mots lemmatisés correspond à un mot-clé d'aspect
                if any(keyword in lemmatized_words for keyword in aspect_keywords):
                    found_aspects.add(aspect_category)
                    continue
            
            # Ajouter chaque aspect trouvé avec le sentiment de la phrase
            for aspect in found_aspects:
                aspect_sentiments.append({
                    'name': aspect,
                    'sentiment_score': sentence_sentiment['sentiment_score'],
                    'sentiment_label': sentence_sentiment['sentiment_label'],
                    'confidence': sentence_sentiment['confidence']
                })
        
        # Agréger les aspects dupliqués en calculant la moyenne des scores
        aggregated_aspects = {}
        
        for aspect in aspect_sentiments:
            name = aspect['name']
            
            if name not in aggregated_aspects:
                aggregated_aspects[name] = {
                    'name': name,
                    'scores': [aspect['sentiment_score']],
                    'labels': [aspect['sentiment_label']],
                    'confidences': [aspect['confidence']]
                }
            else:
                aggregated_aspects[name]['scores'].append(aspect['sentiment_score'])
                aggregated_aspects[name]['labels'].append(aspect['sentiment_label'])
                aggregated_aspects[name]['confidences'].append(aspect['confidence'])
        
        # Calculer les moyennes pour chaque aspect
        result = []
        
        for name, data in aggregated_aspects.items():
            # Moyenne des scores de sentiment
            avg_score = sum(data['scores']) / len(data['scores'])
            
            # Déterminer le label majoritaire
            labels_counter = Counter(data['labels'])
            majority_label = labels_counter.most_common(1)[0][0]
            
            # Moyenne des confiances
            avg_confidence = sum(data['confidences']) / len(data['confidences'])
            
            result.append({
                'name': name,
                'sentiment_score': avg_score,
                'sentiment_label': majority_label,
                'confidence': avg_confidence,
                'mention_count': len(data['scores'])
            })
        
        return result
    
    def batch_analyze_reviews(self, reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyse un lot d'avis clients.
        
        Args:
            reviews: Liste d'avis à analyser
            
        Returns:
            Liste de résultats d'analyse avec sentiment global et aspects
        """
        results = []
        
        for review in reviews:
            # Récupérer le texte de l'avis
            review_text = review.get('review_text', '')
            
            # Analyser le sentiment global
            sentiment = self.analyze_sentiment(review_text)
            
            # Extraire les aspects
            aspects = self.extract_aspects(review_text)
            
            # Créer le résultat d'analyse
            analysis_result = {
                'review_id': review.get('review_id'),
                'sentiment_score': sentiment['sentiment_score'],
                'sentiment_label': sentiment['sentiment_label'],
                'confidence': sentiment['confidence'],
                'aspects': aspects
            }
            
            results.append(analysis_result)
        
        return results
    
    def analyze_product_sentiment(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyse le sentiment global pour un produit à partir de ses avis.
        
        Args:
            reviews: Liste d'avis du produit
            
        Returns:
            Rapport d'analyse de sentiment pour le produit
        """
        if not reviews:
            return {
                'average_sentiment': 0,
                'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
                'aspect_sentiment': {},
                'review_count': 0
            }
        
        # Analyser chaque avis
        analyses = self.batch_analyze_reviews(reviews)
        
        # Calculer le sentiment moyen
        sentiment_scores = [analysis['sentiment_score'] for analysis in analyses]
        average_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        
        # Calculer la distribution des sentiments
        sentiment_labels = [analysis['sentiment_label'] for analysis in analyses]
        label_counts = Counter(sentiment_labels)
        total_reviews = len(analyses)
        
        sentiment_distribution = {
            'positive': label_counts.get('positive', 0) / total_reviews * 100,
            'neutral': label_counts.get('neutral', 0) / total_reviews * 100,
            'negative': label_counts.get('negative', 0) / total_reviews * 100
        }
        
        # Agréger les sentiments par aspect
        all_aspects = {}
        
        for analysis in analyses:
            for aspect in analysis.get('aspects', []):
                aspect_name = aspect['name']
                
                if aspect_name not in all_aspects:
                    all_aspects[aspect_name] = {
                        'scores': [aspect['sentiment_score']],
                        'labels': [aspect['sentiment_label']],
                        'mention_count': 1
                    }
                else:
                    all_aspects[aspect_name]['scores'].append(aspect['sentiment_score'])
                    all_aspects[aspect_name]['labels'].append(aspect['sentiment_label'])
                    all_aspects[aspect_name]['mention_count'] += 1
        
        # Formater les résultats par aspect
        aspect_sentiment = {}
        
        for aspect_name, data in all_aspects.items():
            aspect_sentiment[aspect_name] = {
                'average_score': sum(data['scores']) / len(data['scores']),
                'mention_count': data['mention_count'],
                'mention_percentage': data['mention_count'] / total_reviews * 100,
                'sentiment_distribution': {
                    'positive': Counter(data['labels']).get('positive', 0) / len(data['labels']) * 100,
                    'neutral': Counter(data['labels']).get('neutral', 0) / len(data['labels']) * 100,
                    'negative': Counter(data['labels']).get('negative', 0) / len(data['labels']) * 100
                }
            }
        
        return {
            'average_sentiment': average_sentiment,
            'sentiment_distribution': sentiment_distribution,
            'aspect_sentiment': aspect_sentiment,
            'review_count': total_reviews
        }
    
    def identify_sentiment_trends(self, reviews: List[Dict[str, Any]], time_frames: List[str] = None) -> Dict[str, Any]:
        """
        Identifie les tendances de sentiment sur différentes périodes.
        
        Args:
            reviews: Liste d'avis triés chronologiquement
            time_frames: Liste de périodes à analyser (ex: ['1W', '1M', '3M', '6M', '1Y'])
            
        Returns:
            Tendances de sentiment par période
        """
        from datetime import datetime, timedelta
        
        # Si aucune période n'est spécifiée, utiliser des périodes par défaut
        if not time_frames:
            time_frames = ['1W', '1M', '3M', '6M', '1Y']
        
        # Trier les avis par date (du plus récent au plus ancien)
        sorted_reviews = sorted(
            reviews,
            key=lambda x: datetime.strptime(x.get('review_date', '2000-01-01'), '%Y-%m-%d'),
            reverse=True
        )
        
        # Date de l'avis le plus récent
        if sorted_reviews:
            latest_date = datetime.strptime(sorted_reviews[0].get('review_date', '2000-01-01'), '%Y-%m-%d')
        else:
            return {time_frame: {} for time_frame in time_frames}
        
        # Analyser chaque période
        trends = {}
        
        for time_frame in time_frames:
            # Déterminer la durée de la période
            unit = time_frame[-1]
            value = int(time_frame[:-1])
            
            if unit == 'D':
                cutoff_date = latest_date - timedelta(days=value)
            elif unit == 'W':
                cutoff_date = latest_date - timedelta(weeks=value)
            elif unit == 'M':
                cutoff_date = latest_date - timedelta(days=value * 30)
            elif unit == 'Y':
                cutoff_date = latest_date - timedelta(days=value * 365)
            else:
                continue
            
            # Filtrer les avis pour cette période
            period_reviews = [
                review for review in sorted_reviews 
                if datetime.strptime(review.get('review_date', '2000-01-01'), '%Y-%m-%d') >= cutoff_date
            ]
            
            # Analyser le sentiment pour cette période
            period_sentiment = self.analyze_product_sentiment(period_reviews)
            
            trends[time_frame] = period_sentiment
        
        return trends

    def compare_sentiment_by_segments(self, reviews: List[Dict[str, Any]], segment_field: str = 'segment') -> Dict[str, Any]:
        """
        Compare les sentiments entre différents segments de clients.
        
        Args:
            reviews: Liste d'avis avec segments de clients
            segment_field: Nom du champ contenant le segment
            
        Returns:
            Comparaison de sentiment par segment
        """
        # Grouper les avis par segment
        segments = {}
        
        for review in reviews:
            segment = review.get(segment_field, 'unknown')
            
            if segment not in segments:
                segments[segment] = []
                
            segments[segment].append(review)
        
        # Analyser le sentiment pour chaque segment
        comparison = {}
        
        for segment, segment_reviews in segments.items():
            comparison[segment] = self.analyze_product_sentiment(segment_reviews)
        
        return comparison
    
    def extract_keywords(self, reviews: List[Dict[str, Any]], max_keywords: int = 20) -> List[Dict[str, int]]:
        """
        Extrait les mots-clés les plus fréquents des avis.
        
        Args:
            reviews: Liste d'avis
            max_keywords: Nombre maximum de mots-clés à extraire
            
        Returns:
            Liste de mots-clés avec leur fréquence
        """
        # Combiner tous les textes d'avis
        all_text = ' '.join([review.get('review_text', '') for review in reviews])
        
        # Tokeniser le texte
        words = word_tokenize(all_text.lower())
        
        # Supprimer les stop words et la ponctuation
        stop_words = set(stopwords.words(self.language))
        filtered_words = [word for word in words if word not in stop_words and word.isalnum() and len(word) > 2]
        
        # Compter les occurrences
        word_counts = Counter(filtered_words)
        
        # Extraire les mots-clés les plus fréquents
        top_keywords = word_counts.most_common(max_keywords)
        
        return [{'word': word, 'count': count} for word, count in top_keywords]