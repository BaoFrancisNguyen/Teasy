"""
Module de contrôle pour le planificateur du programme de fidélité

Ce module fournit les fonctions pour contrôler et configurer le planificateur
qui exécute automatiquement les tâches du programme de fidélité.
"""

import os
import json
import logging
import subprocess
import signal
import time
from datetime import datetime
import psutil

# Configuration du logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='loyalty_scheduler_controller.log')
logger = logging.getLogger(__name__)

# Chemins des fichiers
CONFIG_FILE = 'loyalty_scheduler_config.json'
PID_FILE = 'loyalty_scheduler.pid'
LOG_FILE = 'loyalty_scheduler.log'

# Tâches par défaut
DEFAULT_TASKS = [
    {
        "id": "evaluate_rules",
        "name": "Évaluation des règles de fidélité",
        "function": "evaluate_rules_task",
        "enabled": True,
        "schedule_type": "daily",
        "time": "02:00",
        "description": "Évalue toutes les règles de fidélité actives et génère des offres pour les clients éligibles."
    },
    {
        "id": "check_expired_offers",
        "name": "Vérification des offres expirées",
        "function": "check_expired_offers_task",
        "enabled": True,
        "schedule_type": "daily",
        "time": "01:00",
        "description": "Vérifie et marque les offres qui ont dépassé leur date d'expiration."
    },
    {
        "id": "send_pending_offers",
        "name": "Envoi des offres en attente",
        "function": "send_pending_offers_task",
        "enabled": True,
        "schedule_type": "daily",
        "time": "10:00",
        "description": "Envoie automatiquement les offres générées aux clients par email."
    }
]

def load_config():
    """Charge la configuration du planificateur."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration: {str(e)}")
            return create_default_config()
    else:
        return create_default_config()

def create_default_config():
    """Crée une configuration par défaut."""
    config = {
        "tasks": DEFAULT_TASKS,
        "status": {
            "is_running": False,
            "last_run": None,
            "active_since": None,
            "pid": None
        }
    }
    
    try:
        save_config(config)
        logger.info("Configuration par défaut créée.")
    except Exception as e:
        logger.error(f"Erreur lors de la création de la configuration par défaut: {str(e)}")
    
    return config

def save_config(config):
    """Sauvegarde la configuration du planificateur."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la configuration: {str(e)}")
        return False

def update_task_config(task_updates):
    """Met à jour la configuration des tâches."""
    config = load_config()
    
    for task in config['tasks']:
        task_id = task['id']
        if f"task_enabled_{task_id}" in task_updates:
            task['enabled'] = task_updates[f"task_enabled_{task_id}"] == "on"
        if f"task_schedule_{task_id}" in task_updates:
            task['schedule_type'] = task_updates[f"task_schedule_{task_id}"]
        if f"task_time_{task_id}" in task_updates:
            task['time'] = task_updates[f"task_time_{task_id}"]
    
    save_config(config)
    return config

def generate_scheduler_code(config):
    """Génère le code de planification à partir de la configuration."""
    tasks = config['tasks']
    
    code = """# -*- coding: utf-8 -*-
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
"""
    
    for task in tasks:
        if task['enabled']:
            function_name = task['function']
            schedule_type = task['schedule_type']
            time = task['time']
            
            schedule_code = ""
            if schedule_type == 'daily':
                schedule_code = f"schedule.every().day.at(\"{time}\").do({function_name})"
            elif schedule_type == 'weekly':
                schedule_code = f"schedule.every().monday.at(\"{time}\").do({function_name})"
            elif schedule_type == 'monthly':
                schedule_code = f"schedule.every(30).days.at(\"{time}\").do({function_name})"
                
            code += f"    {schedule_code}\n"
    
    code += """
    logger.info("Tâches planifiées configurées avec succès")

def run_scheduler():
    # Demarre le planificateur et execute les taches en continu
    logger.info("Démarrage du planificateur de tâches du programme de fidélité")
    
    # Configurer les tâches planifiées
    setup_schedules()
    
    # Exécuter les tâches au démarrage
"""
    
    # Ajouter l'exécution des tâches au démarrage
    for task in tasks:
        if task['enabled']:
            code += f"    {task['function']}()\n"
    
    code += """
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
"""
    
    return code

