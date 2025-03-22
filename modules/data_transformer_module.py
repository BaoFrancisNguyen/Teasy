import os
import sys
import pandas as pd
import numpy as np
import re
import logging
import requests
import json
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

# Configuration avancée du logging
def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Configuration complète du système de logging
    
    Args:
        log_level: Niveau de logging
        log_file: Fichier de log (optionnel)
    """
    # Configuration des handlers
    handlers = [logging.StreamHandler(sys.stdout)]  # Toujours log vers la console
    
    # Ajouter un handler de fichier si un chemin est fourni
    if log_file:
        try:
            # Utiliser un chemin absolu si possible
            log_dir = os.path.dirname(os.path.abspath(log_file))
            os.makedirs(log_dir, exist_ok=True)
            
            # Ajouter le handler de fichier
            file_handler = logging.FileHandler(log_file, mode='a')
            handlers.append(file_handler)
        except Exception as e:
            print(f"Impossible de créer le fichier de log : {e}")
    
    # Configuration du logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    return logging.getLogger(__name__)

# Initialiser le logger avec un nom de fichier par défaut
log_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    'data_transformer.log'
)
logger = setup_logging(log_file=log_file)

class DataTransformer:
    """
    Classe avancée pour la transformation et l'analyse de données avec capacités d'IA
    """
    
    def __init__(self, 
                 model_name="mistral:latest", 
                 context_size=4096, 
                 log_level=logging.INFO,
                 ollama_url=None):
        """
        Initialisation du transformateur de données
        
        Args:
            model_name: Nom du modèle IA
            context_size: Taille maximale du contexte
            log_level: Niveau de logging
            ollama_url: URL personnalisée pour l'API Ollama
        """
        self.model_name = model_name
        self.context_size = context_size
        
        # Configuration du logger
        self.logger = setup_logging(log_level, log_file)
        
        # Configuration de l'URL Ollama
        self.ollama_url = ollama_url or os.environ.get(
            "OLLAMA_API_URL", 
            "http://localhost:11434/api/generate"
        )
        
        # Vérifier la disponibilité du modèle
        self._validate_model_availability()
    
    def _validate_model_availability(self):
        """
        Vérifie la disponibilité et la configuration du modèle IA
        """
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [m.get("name") for m in models]
                
                if self.model_name in available_models:
                    self.logger.info(f"Modèle IA disponible : {self.model_name}")
                else:
                    self.logger.warning(
                        f"Modèle {self.model_name} non trouvé. "
                        f"Modèles disponibles : {available_models}"
                    )
            else:
                self.logger.error("Impossible de se connecter à l'API Ollama")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erreur de connexion à Ollama : {e}")
    
    # Dans data_transformer_module.py, améliorez la fonction generate_with_ai

    def generate_with_ai(self, prompt: str, max_tokens: int = 800, temperature: float = 0.3):
        """
        Génération de réponse avec le modèle IA
        """
        self.logger.info("=== DÉBUT GÉNÉRATION IA ===")
        self.logger.info(f"Prompt: {prompt[:100]}...")
        self.logger.info(f"Modèle: {self.model_name}")
        self.logger.info(f"URL Ollama: {self.ollama_url}")
        
        try:
            # Configuration du payload de la requête
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            self.logger.info(f"Requête Ollama envoyée, attente de réponse...")
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            self.logger.info(f"Réponse reçue: {response.status_code}")
            
            # Vérifier le statut de la réponse
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                preview = response_text[:100].replace('\n', ' ') if response_text else "VIDE"
                self.logger.info(f"Réponse: {preview}...")
                self.logger.info("=== FIN GÉNÉRATION IA RÉUSSIE ===")
                
                # Format uniforme pour la réponse
                return {"choices": [{"text": response_text}]}
            else:
                self.logger.error(f"Erreur Ollama: {response.status_code}")
                self.logger.error(f"Contenu de l'erreur: {response.text}")
                self.logger.error("=== FIN GÉNÉRATION IA ÉCHOUÉE ===")
                # Retourner un format de réponse cohérent même en cas d'erreur
                return {"choices": [{"text": f"Erreur de l'API IA ({response.status_code}): {response.text[:100]}..."}]}
        
        except Exception as e:
            self.logger.error(f"Exception lors de l'appel à Ollama: {e}")
            import traceback
            error_trace = traceback.format_exc()
            self.logger.error(error_trace)
            self.logger.error("=== FIN GÉNÉRATION IA ÉCHOUÉE ===")
            # Retourner un format de réponse cohérent même en cas d'exception
            return {"choices": [{"text": f"Erreur de connexion à l'API IA: {str(e)}"}]}
    
    def generate_dataset_analysis(self, df: pd.DataFrame, context: Optional[str] = None) -> str:
        """
        Génère une analyse complète du dataset
        
        Args:
            df: DataFrame à analyser
            context: Contexte ou question spécifique
        
        Returns:
            Analyse textuelle du dataset
        """
        try:
            # Imposer une limite sur la taille du DataFrame à traiter
            sample_size = min(1000, len(df))
            df_sample = df.sample(sample_size) if len(df) > sample_size else df
            
            # Collecter les statistiques de base (limitées pour éviter des prompts trop grands)
            numeric_cols = df_sample.select_dtypes(include=[np.number]).columns.tolist()
            categorical_cols = df_sample.select_dtypes(include=['object', 'category']).columns.tolist()
            
            # Statistiques numériques (limitées)
            numeric_stats = {}
            if numeric_cols:
                for col in numeric_cols[:5]:  # Limiter à 5 colonnes numériques
                    numeric_stats[col] = {
                        'min': float(df_sample[col].min()) if not pd.isna(df_sample[col].min()) else 'N/A',
                        'max': float(df_sample[col].max()) if not pd.isna(df_sample[col].max()) else 'N/A',
                        'mean': float(df_sample[col].mean()) if not pd.isna(df_sample[col].mean()) else 'N/A',
                        'missing': int(df_sample[col].isna().sum())
                    }
            
            # Statistiques catégorielles (limitées)
            cat_stats = {}
            if categorical_cols:
                for col in categorical_cols[:5]:  # Limiter à 5 colonnes catégorielles
                    value_counts = df_sample[col].value_counts().head(3).to_dict()  # Top 3 valeurs
                    cat_stats[col] = {
                        'unique_values': min(df_sample[col].nunique(), 1000),  # Limiter à 1000
                        'top_values': value_counts,
                        'missing': int(df_sample[col].isna().sum())
                    }
            
            # Préparation du prompt (limité et structuré)
            prompt = f"""
    Analyse détaillée d'un jeu de données (échantillon de {sample_size} lignes sur {len(df)} au total):

    STRUCTURE:
    - Dimensions: {df.shape[0]} lignes, {df.shape[1]} colonnes
    - Valeurs manquantes: {df.isna().sum().sum()} au total ({round(df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100, 2)}%)

    COLONNES ({len(df.columns)} au total):
    - Numériques ({len(numeric_cols)}): {', '.join(numeric_cols[:10])}{'...' if len(numeric_cols) > 10 else ''}
    - Catégorielles ({len(categorical_cols)}): {', '.join(categorical_cols[:10])}{'...' if len(categorical_cols) > 10 else ''}

    DEMANDE SPÉCIFIQUE:
    {context if context else "Fournir une analyse générale du jeu de données avec des insights sur sa structure, la qualité des données, et des recommandations d'analyses pertinentes."}

    FORMAT:
    1. Résumé et insights principaux
    2. Qualité des données et problèmes détectés
    3. Patterns intéressants
    4. Recommandations pour l'analyse ou le nettoyage des données
    """
            
            # Génération de l'analyse
            self.logger.info("Envoi de la demande d'analyse au modèle IA...")
            response = self.generate_with_ai(prompt, max_tokens=800, temperature=0.3)
            self.logger.info(f"Réponse reçue: {response is not None}")
            
            # Vérifier la réponse et extraire le texte
            if response and 'choices' in response and len(response['choices']) > 0 and response['choices'][0].get('text'):
                analysis_text = response['choices'][0]['text']
                self.logger.info(f"Analyse générée: {len(analysis_text)} caractères")
                return analysis_text
            else:
                self.logger.error("Réponse vide ou invalide du modèle IA")
                # Création d'une analyse de secours basée sur les statistiques
                fallback_analysis = self._generate_fallback_analysis(df, numeric_stats, cat_stats)
                return fallback_analysis
        
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return f"Analyse impossible: une erreur est survenue pendant la génération de l'analyse. Détails: {str(e)}"
    
    def transform(self, 
                  df: pd.DataFrame, 
                  transformations=None, 
                  context: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Transformation de base du DataFrame
        
        Args:
            df: DataFrame à transformer
            transformations: Liste de transformations
            context: Contexte utilisateur
        
        Returns:
            DataFrame et métadonnées
        """
        # Initialiser les métadonnées
        metadata = {
            "original_shape": df.shape,
            "missing_values": {
                "before": df.isna().sum().sum()
            },
            "transformations": transformations or []
        }
        
        # Générer une analyse si un contexte est fourni
        if context:
            analysis = self.generate_dataset_analysis(df, context)
            metadata["analysis"] = analysis
        
        return df, metadata

