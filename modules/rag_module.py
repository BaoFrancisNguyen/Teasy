"""
Module de Retrieval Augmented Generation (RAG) pour enrichir les réponses du LLM
avec des données contextuelles spécifiques à l'application.
"""

import os
import numpy as np
import pandas as pd
import json
import pickle
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RAGSystem:
    """Système de Retrieval Augmented Generation pour enrichir les réponses du LLM"""
    
    def __init__(self, vector_db_path="data/vector_db/", use_local_embeddings=True):
        """
        Initialise le système RAG
        
        Args:
            vector_db_path: Chemin vers le stockage des vecteurs
            use_local_embeddings: Si True, utilise un modèle d'embedding local simple
                                 Si False, utilise sentence-transformers (nécessite l'installation)
        """
        self.vector_db_path = vector_db_path
        os.makedirs(vector_db_path, exist_ok=True)
        self.use_local_embeddings = use_local_embeddings
        
        # Initialisation du modèle d'embedding
        if use_local_embeddings:
            # Utiliser une implémentation simple basée sur TF-IDF
            logger.info("Utilisation de l'embedding local simple")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.embedding_model = TfidfVectorizer(max_features=5000)
            
            # Initialiser le modèle avec un texte fictif pour s'assurer qu'il est prêt
            dummy_texts = ["Texte d'initialisation pour le modèle"]
            self.embedding_model.fit(dummy_texts)
            self._model_initialized = True
            logger.info("Modèle d'embedding local initialisé avec succès")
        else:
            # Utiliser sentence-transformers pour des embeddings plus sophistiqués
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self._model_initialized = True
                logger.info("Modèle d'embedding SentenceTransformer chargé avec succès")
            except ImportError:
                logger.warning("SentenceTransformer non installé. Utilisation de l'embedding local simple à la place.")
                from sklearn.feature_extraction.text import TfidfVectorizer
                self.embedding_model = TfidfVectorizer(max_features=5000)
                self.use_local_embeddings = True
                
                # Initialiser le modèle avec un texte fictif
                dummy_texts = ["Texte d'initialisation pour le modèle"]
                self.embedding_model.fit(dummy_texts)
                self._model_initialized = True
                logger.info("Modèle d'embedding local initialisé par défaut")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du modèle d'embedding: {e}")
                self._model_initialized = False
                raise
            
        # Dictionnaire pour stocker les collections de vecteurs
        self.collections = {}
        
        # Charger les collections existantes
        self._load_collections()
    
    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """Convertit une liste de textes en embeddings"""
        if not self._model_initialized:
            logger.error("Tentative d'utilisation du modèle d'embedding non initialisé")
            raise RuntimeError("Le modèle d'embedding n'est pas initialisé")
            
        if self.use_local_embeddings:
            return self.embedding_model.transform(texts).toarray()
        else:
            # Utiliser sentence-transformers
            return self.embedding_model.encode(texts)
    
    def _embed_query(self, query: str) -> np.ndarray:
        """Convertit une requête en embedding"""
        if not self._model_initialized:
            logger.error("Impossible d'encoder la requête: le modèle n'est pas initialisé")
            raise RuntimeError("Le modèle d'embedding n'est pas initialisé")
            
        if self.use_local_embeddings:
            return self.embedding_model.transform([query]).toarray()[0]
        else:
            # Utiliser sentence-transformers
            return self.embedding_model.encode([query])[0]
    
    def _compute_similarity(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
        """Calcule la similarité cosinus entre une requête et des documents"""
        # Normaliser les vecteurs pour la similarité cosinus
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        
        doc_norms = np.linalg.norm(doc_embeddings, axis=1)
        doc_norms[doc_norms == 0] = 1  # Éviter la division par zéro
        doc_embeddings = doc_embeddings / doc_norms[:, np.newaxis]
        
        # Calculer les similarités
        return np.dot(doc_embeddings, query_embedding)
    
    def _load_collections(self):
        """Charge les collections d'embeddings existantes"""
        try:
            for filename in os.listdir(self.vector_db_path):
                if filename.endswith('.pkl'):
                    collection_name = os.path.splitext(filename)[0]
                    collection_path = os.path.join(self.vector_db_path, filename)
                    
                    try:
                        with open(collection_path, 'rb') as f:
                            collection_data = pickle.load(f)
                            
                        # Vérifier la compatibilité dimensionnelle
                        if self._model_initialized and self.use_local_embeddings:
                            if 'embeddings' in collection_data and len(collection_data['embeddings']) > 0:
                                expected_dim = self.embedding_model.get_feature_names_out().shape[0]
                                actual_dim = collection_data['embeddings'][0].shape[0]
                                
                                if expected_dim != actual_dim:
                                    logger.warning(f"Dimensions incompatibles pour la collection '{collection_name}': "
                                                  f"attendu {expected_dim}, obtenu {actual_dim}. "
                                                  f"Cette collection pourrait nécessiter une réindexation.")
                                    continue
                        
                        self.collections[collection_name] = collection_data
                        logger.info(f"Collection '{collection_name}' chargée: {len(collection_data['texts'])} documents")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement de la collection '{collection_name}': {e}")
                        # Continuer avec les autres collections
        except Exception as e:
            logger.error(f"Erreur lors du chargement des collections: {e}")
    
    def create_collection(self, collection_name: str, texts: List[str], metadata: Optional[List[Dict]] = None) -> bool:
        """
        Crée une nouvelle collection d'embeddings
        
        Args:
            collection_name: Nom de la collection
            texts: Liste de textes à encoder
            metadata: Liste de métadonnées associées à chaque texte (optionnel)
        
        Returns:
            bool: True si la création a réussi, False sinon
        """
        try:
            if not self._model_initialized:
                logger.error("Impossible de créer une collection: le modèle d'embedding n'est pas initialisé")
                return False
                
            # Encoder les textes
            embeddings = self._embed_texts(texts)
            
            # Créer la collection
            self.collections[collection_name] = {
                'texts': texts,
                'embeddings': embeddings,
                'metadata': metadata if metadata else [{}] * len(texts),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Sauvegarder la collection
            self._save_collection(collection_name)
            
            logger.info(f"Collection '{collection_name}' créée avec {len(texts)} documents")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la création de la collection '{collection_name}': {e}")
            return False
    
    def _save_collection(self, collection_name: str) -> bool:
        """Sauvegarde une collection sur le disque"""
        try:
            collection_path = os.path.join(self.vector_db_path, f"{collection_name}.pkl")
            with open(collection_path, 'wb') as f:
                pickle.dump(self.collections[collection_name], f)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la collection '{collection_name}': {e}")
            return False
    
    def add_to_collection(self, collection_name: str, texts: List[str], metadata: Optional[List[Dict]] = None) -> bool:
        """Ajoute des documents à une collection existante"""
        if collection_name not in self.collections:
            logger.info(f"Collection '{collection_name}' n'existe pas, création...")
            return self.create_collection(collection_name, texts, metadata)
        
        try:
            if not self._model_initialized:
                logger.error("Impossible d'ajouter à une collection: le modèle d'embedding n'est pas initialisé")
                return False
                
            # Encoder les nouveaux textes
            new_embeddings = self._embed_texts(texts)
            
            # Ajouter à la collection existante
            current_collection = self.collections[collection_name]
            current_collection['texts'].extend(texts)
            
            # Gérer les différents types d'embeddings (sparse ou dense)
            if isinstance(new_embeddings, np.ndarray) and isinstance(current_collection['embeddings'], np.ndarray):
                # Les deux sont des arrays numpy, vérifier les dimensions
                if len(current_collection['embeddings']) == 0:
                    current_collection['embeddings'] = new_embeddings
                else:
                    # Vérifier que les dimensions correspondent
                    if current_collection['embeddings'].shape[1] == new_embeddings.shape[1]:
                        current_collection['embeddings'] = np.vstack([current_collection['embeddings'], new_embeddings])
                    else:
                        logger.error(f"Incompatibilité de dimensions entre les embeddings existants et nouveaux")
                        return False
            else:
                # Gérer d'autres types si nécessaire
                logger.error(f"Type d'embedding non pris en charge")
                return False
            
            # Gérer les métadonnées
            if metadata:
                current_collection['metadata'].extend(metadata)
            else:
                current_collection['metadata'].extend([{}] * len(texts))
            
            # Mettre à jour la date de modification
            current_collection['updated_at'] = datetime.now().isoformat()
            
            # Sauvegarder la collection mise à jour
            self._save_collection(collection_name)
            
            logger.info(f"{len(texts)} documents ajoutés à la collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout à la collection '{collection_name}': {e}")
            return False
    
    def query_collection(self, collection_name: str, query: str, top_k: int = 5) -> List[Dict]:
        """
        Recherche les documents les plus pertinents dans une collection
        
        Args:
            collection_name: Nom de la collection à interroger
            query: Texte de la requête
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste des top_k textes et métadonnées les plus pertinents
        """
        if collection_name not in self.collections:
            logger.warning(f"Collection '{collection_name}' non trouvée")
            return []
        
        try:
            if not self._model_initialized:
                logger.error("Impossible d'interroger une collection: le modèle d'embedding n'est pas initialisé")
                return []
                
            # Encoder la requête
            query_embedding = self._embed_query(query)
            
            # Calculer les similarités
            collection = self.collections[collection_name]
            similarities = self._compute_similarity(
                query_embedding, 
                collection['embeddings']
            )
            
            # Trier les résultats par similarité
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Préparer les résultats
            results = []
            for idx in top_indices:
                results.append({
                    'text': collection['texts'][idx],
                    'metadata': collection['metadata'][idx],
                    'similarity': float(similarities[idx])
                })
            
            return results
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans la collection '{collection_name}': {e}")
            return []
    
    def build_context_from_query(self, collection_name: str, query: str, max_tokens: int = 2000) -> str:
        """
        Construit un contexte pour le LLM basé sur les résultats de la recherche
        
        Args:
            collection_name: Nom de la collection à interroger
            query: Requête de l'utilisateur
            max_tokens: Nombre maximum de tokens approximatif pour le contexte
            
        Returns:
            Texte formaté pour le contexte du LLM
        """
        try:
            # Vérifier que le modèle d'embedding est initialisé
            if not self._model_initialized:
                logger.warning(f"Le modèle d'embedding n'est pas initialisé pour la requête: {query}")
                return "Le système de recherche n'est pas correctement initialisé. Veuillez réessayer plus tard ou contacter l'administrateur."
                
            # Vérifier que la collection existe
            if collection_name not in self.collections:
                logger.warning(f"Collection '{collection_name}' non trouvée pour la requête: {query}")
                return f"La collection '{collection_name}' n'existe pas dans la base de connaissances."
            
            # Effectuer la recherche
            try:
                results = self.query_collection(collection_name, query)
            except Exception as search_error:
                logger.error(f"Erreur lors de la recherche dans la collection '{collection_name}': {search_error}")
                return "Une erreur est survenue lors de la recherche d'informations. Veuillez vérifier la cohérence de la collection."
            
            if not results:
                return "Aucune information pertinente trouvée dans la base de connaissances."
            
            # Construire le contexte
            context = "Informations pertinentes :\n\n"
            total_length = len(context)
            
            for i, result in enumerate(results):
                # Estimer la longueur en tokens (approximatif: 4 caractères ~ 1 token)
                text_length = len(result['text'])
                
                if total_length + text_length > max_tokens * 4:
                    break
                    
                context += f"[Document {i+1}] (Pertinence: {result['similarity']:.2f})\n"
                context += f"{result['text']}\n"
                
                # Ajouter les métadonnées si présentes et non vides
                if result['metadata'] and any(result['metadata'].values()):
                    meta_str = "Métadonnées: " + ", ".join([f"{k}: {v}" for k, v in result['metadata'].items() if v])
                    context += meta_str + "\n"
                    
                context += "---\n\n"
                total_length += text_length
            
            if len(results) > 0:
                logger.info(f"Contexte généré pour '{collection_name}' avec {len(results)} résultats, longueur: {total_length} caractères")
            
            return context

        except Exception as e:
            # Capture toutes les autres erreurs
            logger.error(f"Erreur inattendue lors de la génération du contexte: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "Une erreur inattendue s'est produite lors de la recherche d'informations contextuelles."

    def generate_response_with_rag(self, collection_name: str, query: str, data_transformer) -> str:
        """
        Génère une réponse avec RAG en utilisant le DataTransformer existant
        
        Args:
            collection_name: Nom de la collection à interroger
            query: Requête de l'utilisateur
            data_transformer: Instance de DataTransformer pour la génération
            
        Returns:
            Réponse générée
        """
        # Construire le contexte avec les informations récupérées
        context = self.build_context_from_query(collection_name, query)
        
        # Construire le prompt avec le contexte et la requête
        prompt = f"""
Tu es un assistant spécialisé dans l'analyse de données commerciales et financières pour l'entreprise.
Ta tâche est de répondre à la question en utilisant uniquement les informations fournies dans le contexte ci-dessous.

Contexte:
{context}

Question: {query}

Instructions:
1. Base ta réponse uniquement sur les informations du contexte fourni
2. Si le contexte ne contient pas assez d'informations, indique clairement les limites de ta réponse
3. Reste factuel et précis
4. Structure ta réponse de manière claire et concise

Réponse:
        """
        
        # Utiliser le DataTransformer pour générer la réponse
        response = data_transformer.generate_with_ai(prompt)
        
        if response and 'choices' in response:
            return response['choices'][0]['text']
        else:
            return "Désolé, je n'ai pas pu générer une réponse."

    def process_dataframe_to_collection(self, df: pd.DataFrame, collection_name: str, 
                                       chunk_strategy: str = 'row', chunk_size: int = 1) -> bool:
        """
        Traite un DataFrame pour créer ou mettre à jour une collection
        
        Args:
            df: DataFrame à traiter
            collection_name: Nom de la collection à créer/mettre à jour
            chunk_strategy: Stratégie de découpage ('row', 'group_by')
            chunk_size: Taille des chunks (nombre de lignes) si pertinent
            
        Returns:
            bool: True si le traitement a réussi
        """
        if not self._model_initialized:
            logger.error("Impossible de traiter le DataFrame: le modèle d'embedding n'est pas initialisé")
            return False
            
        texts = []
        metadata = []
        
        try:
            if chunk_strategy == 'row':
                # Traiter chaque ligne comme un document séparé
                for i in range(0, len(df), chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    
                    # Construire un texte descriptif pour chaque chunk
                    text = self._dataframe_chunk_to_text(chunk)
                    texts.append(text)
                    
                    # Créer les métadonnées
                    meta = {
                        'row_start': i,
                        'row_end': min(i+chunk_size-1, len(df)-1),
                        'chunk_size': len(chunk)
                    }
                    metadata.append(meta)
            
            elif chunk_strategy == 'group_by' and 'date_transaction' in df.columns:
                # Grouper par date pour avoir des insights temporels
                df['date_group'] = df['date_transaction'].dt.date if hasattr(df['date_transaction'], 'dt') else df['date_transaction']
                grouped = df.groupby('date_group')
                
                for date, group in grouped:
                    # Créer un texte descriptif pour cette journée
                    text = f"Date: {date}\n"
                    text += f"Nombre de transactions: {len(group)}\n"
                    
                    if 'montant_total' in group.columns:
                        text += f"Montant total: {group['montant_total'].sum():.2f}€\n"
                        text += f"Panier moyen: {group['montant_total'].mean():.2f}€\n"
                    
                    if 'magasin' in group.columns:
                        # Ajouter les magasins les plus fréquents
                        top_stores = group['magasin'].value_counts().head(3)
                        text += "Principaux magasins:\n"
                        for store, count in top_stores.items():
                            text += f"- {store}: {count} transactions\n"
                    
                    texts.append(text)
                    metadata.append({
                        'date': str(date),
                        'transactions_count': len(group),
                        'total_amount': float(group['montant_total'].sum()) if 'montant_total' in group.columns else 0
                    })
            
            else:
                # Stratégie de découpage non reconnue ou colonnes manquantes
                logger.warning(f"Stratégie de découpage non reconnue ou colonnes requises manquantes")
                
                # Traiter l'ensemble du DataFrame comme un seul document avec des statistiques
                text = f"Statistiques globales du DataFrame:\n"
                text += f"Nombre de lignes: {len(df)}\n"
                text += f"Colonnes: {', '.join(df.columns)}\n\n"
                
                # Ajouter des statistiques de base pour les colonnes numériques
                for col in df.select_dtypes(include=['number']).columns:
                    text += f"Statistiques pour {col}:\n"
                    text += f"- Moyenne: {df[col].mean():.2f}\n"
                    text += f"- Médiane: {df[col].median():.2f}\n"
                    text += f"- Min: {df[col].min():.2f}\n"
                    text += f"- Max: {df[col].max():.2f}\n\n"
                
                texts.append(text)
                metadata.append({
                    'rows': len(df),
                    'columns': list(df.columns)
                })
            
            # Vérifier si la collection existe
            if collection_name in self.collections:
                # Mise à jour de la collection existante
                return self.add_to_collection(collection_name, texts, metadata)
            else:
                # Création d'une nouvelle collection
                return self.create_collection(collection_name, texts, metadata)
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement du DataFrame: {e}")
            return False
    
    def _dataframe_chunk_to_text(self, chunk: pd.DataFrame) -> str:
        """Convertit un chunk de DataFrame en texte descriptif"""
        # Cette méthode peut être adaptée selon le type de données
        
        # Pour un petit chunk, on peut représenter les données directement
        if len(chunk) <= 3:
            # Convertir chaque ligne en texte descriptif
            lines = []
            for _, row in chunk.iterrows():
                line_items = []
                for col, val in row.items():
                    if pd.notna(val):  # Ignorer les valeurs NaN
                        line_items.append(f"{col}: {val}")
                lines.append(", ".join(line_items))
            
            return "\n".join(lines)
        
        # Pour un chunk plus grand, créer un résumé statistique
        else:
            text = f"Résumé de {len(chunk)} lignes:\n"
            
            # Ajouter des statistiques pour les colonnes numériques
            for col in chunk.select_dtypes(include=['number']).columns:
                text += f"{col}: moyenne={chunk[col].mean():.2f}, somme={chunk[col].sum():.2f}\n"
            
            # Pour les colonnes catégorielles, montrer les valeurs les plus fréquentes
            for col in chunk.select_dtypes(exclude=['number']).columns:
                if chunk[col].nunique() < 10:  # Seulement pour les colonnes avec peu de valeurs uniques
                    value_counts = chunk[col].value_counts().head(3)
                    top_values = [f"{val} ({count})" for val, count in value_counts.items()]
                    text += f"{col} top valeurs: {', '.join(top_values)}\n"
            
            return text

    def list_collections(self) -> List[Dict]:
        """
        Liste toutes les collections disponibles avec des métadonnées
        
        Returns:
            Liste des collections avec leurs métadonnées
        """
        collections_info = []
        
        for name, collection in self.collections.items():
            info = {
                'name': name,
                'document_count': len(collection['texts']),
                'created_at': collection.get('created_at', 'inconnu'),
                'updated_at': collection.get('updated_at', 'inconnu')
            }
            collections_info.append(info)
        
        return collections_info
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Supprime une collection
        
        Args:
            collection_name: Nom de la collection à supprimer
            
        Returns:
            bool: True si la suppression a réussi
        """
        if collection_name not in self.collections:
            logger.warning(f"Collection '{collection_name}' non trouvée")
            return False
        
        try:
            # Supprimer du dictionnaire
            del self.collections[collection_name]
            
            # Supprimer le fichier
            collection_path = os.path.join(self.vector_db_path, f"{collection_name}.pkl")
            if os.path.exists(collection_path):
                os.remove(collection_path)
            
            logger.info(f"Collection '{collection_name}' supprimée avec succès")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la collection '{collection_name}': {e}")
            return False