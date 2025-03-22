import os
import pickle
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import traceback
from typing import Dict, Any, Optional, Tuple, List, Union

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.FileHandler("transformations.log"),
                       logging.StreamHandler()
                   ])
logger = logging.getLogger(__name__)

def convert_numpy_types(obj):
    """
    Convertit les types NumPy en types Python standards pour la sérialisation JSON
    
    Args:
        obj: Objet à convertir
        
    Returns:
        Objet avec les types NumPy convertis en types Python standards
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(i) for i in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj

class TransformationManager:
    """
    Classe pour gérer la persistance des transformations de données
    """
    
    def __init__(self, storage_dir=None, app=None):
        """
        Initialise le gestionnaire de transformations
        
        Args:
            storage_dir: Répertoire de stockage (par défaut None)
            app: Application Flask (par défaut None)
        """
        self.app = app
        
        if storage_dir:
            self.storage_dir = storage_dir
        elif app:
            self.storage_dir = os.path.join(app.root_path, 'temp')
        else:
            self.storage_dir = 'temp'
            
        # S'assurer que le répertoire de stockage existe
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Logger spécifique à cette classe
        self.logger = logging.getLogger(__name__ + '.TransformationManager')
        self.logger.info(f"TransformationManager initialisé avec répertoire de stockage: {self.storage_dir}")
    
    def _get_file_path(self, file_id: str, suffix: str) -> str:
        """
        Retourne le chemin complet pour un fichier
        
        Args:
            file_id: Identifiant unique du fichier
            suffix: Suffixe du fichier
            
        Returns:
            Chemin complet du fichier
        """
        file_path = os.path.join(self.storage_dir, f"{file_id}_{suffix}")
        self.logger.debug(f"Chemin de fichier généré: {file_path}")
        return file_path
    
    def save_dataframe(self, file_id: str, df: pd.DataFrame, is_transformed: bool = True) -> bool:
        """
        Sauvegarde un DataFrame original ou transformé
        
        Args:
            file_id: Identifiant unique du fichier
            df: DataFrame à sauvegarder
            is_transformed: Si True, sauvegarde en tant que transformé, sinon en tant qu'original
            
        Returns:
            True si la sauvegarde a réussi, False sinon
        """
        suffix = "transformed.pkl" if is_transformed else "original.pkl"
        file_path = self._get_file_path(file_id, suffix)
        
        try:
            # S'assurer que le DataFrame n'est pas None
            if df is None:
                self.logger.error(f"Tentative de sauvegarde d'un DataFrame None")
                return False
                
            # Vérifier si le DataFrame est vide
            if df.empty:
                self.logger.warning(f"Sauvegarde d'un DataFrame vide")
            
            # Sauvegarde du DataFrame
            with open(file_path, 'wb') as f:
                pickle.dump(df, f)
                
            self.logger.info(f"DataFrame {'transformé' if is_transformed else 'original'} sauvegardé: {file_path}")
            self.logger.info(f"Forme du DataFrame sauvegardé: {df.shape}")
            
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du DataFrame: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def load_dataframe(self, file_id: str, is_transformed: bool = True) -> Optional[pd.DataFrame]:
        """
        Charge un DataFrame original ou transformé
        
        Args:
            file_id: Identifiant unique du fichier
            is_transformed: Si True, charge le transformé, sinon l'original
            
        Returns:
            DataFrame ou None en cas d'erreur
        """
        suffix = "transformed.pkl" if is_transformed else "original.pkl"
        file_path = self._get_file_path(file_id, suffix)
        
        if not os.path.exists(file_path):
            self.logger.warning(f"Fichier non trouvé: {file_path}")
            # Si le fichier transformé n'existe pas, essayer de charger l'original
            if is_transformed:
                self.logger.info("Tentative de chargement du DataFrame original à la place")
                return self.load_dataframe(file_id, is_transformed=False)
            return None
        
        try:
            with open(file_path, 'rb') as f:
                df = pickle.load(f)
            
            if df is None or not isinstance(df, pd.DataFrame):
                self.logger.error(f"Le fichier chargé ne contient pas un DataFrame valide: {file_path}")
                return None
                
            self.logger.info(f"DataFrame chargé avec succès: {file_path}")
            self.logger.info(f"Forme du DataFrame chargé: {df.shape}")
            
            return df
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement du DataFrame: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    def get_current_dataframe(self, file_id: str) -> Optional[pd.DataFrame]:
        """
        Renvoie le DataFrame transformé ou original si le transformé n'existe pas
        
        Args:
            file_id: Identifiant unique du fichier
            
        Returns:
            DataFrame ou None en cas d'erreur
        """
        self.logger.info(f"Récupération du DataFrame courant pour {file_id}")
        
        df = self.load_dataframe(file_id, is_transformed=True)
        if df is None:
            self.logger.info(f"DataFrame transformé non disponible, chargement de l'original")
            df = self.load_dataframe(file_id, is_transformed=False)
            
            if df is None:
                self.logger.error(f"Aucun DataFrame disponible pour {file_id}")
            else:
                self.logger.info(f"DataFrame original chargé pour {file_id}, forme: {df.shape}")
        else:
            self.logger.info(f"DataFrame transformé chargé pour {file_id}, forme: {df.shape}")
            
        return df
    
    def save_transformations(self, file_id: str, history: Dict) -> bool:
        """
        Sauvegarde l'historique des transformations
        
        Args:
            file_id: Identifiant unique du fichier
            history: Historique des transformations
            
        Returns:
            True si la sauvegarde a réussi, False sinon
        """
        file_path = self._get_file_path(file_id, "transforms.json")
        try:
            # Convertir les types NumPy avant la sérialisation
            history = convert_numpy_types(history)
            
            # Vérifier la structure de l'historique
            if not isinstance(history, dict) or 'history' not in history:
                self.logger.warning(f"Structure d'historique incorrecte, ajout de la clé 'history'")
                if not isinstance(history, dict):
                    history = {'history': history if isinstance(history, list) else []}
                elif 'history' not in history:
                    history['history'] = []
            
            # Sauvegarde de l'historique
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Historique des transformations sauvegardé: {file_path}")
            self.logger.info(f"Nombre de transformations: {len(history.get('history', []))}")
            
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de l'historique: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def get_transformations(self, file_id: str) -> Dict:
        """
        Charge l'historique des transformations
        
        Args:
            file_id: Identifiant unique du fichier
            
        Returns:
            Dictionnaire contenant l'historique des transformations
        """
        file_path = self._get_file_path(file_id, "transforms.json")
        if not os.path.exists(file_path):
            self.logger.warning(f"Historique des transformations non trouvé: {file_path}")
            return {'history': []}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            # Vérifier la structure de l'historique
            if not isinstance(history, dict) or 'history' not in history:
                self.logger.warning(f"Structure d'historique incorrecte dans le fichier")
                if not isinstance(history, dict):
                    history = {'history': history if isinstance(history, list) else []}
                elif 'history' not in history:
                    history['history'] = []
            
            self.logger.info(f"Historique des transformations chargé: {file_path}")
            self.logger.info(f"Nombre de transformations: {len(history.get('history', []))}")
            
            return history
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de l'historique: {e}")
            self.logger.error(traceback.format_exc())
            return {'history': []}
    
    def load_transformation_history(self, file_id: str) -> Dict:
        """
        Alias pour get_transformations pour compatibilité avec le code existant
        """
        return self.get_transformations(file_id)
    
    def add_transformation(self, file_id: str, transform_data: Dict) -> bool:
        """
        Ajoute une transformation à l'historique
        
        Args:
            file_id: Identifiant unique du fichier
            transform_data: Données de la transformation
            
        Returns:
            True si l'ajout a réussi, False sinon
        """
        self.logger.info(f"Ajout d'une transformation pour {file_id}: {transform_data.get('type', 'inconnu')}")
        
        # Récupérer l'historique actuel
        history = self.get_transformations(file_id)
        
        if 'history' not in history:
            history['history'] = []
        
        # Ajouter un horodatage si non présent
        if 'timestamp' not in transform_data:
            transform_data['timestamp'] = datetime.now().isoformat()
            
        # Ajouter la transformation à l'historique
        history['history'].append(transform_data)
        
        # Sauvegarder l'historique mis à jour
        success = self.save_transformations(file_id, history)
        
        if success:
            self.logger.info(f"Transformation ajoutée avec succès. Total: {len(history['history'])}")
        else:
            self.logger.error(f"Échec de l'ajout de la transformation")
            
        return success
    
    def undo_last_transformation(self, file_id: str) -> Tuple[Optional[Dict], bool]:
        """
        Supprime la dernière transformation de l'historique
        
        Args:
            file_id: Identifiant unique du fichier
            
        Returns:
            tuple: (transformation supprimée, succès)
        """
        self.logger.info(f"Annulation de la dernière transformation pour {file_id}")
        
        # Récupérer l'historique actuel
        history = self.get_transformations(file_id)
        
        if 'history' not in history or not history['history']:
            self.logger.warning(f"Aucune transformation à annuler pour {file_id}")
            return None, False
        
        # Supprimer la dernière transformation
        last_transformation = history['history'].pop()
        
        # Sauvegarder l'historique mis à jour
        success = self.save_transformations(file_id, history)
        
        # Réappliquer toutes les transformations si l'annulation a réussi
        if success:
            self.logger.info(f"Dernière transformation annulée: {last_transformation.get('type', 'inconnu')}")
            
            # Charger le DataFrame original
            original_df = self.load_dataframe(file_id, is_transformed=False)
            
            if original_df is not None and history['history']:
                self.logger.info(f"Réapplication de {len(history['history'])} transformations restantes")
                
                # Cette partie nécessite le DataProcessor qui n'est pas disponible ici
                # Ce sera géré par l'appelant
            
        else:
            self.logger.error(f"Échec de l'annulation de la dernière transformation")
            
        return last_transformation, success
    
    def save_transformed_dataframe(self, file_id: str, df: pd.DataFrame) -> bool:
        """
        Alias pour save_dataframe avec is_transformed=True pour compatibilité avec le code existant
        """
        return self.save_dataframe(file_id, df, is_transformed=True)
    
    def load_transformed_dataframe(self, file_id: str) -> Optional[pd.DataFrame]:
        """
        Alias pour load_dataframe avec is_transformed=True pour compatibilité avec le code existant
        """
        return self.load_dataframe(file_id, is_transformed=True)
    
    def save_original_dataframe(self, file_id: str, df: pd.DataFrame) -> bool:
        """
        Alias pour save_dataframe avec is_transformed=False pour compatibilité avec le code existant
        """
        return self.save_dataframe(file_id, df, is_transformed=False)
    
    def load_original_dataframe(self, file_id: str) -> Optional[pd.DataFrame]:
        """
        Alias pour load_dataframe avec is_transformed=False pour compatibilité avec le code existant
        """
        return self.load_dataframe(file_id, is_transformed=False)
    
    def reapply_transformations(self, file_id: str, processor) -> Optional[pd.DataFrame]:
        """
        Réapplique toutes les transformations sur le DataFrame original
        
        Args:
            file_id: Identifiant unique du fichier
            processor: Instance de DataProcessor pour appliquer les transformations
            
        Returns:
            DataFrame résultant ou None en cas d'erreur
        """
        self.logger.info(f"Réapplication des transformations pour {file_id}")
        
        # Charger le DataFrame original
        df_original = self.load_dataframe(file_id, is_transformed=False)
        if df_original is None:
            self.logger.error(f"Impossible de charger le DataFrame original pour {file_id}")
            return None
        
        # Charger l'historique des transformations
        history = self.get_transformations(file_id)
        if 'history' not in history or not history['history']:
            self.logger.info(f"Aucune transformation à réappliquer pour {file_id}")
            return df_original
        
        # Réappliquer chaque transformation
        current_df = df_original.copy()
        transformation_count = len(history['history'])
        
        self.logger.info(f"Début de réapplication de {transformation_count} transformations")
        
        for i, transform in enumerate(history['history'], 1):
            transform_type = transform.get('type', '')
            transform_params = transform.get('params', {})
            
            self.logger.info(f"Réapplication de la transformation {i}/{transformation_count}: {transform_type}")
            
            # Créer un dictionnaire de transformation au format attendu par process_dataframe
            transform_dict = {transform_type: transform_params}
            
            try:
                # Appliquer la transformation
                current_df, _ = processor.process_dataframe(current_df, transform_dict)
                
                if current_df is None:
                    self.logger.error(f"La transformation {transform_type} a retourné un DataFrame None")
                    return None
                    
                self.logger.info(f"Transformation {transform_type} réappliquée avec succès")
                
            except Exception as e:
                self.logger.error(f"Erreur lors de la réapplication de la transformation {transform_type}: {e}")
                self.logger.error(traceback.format_exc())
                return None
        
        # Sauvegarder le DataFrame résultant
        success = self.save_transformed_dataframe(file_id, current_df)
        
        if success:
            self.logger.info(f"Réapplication des transformations terminée avec succès")
        else:
            self.logger.error(f"Échec lors de la sauvegarde du DataFrame après réapplication")
            
        return current_df
    
    def clear_transformations(self, file_id: str) -> bool:
        """
        Efface l'historique des transformations et le DataFrame transformé
        
        Args:
            file_id: Identifiant unique du fichier
            
        Returns:
            True si l'effacement a réussi, False sinon
        """
        self.logger.info(f"Effacement des transformations pour {file_id}")
        
        # Effacer l'historique des transformations
        history_path = self._get_file_path(file_id, "transforms.json")
        transformed_path = self._get_file_path(file_id, "transformed.pkl")
        
        success = True
        
        # Supprimer le fichier d'historique
        if os.path.exists(history_path):
            try:
                os.remove(history_path)
                self.logger.info(f"Fichier d'historique supprimé: {history_path}")
            except Exception as e:
                self.logger.error(f"Erreur lors de la suppression du fichier d'historique: {e}")
                success = False
        
        # Supprimer le fichier de DataFrame transformé
        if os.path.exists(transformed_path):
            try:
                os.remove(transformed_path)
                self.logger.info(f"Fichier de DataFrame transformé supprimé: {transformed_path}")
            except Exception as e:
                self.logger.error(f"Erreur lors de la suppression du fichier transformé: {e}")
                success = False
        
        return success
    
    def rename_transformation_file(self, old_file_id: str, new_file_id: str) -> bool:
        """
        Renomme les fichiers de transformation
        
        Args:
            old_file_id: Ancien identifiant du fichier
            new_file_id: Nouvel identifiant du fichier
            
        Returns:
            True si le renommage a réussi, False sinon
        """
        self.logger.info(f"Renommage des fichiers de transformation de {old_file_id} vers {new_file_id}")
        
        # Liste des suffixes à renommer
        suffixes = ["original.pkl", "transformed.pkl", "transforms.json"]
        
        success = True
        
        for suffix in suffixes:
            old_path = self._get_file_path(old_file_id, suffix)
            new_path = self._get_file_path(new_file_id, suffix)
            
            if os.path.exists(old_path):
                try:
                    os.rename(old_path, new_path)
                    self.logger.info(f"Fichier renommé: {old_path} -> {new_path}")
                except Exception as e:
                    self.logger.error(f"Erreur lors du renommage du fichier {suffix}: {e}")
                    success = False
        
        return success
    
    def check_file_integrity(self, file_id: str) -> bool:
        """
        Vérifie l'intégrité des fichiers de transformation
        
        Args:
            file_id: Identifiant unique du fichier
            
        Returns:
            True si tous les fichiers sont intègres, False sinon
        """
        self.logger.info(f"Vérification de l'intégrité des fichiers pour {file_id}")
        
        # Vérifier l'existence du fichier original
        original_path = self._get_file_path(file_id, "original.pkl")
        if not os.path.exists(original_path):
            self.logger.error(f"Fichier original manquant: {original_path}")
            return False
            
        # Vérifier que le fichier original est un DataFrame valide
        original_df = self.load_original_dataframe(file_id)
        if original_df is None:
            self.logger.error(f"Le fichier original ne contient pas un DataFrame valide: {original_path}")
            return False
            
        # Vérifier l'historique des transformations
        history = self.get_transformations(file_id)
        if not isinstance(history, dict) or 'history' not in history:
            self.logger.warning(f"Structure d'historique incorrecte pour {file_id}")
            
        # Vérifier le fichier transformé si des transformations existent
        if history.get('history', []):
            transformed_path = self._get_file_path(file_id, "transformed.pkl")
            if not os.path.exists(transformed_path):
                self.logger.warning(f"Fichier transformé manquant malgré des transformations: {transformed_path}")
                return False
                
            # Vérifier que le fichier transformé est un DataFrame valide
            transformed_df = self.load_transformed_dataframe(file_id)
            if transformed_df is None:
                self.logger.error(f"Le fichier transformé ne contient pas un DataFrame valide: {transformed_path}")
                return False
        
        self.logger.info(f"Tous les fichiers sont intègres pour {file_id}")
        return True

# Pour compatibilité avec le code existant
DataManager = TransformationManager