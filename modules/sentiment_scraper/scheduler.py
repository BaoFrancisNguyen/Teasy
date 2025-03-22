"""
Module de planification des tâches de scraping et d'analyse.
Permet d'automatiser la récupération et l'analyse des avis clients.
"""

import os
import time
import json
import logging
import threading
import datetime
import schedule
from typing import List, Dict, Any, Callable, Optional

from .scrapers.amazon_scraper import AmazonScraper
from .scrapers.fnac_scraper import FnacScraper
from .scrapers.social_media_scraper import SocialMediaScraper
from .analyzers.sentiment_analyzer import SentimentAnalyzer
from .analyzers.entity_extractor import EntityExtractor
from .segmentation.customer_segmenter import CustomerSegmenter
from .data_manager import SentimentDataManager

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SentimentScraperScheduler:
    """Planificateur pour les tâches de scraping et d'analyse"""
    
    def __init__(self, config_path: str = 'modules/sentiment_scraper/config/scheduler.json'):
        """
        Initialise le planificateur.
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.running_tasks = {}
        self.lock = threading.Lock()
        
        # Initialiser les modules
        self.data_manager = SentimentDataManager()
        
        # Instancier les scrapers
        self.scrapers = {
            'amazon': AmazonScraper(),
            'fnac': FnacScraper(),
            'social_media': SocialMediaScraper()
        }
        
        # Instancier les analyseurs
        self.sentiment_analyzer = SentimentAnalyzer()
        self.entity_extractor = EntityExtractor()
        
        # Instancier le segmenteur
        self.customer_segmenter = CustomerSegmenter()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Charge la configuration depuis le fichier JSON.
        
        Returns:
            Configuration chargée ou configuration par défaut
        """
        default_config = {
            "tasks": {
                "scrape_amazon": {
                    "enabled": True,
                    "schedule": "daily",
                    "time": "01:00",
                    "max_products": 5,
                    "max_reviews_per_product": 20,
                    "products": [
                        {"keywords": "laptop", "category": "electronics"},
                        {"keywords": "smartphone", "category": "electronics"},
                        {"keywords": "refrigerator", "category": "appliances"}
                    ]
                },
                "scrape_fnac": {
                    "enabled": False,
                    "schedule": "daily",
                    "time": "02:00",
                    "max_products": 5,
                    "max_reviews_per_product": 20,
                    "products": [
                        {"keywords": "ordinateur portable", "category": "informatique"},
                        {"keywords": "smartphone", "category": "telephonie"},
                        {"keywords": "réfrigérateur", "category": "gros-electromenager"}
                    ]
                },
                "analyze_sentiments": {
                    "enabled": True,
                    "schedule": "daily",
                    "time": "03:00",
                    "batch_size": 100
                },
                "segment_customers": {
                    "enabled": True,
                    "schedule": "weekly",
                    "day": "monday",
                    "time": "04:00"
                },
                "generate_reports": {
                    "enabled": True,
                    "schedule": "weekly",
                    "day": "monday",
                    "time": "05:00"
                }
            },
            "settings": {
                "use_selenium": True,
                "headless": True,
                "proxy": None,
                "user_agent": "TEASY Sentiment Analyzer/1.0",
                "language": "english",
                "max_retries": 3,
                "retry_delay": 300
            }
        }
        
        try:
            # Créer le dossier de configuration s'il n'existe pas
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Charger la configuration si le fichier existe
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Sinon, créer le fichier avec la configuration par défaut
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            
            return default_config
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration: {e}")
            return default_config
    
    def save_config(self):
        """Sauvegarde la configuration actuelle dans le fichier JSON"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration sauvegardée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la configuration: {e}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        Met à jour la configuration.
        
        Args:
            new_config: Nouvelle configuration
        """
        with self.lock:
            self.config = new_config
            self.save_config()
            
            # Réinitialiser les tâches planifiées
            self.reset_scheduler()
            self.initialize_tasks()
    
    def reset_scheduler(self):
        """Réinitialise le planificateur en supprimant toutes les tâches"""
        schedule.clear()
        
        # Arrêter les tâches en cours
        for task_id, task_thread in list(self.running_tasks.items()):
            if task_thread.is_alive():
                # Nous ne pouvons pas vraiment arrêter les threads, mais nous pouvons les marquer
                logger.info(f"Marquage de la tâche {task_id} comme devant être arrêtée")
        
        self.running_tasks = {}
        logger.info("Planificateur réinitialisé")
    
    def initialize_tasks(self):
        """Initialise toutes les tâches planifiées"""
        # Scraping Amazon
        if self.config["tasks"]["scrape_amazon"]["enabled"]:
            self._schedule_task(
                "scrape_amazon",
                self.scrape_amazon,
                self.config["tasks"]["scrape_amazon"]
            )
        
        # Scraping Fnac
        if self.config["tasks"]["scrape_fnac"]["enabled"]:
            self._schedule_task(
                "scrape_fnac",
                self.scrape_fnac,
                self.config["tasks"]["scrape_fnac"]
            )
        
        # Analyse des sentiments
        if self.config["tasks"]["analyze_sentiments"]["enabled"]:
            self._schedule_task(
                "analyze_sentiments",
                self.analyze_sentiments,
                self.config["tasks"]["analyze_sentiments"]
            )
        
        # Segmentation des clients
        if self.config["tasks"]["segment_customers"]["enabled"]:
            self._schedule_task(
                "segment_customers",
                self.segment_customers,
                self.config["tasks"]["segment_customers"]
            )
        
        # Génération de rapports
        if self.config["tasks"]["generate_reports"]["enabled"]:
            self._schedule_task(
                "generate_reports",
                self.generate_reports,
                self.config["tasks"]["generate_reports"]
            )
        
        logger.info("Tâches planifiées initialisées")
    
    def _schedule_task(self, task_id: str, task_func: Callable, task_config: Dict[str, Any]):
        """
        Planifie une tâche selon sa configuration.
        
        Args:
            task_id: Identifiant de la tâche
            task_func: Fonction à exécuter
            task_config: Configuration de la tâche
        """
        schedule_type = task_config.get("schedule", "daily")
        
        if schedule_type == "daily":
            task_time = task_config.get("time", "00:00")
            schedule.every().day.at(task_time).do(self._run_task, task_id, task_func, task_config)
            logger.info(f"Tâche {task_id} planifiée quotidiennement à {task_time}")
            
        elif schedule_type == "weekly":
            task_day = task_config.get("day", "monday").lower()
            task_time = task_config.get("time", "00:00")
            
            if task_day == "monday":
                schedule.every().monday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "tuesday":
                schedule.every().tuesday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "wednesday":
                schedule.every().wednesday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "thursday":
                schedule.every().thursday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "friday":
                schedule.every().friday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "saturday":
                schedule.every().saturday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            elif task_day == "sunday":
                schedule.every().sunday.at(task_time).do(self._run_task, task_id, task_func, task_config)
            
            logger.info(f"Tâche {task_id} planifiée hebdomadairement le {task_day} à {task_time}")
            
        elif schedule_type == "hourly":
            schedule.every().hour.do(self._run_task, task_id, task_func, task_config)
            logger.info(f"Tâche {task_id} planifiée toutes les heures")
            
        elif schedule_type == "minutes":
            interval = task_config.get("interval", 60)
            schedule.every(interval).minutes.do(self._run_task, task_id, task_func, task_config)
            logger.info(f"Tâche {task_id} planifiée toutes les {interval} minutes")
    
    def _run_task(self, task_id: str, task_func: Callable, task_config: Dict[str, Any]) -> bool:
        """
        Exécute une tâche dans un thread séparé.
        
        Args:
            task_id: Identifiant de la tâche
            task_func: Fonction à exécuter
            task_config: Configuration de la tâche
            
        Returns:
            True pour que la tâche reste planifiée
        """
        # Vérifier si la tâche est déjà en cours d'exécution
        if task_id in self.running_tasks and self.running_tasks[task_id].is_alive():
            logger.warning(f"La tâche {task_id} est déjà en cours d'exécution. Elle sera ignorée cette fois-ci.")
            return True
        
        # Exécuter la tâche dans un thread séparé
        thread = threading.Thread(target=self._execute_task, args=(task_id, task_func, task_config))
        thread.daemon = True
        thread.start()
        
        # Enregistrer le thread
        self.running_tasks[task_id] = thread
        
        return True
    
    def _execute_task(self, task_id: str, task_func: Callable, task_config: Dict[str, Any]):
        """
        Exécute la fonction de tâche et gère les erreurs.
        
        Args:
            task_id: Identifiant de la tâche
            task_func: Fonction à exécuter
            task_config: Configuration de la tâche
        """
        try:
            logger.info(f"Début de l'exécution de la tâche {task_id}")
            start_time = time.time()
            
            # Exécuter la fonction
            task_func(task_config)
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"Tâche {task_id} terminée en {execution_time:.2f} secondes")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche {task_id}: {e}")
        
        finally:
            # Supprimer le thread de la liste des tâches en cours
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
    
    def run_forever(self):
        """Exécute le planificateur en continu"""
        logger.info("Démarrage du planificateur")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Arrêt du planificateur")
        except Exception as e:
            logger.error(f"Erreur dans le planificateur: {e}")
    
    def run_in_thread(self):
        """Exécute le planificateur dans un thread séparé"""
        scheduler_thread = threading.Thread(target=self.run_forever)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        logger.info("Planificateur démarré dans un thread séparé")
        return scheduler_thread
    
    def scrape_amazon(self, config: Dict[str, Any]):
        """
        Exécute le scraping des avis Amazon.
        
        Args:
            config: Configuration de la tâche
        """
        scraper = self.scrapers['amazon']
        max_products = config.get('max_products', 5)
        max_reviews = config.get('max_reviews_per_product', 20)
        products_to_scrape = config.get('products', [])
        
        try:
            for product_info in products_to_scrape:
                keywords = product_info.get('keywords', '')
                category = product_info.get('category', None)
                
                logger.info(f"Recherche de produits pour: {keywords}")
                products = scraper.search_products(keywords, category, max_products)
                
                for product in products:
                    try:
                        logger.info(f"Scraping des avis pour: {product['product_name']}")
                        reviews = scraper.get_reviews(product['url'], max_reviews)
                        
                        if reviews:
                            logger.info(f"Sauvegarde de {len(reviews)} avis")
                            self.data_manager.save_reviews(reviews)
                    except Exception as e:
                        logger.error(f"Erreur lors du scraping des avis: {e}")
                        continue
        finally:
            # Fermer le scraper
            scraper.close()
    
    def scrape_fnac(self, config: Dict[str, Any]):
        """
        Exécute le scraping des avis Fnac.
        
        Args:
            config: Configuration de la tâche
        """
        # Implémentation similaire à scrape_amazon
        logger.info("Scraping des avis Fnac")
        # TODO: Implémenter le scraping de Fnac
    
    def analyze_sentiments(self, config: Dict[str, Any]):
        """
        Exécute l'analyse des sentiments sur les avis non analysés.
        
        Args:
            config: Configuration de la tâche
        """
        batch_size = config.get('batch_size', 100)
        
        # Récupérer les avis non analysés
        reviews = self.data_manager.get_reviews_for_analysis(batch_size)
        
        if not reviews:
            logger.info("Aucun nouvel avis à analyser")
            return
        
        logger.info(f"Analyse des sentiments pour {len(reviews)} avis")
        
        # Analyser les sentiments
        sentiment_results = self.sentiment_analyzer.batch_analyze_reviews(reviews)
        
        # Sauvegarder les résultats
        self.data_manager.save_sentiment_analysis(sentiment_results)
        
        logger.info(f"Analyse des sentiments terminée pour {len(sentiment_results)} avis")
    
    def segment_customers(self, config: Dict[str, Any]):
        """
        Exécute la segmentation des clients.
        
        Args:
            config: Configuration de la tâche
        """
        # TODO: Implémenter la segmentation des clients
        logger.info("Segmentation des clients")
    
    def generate_reports(self, config: Dict[str, Any]):
        """
        Génère des rapports d'analyse.
        
        Args:
            config: Configuration de la tâche
        """
        # TODO: Implémenter la génération de rapports
        logger.info("Génération de rapports")
    
    def run_task_now(self, task_id: str):
        """
        Exécute immédiatement une tâche planifiée.
        
        Args:
            task_id: Identifiant de la tâche à exécuter
        """
        if task_id not in self.config['tasks']:
            logger.error(f"Tâche {task_id} non trouvée dans la configuration")
            return False
        
        task_config = self.config['tasks'][task_id]
        
        if not task_config.get('enabled', False):
            logger.warning(f"La tâche {task_id} est désactivée")
            return False
        
        # Mapper les IDs de tâche aux fonctions
        task_functions = {
            'scrape_amazon': self.scrape_amazon,
            'scrape_fnac': self.scrape_fnac,
            'analyze_sentiments': self.analyze_sentiments,
            'segment_customers': self.segment_customers,
            'generate_reports': self.generate_reports
        }
        
        if task_id not in task_functions:
            logger.error(f"Aucune fonction associée à la tâche {task_id}")
            return False
        
        # Exécuter la tâche immédiatement
        self._run_task(task_id, task_functions[task_id], task_config)
        return True