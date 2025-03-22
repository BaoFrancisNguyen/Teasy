"""
Module de segmentation client basé sur l'analyse des avis.
Identifie différents segments clients à partir de leurs commentaires.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CustomerSegmenter:
    """Segmenteur de clients basé sur l'analyse des avis"""
    
    def __init__(self, language: str = 'english'):
        """
        Initialise le segmenteur de clients.
        
        Args:
            language: Langue des textes à analyser ('english' ou 'french')
        """
        self.language = language
        
        # Définir des indicateurs pour les différents segments
        self.segment_indicators = self._initialize_segment_indicators()
        
        # Configuration des vecteurs de caractéristiques
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english' if language == 'english' else 'french',
            ngram_range=(1, 2)
        )
    
    def _initialize_segment_indicators(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Initialise les indicateurs de chaque segment client.
        Ces indicateurs sont des ensembles de mots-clés qui caractérisent chaque segment.
        
        Returns:
            Dictionnaire des indicateurs par segment
        """
        # Indicateurs en anglais par défaut
        indicators = {
            "tech_enthusiast": {
                "keywords": [
                    "latest", "innovative", "technology", "features", "specs", "advanced", 
                    "cutting edge", "high-end", "premium", "smart", "connected", "app", 
                    "bluetooth", "wifi", "wireless", "integration", "ecosystem"
                ],
                "topics": ["innovation", "technology", "features", "connectivity"],
                "value_factors": ["innovation", "performance", "features"]
            },
            "practical_user": {
                "keywords": [
                    "practical", "simple", "easy", "straightforward", "basic", "convenient", 
                    "useful", "functional", "everyday", "reliable", "intuitive", "works", 
                    "does the job", "value", "worth", "price"
                ],
                "topics": ["ease of use", "reliability", "practicality"],
                "value_factors": ["simplicity", "reliability", "price"]
            },
            "budget_conscious": {
                "keywords": [
                    "price", "affordable", "cheap", "budget", "cost", "expensive", "value", 
                    "money", "worth", "deal", "discount", "promotion", "saving", "alternative", 
                    "comparable", "cheaper"
                ],
                "topics": ["price", "value", "comparisons"],
                "value_factors": ["price", "value for money", "durability"]
            },
            "quality_seeker": {
                "keywords": [
                    "quality", "premium", "durable", "solid", "well-made", "craftsmanship", 
                    "robust", "build", "materials", "finish", "detail", "design", "construction", 
                    "high-quality", "performance", "reliable"
                ],
                "topics": ["quality", "durability", "performance"],
                "value_factors": ["quality", "durability", "design"]
            },
            "brand_loyal": {
                "keywords": [
                    "brand", "loyal", "always", "consistently", "previous", "upgrade", 
                    "replaced", "another", "same brand", "trust", "reputation", "recommend", 
                    "customer", "service", "warranty", "support", "experience"
                ],
                "topics": ["brand loyalty", "customer service", "trust"],
                "value_factors": ["brand reputation", "customer service", "consistency"]
            },
            "eco_conscious": {
                "keywords": [
                    "environmental", "eco", "sustainable", "energy", "efficient", "green", 
                    "consumption", "recyclable", "packaging", "carbon", "footprint", 
                    "responsible", "planet", "eco-friendly", "waste", "plastic"
                ],
                "topics": ["sustainability", "energy efficiency", "ethical consumption"],
                "value_factors": ["sustainability", "energy efficiency", "ethical practices"]
            }
        }
        
        # Traduire les indicateurs si la langue est le français
        if self.language == 'french':
            indicators = {
                "passionné_tech": {
                    "keywords": [
                        "dernier", "innovant", "technologie", "fonctionnalités", "specs", "avancé", 
                        "pointe", "haut de gamme", "premium", "intelligent", "connecté", "application", 
                        "bluetooth", "wifi", "sans fil", "intégration", "écosystème"
                    ],
                    "topics": ["innovation", "technologie", "fonctionnalités", "connectivité"],
                    "value_factors": ["innovation", "performance", "fonctionnalités"]
                },
                "utilisateur_pratique": {
                    "keywords": [
                        "pratique", "simple", "facile", "direct", "basique", "commode", 
                        "utile", "fonctionnel", "quotidien", "fiable", "intuitif", "fonctionne", 
                        "fait le travail", "valeur", "vaut", "prix"
                    ],
                    "topics": ["facilité d'utilisation", "fiabilité", "aspect pratique"],
                    "value_factors": ["simplicité", "fiabilité", "prix"]
                },
                "économe": {
                    "keywords": [
                        "prix", "abordable", "pas cher", "budget", "coût", "cher", "valeur", 
                        "argent", "vaut", "affaire", "remise", "promotion", "économie", "alternative", 
                        "comparable", "moins cher"
                    ],
                    "topics": ["prix", "valeur", "comparaisons"],
                    "value_factors": ["prix", "rapport qualité-prix", "durabilité"]
                },
                "chercheur_qualité": {
                    "keywords": [
                        "qualité", "premium", "durable", "solide", "bien fait", "fabrication", 
                        "robuste", "construction", "matériaux", "finition", "détail", "design", "conception", 
                        "haute qualité", "performance", "fiable"
                    ],
                    "topics": ["qualité", "durabilité", "performance"],
                    "value_factors": ["qualité", "durabilité", "design"]
                },
                "fidèle_marque": {
                    "keywords": [
                        "marque", "fidèle", "toujours", "constamment", "précédent", "mise à niveau", 
                        "remplacé", "autre", "même marque", "confiance", "réputation", "recommande", 
                        "client", "service", "garantie", "support", "expérience"
                    ],
                    "topics": ["fidélité à la marque", "service client", "confiance"],
                    "value_factors": ["réputation de la marque", "service client", "constance"]
                },
                "éco_conscient": {
                    "keywords": [
                        "environnemental", "éco", "durable", "énergie", "efficient", "vert", 
                        "consommation", "recyclable", "emballage", "carbone", "empreinte", 
                        "responsable", "planète", "écologique", "déchet", "plastique"
                    ],
                    "topics": ["durabilité", "efficacité énergétique", "consommation éthique"],
                    "value_factors": ["durabilité", "efficacité énergétique", "pratiques éthiques"]
                }
            }
        
        return indicators
    
    def segment_customer(self, reviews: List[Dict[str, Any]]) -> str:
        """
        Détermine le segment d'un client basé sur ses avis.
        
        Args:
            reviews: Liste des avis du client
            
        Returns:
            Segment client (ex: "tech_enthusiast")
        """
        if not reviews:
            return "unknown"
        
        # Concaténer tous les textes d'avis
        all_text = ' '.join([review.get('review_text', '') for review in reviews])
        all_text = all_text.lower()
        
        # Calculer les scores de correspondance pour chaque segment
        segment_scores = {}
        
        for segment, indicators in self.segment_indicators.items():
            # Compter les occurrences de mots-clés
            keywords = indicators.get('keywords', [])
            keyword_count = sum(1 for keyword in keywords if keyword.lower() in all_text)
            
            # Pondérer le score en fonction du nombre total de mots-clés
            keyword_score = keyword_count / len(keywords) if keywords else 0
            
            # Vérifier les sujets abordés
            topics = indicators.get('topics', [])
            topic_count = sum(1 for topic in topics if topic.lower() in all_text)
            topic_score = topic_count / len(topics) if topics else 0
            
            # Vérifier les facteurs de valeur mentionnés
            value_factors = indicators.get('value_factors', [])
            value_count = sum(1 for factor in value_factors if factor.lower() in all_text)
            value_score = value_count / len(value_factors) if value_factors else 0
            
            # Calculer le score composite (différentes pondérations possibles)
            composite_score = (0.5 * keyword_score) + (0.3 * topic_score) + (0.2 * value_score)
            segment_scores[segment] = composite_score
        
        # Déterminer le segment avec le score le plus élevé
        best_segment = max(segment_scores.items(), key=lambda x: x[1])
        
        # Si le meilleur score est trop faible, considérer comme inconnu
        if best_segment[1] < 0.1:
            return "unknown"
        
        return best_segment[0]
    
    def segment_customers_rule_based(self, customer_reviews: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """
        Segmente un ensemble de clients selon une approche basée sur des règles.
        
        Args:
            customer_reviews: Dictionnaire {reviewer_id: [avis]}
            
        Returns:
            Dictionnaire {reviewer_id: segment}
        """
        segments = {}
        
        for reviewer_id, reviews in customer_reviews.items():
            segment = self.segment_customer(reviews)
            segments[reviewer_id] = segment
        
        return segments
    
    def segment_customers_clustering(self, customer_reviews: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """
        Segmente un ensemble de clients par clustering de leurs avis.
        
        Args:
            customer_reviews: Dictionnaire {reviewer_id: [avis]}
            
        Returns:
            Dictionnaire {reviewer_id: segment}
        """
        # Préparer les données pour le clustering
        reviewer_ids = []
        review_texts = []
        
        for reviewer_id, reviews in customer_reviews.items():
            # Concaténer tous les avis d'un même client
            combined_text = ' '.join([review.get('review_text', '') for review in reviews])
            
            reviewer_ids.append(reviewer_id)
            review_texts.append(combined_text)
        
        # Si aucun avis, retourner un dictionnaire vide
        if not review_texts:
            return {}
        
        # Vectoriser les textes
        try:
            X = self.vectorizer.fit_transform(review_texts)
            
            # Réduire la dimensionnalité pour faciliter le clustering
            pca = PCA(n_components=min(10, X.shape[0], X.shape[1]), random_state=42)
            X_reduced = pca.fit_transform(X.toarray())
            
            # Trouver le nombre optimal de clusters (entre 2 et 6)
            best_n_clusters = 3  # Valeur par défaut
            best_score = -1
            
            for n_clusters in range(2, min(7, len(reviewer_ids) + 1)):
                if n_clusters >= len(reviewer_ids):
                    continue
                    
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                cluster_labels = kmeans.fit_predict(X_reduced)
                
                if len(set(cluster_labels)) > 1:  # Au moins 2 clusters différents
                    score = silhouette_score(X_reduced, cluster_labels)
                    
                    if score > best_score:
                        best_score = score
                        best_n_clusters = n_clusters
            
            # Appliquer KMeans avec le nombre optimal de clusters
            kmeans = KMeans(n_clusters=best_n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(X_reduced)
            
            # Analyser les clusters pour leur attribuer un nom de segment
            segments = {}
            
            # Pour chaque cluster, déterminer les mots les plus caractéristiques
            cluster_keywords = self._extract_cluster_keywords(X, cluster_labels)
            
            # Associer chaque cluster à un segment prédéfini
            cluster_to_segment = self._map_clusters_to_segments(cluster_keywords)
            
            # Assigner les segments aux clients
            for i, reviewer_id in enumerate(reviewer_ids):
                cluster_id = cluster_labels[i]
                segment = cluster_to_segment.get(cluster_id, f"segment_{cluster_id}")
                segments[reviewer_id] = segment
            
            return segments
            
        except Exception as e:
            logger.error(f"Erreur lors du clustering des clients: {e}")
            
            # Fallback : utiliser l'approche basée sur des règles
            return self.segment_customers_rule_based(customer_reviews)
    
    def _extract_cluster_keywords(self, X, cluster_labels) -> Dict[int, List[str]]:
        """
        Extrait les mots-clés les plus caractéristiques de chaque cluster.
        
        Args:
            X: Matrice TF-IDF des textes
            cluster_labels: Étiquettes de cluster pour chaque texte
            
        Returns:
            Dictionnaire {cluster_id: [mots-clés]}
        """
        # Obtenir les noms des features (mots)
        feature_names = self.vectorizer.get_feature_names_out()
        
        # Pour chaque cluster, calculer la moyenne des vecteurs TF-IDF
        cluster_keywords = {}
        
        for cluster_id in set(cluster_labels):
            # Indices des documents dans ce cluster
            indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
            
            # Extraire les vecteurs TF-IDF pour ces documents
            cluster_vectors = X[indices].toarray()
            
            # Calculer la moyenne des vecteurs
            centroid = np.mean(cluster_vectors, axis=0)
            
            # Extraire les 20 mots avec les scores TF-IDF les plus élevés
            top_features_idx = centroid.argsort()[-20:]
            top_keywords = [feature_names[idx] for idx in top_features_idx]
            
            cluster_keywords[cluster_id] = top_keywords
        
        return cluster_keywords
    
    def _map_clusters_to_segments(self, cluster_keywords) -> Dict[int, str]:
        """
        Associe chaque cluster à un segment prédéfini en fonction des mots-clés.
        
        Args:
            cluster_keywords: Dictionnaire {cluster_id: [mots-clés]}
            
        Returns:
            Dictionnaire {cluster_id: nom_segment}
        """
        cluster_to_segment = {}
        
        for cluster_id, keywords in cluster_keywords.items():
            # Calculer le score de correspondance pour chaque segment
            segment_scores = {}
            
            for segment, indicators in self.segment_indicators.items():
                segment_keywords = set(indicators.get('keywords', []))
                
                # Compter les mots-clés du segment présents dans les mots-clés du cluster
                # Compter les mots-clés du segment présents dans les mots-clés du cluster
                matching_keywords = sum(1 for kw in keywords if any(seg_kw.lower() in kw.lower() for seg_kw in segment_keywords))
                
                # Calculer un score de correspondance normalisé
                score = matching_keywords / len(keywords) if keywords else 0
                segment_scores[segment] = score
            
            # Assigner le segment avec le score le plus élevé
            if segment_scores:
                best_segment = max(segment_scores.items(), key=lambda x: x[1])
                
                # Si le score est suffisamment élevé
                if best_segment[1] >= 0.1:
                    cluster_to_segment[cluster_id] = best_segment[0]
                else:
                    # Sinon, attribuer un nom générique
                    cluster_to_segment[cluster_id] = f"segment_{cluster_id}"
            else:
                cluster_to_segment[cluster_id] = f"segment_{cluster_id}"
        
        return cluster_to_segment
    
    def extract_segment_personas(self, customer_reviews: Dict[str, List[Dict[str, Any]]], 
                                customer_segments: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """
        Génère des personas pour chaque segment basés sur les avis.
        
        Args:
            customer_reviews: Dictionnaire {reviewer_id: [avis]}
            customer_segments: Dictionnaire {reviewer_id: segment}
            
        Returns:
            Dictionnaire des personas par segment
        """
        # Regrouper les avis par segment
        segment_reviews = defaultdict(list)
        
        for reviewer_id, segment in customer_segments.items():
            if reviewer_id in customer_reviews:
                reviews = customer_reviews[reviewer_id]
                for review in reviews:
                    # Ajouter le segment au review pour l'analyse future
                    review_with_segment = review.copy()
                    review_with_segment['segment'] = segment
                    segment_reviews[segment].append(review_with_segment)
        
        # Générer un persona pour chaque segment
        personas = {}
        
        for segment, reviews in segment_reviews.items():
            if not reviews:
                continue
                
            # Statistiques de base
            review_count = len(reviews)
            avg_rating = sum(r.get('rating', 0) for r in reviews if r.get('rating') is not None) / review_count if review_count > 0 else 0
            
            # Extraire les produits les plus populaires pour ce segment
            product_counts = Counter([r.get('product_name', 'Unknown') for r in reviews])
            top_products = product_counts.most_common(5)
            
            # Extraire les marques les plus populaires
            brand_counts = Counter([r.get('product_brand', 'Unknown') for r in reviews])
            top_brands = brand_counts.most_common(3)
            
            # Extraire les catégories les plus populaires
            category_counts = Counter([r.get('product_category', 'Unknown') for r in reviews])
            top_categories = category_counts.most_common(3)
            
            # Extraire les mots-clés les plus fréquents
            all_text = ' '.join([r.get('review_text', '') for r in reviews])
            keywords = self._extract_keywords_from_text(all_text, max_keywords=10)
            
            # Créer le persona
            personas[segment] = {
                'segment_name': segment,
                'review_count': review_count,
                'average_rating': avg_rating,
                'top_products': [{'name': p[0], 'count': p[1]} for p in top_products],
                'top_brands': [{'name': b[0], 'count': b[1]} for b in top_brands],
                'top_categories': [{'name': c[0], 'count': c[1]} for c in top_categories],
                'keywords': keywords,
                'summary': self._generate_segment_summary(segment, reviews),
                'preferences': self._extract_segment_preferences(reviews),
                'pain_points': self._extract_segment_pain_points(reviews)
            }
        
        return personas
    
    def _extract_keywords_from_text(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extrait les mots-clés les plus fréquents d'un texte.
        
        Args:
            text: Texte à analyser
            max_keywords: Nombre maximum de mots-clés à extraire
            
        Returns:
            Liste de mots-clés
        """
        import nltk
        from nltk.corpus import stopwords
        from nltk.tokenize import word_tokenize
        
        # Télécharger les ressources NLTK si nécessaire
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
            
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        # Tokeniser le texte
        words = word_tokenize(text.lower())
        
        # Supprimer les stop words et les mots courts
        stop_words = set(stopwords.words(self.language))
        filtered_words = [word for word in words if word.isalnum() and len(word) > 3 and word not in stop_words]
        
        # Compter les occurrences
        word_counts = Counter(filtered_words)
        
        # Extraire les mots-clés les plus fréquents
        return [word for word, count in word_counts.most_common(max_keywords)]
    
    def _generate_segment_summary(self, segment: str, reviews: List[Dict[str, Any]]) -> str:
        """
        Génère un résumé du segment client.
        
        Args:
            segment: Nom du segment
            reviews: Liste d'avis du segment
            
        Returns:
            Résumé textuel du segment
        """
        # Récupérer les indicateurs du segment
        indicators = self.segment_indicators.get(segment, {})
        
        # Si aucun indicateur, générer un résumé générique
        if not indicators:
            return f"Segment {segment} avec {len(reviews)} avis."
        
        # Statistiques de base
        avg_rating = sum(r.get('rating', 0) for r in reviews if r.get('rating') is not None) / len(reviews) if reviews else 0
        
        # Calculer les aspects les plus mentionnés
        aspect_mentions = defaultdict(int)
        for review in reviews:
            review_text = review.get('review_text', '').lower()
            for aspect_category, aspect_keywords in self.aspects.items():
                for keyword in aspect_keywords:
                    if keyword in review_text:
                        aspect_mentions[aspect_category] += 1
                        break
        
        top_aspects = sorted(aspect_mentions.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Générer le résumé
        value_factors = ', '.join(indicators.get('value_factors', []))
        
        summary = f"Les clients du segment {segment} accordent de l'importance à {value_factors}. "
        
        if top_aspects:
            aspects_text = ', '.join([f"{aspect}" for aspect, count in top_aspects])
            summary += f"Ils mentionnent souvent {aspects_text} dans leurs avis. "
            
        summary += f"Leur note moyenne est de {avg_rating:.1f}/5."
        
        return summary
    
    def _extract_segment_preferences(self, reviews: List[Dict[str, Any]]) -> List[str]:
        """
        Extrait les préférences d'un segment à partir des avis positifs.
        
        Args:
            reviews: Liste d'avis du segment
            
        Returns:
            Liste des préférences identifiées
        """
        # Filtrer les avis positifs (rating > 3)
        positive_reviews = [r for r in reviews if r.get('rating', 0) >= 4]
        
        # Si aucun avis positif, retourner une liste vide
        if not positive_reviews:
            return []
        
        # Combiner les textes des avis positifs
        positive_text = ' '.join([r.get('review_text', '') for r in positive_reviews])
        
        # Extraire les aspects fréquemment mentionnés positivement
        preferences = []
        
        for aspect_category, aspect_keywords in self.aspects.items():
            for keyword in aspect_keywords:
                if keyword in positive_text.lower():
                    preferences.append(aspect_category)
                    break
        
        return preferences
    
    def _extract_segment_pain_points(self, reviews: List[Dict[str, Any]]) -> List[str]:
        """
        Extrait les points de douleur d'un segment à partir des avis négatifs.
        
        Args:
            reviews: Liste d'avis du segment
            
        Returns:
            Liste des points de douleur identifiés
        """
        # Filtrer les avis négatifs (rating < 3)
        negative_reviews = [r for r in reviews if r.get('rating', 0) <= 2]
        
        # Si aucun avis négatif, retourner une liste vide
        if not negative_reviews:
            return []
        
        # Combiner les textes des avis négatifs
        negative_text = ' '.join([r.get('review_text', '') for r in negative_reviews])
        
        # Extraire les aspects fréquemment mentionnés négativement
        pain_points = []
        
        for aspect_category, aspect_keywords in self.aspects.items():
            for keyword in aspect_keywords:
                if keyword in negative_text.lower():
                    pain_points.append(aspect_category)
                    break
        
        return pain_points
    
    # Ajouter ici tout autre attribut ou méthode nécessaire pour la segmentation