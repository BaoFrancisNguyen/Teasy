import pandas as pd
import numpy as np
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score
import logging
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

class ClusteringProcessor:
    """
    Module pour effectuer le clustering de données tabulaires
    """
    
    def __init__(self):
        """Initialisation du module de clustering"""
        self.algorithms = {
            'kmeans': self._apply_kmeans,
            'dbscan': self._apply_dbscan,
            'hierarchical': self._apply_hierarchical
        }
        self.last_result = None
    
    def cluster_data(self, df, algorithm='kmeans', columns=None, params=None):
        """
        Effectue le clustering des données selon l'algorithme spécifié
        
        Args:
            df: DataFrame pandas contenant les données
            algorithm: Algorithme de clustering ('kmeans', 'dbscan', 'hierarchical')
            columns: Liste des colonnes à utiliser (ou None pour toutes les colonnes numériques)
            params: Paramètres spécifiques pour l'algorithme
            
        Returns:
            dict: Résultat du clustering avec métadonnées
        """
        try:
            # Vérifier que le DataFrame n'est pas vide
            if df.empty:
                return {"success": False, "error": "Le DataFrame est vide"}
            
            # Sélectionner les colonnes numériques si columns=None
            if columns is None:
                columns = df.select_dtypes(include=[np.number]).columns.tolist()
            else:
                # Vérifier que les colonnes existent et sont numériques
                valid_columns = []
                for col in columns:
                    if col in df.columns:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            valid_columns.append(col)
                        else:
                            logger.warning(f"La colonne {col} n'est pas numérique et sera ignorée")
                    else:
                        logger.warning(f"La colonne {col} n'existe pas dans le DataFrame")
                
                columns = valid_columns
            
            if not columns:
                return {"success": False, "error": "Aucune colonne numérique valide n'a été trouvée ou spécifiée"}
            
            # Préparation des données
            data = df[columns].copy()
            
            # Traitement des valeurs manquantes
            data = data.dropna()
            
            if data.empty:
                return {"success": False, "error": "Après suppression des valeurs manquantes, aucune donnée n'est disponible"}
            
            # Standardisation des données
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            # Paramètres par défaut si non spécifiés
            if params is None:
                params = {}
            
            # Appliquer l'algorithme de clustering
            if algorithm in self.algorithms:
                result = self.algorithms[algorithm](scaled_data, data, params)
                
                if not result["success"]:
                    return result
                
                # Ajouter les métadonnées communes
                result["algorithm"] = algorithm
                result["columns_used"] = columns
                result["data_shape"] = data.shape
                result["params"] = params
                
                # Ajouter les résultats au DataFrame original si demandé
                if result.get("labels") is not None:
                    result_df = df.copy()
                    # Ajouter uniquement pour les lignes sans valeurs manquantes dans les colonnes utilisées
                    mask = ~df[columns].isna().any(axis=1)
                    cluster_labels = pd.Series(index=df.index, dtype='Int64')  # Type qui supporte les NA
                    cluster_labels.loc[mask] = result["labels"]
                    result_df[f"cluster_{algorithm}"] = cluster_labels
                    result["result_df"] = result_df
                
                # Stocker le dernier résultat
                self.last_result = result
                
                return result
            else:
                return {"success": False, "error": f"Algorithme '{algorithm}' non pris en charge"}
        
        except Exception as e:
            logger.error(f"Erreur lors du clustering: {e}", exc_info=True)
            return {"success": False, "error": f"Erreur lors du clustering: {str(e)}"}
    
    def _apply_kmeans(self, scaled_data, original_data, params):
        """Applique l'algorithme K-means"""
        # Paramètres par défaut
        n_clusters = params.get('n_clusters', 3)
        max_iter = params.get('max_iter', 300)
        n_init = params.get('n_init', 10)
        random_state = params.get('random_state', 42)
        
        try:
            # Appliquer K-means
            kmeans = KMeans(
                n_clusters=n_clusters,
                max_iter=max_iter,
                n_init=n_init,
                random_state=random_state
            )
            
            labels = kmeans.fit_predict(scaled_data)
            
            # Calcul des métriques d'évaluation
            if len(np.unique(labels)) > 1:  # Nécessite au moins 2 clusters pour calculer le silhouette score
                silhouette = silhouette_score(scaled_data, labels)
                calinski = calinski_harabasz_score(scaled_data, labels)
            else:
                silhouette = None
                calinski = None
            
            # Réduire les dimensions pour la visualisation si nécessaire
            pca_components = min(scaled_data.shape[1], 2)  # Au maximum 2 composantes
            pca = PCA(n_components=pca_components)
            pca_result = pca.fit_transform(scaled_data)
            
            # Préparer les résultats
            result = {
                "success": True,
                "labels": labels.tolist(),
                "cluster_centers": kmeans.cluster_centers_.tolist(),
                "n_clusters": n_clusters,
                "inertia": float(kmeans.inertia_),
                "silhouette_score": float(silhouette) if silhouette is not None else None,
                "calinski_harabasz_score": float(calinski) if calinski is not None else None,
                "cluster_sizes": {i: int((labels == i).sum()) for i in range(n_clusters)},
                "pca_result": pca_result.tolist(),
                "pca_explained_variance": pca.explained_variance_ratio_.tolist()
            }
            
            # Statistiques pour chaque cluster
            cluster_stats = []
            for i in range(n_clusters):
                cluster_data = original_data[labels == i]
                stats = {}
                for col in original_data.columns:
                    stats[col] = {
                        "mean": float(cluster_data[col].mean()),
                        "median": float(cluster_data[col].median()),
                        "std": float(cluster_data[col].std()),
                        "min": float(cluster_data[col].min()),
                        "max": float(cluster_data[col].max())
                    }
                cluster_stats.append(stats)
            
            result["cluster_stats"] = cluster_stats
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur lors de l'application de K-means: {e}", exc_info=True)
            return {"success": False, "error": f"Erreur lors de l'application de K-means: {str(e)}"}
    
    def _apply_dbscan(self, scaled_data, original_data, params):
        """Applique l'algorithme DBSCAN"""
        # Paramètres par défaut
        eps = params.get('eps', 0.5)
        min_samples = params.get('min_samples', 5)
        
        try:
            # Appliquer DBSCAN
            dbscan = DBSCAN(
                eps=eps,
                min_samples=min_samples
            )
            
            labels = dbscan.fit_predict(scaled_data)
            
            # Calcul des métriques d'évaluation
            n_clusters = len(np.unique(labels[labels >= 0]))  # Nombre de clusters (excluant le bruit -1)
            
            if n_clusters > 1 and len(np.unique(labels)) > 1:  # Au moins 2 clusters et pas uniquement du bruit
                silhouette = silhouette_score(scaled_data, labels)
                calinski = calinski_harabasz_score(scaled_data, labels)
            else:
                silhouette = None
                calinski = None
            
            # Réduire les dimensions pour la visualisation
            pca_components = min(scaled_data.shape[1], 2)  # Au maximum 2 composantes
            pca = PCA(n_components=pca_components)
            pca_result = pca.fit_transform(scaled_data)
            
            # Compter les points par cluster (y compris le bruit)
            unique_labels = np.unique(labels)
            cluster_sizes = {int(label): int((labels == label).sum()) for label in unique_labels}
            
            # Préparer les résultats
            result = {
                "success": True,
                "labels": labels.tolist(),
                "n_clusters": n_clusters,
                "silhouette_score": float(silhouette) if silhouette is not None else None,
                "calinski_harabasz_score": float(calinski) if calinski is not None else None,
                "noise_points": int((labels == -1).sum()),
                "cluster_sizes": cluster_sizes,
                "pca_result": pca_result.tolist(),
                "pca_explained_variance": pca.explained_variance_ratio_.tolist()
            }
            
            # Statistiques pour chaque cluster
            cluster_stats = {}
            for label in unique_labels:
                if label != -1:  # Ignorer le bruit pour les statistiques
                    cluster_data = original_data[labels == label]
                    stats = {}
                    for col in original_data.columns:
                        stats[col] = {
                            "mean": float(cluster_data[col].mean()),
                            "median": float(cluster_data[col].median()),
                            "std": float(cluster_data[col].std()),
                            "min": float(cluster_data[col].min()),
                            "max": float(cluster_data[col].max())
                        }
                    cluster_stats[int(label)] = stats
            
            result["cluster_stats"] = cluster_stats
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur lors de l'application de DBSCAN: {e}", exc_info=True)
            return {"success": False, "error": f"Erreur lors de l'application de DBSCAN: {str(e)}"}
    
    def _apply_hierarchical(self, scaled_data, original_data, params):
        """Applique l'algorithme de clustering hiérarchique"""
        # Paramètres par défaut
        n_clusters = params.get('n_clusters', 3)
        affinity = params.get('affinity', 'euclidean')
        linkage = params.get('linkage', 'ward')
        
        try:
            # Appliquer le clustering hiérarchique
            hierarchical = AgglomerativeClustering(
                n_clusters=n_clusters,
                affinity=affinity,
                linkage=linkage
            )
            
            labels = hierarchical.fit_predict(scaled_data)
            
            # Calcul des métriques d'évaluation
            if len(np.unique(labels)) > 1:  # Nécessite au moins 2 clusters
                silhouette = silhouette_score(scaled_data, labels)
                calinski = calinski_harabasz_score(scaled_data, labels)
            else:
                silhouette = None
                calinski = None
            
            # Réduire les dimensions pour la visualisation
            pca_components = min(scaled_data.shape[1], 2)  # Au maximum 2 composantes
            pca = PCA(n_components=pca_components)
            pca_result = pca.fit_transform(scaled_data)
            
            # Préparer les résultats
            result = {
                "success": True,
                "labels": labels.tolist(),
                "n_clusters": n_clusters,
                "silhouette_score": float(silhouette) if silhouette is not None else None,
                "calinski_harabasz_score": float(calinski) if calinski is not None else None,
                "cluster_sizes": {i: int((labels == i).sum()) for i in range(n_clusters)},
                "pca_result": pca_result.tolist(),
                "pca_explained_variance": pca.explained_variance_ratio_.tolist()
            }
            
            # Statistiques pour chaque cluster
            cluster_stats = []
            for i in range(n_clusters):
                cluster_data = original_data[labels == i]
                stats = {}
                for col in original_data.columns:
                    stats[col] = {
                        "mean": float(cluster_data[col].mean()),
                        "median": float(cluster_data[col].median()),
                        "std": float(cluster_data[col].std()),
                        "min": float(cluster_data[col].min()),
                        "max": float(cluster_data[col].max())
                    }
                cluster_stats.append(stats)
            
            result["cluster_stats"] = cluster_stats
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur lors de l'application du clustering hiérarchique: {e}", exc_info=True)
            return {"success": False, "error": f"Erreur lors de l'application du clustering hiérarchique: {str(e)}"}
    
    def get_elbow_method_data(self, df, columns=None, max_clusters=10):
        """
        Calcule les données pour la méthode du coude (K-means)
        
        Args:
            df: DataFrame pandas contenant les données
            columns: Liste des colonnes à utiliser (ou None pour toutes les colonnes numériques)
            max_clusters: Nombre maximum de clusters à tester
            
        Returns:
            dict: Résultat avec les inerties pour chaque nombre de clusters
        """
        try:
            # Vérifier que le DataFrame n'est pas vide
            if df.empty:
                return {"success": False, "error": "Le DataFrame est vide"}
            
            # Sélectionner les colonnes numériques si columns=None
            if columns is None:
                columns = df.select_dtypes(include=[np.number]).columns.tolist()
            else:
                # Vérifier que les colonnes existent et sont numériques
                valid_columns = []
                for col in columns:
                    if col in df.columns:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            valid_columns.append(col)
                        else:
                            logger.warning(f"La colonne {col} n'est pas numérique et sera ignorée")
                    else:
                        logger.warning(f"La colonne {col} n'existe pas dans le DataFrame")
                
                columns = valid_columns
            
            if not columns:
                return {"success": False, "error": "Aucune colonne numérique valide n'a été trouvée ou spécifiée"}
            
            # Préparation des données
            data = df[columns].copy()
            
            # Traitement des valeurs manquantes
            data = data.dropna()
            
            if data.empty:
                return {"success": False, "error": "Après suppression des valeurs manquantes, aucune donnée n'est disponible"}
            
            # Standardisation des données
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            # Calcul de l'inertie pour différents nombres de clusters
            inertias = []
            silhouette_scores = []
            calinski_scores = []
            
            range_clusters = range(2, min(max_clusters + 1, len(data) + 1))
            
            for k in range_clusters:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                kmeans.fit(scaled_data)
                inertias.append(float(kmeans.inertia_))
                
                labels = kmeans.labels_
                
                # Calcul des métriques d'évaluation
                if len(np.unique(labels)) > 1:  # Nécessite au moins 2 clusters
                    silhouette = silhouette_score(scaled_data, labels)
                    calinski = calinski_harabasz_score(scaled_data, labels)
                    silhouette_scores.append(float(silhouette))
                    calinski_scores.append(float(calinski))
                else:
                    silhouette_scores.append(None)
                    calinski_scores.append(None)
            
            return {
                "success": True,
                "n_clusters_range": list(range_clusters),
                "inertias": inertias,
                "silhouette_scores": silhouette_scores,
                "calinski_scores": calinski_scores
            }
        
        except Exception as e:
            logger.error(f"Erreur lors du calcul des données pour la méthode du coude: {e}", exc_info=True)
            return {"success": False, "error": f"Erreur lors du calcul des données pour la méthode du coude: {str(e)}"}
    
    def generate_cluster_summary(self, result):
        """
        Génère un résumé textuel des résultats du clustering
        
        Args:
            result: Résultat de la méthode cluster_data
            
        Returns:
            str: Résumé textuel
        """
        if not result or not result.get("success", False):
            return "Aucun résultat de clustering valide disponible."
        
        algorithm = result.get("algorithm", "inconnu")
        n_clusters = result.get("n_clusters", 0)
        
        if algorithm == "kmeans":
            summary = f"## Résultats du clustering K-Means\n\n"
            summary += f"**Nombre de clusters:** {n_clusters}\n"
            summary += f"**Inertie:** {result.get('inertia', 'N/A'):.2f}\n"
            
            if result.get("silhouette_score") is not None:
                summary += f"**Score silhouette:** {result.get('silhouette_score', 0):.4f} (entre -1 et 1, plus élevé = meilleur)\n"
            
            if result.get("calinski_harabasz_score") is not None:
                summary += f"**Score Calinski-Harabasz:** {result.get('calinski_harabasz_score', 0):.2f} (plus élevé = meilleur)\n"
            
            # Taille des clusters
            summary += "\n### Taille des clusters\n"
            for cluster, size in result.get("cluster_sizes", {}).items():
                summary += f"- Cluster {cluster}: {size} points\n"
            
            # Caractéristiques des clusters
            summary += "\n### Caractéristiques des clusters\n"
            for i, stats in enumerate(result.get("cluster_stats", [])):
                summary += f"\n#### Cluster {i}:\n"
                for col, values in stats.items():
                    summary += f"- {col}: moyenne = {values['mean']:.2f}, médiane = {values['median']:.2f}, écart-type = {values['std']:.2f}\n"
        
        elif algorithm == "dbscan":
            summary = f"## Résultats du clustering DBSCAN\n\n"
            summary += f"**Nombre de clusters:** {n_clusters}\n"
            summary += f"**Points de bruit:** {result.get('noise_points', 0)} ({result.get('noise_points', 0) / sum(result.get('cluster_sizes', {}).values()) * 100:.1f}%)\n"
            
            if result.get("silhouette_score") is not None:
                summary += f"**Score silhouette:** {result.get('silhouette_score', 0):.4f} (entre -1 et 1, plus élevé = meilleur)\n"
            
            if result.get("calinski_harabasz_score") is not None:
                summary += f"**Score Calinski-Harabasz:** {result.get('calinski_harabasz_score', 0):.2f} (plus élevé = meilleur)\n"
            
            # Taille des clusters
            summary += "\n### Taille des clusters\n"
            for cluster, size in result.get("cluster_sizes", {}).items():
                if cluster != -1:  # Ignorer le cluster de bruit (-1)
                    summary += f"- Cluster {cluster}: {size} points\n"
            
            # Caractéristiques des clusters
            summary += "\n### Caractéristiques des clusters\n"
            for cluster, stats in result.get("cluster_stats", {}).items():
                summary += f"\n#### Cluster {cluster}:\n"
                for col, values in stats.items():
                    summary += f"- {col}: moyenne = {values['mean']:.2f}, médiane = {values['median']:.2f}, écart-type = {values['std']:.2f}\n"
        
        elif algorithm == "hierarchical":
            summary = f"## Résultats du clustering hiérarchique\n\n"
            summary += f"**Nombre de clusters:** {n_clusters}\n"
            
            if result.get("silhouette_score") is not None:
                summary += f"**Score silhouette:** {result.get('silhouette_score', 0):.4f} (entre -1 et 1, plus élevé = meilleur)\n"
            
            if result.get("calinski_harabasz_score") is not None:
                summary += f"**Score Calinski-Harabasz:** {result.get('calinski_harabasz_score', 0):.2f} (plus élevé = meilleur)\n"
            
            # Taille des clusters
            summary += "\n### Taille des clusters\n"
            for cluster, size in result.get("cluster_sizes", {}).items():
                summary += f"- Cluster {cluster}: {size} points\n"
            
            # Caractéristiques des clusters
            summary += "\n### Caractéristiques des clusters\n"
            for i, stats in enumerate(result.get("cluster_stats", [])):
                summary += f"\n#### Cluster {i}:\n"
                for col, values in stats.items():
                    summary += f"- {col}: moyenne = {values['mean']:.2f}, médiane = {values['median']:.2f}, écart-type = {values['std']:.2f}\n"
        
        else:
            summary = f"## Résultats du clustering ({algorithm})\n\n"
            summary += f"**Nombre de clusters:** {n_clusters}\n"
            
            if result.get("silhouette_score") is not None:
                summary += f"**Score silhouette:** {result.get('silhouette_score', 0):.4f} (entre -1 et 1, plus élevé = meilleur)\n"
        
        return summary

    # 1. Ajout de la méthode d'analyse IA des clusters au ClusteringProcessor

