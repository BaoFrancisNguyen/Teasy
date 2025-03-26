from flask import Blueprint, render_template, request, jsonify, current_app, session, redirect, url_for
import os
import json
import logging
import requests
import shutil
import psutil
import subprocess
import platform
from datetime import datetime
import threading
import time

# Configuration du logging
logger = logging.getLogger(__name__)

# Création du Blueprint
settings_bp = Blueprint('settings', __name__)

# URL de l'API Ollama (configurable)
OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434')

# Chemin pour stocker les paramètres des modèles
APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.hetic_app')
SETTINGS_FILE = os.path.join(APP_DATA_DIR, 'settings.json')
MODEL_PARAMS_DIR = os.path.join(APP_DATA_DIR, 'model_params')

# Assurer que les répertoires existent
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(MODEL_PARAMS_DIR, exist_ok=True)

# Valeurs par défaut pour les paramètres
DEFAULT_MODEL_PARAMS = {
    'temperature': 0.7,
    'top_p': 0.9,
    'max_tokens': 800,
    'context_size': 4096,
    'top_k': 40,
    'repeat_penalty': 1.1,
    'presence_penalty': 0,
    'frequency_penalty': 0,
    'mirostat': 0,
    'seed': -1
}

# Fonction pour charger les paramètres globaux
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement des paramètres: {e}")
    
    # Paramètres par défaut
    return {
        'api_url': OLLAMA_API_URL,
        'selected_model': 'dolphin-mixtral:latest',
        'history_enabled': True,
        'app_language': 'fr',
        'theme': 'light'
    }

# Fonction pour sauvegarder les paramètres globaux
def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des paramètres: {e}")
        return False

# Fonction pour charger les paramètres d'un modèle spécifique
def load_model_params(model_name):
    model_file = os.path.join(MODEL_PARAMS_DIR, f"{model_name.replace(':', '_')}.json")
    
    if os.path.exists(model_file):
        try:
            with open(model_file, 'r', encoding='utf-8') as f:
                params = json.load(f)
                # Fusionner avec les paramètres par défaut pour s'assurer que tous les champs sont présents
                return {**DEFAULT_MODEL_PARAMS, **params}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des paramètres du modèle {model_name}: {e}")
    
    # Retourner les paramètres par défaut si le fichier n'existe pas ou en cas d'erreur
    return DEFAULT_MODEL_PARAMS

# Fonction pour sauvegarder les paramètres d'un modèle
def save_model_params(model_name, params):
    try:
        model_file = os.path.join(MODEL_PARAMS_DIR, f"{model_name.replace(':', '_')}.json")
        with open(model_file, 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des paramètres du modèle {model_name}: {e}")
        return False

# Fonction pour vérifier si Ollama est en cours d'exécution
def check_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/version", timeout=2)
        return response.status_code == 200
    except:
        return False

# Fonction pour obtenir des informations système
def get_system_info():
    info = {
        'cpu_usage': psutil.cpu_percent(),
        'memory': {
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'percent': psutil.virtual_memory().percent
        },
        'disk': {
            'total': psutil.disk_usage('/').total,
            'free': psutil.disk_usage('/').free,
            'percent': psutil.disk_usage('/').percent
        },
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'gpu': 'Non détecté'
    }
    
    # Tenter de détecter le GPU (NVIDIA uniquement)
    try:
        if platform.system() == 'Windows':
            # Sur Windows, utiliser un appel système pour nvidia-smi
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv,noheader'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if result.returncode == 0:
                gpu_info = result.stdout.strip().split(',')
                info['gpu'] = {
                    'name': gpu_info[0].strip(),
                    'memory_total': gpu_info[1].strip(),
                    'memory_used': gpu_info[2].strip()
                }
        else:
            # Sur Linux/Mac, utiliser nvidia-smi
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv,noheader'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if result.returncode == 0:
                gpu_info = result.stdout.strip().split(',')
                info['gpu'] = {
                    'name': gpu_info[0].strip(),
                    'memory_total': gpu_info[1].strip(),
                    'memory_used': gpu_info[2].strip()
                }
    except Exception as e:
        logger.warning(f"Impossible de détecter le GPU: {e}")
    
    return info

# Fonction pour obtenir la taille du répertoire Ollama
def get_ollama_size():
    ollama_dir = os.path.join(os.path.expanduser('~'), '.ollama')
    
    if os.path.exists(ollama_dir):
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(ollama_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            
            return total_size
        except Exception as e:
            logger.error(f"Erreur lors du calcul de la taille du répertoire Ollama: {e}")
    
    return 0

# Route principale pour les paramètres
@settings_bp.route('/settings')
def settings():
    app_settings = load_settings()
    
    # Vérifier si Ollama est en cours d'exécution
    ollama_running = check_ollama_running()
    
    # Contexte à passer au template
    context = {
        'ollama_running': ollama_running,
        'ollama_url': app_settings.get('api_url', OLLAMA_API_URL),
        'selected_model': app_settings.get('selected_model', ''),
        'settings': app_settings
    }
    
    return render_template('settings.html', **context)

# Route pour mettre à jour les paramètres globaux
@settings_bp.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'Données invalides'}), 400
    
    # Charger les paramètres actuels
    current_settings = load_settings()
    
    # Mettre à jour les paramètres
    for key, value in data.items():
        current_settings[key] = value
    
    # Sauvegarder les paramètres
    if save_settings(current_settings):
        # Mettre à jour les paramètres dans l'application
        if 'api_url' in data:
            global OLLAMA_API_URL
            OLLAMA_API_URL = data['api_url']
        
        return jsonify({'success': True, 'message': 'Paramètres mis à jour avec succès'})
    else:
        return jsonify({'success': False, 'message': 'Erreur lors de la sauvegarde des paramètres'}), 500

