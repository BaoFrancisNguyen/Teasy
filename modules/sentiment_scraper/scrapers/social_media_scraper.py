"""
Module de scraping pour les avis et mentions sur les réseaux sociaux.
Extrait les commentaires, mentions et réactions concernant des produits ou marques.
"""

import os
import time
import random
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SocialMediaScraper:
    """Scraper pour les mentions et avis sur les réseaux sociaux"""
    
    def __init__(self, 
                 api_keys: Optional[Dict[str, str]] = None, 
                 proxy: Optional[str] = None,
                 cache_dir: str = "cache/social_media"):
        """
        Initialise le scraper pour réseaux sociaux.
        
        Args:
            api_keys: Dictionnaire des clés API pour les différentes plateformes
            proxy: Proxy à utiliser pour les requêtes (format 'ip:port')
            cache_dir: Répertoire où stocker les données en cache
        """
        self.api_keys = api_keys or {}
        self.proxy = proxy
        self.cache_dir = cache_dir
        
        # Créer le répertoire de cache s'il n'existe pas
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialiser une session HTTP standard
        self.session = requests.Session()
        
        # Configuration du proxy si spécifié
        if proxy:
            self.session.proxies.update({
                'http': f'http://{proxy}',
                'https': f'https://{proxy}'
            })
    
    def _get_cache_file(self, platform: str, query: str, time_period: str) -> str:
        """
        Obtient le chemin du fichier de cache pour une requête donnée.
        
        Args:
            platform: Nom de la plateforme (twitter, instagram, etc.)
            query: Requête de recherche
            time_period: Période temporelle (1d, 7d, 30d, etc.)
            
        Returns:
            Chemin du fichier de cache
        """
        # Nettoyer la requête pour l'utiliser dans un nom de fichier
        clean_query = "".join(c if c.isalnum() else "_" for c in query)
        return os.path.join(self.cache_dir, f"{platform}_{clean_query}_{time_period}.json")
    
    def _load_from_cache(self, cache_file: str, max_age_hours: int = 24) -> Optional[List[Dict[str, Any]]]:
        """
        Charge les données depuis le cache si disponibles et pas trop anciennes.
        
        Args:
            cache_file: Chemin du fichier de cache
            max_age_hours: Âge maximum du cache en heures
            
        Returns:
            Données chargées ou None si le cache est invalide/absent
        """
        if not os.path.exists(cache_file):
            return None
        
        # Vérifier l'âge du fichier
        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
        if file_age > timedelta(hours=max_age_hours):
            logger.info(f"Cache trop ancien ({file_age.total_seconds() / 3600:.1f} heures) : {cache_file}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement du cache : {e}")
            return None
    
    def _save_to_cache(self, cache_file: str, data: List[Dict[str, Any]]) -> bool:
        """
        Sauvegarde les données dans le cache.
        
        Args:
            cache_file: Chemin du fichier de cache
            data: Données à sauvegarder
            
        Returns:
            True si la sauvegarde a réussi, False sinon
        """
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du cache : {e}")
            return False
    
    def search_twitter(self, 
                      query: str, 
                      time_period: str = "7d", 
                      max_results: int = 100, 
                      include_sentiment: bool = True) -> List[Dict[str, Any]]:
        """
        Recherche des mentions sur Twitter (X).
        
        Args:
            query: Terme de recherche (marque, produit, etc.)
            time_period: Période temporelle ('1d', '7d', '30d', '90d')
            max_results: Nombre maximum de résultats à retourner
            include_sentiment: Inclure une analyse de sentiment basique
            
        Returns:
            Liste de tweets correspondant à la recherche
        """
        # Vérifier si une API key est disponible
        if 'twitter' not in self.api_keys:
            logger.warning("Pas de clé API Twitter configurée. Utilisation de données simulées.")
            return self._simulate_twitter_data(query, max_results)
        
        # Essayer de charger depuis le cache
        cache_file = self._get_cache_file('twitter', query, time_period)
        cached_data = self._load_from_cache(cache_file)
        
        if cached_data:
            logger.info(f"Données Twitter chargées depuis le cache pour '{query}'")
            return cached_data[:max_results]
        
        # Construire les paramètres de recherche
        endpoint = "https://api.twitter.com/2/tweets/search/recent"
        
        # Convertir la période en format ISO 8601
        end_time = datetime.now()
        if time_period.endswith('d'):
            days = int(time_period[:-1])
            start_time = end_time - timedelta(days=days)
        elif time_period.endswith('h'):
            hours = int(time_period[:-1])
            start_time = end_time - timedelta(hours=hours)
        else:
            # Par défaut, 7 jours
            start_time = end_time - timedelta(days=7)
        
        # Formater les dates
        start_time_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_iso = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            'query': query,
            'start_time': start_time_iso,
            'end_time': end_time_iso,
            'max_results': min(100, max_results),  # Maximum 100 par requête API
            'tweet.fields': 'created_at,public_metrics,author_id',
            'user.fields': 'name,username,profile_image_url,verified',
            'expansions': 'author_id'
        }
        
        headers = {
            'Authorization': f"Bearer {self.api_keys['twitter']}",
            'Content-Type': 'application/json'
        }
        
        try:
            # Utilisation de données simulées pour la démo
            # Dans un environnement de production, remplacer par l'appel API réel
            # response = self.session.get(endpoint, params=params, headers=headers)
            # response.raise_for_status()
            # result = response.json()
            
            # Simulation pour la démo
            result = self._simulate_twitter_data(query, max_results)
            
            # Enregistrer dans le cache
            self._save_to_cache(cache_file, result)
            
            return result[:max_results]
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Twitter : {e}")
            return self._simulate_twitter_data(query, max_results)
    
    def _simulate_twitter_data(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Simule des données Twitter pour la démonstration.
        
        Args:
            query: Terme de recherche
            max_results: Nombre maximum de résultats à simuler
            
        Returns:
            Liste de tweets simulés
        """
        # Exemples d'auteurs
        authors = [
            {"id": "user123", "name": "Jean Dupont", "username": "jdupont", "verified": False},
            {"id": "user456", "name": "Marie Martin", "username": "marie_m", "verified": True},
            {"id": "user789", "name": "Tech Reviewer", "username": "tech_review", "verified": True},
            {"id": "user101", "name": "Consomm'Acteur", "username": "conso_acteur", "verified": False},
            {"id": "user202", "name": "Gadget Fan", "username": "gadget_addict", "verified": False}
        ]
        
        # Exemples de sentiments positifs
        positive_templates = [
            f"J'adore mon nouveau {query} ! Tellement satisfait de cet achat.",
            f"Le {query} est vraiment bien pensé, excellente expérience utilisateur.",
            f"Très impressionné par la qualité du {query}, ça vaut vraiment le prix.",
            f"Le service client de {query} est top, problème résolu en quelques minutes.",
            f"Je recommande vivement {query} à tous ceux qui cherchent un produit fiable."
        ]
        
        # Exemples de sentiments neutres
        neutral_templates = [
            f"Je viens d'acheter un {query}, je vous dirai ce que j'en pense après quelques jours.",
            f"Quelqu'un a des infos sur la sortie du prochain {query} ?",
            f"Est-ce que le {query} est compatible avec mon installation actuelle ?",
            f"Je compare le {query} avec d'autres marques avant de me décider.",
            f"Le prix du {query} vient de changer, à surveiller si vous vouliez l'acheter."
        ]
        
        # Exemples de sentiments négatifs
        negative_templates = [
            f"Déçu par mon {query}, ne répond pas à mes attentes malgré le prix élevé.",
            f"Problème de fiabilité avec le {query}, déjà en panne après 2 mois...",
            f"Le service après-vente de {query} est vraiment à revoir, 3 semaines pour une réponse !",
            f"Attention aux arnaques avec les {query} contrefaits qui circulent partout.",
            f"Je regrette mon achat du {query}, l'ancien modèle était bien meilleur."
        ]
        
        # Générer des tweets simulés
        tweets = []
        sentiment_options = ["positive", "neutral", "negative"]
        sentiment_weights = [0.5, 0.3, 0.2]  # Distribution de probabilité
        
        for i in range(min(max_results, 50)):  # Limiter à 50 simulations max
            # Choisir aléatoirement un auteur et un sentiment
            author = random.choice(authors)
            sentiment = random.choices(sentiment_options, sentiment_weights)[0]
            
            # Choisir un modèle en fonction du sentiment
            if sentiment == "positive":
                text = random.choice(positive_templates)
                score = random.uniform(0.6, 1.0)
            elif sentiment == "neutral":
                text = random.choice(neutral_templates)
                score = random.uniform(-0.3, 0.3)
            else:
                text = random.choice(negative_templates)
                score = random.uniform(-1.0, -0.6)
            
            # Générer une date aléatoire dans les 7 derniers jours
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            created_at = (datetime.now() - timedelta(days=days_ago, hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Créer le tweet
            tweet = {
                "id": f"tweet{i+1000}",
                "source": "twitter",
                "text": text,
                "created_at": created_at,
                "author": {
                    "id": author["id"],
                    "name": author["name"],
                    "username": author["username"],
                    "verified": author["verified"]
                },
                "metrics": {
                    "retweet_count": random.randint(0, 50),
                    "reply_count": random.randint(0, 20),
                    "like_count": random.randint(0, 100),
                    "quote_count": random.randint(0, 10)
                },
                "sentiment": {
                    "label": sentiment,
                    "score": score
                },
                "product_mentions": [{
                    "product": query,
                    "confidence": random.uniform(0.8, 1.0)
                }]
            }
            
            tweets.append(tweet)
        
        return tweets
    
    def search_instagram(self, 
                        query: str, 
                        time_period: str = "7d", 
                        max_results: int = 100, 
                        include_sentiment: bool = True) -> List[Dict[str, Any]]:
        """
        Recherche des mentions sur Instagram.
        
        Args:
            query: Terme de recherche (marque, produit, etc.)
            time_period: Période temporelle ('1d', '7d', '30d', '90d')
            max_results: Nombre maximum de résultats à retourner
            include_sentiment: Inclure une analyse de sentiment basique
            
        Returns:
            Liste de posts Instagram correspondant à la recherche
        """
        # Instagram nécessite l'API Facebook Graph, mais nous utiliserons des données simulées
        logger.info(f"Recherche Instagram pour '{query}' (simulée)")
        
        # Essayer de charger depuis le cache
        cache_file = self._get_cache_file('instagram', query, time_period)
        cached_data = self._load_from_cache(cache_file)
        
        if cached_data:
            logger.info(f"Données Instagram chargées depuis le cache pour '{query}'")
            return cached_data[:max_results]
        
        # Simuler des données Instagram
        posts = self._simulate_instagram_data(query, max_results)
        
        # Enregistrer dans le cache
        self._save_to_cache(cache_file, posts)
        
        return posts
    
    def _simulate_instagram_data(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Simule des données Instagram pour la démonstration.
        
        Args:
            query: Terme de recherche
            max_results: Nombre maximum de résultats à simuler
            
        Returns:
            Liste de posts Instagram simulés
        """
        # Exemples de légendes positives
        positive_captions = [
            f"Mon nouveau {query} est arrivé ! 😍 #new #happy #shopping",
            f"Tellement content de mon achat {query} ! La qualité est au rendez-vous ✨ #quality #premium",
            f"Le {query} change vraiment la donne, meilleur investissement de l'année 👌 #worthit",
            f"Petit cadeau à moi-même : le {query} tant attendu ! #treatyourself #noregrets",
            f"Coup de cœur pour ce {query} 💖 #love #musthave #recommendation"
        ]
        
        # Exemples de légendes neutres
        neutral_captions = [
            f"Test du {query} en cours... Vous en pensez quoi vous ? #testing #newproduct",
            f"Unboxing de mon {query} ! #unboxing #newstuff",
            f"Le {query} dans mon setup actuel. Des suggestions d'amélioration ? #setup #advice",
            f"Journée shopping : j'ai craqué pour le {query} #shopping #newthings",
            f"Quand tu hésites entre plusieurs modèles de {query}... 🤔 #choices #help"
        ]
        
        # Exemples de légendes négatives
        negative_captions = [
            f"Déception avec le {query}... Pas à la hauteur de mes attentes 😕 #disappointed",
            f"Problèmes de qualité avec mon {query}, déjà cassé ! #quality #issues #waste",
            f"Le {query} ne fonctionne pas comme prévu, c'est frustrant 😤 #frustrated #help",
            f"Je déconseille le {query}, trop cher pour ce que c'est ! #overpriced #notworth",
            f"Retour du {query} au magasin... Service client horrible en plus ! #badservice #return"
        ]
        
        # Générer des posts simulés
        posts = []
        sentiment_options = ["positive", "neutral", "negative"]
        sentiment_weights = [0.6, 0.25, 0.15]  # Distribution de probabilité
        
        for i in range(min(max_results, 50)):  # Limiter à 50 simulations max
            # Choisir aléatoirement un sentiment
            sentiment = random.choices(sentiment_options, sentiment_weights)[0]
            
            # Choisir une légende en fonction du sentiment
            if sentiment == "positive":
                caption = random.choice(positive_captions)
                score = random.uniform(0.6, 1.0)
            elif sentiment == "neutral":
                caption = random.choice(neutral_captions)
                score = random.uniform(-0.3, 0.3)
            else:
                caption = random.choice(negative_captions)
                score = random.uniform(-1.0, -0.6)
            
            # Générer une date aléatoire dans les 7 derniers jours
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            created_at = (datetime.now() - timedelta(days=days_ago, hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Créer le post
            post = {
                "id": f"post{i+2000}",
                "source": "instagram",
                "caption": caption,
                "created_at": created_at,
                "author": {
                    "id": f"user{i+3000}",
                    "username": f"insta_user_{random.randint(100, 999)}",
                    "is_verified": random.random() < 0.1  # 10% de chance d'être vérifié
                },
                "metrics": {
                    "like_count": random.randint(10, 500),
                    "comment_count": random.randint(0, 50)
                },
                "sentiment": {
                    "label": sentiment,
                    "score": score
                },
                "product_mentions": [{
                    "product": query,
                    "confidence": random.uniform(0.7, 1.0)
                }],
                "hashtags": [tag.replace('#', '') for tag in caption.split() if tag.startswith('#')]
            }
            
            posts.append(post)
        
        return posts
    
    def search_reddit(self, 
                     query: str, 
                     time_period: str = "7d", 
                     max_results: int = 100, 
                     include_sentiment: bool = True) -> List[Dict[str, Any]]:
        """
        Recherche des mentions sur Reddit.
        
        Args:
            query: Terme de recherche (marque, produit, etc.)
            time_period: Période temporelle ('1d', '7d', '30d', '90d')
            max_results: Nombre maximum de résultats à retourner
            include_sentiment: Inclure une analyse de sentiment basique
            
        Returns:
            Liste de posts et commentaires Reddit correspondant à la recherche
        """
        # Vérifier si une API key est disponible
        if 'reddit' not in self.api_keys:
            logger.warning("Pas de clé API Reddit configurée. Utilisation de données simulées.")
            return self._simulate_reddit_data(query, max_results)
        
        # Essayer de charger depuis le cache
        cache_file = self._get_cache_file('reddit', query, time_period)
        cached_data = self._load_from_cache(cache_file)
        
        if cached_data:
            logger.info(f"Données Reddit chargées depuis le cache pour '{query}'")
            return cached_data[:max_results]
        
        # Dans un environnement de production, remplacer par l'appel API réel à l'API Reddit
        # Ici, nous utilisons des données simulées pour la démo
        result = self._simulate_reddit_data(query, max_results)
        
        # Enregistrer dans le cache
        self._save_to_cache(cache_file, result)
        
        return result[:max_results]
    
    def _simulate_reddit_data(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Simule des données Reddit pour la démonstration.
        
        Args:
            query: Terme de recherche
            max_results: Nombre maximum de résultats à simuler
            
        Returns:
            Liste de posts Reddit simulés
        """
        # Exemples de titres/textes positifs
        positive_texts = [
            f"Retour d'expérience très positif sur le {query}",
            f"Je suis impressionné par le {query}, voici pourquoi...",
            f"Le {query} a dépassé toutes mes attentes ! Petit review après 3 mois d'utilisation",
            f"Pourquoi le {query} est devenu mon produit préféré cette année",
            f"Après avoir tout essayé, le {query} reste le meilleur choix"
        ]
        
        # Exemples de titres/textes neutres
        neutral_texts = [
            f"Questions sur le {query} avant achat",
            f"Quelqu'un a des infos sur la prochaine version du {query} ?",
            f"Comparaison entre le {query} et ses concurrents",
            f"Discussion : Le {query} vaut-il son prix ?",
            f"Où acheter le {query} au meilleur prix ?"
        ]
        
        # Exemples de titres/textes négatifs
        negative_texts = [
            f"Problèmes avec le {query} : mon expérience catastrophique",
            f"Le {query} est-il surévalué ? Mon avis après 2 mois",
            f"Attention aux défauts de fabrication du {query}",
            f"J'ai retourné mon {query}, voici pourquoi",
            f"Le service client de {query} est horrible - mon témoignage"
        ]
        
        # Exemples de sous-reddits pertinents
        subreddits = [
            "tech", "gadgets", "BuyItForLife", "ProductReviews", "shopping", 
            f"{query.lower()}fans", "consumeradvice", "technology", "reviews", "deals"
        ]
        
        # Générer des posts simulés
        posts = []
        sentiment_options = ["positive", "neutral", "negative"]
        sentiment_weights = [0.45, 0.3, 0.25]  # Distribution de probabilité
        
        for i in range(min(max_results, 50)):  # Limiter à 50 simulations max
            # Choisir aléatoirement un sentiment
            sentiment = random.choices(sentiment_options, sentiment_weights)[0]
            
            # Choisir un texte en fonction du sentiment
            if sentiment == "positive":
                title = random.choice(positive_texts)
                body = f"J'utilise le {query} depuis quelques temps maintenant et je dois dire que c'est vraiment un excellent produit. La qualité de fabrication est impressionnante, les fonctionnalités sont complètes, et le rapport qualité-prix est excellent. Je recommande vivement !"
                score = random.uniform(0.6, 1.0)
            elif sentiment == "neutral":
                title = random.choice(neutral_texts)
                body = f"Je m'intéresse au {query} mais j'hésite encore. Quelqu'un a-t-il des retours d'expérience à partager ? Je cherche particulièrement des infos sur la durabilité et les performances au quotidien. Merci d'avance pour vos conseils."
                score = random.uniform(-0.3, 0.3)
            else:
                title = random.choice(negative_texts)
                body = f"J'ai acheté le {query} il y a un mois et je regrette déjà. Plusieurs problèmes sont apparus rapidement, le support client est inexistant, et le prix ne justifie absolument pas la qualité. Je ne recommande pas du tout."
                score = random.uniform(-1.0, -0.6)
            
            # Générer une date aléatoire dans les 7 derniers jours
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            created_at = (datetime.now() - timedelta(days=days_ago, hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Choisir un subreddit aléatoire
            subreddit = random.choice(subreddits)
            
            # Créer le post
            post = {
                "id": f"reddit_post_{i+4000}",
                "source": "reddit",
                "title": title,
                "body": body,
                "created_at": created_at,
                "subreddit": subreddit,
                "author": {
                    "username": f"redditor_{random.randint(1000, 9999)}"
                },
                "metrics": {
                    "score": random.randint(-10, 200),
                    "upvote_ratio": random.uniform(0.5, 1.0),
                    "num_comments": random.randint(0, 50)
                },
                "sentiment": {
                    "label": sentiment,
                    "score": score
                },
                "product_mentions": [{
                    "product": query,
                    "confidence": random.uniform(0.75, 1.0)
                }]
            }
            
            posts.append(post)
        
        return posts
    
    def search_all_platforms(self, 
                           query: str, 
                           time_period: str = "7d", 
                           max_results_per_platform: int = 30, 
                           include_sentiment: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Recherche des mentions sur toutes les plateformes supportées.
        
        Args:
            query: Terme de recherche (marque, produit, etc.)
            time_period: Période temporelle ('1d', '7d', '30d', '90d')
            max_results_per_platform: Nombre maximum de résultats par plateforme
            include_sentiment: Inclure une analyse de sentiment basique
            
        Returns:
            Dictionnaire avec les résultats par plateforme
        """
        logger.info(f"Recherche de mentions pour '{query}' sur toutes les plateformes")
        
        results = {}
        
        # Twitter
        results['twitter'] = self.search_twitter(
            query, time_period, max_results_per_platform, include_sentiment
        )
        
        # Instagram
        results['instagram'] = self.search_instagram(
            query, time_period, max_results_per_platform, include_sentiment
        )
        
        # Reddit
        results['reddit'] = self.search_reddit(
            query, time_period, max_results_per_platform, include_sentiment
        )
        
        return results
    
    def analyze_sentiment_distribution(self, data: List[Dict[str, Any]]) -> Dict[str, Union[float, int]]:
        """
        Analyse la distribution des sentiments dans un ensemble de données.
        
        Args:
            data: Liste de mentions avec analyse de sentiment
            
        Returns:
            Statistiques sur la distribution des sentiments
        """
        if not data:
            return {
                "positive_percentage": 0,
                "neutral_percentage": 0,
                "negative_percentage": 0,
                "average_score": 0,
                "total_mentions": 0
            }
        
        sentiments = {"positive": 0, "neutral": 0, "negative": 0}
        total_score = 0
        
        for item in data:
            if "sentiment" in item and "label" in item["sentiment"]:
                label = item["sentiment"]["label"]
                if label in sentiments:
                    sentiments[label] += 1
                
                if "score" in item["sentiment"]:
                    total_score += item["sentiment"]["score"]
        
        total = sum(sentiments.values())
        
        if total == 0:
            return {
                "positive_percentage": 0,
                "neutral_percentage": 0,
                "negative_percentage": 0,
                "average_score": 0,
                "total_mentions": 0
            }
        
        return {
            "positive_percentage": (sentiments["positive"] / total) * 100,
            "neutral_percentage": (sentiments["neutral"] / total) * 100,
            "negative_percentage": (sentiments["negative"] / total) * 100,
            "average_score": total_score / total,
            "total_mentions": total
        }
    
    def get_trending_topics(self, data: List[Dict[str, Any]], min_occurrences: int = 2) -> List[Dict[str, Union[str, int]]]:
        """
        Extrait les sujets tendance à partir des mentions.
        
        Args:
            data: Liste de mentions
            min_occurrences: Nombre minimum d'occurrences pour considérer un sujet comme tendance
            
        Returns:
            Liste de sujets tendance avec leur nombre d'occurrences
        """
        # Extraire le texte de chaque mention
        texts = []
        for item in data:
            if "text" in item:
                texts.append(item["text"])
            elif "body" in item:
                texts.append(item["body"])
            elif "caption" in item:
                texts.append(item["caption"])
            
        # Extraire les hashtags
        all_hashtags = []
        for item in data:
            if "hashtags" in item and isinstance(item["hashtags"], list):
                all_hashtags.extend(item["hashtags"])
        
        # Compter les occurrences
        hashtag_counts = {}
        for tag in all_hashtags:
            hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        
        # Filtrer et trier
        trending = [
            {"topic": tag, "occurrences": count}
            for tag, count in hashtag_counts.items()
            if count >= min_occurrences
        ]
        
        return sorted(trending, key=lambda x: x["occurrences"], reverse=True)
    
    def extract_top_influencers(self, data: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Identifie les utilisateurs les plus influents dans l'ensemble de données.
        
        Args:
            data: Liste de mentions
            top_n: Nombre d'influenceurs à retourner
            
        Returns:
            Liste des utilisateurs les plus influents
        """
        # Identifier les métriques par plateforme
        influencers = {}
        
        for item in data:
            author = None
            engagement = 0
            is_verified = False
            platform = item.get("source", "unknown")
            
            # Extraire les informations selon la plateforme
            if platform == "twitter":
                if "author" in item and "username" in item["author"]:
                    author = item["author"]["username"]
                    is_verified = item["author"].get("verified", False)
                    
                if "metrics" in item:
                    metrics = item["metrics"]
                    engagement = (
                        metrics.get("retweet_count", 0) * 2 +
                        metrics.get("like_count", 0) +
                        metrics.get("reply_count", 0) * 1.5 +
                        metrics.get("quote_count", 0) * 1.8
                    )
            
            elif platform == "instagram":
                if "author" in item and "username" in item["author"]:
                    author = item["author"]["username"]
                    is_verified = item["author"].get("is_verified", False)
                    
                if "metrics" in item:
                    metrics = item["metrics"]
                    engagement = (
                        metrics.get("like_count", 0) +
                        metrics.get("comment_count", 0) * 2
                    )
            
            elif platform == "reddit":
                if "author" in item and "username" in item["author"]:
                    author = item["author"]["username"]
                    
                if "metrics" in item:
                    metrics = item["metrics"]
                    engagement = (
                        metrics.get("score", 0) +
                        metrics.get("num_comments", 0) * 3
                    )
            
            # Ajouter ou mettre à jour l'auteur
            if author:
                if author not in influencers:
                    influencers[author] = {
                        "username": author,
                        "platform": platform,
                        "is_verified": is_verified,
                        "total_engagement": 0,
                        "mention_count": 0,
                        "average_sentiment": 0,
                        "sentiment_sum": 0
                    }
                
                influencers[author]["total_engagement"] += engagement
                influencers[author]["mention_count"] += 1
                
                # Ajouter le sentiment s'il est disponible
                if "sentiment" in item and "score" in item["sentiment"]:
                    influencers[author]["sentiment_sum"] += item["sentiment"]["score"]
        
        # Calculer le sentiment moyen et trier par engagement
        for username, data in influencers.items():
            if data["mention_count"] > 0:
                data["average_sentiment"] = data["sentiment_sum"] / data["mention_count"]
            del data["sentiment_sum"]
        
        # Convertir en liste et trier
        influencers_list = list(influencers.values())
        influencers_list.sort(key=lambda x: x["total_engagement"], reverse=True)
        
        return influencers_list[:top_n]
    
    def generate_word_cloud_data(self, data: List[Dict[str, Any]], exclude_words: List[str] = None) -> List[Dict[str, Union[str, int]]]:
        """
        Génère des données pour un nuage de mots à partir des mentions.
        
        Args:
            data: Liste de mentions
            exclude_words: Liste de mots à exclure (mots vides, etc.)
            
        Returns:
            Liste de mots avec leur nombre d'occurrences
        """
        if not exclude_words:
            exclude_words = ["le", "la", "les", "un", "une", "des", "et", "ou", "de", "du", "au", "aux", 
                            "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses"]
        
        # Convertir en minuscules pour uniformisation
        exclude_words = [w.lower() for w in exclude_words]
        
        # Extraire tout le texte
        all_text = ""
        for item in data:
            if "text" in item:
                all_text += " " + item["text"].lower()
            elif "body" in item:
                all_text += " " + item["body"].lower()
            elif "caption" in item:
                all_text += " " + item["caption"].lower()
        
        # Nettoyer le texte (caractères spéciaux, liens, etc.)
        import re
        all_text = re.sub(r'https?://\S+', '', all_text)  # Supprimer les URLs
        all_text = re.sub(r'@\w+', '', all_text)  # Supprimer les mentions @
        all_text = re.sub(r'[^\w\s]', '', all_text)  # Supprimer la ponctuation
        
        # Diviser en mots
        words = all_text.split()
        
        # Compter les occurrences
        word_counts = {}
        for word in words:
            if len(word) > 2 and word not in exclude_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Convertir en liste et trier
        word_cloud_data = [{"text": word, "value": count} for word, count in word_counts.items()]
        word_cloud_data.sort(key=lambda x: x["value"], reverse=True)
        
        return word_cloud_data[:100]  # Limiter aux 100 mots les plus fréquents
    
    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> bool:
        """
        Exporte les données vers un fichier CSV.
        
        Args:
            data: Liste de mentions
            filename: Nom du fichier de sortie
            
        Returns:
            True si l'export a réussi, False sinon
        """
        if not data:
            logger.warning("Pas de données à exporter")
            return False
        
        try:
            import csv
            
            # Déterminer les colonnes en fonction de la première entrée
            first_item = data[0]
            platform = first_item.get("source", "unknown")
            
            # Définir les champs communs
            fields = ["id", "created_at"]
            
            # Ajouter les champs spécifiques à la plateforme
            if platform == "twitter":
                fields.extend(["text", "author.username", "author.name", "author.verified", 
                              "metrics.retweet_count", "metrics.like_count", "sentiment.label", "sentiment.score"])
            elif platform == "instagram":
                fields.extend(["caption", "author.username", "author.is_verified", 
                              "metrics.like_count", "metrics.comment_count", "sentiment.label", "sentiment.score", "hashtags"])
            elif platform == "reddit":
                fields.extend(["title", "body", "author.username", "subreddit", 
                              "metrics.score", "metrics.num_comments", "sentiment.label", "sentiment.score"])
            
            # Ouvrir le fichier et écrire l'en-tête
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Écrire l'en-tête
                header = [field.split('.')[-1] for field in fields]
                writer.writerow(header)
                
                # Écrire les données
                for item in data:
                    row = []
                    for field in fields:
                        # Gestion des champs imbriqués (e.g., metrics.retweet_count)
                        parts = field.split('.')
                        value = item
                        for part in parts:
                            if isinstance(value, dict) and part in value:
                                value = value[part]
                            else:
                                value = ""
                                break
                        row.append(value)
                    writer.writerow(row)
            
            logger.info(f"Données exportées avec succès vers {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export CSV : {e}")
            return False
    
    def export_to_json(self, data: List[Dict[str, Any]], filename: str) -> bool:
        """
        Exporte les données vers un fichier JSON.
        
        Args:
            data: Liste de mentions
            filename: Nom du fichier de sortie
            
        Returns:
            True si l'export a réussi, False sinon
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Données exportées avec succès vers {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export JSON : {e}")
            return False


# Exemple d'utilisation du module
if __name__ == "__main__":
    # Initialiser le scraper
    scraper = SocialMediaScraper(
        api_keys={
            # Ajouter vos clés API ici
            # 'twitter': 'YOUR_TWITTER_API_KEY',
            # 'reddit': 'YOUR_REDDIT_API_KEY'
        }
    )
    
    # Exemples de recherche
    product_name = "smartphones"
    
    # Rechercher sur Twitter
    twitter_results = scraper.search_twitter(product_name, time_period="7d", max_results=20)
    print(f"Mentions Twitter: {len(twitter_results)}")
    
    # Rechercher sur Instagram
    instagram_results = scraper.search_instagram(product_name, time_period="7d", max_results=20)
    print(f"Mentions Instagram: {len(instagram_results)}")
    
    # Rechercher sur Reddit
    reddit_results = scraper.search_reddit(product_name, time_period="7d", max_results=20)
    print(f"Mentions Reddit: {len(reddit_results)}")
    
    # Rechercher sur toutes les plateformes
    all_results = scraper.search_all_platforms(product_name)
    total_mentions = sum(len(results) for results in all_results.values())
    print(f"Total des mentions: {total_mentions}")
    
    # Analyser les sentiments
    all_mentions = []
    for platform, mentions in all_results.items():
        all_mentions.extend(mentions)
    
    sentiment_stats = scraper.analyze_sentiment_distribution(all_mentions)
    print(f"Distribution des sentiments:")
    print(f"  Positif: {sentiment_stats['positive_percentage']:.1f}%")
    print(f"  Neutre: {sentiment_stats['neutral_percentage']:.1f}%")
    print(f"  Négatif: {sentiment_stats['negative_percentage']:.1f}%")
    
    # Exporter les résultats (optionnel)
    # scraper.export_to_json(all_mentions, "mentions_produit.json")
    # scraper.export_to_csv(twitter_results, "mentions_twitter.csv")