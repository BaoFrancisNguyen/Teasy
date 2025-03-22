# -*- coding: utf-8 -*-
import schedule
import time
from loyalty_manager import LoyaltyManager
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='loyalty_scheduler.log')
logger = logging.getLogger(__name__)

# Initialiser le gestionnaire de fidélité
loyalty_manager = LoyaltyManager()

def evaluate_rules_task():
    # Tache pour evaluer les regles de fidelite
    logger.info("Démarrage de la tâche d'évaluation des règles")
    try:
        result = loyalty_manager.evaluate_all_rules()
        if result['success']:
            stats = result['stats']
            logger.info(f"Évaluation terminée: {stats['total_offers_generated']} offres générées pour {stats['total_clients_evaluated']} clients")
        else:
            logger.error(f"Échec de l'évaluation des règles: {result.get('error', 'Erreur inconnue')}")
    except Exception as e:
        logger.error(f"Exception lors de l'évaluation des règles: {str(e)}")

def check_expired_offers_task():
    # Tache pour verifier les offres expirees
    logger.info("Démarrage de la tâche de vérification des offres expirées")
    try:
        result = loyalty_manager.check_expired_offers()
        if result['success']:
            logger.info(f"{result['offers_expired']} offres marquées comme expirées")
        else:
            logger.error(f"Échec de la vérification des offres expirées: {result.get('error', 'Erreur inconnue')}")
    except Exception as e:
        logger.error(f"Exception lors de la vérification des offres expirées: {str(e)}")

def send_pending_offers_task():
    # Tache pour envoyer les offres en attente
    logger.info("Démarrage de la tâche d'envoi des offres en attente")
    try:
        result = loyalty_manager.send_offers(channel='email')
        if result['success']:
            logger.info(f"{result['offers_sent']} offres envoyées")
        else:
            logger.error(f"Échec de l'envoi des offres: {result.get('error', 'Erreur inconnue')}")
    except Exception as e:
        logger.error(f"Exception lors de l'envoi des offres: {str(e)}")

def setup_schedules():
    # Configure les taches planifiees
    schedule.every().day.at("02:00").do(evaluate_rules_task)
    schedule.every().day.at("01:00").do(check_expired_offers_task)
    schedule.every().day.at("10:00").do(send_pending_offers_task)

    logger.info("Tâches planifiées configurées avec succès")

def run_scheduler():
    # Demarre le planificateur et execute les taches en continu
    logger.info("Démarrage du planificateur de tâches du programme de fidélité")
    
    # Configurer les tâches planifiées
    setup_schedules()
    
    # Exécuter les tâches au démarrage
    evaluate_rules_task()
    check_expired_offers_task()
    send_pending_offers_task()

    # Boucle principale du planificateur
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les minutes
        except Exception as e:
            logger.error(f"Erreur dans la boucle du planificateur: {str(e)}")
            time.sleep(300)  # Pause plus longue en cas d'erreur

if __name__ == "__main__":
    run_scheduler()