# Route pour obtenir la liste des modèles
@settings_bp.route('/api/models')
def get_models():
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Erreur HTTP: {response.status_code}'}), response.status_code
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modèles: {e}")
        return jsonify({'error': str(e)}), 500

# Route pour obtenir les informations d'un modèle
@settings_bp.route('/api/models/<model_name>')
def get_model_info(model_name):
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/show", 
            json={'name': model_name},
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Erreur HTTP: {response.status_code}'}), response.status_code
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations du modèle {model_name}: {e}")
        return jsonify({'error': str(e)}), 500

# Route pour supprimer un modèle
@settings_bp.route('/api/models/<model_name>', methods=['DELETE'])
def delete_model(model_name):
    try:
        response = requests.delete(
            f"{OLLAMA_API_URL}/api/delete", 
            json={'name': model_name},
            timeout=10
        )
        
        if response.status_code == 200:
            # Supprimer également les paramètres associés
            model_file = os.path.join(MODEL_PARAMS_DIR, f"{model_name.replace(':', '_')}.json")
            if os.path.exists(model_file):
                os.remove(model_file)
            
            return jsonify({'success': True, 'message': f'Modèle {model_name} supprimé avec succès'})
        else:
            return jsonify({'error': f'Erreur HTTP: {response.status_code}'}), response.status_code
    
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du modèle {model_name}: {e}")
        return jsonify({'error': str(e)}), 500

# Route pour télécharger un modèle (pull)
@settings_bp.route('/api/models/pull', methods=['POST'])
def pull_model():
    data = request.json
    
    if not data or 'name' not in data:
        return jsonify({'success': False, 'message': 'Nom du modèle manquant'}), 400
    
    model_name = data['name']
    
    try:
        # Streaming de la réponse pour suivre la progression
        def generate():
            response = requests.post(
                f"{OLLAMA_API_URL}/api/pull", 
                json={'name': model_name},
                stream=True
            )
            
            for chunk in response.iter_lines():
                if chunk:
                    # Envoyer chaque ligne JSON comme un événement SSE
                    yield f"data: {chunk.decode('utf-8')}\n\n"
        
        return current_app.response_class(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du modèle {model_name}: {e}")
        return jsonify({'error': str(e)}), 500

# Route pour obtenir/mettre à jour les paramètres d'un modèle
@settings_bp.route('/api/models/<model_name>/params', methods=['GET', 'POST'])
def model_params(model_name):
    if request.method == 'GET':
        params = load_model_params(model_name)
        return jsonify(params)
    
    elif request.method == 'POST':
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'message': 'Données invalides'}), 400
        
        # Valider les paramètres
        for key in data:
            if key not in DEFAULT_MODEL_PARAMS:
                return jsonify({'success': False, 'message': f'Paramètre inconnu: {key}'}), 400
        
        # Charger les paramètres actuels
        current_params = load_model_params(model_name)
        
        # Mettre à jour les paramètres
        for key, value in data.items():
            current_params[key] = value
        
        # Sauvegarder les paramètres
        if save_model_params(model_name, current_params):
            # Mettre à jour le modèle sélectionné
            app_settings = load_settings()
            app_settings['selected_model'] = model_name
            save_settings(app_settings)
            
            return jsonify({'success': True, 'message': 'Paramètres mis à jour avec succès'})
        else:
            return jsonify({'success': False, 'message': 'Erreur lors de la sauvegarde des paramètres'}), 500

# Route pour obtenir les informations système
@settings_bp.route('/api/system_info')
def system_info():
    info = get_system_info()
    
    # Ajouter les informations sur Ollama
    info['ollama'] = {
        'running': check_ollama_running(),
        'url': OLLAMA_API_URL,
        'directory_size': get_ollama_size()
    }
    
    # Tenter d'obtenir la version d'Ollama
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/version", timeout=2)
        if response.status_code == 200:
            info['ollama']['version'] = response.json().get('version', 'Inconnue')
    except:
        info['ollama']['version'] = 'Inconnue'
    
    return jsonify(info)

# Fonction pour démarrer Ollama (si nécessaire)
def start_ollama():
    # Cette fonction dépend du système d'exploitation
    try:
        if platform.system() == 'Windows':
            subprocess.Popen(['ollama', 'serve'], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        
        # Attendre que le service soit prêt
        for _ in range(10):  # Essayer pendant 10 secondes
            if check_ollama_running():
                logger.info("Service Ollama démarré avec succès")
                return True
            time.sleep(1)
        
        logger.warning("Impossible de confirmer que le service Ollama est démarré")
        return False
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage d'Ollama: {e}")
        return False

# Route pour démarrer Ollama
@settings_bp.route('/api/start_ollama', methods=['POST'])
def api_start_ollama():
    # Démarrer Ollama dans un thread séparé pour ne pas bloquer la réponse
    thread = threading.Thread(target=start_ollama)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': "Démarrage d'Ollama en cours, veuillez patienter quelques secondes."
    })