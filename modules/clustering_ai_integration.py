"""
Ce module étend la classe ClusteringProcessor avec des fonctionnalités d'analyse IA
au lieu d'ajouter dynamiquement une méthode à la fin du fichier original.
"""

from clustering_module import ClusteringProcessor
from data_transformer_module import DataTransformer
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AIEnhancedClusteringProcessor(ClusteringProcessor):
    """
    Version améliorée du ClusteringProcessor avec des capacités d'analyse IA intégrées
    """
    
    def __init__(self):
        """Initialisation en appelant le constructeur parent"""
        super().__init__()
        
    def analyze_clusters_with_ai(self, clustering_result, user_context=""):
        """
        Analyse les résultats du clustering avec l'IA locale
        
        Args:
            clustering_result: Résultat du clustering obtenu avec cluster_data
            user_context: Contexte utilisateur pour orienter l'analyse
            
        Returns:
            dict: Résultat de l'analyse avec un texte explicatif
        """
        if not clustering_result or not clustering_result.get("success", False):
            return {
                "success": False,
                "error": "Aucun résultat de clustering valide disponible pour l'analyse."
            }

        # Créer le transformateur de données qui contient l'accès à l'IA locale
        data_transformer = DataTransformer()
        
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
            # Créer un DataFrame minimal pour la méthode generate_dataset_analysis
            # Le DataFrame sert uniquement de support, car l'analyse réelle 
            # se fera à partir des informations du clustering via le prompt
            minimal_df = pd.DataFrame({
                "cluster_id": list(range(n_clusters)),
                "size": [clustering_result.get("cluster_sizes", {}).get(i, 0) 
                        for i in range(n_clusters)]
            })
            
            # Appeler generate_dataset_analysis avec le DataFrame minimal 
            # et le prompt détaillé comme contexte
            analysis_result = data_transformer.generate_dataset_analysis(
                minimal_df, 
                context=prompt
            )
            
            return {
                "success": True,
                "analysis": analysis_result,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse IA des clusters: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur lors de l'analyse IA: {str(e)}"
            }
