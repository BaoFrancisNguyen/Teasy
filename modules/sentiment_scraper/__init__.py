"""
Module de scraping et d'analyse de sentiments pour TEASY.
Récupère et analyse les avis clients sur différentes sources en ligne.
"""

from .data_manager import SentimentDataManager
from .schedulers import SentimentScraperScheduler

# Version du module
__version__ = '1.0.0'

# Exportation des classes principales pour une utilisation facile
data_manager = SentimentDataManager()
scheduler = SentimentScraperScheduler()

def initialize():
    """Initialise le module de scraping et d'analyse de sentiments"""
    data_manager.initialize_database()
    scheduler.initialize_tasks()
    print("Module d'analyse de sentiments initialisé avec succès.")
    
def get_sentiment_data(product_category=None, time_period=None, segment=None):
    """
    Récupère les données d'analyse de sentiments filtrées.
    
    Args:
        product_category (str, optional): Catégorie de produit à filtrer
        time_period (str, optional): Période temporelle (ex: '30d', '6m', '1y')
        segment (str, optional): Segment client à filtrer
        
    Returns:
        dict: Données d'analyse de sentiments formatées pour l'affichage
    """
    return data_manager.get_formatted_sentiment_data(
        product_category=product_category,
        time_period=time_period,
        segment=segment
    )