def is_scheduler_running():
    """Vérifie si le planificateur est en cours d'exécution."""
    config = load_config()
    
    # Vérifier le PID enregistré
    pid = config['status'].get('pid')
    if pid:
        try:
            # Vérifier si le processus existe
            process = psutil.Process(pid)
            if process.is_running() and 'python' in process.name().lower() and any('loyalty_scheduler' in cmd.lower() for cmd in process.cmdline()):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Si on arrive ici, c'est que le processus n'est pas en cours d'exécution
    # Mettre à jour le statut
    config['status']['is_running'] = False
    config['status']['pid'] = None
    save_config(config)
    
    return False

def start_scheduler():
    """Démarre le planificateur."""
    if is_scheduler_running():
        logger.info("Le planificateur est déjà en cours d'exécution.")
        return {
            'success': False,
            'message': "Le planificateur est déjà en cours d'exécution."
        }
    
    try:
        # Charger la configuration
        config = load_config()
        
        # Générer le code du planificateur à partir de la configuration
        scheduler_code = generate_scheduler_code(config)
        
        # Sauvegarder le code dans un fichier temporaire
        temp_scheduler_file = 'temp_loyalty_scheduler.py'
        with open(temp_scheduler_file, 'w', encoding='utf-8') as f:
            f.write(scheduler_code)
        
        # Démarrer le processus
        process = subprocess.Popen(['python', temp_scheduler_file], 
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   start_new_session=True)
        
        # Attendre un peu pour s'assurer que le processus démarre correctement
        time.sleep(2)
        
        # Vérifier que le processus est bien démarré
        if process.poll() is None:  # None signifie que le processus est toujours en cours d'exécution
            # Mettre à jour le statut
            config['status']['is_running'] = True
            config['status']['pid'] = process.pid
            config['status']['active_since'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_config(config)
            
            logger.info(f"Planificateur démarré avec PID {process.pid}")
            return {
                'success': True,
                'message': f"Planificateur démarré avec PID {process.pid}"
            }
        else:
            stdout, stderr = process.communicate()
            error_msg = stderr.decode() if stderr else "Erreur inconnue"
            logger.error(f"Échec du démarrage du planificateur: {error_msg}")
            return {
                'success': False,
                'message': f"Échec du démarrage du planificateur: {error_msg}"
            }
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du planificateur: {str(e)}")
        return {
            'success': False,
            'message': f"Erreur lors du démarrage du planificateur: {str(e)}"
        }



def stop_scheduler():
    """Arrête le planificateur."""
    config = load_config()
    pid = config['status'].get('pid')
    
    if not pid or not is_scheduler_running():
        logger.info("Le planificateur n'est pas en cours d'exécution.")
        return {
            'success': False,
            'message': "Le planificateur n'est pas en cours d'exécution."
        }
    
    try:
        # Tenter de terminer le processus
        process = psutil.Process(pid)
        process.terminate()
        
        # Attendre que le processus se termine
        gone, alive = psutil.wait_procs([process], timeout=3)
        
        # Si le processus est toujours en vie, le tuer de force
        if alive:
            for p in alive:
                p.kill()
        
        # Mettre à jour le statut
        config['status']['is_running'] = False
        config['status']['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        config['status']['pid'] = None
        save_config(config)
        
        logger.info("Planificateur arrêté avec succès")
        return {
            'success': True,
            'message': "Planificateur arrêté avec succès"
        }
    
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        # Le processus n'existe plus ou on n'a pas les droits
        config['status']['is_running'] = False
        config['status']['pid'] = None
        save_config(config)
        
        logger.info("Le processus du planificateur n'existe plus")
        return {
            'success': True,
            'message': "Le processus du planificateur n'existe plus"
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du planificateur: {str(e)}")
        return {
            'success': False,
            'message': f"Erreur lors de l'arrêt du planificateur: {str(e)}"
        }

def restart_scheduler():
    """Redémarre le planificateur."""
    stop_result = stop_scheduler()
    
    # Attendre un peu pour s'assurer que le processus est bien arrêté
    time.sleep(2)
    
    start_result = start_scheduler()
    
    if start_result['success']:
        logger.info("Planificateur redémarré avec succès")
        return {
            'success': True,
            'message': "Planificateur redémarré avec succès"
        }
    else:
        logger.error(f"Échec du redémarrage du planificateur: {start_result['message']}")
        return {
            'success': False,
            'message': f"Échec du redémarrage du planificateur: {start_result['message']}"
        }

def run_specific_task(task_id):
    """Exécute une tâche spécifique immédiatement."""
    config = load_config()
    
    # Trouver la tâche dans la configuration
    task = next((t for t in config['tasks'] if t['id'] == task_id), None)
    
    if not task:
        logger.error(f"Tâche non trouvée: {task_id}")
        return {
            'success': False,
            'message': f"Tâche non trouvée: {task_id}"
        }
    
    try:
        from loyalty_manager import LoyaltyManager
        loyalty_manager = LoyaltyManager()
        
        # Exécuter la fonction correspondante
        if task['function'] == 'evaluate_rules_task':
            logger.info("Exécution manuelle de l'évaluation des règles")
            result = loyalty_manager.evaluate_all_rules()
            if result['success']:
                stats = result['stats']
                message = f"Évaluation terminée: {stats['total_offers_generated']} offres générées pour {stats['total_clients_evaluated']} clients"
                logger.info(message)
                return {
                    'success': True,
                    'message': message
                }
            else:
                error_msg = f"Échec de l'évaluation des règles: {result.get('error', 'Erreur inconnue')}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
                
        elif task['function'] == 'check_expired_offers_task':
            logger.info("Exécution manuelle de la vérification des offres expirées")
            result = loyalty_manager.check_expired_offers()
            if result['success']:
                message = f"{result['offers_expired']} offres marquées comme expirées"
                logger.info(message)
                return {
                    'success': True,
                    'message': message
                }
            else:
                error_msg = f"Échec de la vérification des offres expirées: {result.get('error', 'Erreur inconnue')}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
                
        elif task['function'] == 'send_pending_offers_task':
            logger.info("Exécution manuelle de l'envoi des offres en attente")
            result = loyalty_manager.send_offers(channel='email')
            if result['success']:
                message = f"{result['offers_sent']} offres envoyées"
                logger.info(message)
                return {
                    'success': True,
                    'message': message
                }
            else:
                error_msg = f"Échec de l'envoi des offres: {result.get('error', 'Erreur inconnue')}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
        
        else:
            logger.error(f"Fonction inconnue: {task['function']}")
            return {
                'success': False,
                'message': f"Fonction inconnue: {task['function']}"
            }
            
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche {task_id}: {str(e)}")
        return {
            'success': False,
            'message': f"Erreur lors de l'exécution de la tâche: {str(e)}"
        }

def get_scheduler_logs(limit=20):
    """Récupère les derniers logs du planificateur."""
    logs = []
    
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Prendre les dernières lignes
                last_lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in last_lines:
                    # Analyser chaque ligne de log
                    try:
                        parts = line.strip().split(' - ', 3)
                        if len(parts) >= 4:
                            timestamp, module, level, message = parts
                            logs.append({
                                'timestamp': timestamp,
                                'module': module,
                                'level': level.lower(),
                                'message': message
                            })
                    except:
                        # Si le format est incorrect, ajouter la ligne brute
                        logs.append({
                            'timestamp': '',
                            'module': '',
                            'level': 'info',
                            'message': line.strip()
                        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {str(e)}")
        logs.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'module': 'controller',
            'level': 'error',
            'message': f"Erreur lors de la récupération des logs: {str(e)}"
        })
    
    return logs

def get_scheduler_status():
    """Récupère le statut actuel du planificateur."""
    config = load_config()
    status = config['status']
    
    # Vérifier si le statut est cohérent avec l'état réel du processus
    is_running = is_scheduler_running()
    
    if is_running != status['is_running']:
        status['is_running'] = is_running
        if not is_running:
            status['pid'] = None
        save_config(config)
    
    return status