def test_data_transformer():
    """
    Fonction de test pour le DataTransformer
    """
    try:
        # Créer un DataFrame de test
        test_df = pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'salaire': [30000, 45000, 50000, 60000, 75000],
            'ville': ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice']
        })
        
        # Initialiser le transformateur
        transformer = DataTransformer()
        
        # Tester l'analyse
        analyse = transformer.generate_dataset_analysis(test_df)
        print("Analyse du dataset :")
        print(analyse)
        
        # Tester la transformation
        _, metadata = transformer.transform(test_df, context="Analyse les caractéristiques principales")
        print("\nMétadonnées de transformation :")
        print(json.dumps(metadata, indent=2))
        
    except Exception as e:
        logger.error(f"Erreur lors des tests : {e}")
        print(f"Erreur lors des tests : {e}")

    def _generate_fallback_analysis(self, df, numeric_stats, cat_stats):
        """
        Génère une analyse de secours basée sur les statistiques basiques
        lorsque l'IA ne répond pas correctement
        """
        analysis = [
            "# Analyse de données générée automatiquement\n",
            f"## Résumé du jeu de données\n",
            f"Ce jeu de données contient {df.shape[0]} observations et {df.shape[1]} variables.\n"
        ]
        
        # Analyse des valeurs manquantes
        missing_count = df.isna().sum().sum()
        missing_percentage = (missing_count / (df.shape[0] * df.shape[1])) * 100
        
        if missing_count > 0:
            analysis.append(f"## Qualité des données\n")
            analysis.append(f"- **Valeurs manquantes**: {missing_count} valeurs manquantes au total ({missing_percentage:.2f}% des données)\n")
            
            # Colonnes avec le plus de valeurs manquantes
            missing_by_column = df.isna().sum().sort_values(ascending=False)
            top_missing = missing_by_column[missing_by_column > 0][:5]
            
            if not top_missing.empty:
                analysis.append("- **Colonnes avec le plus de valeurs manquantes**:\n")
                for col, count in top_missing.items():
                    percentage = (count / len(df)) * 100
                    analysis.append(f"  - {col}: {count} valeurs manquantes ({percentage:.2f}%)\n")
        
        # Statistiques numériques
        if numeric_stats:
            analysis.append(f"## Statistiques des variables numériques\n")
            for col, stats in numeric_stats.items():
                analysis.append(f"- **{col}**:\n")
                analysis.append(f"  - Plage: {stats['min']} à {stats['max']}\n")
                analysis.append(f"  - Moyenne: {stats['mean']}\n")
                analysis.append(f"  - Valeurs manquantes: {stats['missing']}\n")
        
        # Statistiques catégorielles
        if cat_stats:
            analysis.append(f"## Statistiques des variables catégorielles\n")
            for col, stats in cat_stats.items():
                analysis.append(f"- **{col}**:\n")
                analysis.append(f"  - Valeurs uniques: {stats['unique_values']}\n")
                analysis.append(f"  - Valeurs les plus fréquentes: {', '.join(str(k) for k in stats['top_values'].keys())}\n")
                analysis.append(f"  - Valeurs manquantes: {stats['missing']}\n")
        
        # Recommandations
        analysis.append(f"## Recommandations\n")
        
        if missing_count > 0:
            analysis.append("- **Traitement des valeurs manquantes**: Envisagez de combler les valeurs manquantes ou de supprimer les colonnes avec trop de données manquantes.\n")
        
        analysis.append("- **Exploration**: Examinez les distributions des variables numériques et les relations entre elles.\n")
        analysis.append("- **Corrélations**: Analysez les corrélations entre les variables numériques pour identifier les relations potentielles.\n")
        
        return "".join(analysis)

if __name__ == "__main__":
    test_data_transformer()