def analyze_clusters_with_ai(self, clustering_result, user_context=""):
    """
    Analyse les résultats du clustering avec Ollama/Mistral
    
    Args:
        clustering_result: Résultat du clustering obtenu avec cluster_data
        user_context: Contexte utilisateur pour orienter l'analyse
        
    Returns:
        dict: Résultat de l'analyse avec un texte explicatif
    """
    import requests
    import json
    from datetime import datetime
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not clustering_result or not clustering_result.get("success", False):
        return {
            "success": False,
            "error": "Aucun résultat de clustering valide disponible pour l'analyse."
        }
    
    # Construire un prompt enrichi pour l'IA
    algorithm = clustering_result.get("algorithm", "inconnu")
    n_clusters = clustering_result.get("n_clusters", 0)
    
    # Récupérer les métriques importantes selon l'algorithme
    metrics = []
    if algorithm == "kmeans":
        metrics.append(f"Inertie: {clustering_result.get('inertia', 'N/A'):.2f}")
    if algorithm in ["kmeans", "dbscan", "hierarchical"]:
        if clustering_result.get("silhouette_score") is not None:
            metrics.append(f"Score silhouette: {clustering_result.get('silhouette_score', 0):.4f}")
        if clustering_result.get("calinski_harabasz_score") is not None:
            metrics.append(f"Score Calinski-Harabasz: {clustering_result.get('calinski_harabasz_score', 0):.2f}")
    
    # Taille des clusters
    cluster_sizes = []
    for cluster, size in clustering_result.get("cluster_sizes", {}).items():
        cluster_name = f"Cluster {cluster}"
        if algorithm == "dbscan" and cluster == -1:
            cluster_name = "Points de bruit (Cluster -1)"
        cluster_sizes.append(f"{cluster_name}: {size} points")
    
    # Caractéristiques des clusters (moyennes des variables par cluster)
    cluster_characteristics = []
    
    # Adapter selon l'algorithme
    if algorithm == "dbscan":
        for cluster_id, stats in clustering_result.get("cluster_stats", {}).items():
            if cluster_id == -1:  # Ignorer les points de bruit pour l'analyse
                continue
            cluster_info = [f"Cluster {cluster_id}:"]
            for col, values in stats.items():
                cluster_info.append(f"- {col}: moyenne = {values['mean']:.2f}, médiane = {values['median']:.2f}")
            cluster_characteristics.append("\n".join(cluster_info))
    else:  # kmeans et hierarchical ont la même structure
        for i, stats in enumerate(clustering_result.get("cluster_stats", [])):
            cluster_info = [f"Cluster {i}:"]
            for col, values in stats.items():
                cluster_info.append(f"- {col}: moyenne = {values['mean']:.2f}, médiane = {values['median']:.2f}")
            cluster_characteristics.append("\n".join(cluster_info))
    
    # Construire le prompt pour l'IA
    columns_used = ", ".join(clustering_result.get("columns_used", []))
    
    prompt = f"""
    Analyse les résultats suivants d'un clustering {algorithm.upper()} réalisé sur un jeu de données.
    
    INFORMATIONS GÉNÉRALES:
    - Algorithme: {algorithm}
    - Nombre de clusters: {n_clusters}
    - Variables utilisées: {columns_used}
    
    MÉTRIQUES:
    {chr(10).join(metrics)}
    
    TAILLE DES CLUSTERS:
    {chr(10).join(cluster_sizes)}
    
    CARACTÉRISTIQUES DES CLUSTERS:
    {chr(10).join(cluster_characteristics)}
    
    CONTEXTE UTILISATEUR:
    {user_context}
    
    INSTRUCTIONS:
    1. Fournir une interprétation des clusters trouvés (que représente chaque cluster?)
    2. Évaluer la qualité de la segmentation (les clusters sont-ils bien séparés?)
    3. Suggérer des noms ou labels pour chaque cluster en fonction de leurs caractéristiques
    4. Proposer des actions ou décisions basées sur cette segmentation
    5. Si pertinent, suggérer d'autres analyses complémentaires
    
    Formatez votre réponse de manière structurée avec des sections et sous-sections.
    """
    
    try:
        # Configuration pour Ollama
        ollama_url = "http://localhost:11434/api/generate"
        
        logger.info("Envoi d'une requête à Ollama pour l'analyse de clustering")
        logger.info(f"URL: {ollama_url}")
        logger.info(f"Prompt généré de {len(prompt)} caractères")
        
        # Paramètres de la requête
        payload = {
            "model": "mistral",  # ou un autre modèle disponible dans votre instance Ollama
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,  # Ajout d'un réglage de température pour la cohérence
            "max_tokens": 2000   # Limiter la longueur de la réponse
        }
        
        # Test préalable de disponibilité
        try:
            logger.info("Test de disponibilité d'Ollama...")
            test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if test_response.status_code != 200:
                logger.error(f"Erreur de connexion à Ollama: {test_response.status_code} - {test_response.text}")
                return {
                    "success": False,
                    "error": f"Ollama ne répond pas correctement (code: {test_response.status_code}). Vérifiez qu'Ollama est bien en cours d'exécution."
                }
                
            # Vérifier si le modèle Mistral est disponible
            models = test_response.json().get('models', [])
            mistral_available = any(model.get('name') == 'mistral' for model in models)
            
            if not mistral_available:
                logger.warning("Le modèle 'mistral' n'est pas disponible dans Ollama")
                # Trouver un modèle alternatif
                available_models = [model.get('name') for model in models]
                if available_models:
                    payload["model"] = available_models[0]  # Utiliser le premier modèle disponible
                    logger.info(f"Utilisation du modèle alternatif: {payload['model']}")
                else:
                    return {
                        "success": False,
                        "error": "Aucun modèle disponible dans Ollama. Veuillez installer le modèle Mistral avec 'ollama pull mistral'."
                    }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Impossible de se connecter à Ollama: {e}")
            return {
                "success": False,
                "error": f"Impossible de se connecter à Ollama ({str(e)}). Assurez-vous qu'Ollama est en cours d'exécution."
            }
        
        # Envoyer la requête à Ollama
        logger.info(f"Envoi de la requête à Ollama avec le modèle {payload['model']}")
        
        # Utiliser un timeout plus long pour la génération
        response = requests.post(ollama_url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            analysis_text = result.get('response', '')
            
            logger.info(f"Réponse reçue d'Ollama: {len(analysis_text)} caractères")
            logger.info(f"Extrait de la réponse: {analysis_text[:100]}...")
            
            # Nettoyer la réponse si nécessaire
            analysis_text = analysis_text.strip()
            
            return {
                "success": True,
                "analysis": analysis_text,
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_message = f"Erreur lors de la requête à Ollama: {response.status_code} - {response.text}"
            logger.error(error_message)
            return {
                "success": False,
                "error": error_message
            }
    except Exception as e:
        error_message = f"Erreur lors de l'analyse IA des clusters: {str(e)}"
        logger.error(error_message, exc_info=True)
        return {
            "success": False,
            "error": error_message
        }

# Ajouter cette méthode à la classe ClusteringProcessor
ClusteringProcessor.analyze_clusters_with_ai = analyze_clusters_with_ai


