import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json

class DashboardKPI:
    """
    Classe qui génère des KPI axés sur la compréhension des données plutôt que sur la structure.
    Permet de personnaliser les indicateurs selon le type de données et les préférences utilisateur.
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialise le générateur de KPI avec un DataFrame
        
        Args:
            df: Le DataFrame à analyser
        """
        self.df = df
        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist() if not df.empty else []
        self.categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist() if not df.empty else []
        self.date_cols = self._detect_date_columns()
        
        # Cache pour stocker les résultats des analyses lourdes
        self._cache = {}
    
    def _detect_date_columns(self) -> List[str]:
        """Détecte automatiquement les colonnes de date de manière robuste"""
        date_cols = []
        
        # Liste des formats de date courants à tester
        date_formats = [
            '%Y-%m-%d',      # YYYY-MM-DD
            '%d/%m/%Y',      # DD/MM/YYYY
            '%m/%d/%Y',      # MM/DD/YYYY
            '%Y/%m/%d',      # YYYY/MM/DD
            '%d-%m-%Y',      # DD-MM-YYYY
            '%m-%d-%Y',      # MM-DD-YYYY
            '%Y.%m.%d',      # YYYY.MM.DD
            '%d.%m.%Y',      # DD.MM.YYYY
            '%Y%m%d',        # YYYYMMDD
        ]
        
        for col in self.df.columns:
            try:
                # Échantillonner les données pour éviter de traiter des DataFrames trop volumineux
                sample = self.df[col].dropna().sample(min(100, len(self.df)))
                
                # Tester chaque format
                for fmt in date_formats:
                    try:
                        # Tenter de convertir avec un format spécifique
                        pd.to_datetime(sample, format=fmt, errors='raise')
                        date_cols.append(col)
                        break  # Sortir si un format fonctionne
                    except (ValueError, TypeError):
                        continue
                
                # Si aucun format spécifique ne fonctionne, essayer la conversion générique
                if col not in date_cols:
                    try:
                        pd.to_datetime(sample, infer_datetime_format=True, errors='raise')
                        date_cols.append(col)
                    except (ValueError, TypeError):
                        continue
            
            except Exception as e:
                # Log silencieux ou ignorer si la conversion échoue
                import logging
                logging.warning(f"Impossible de convertir la colonne {col} en date: {e}")
        
        return date_cols
    
    def get_available_kpi_types(self) -> Dict[str, List[str]]:
        """
        Renvoie tous les types de KPI disponibles par catégorie
        
        Returns:
            Dictionnaire des types de KPI disponibles
        """
        kpi_categories = {
            "Distribution": [
                "distribution_normality", 
                "distribution_skewness",
                "distribution_kurtosis",
                "distribution_outliers",
                "distribution_range"
            ],
            "Tendance": [
                "trend_central_tendency",
                "trend_variance",
                "trend_growth_rate"
            ],
            "Corrélation": [
                "correlation_strength",
                "correlation_matrix",
                "correlation_top_pairs"
            ],
            "Qualité": [
                "quality_completeness",
                "quality_consistency",
                "quality_duplicates",
                "quality_anomalies"
            ],
            "Segmentation": [
                "segment_pareto",
                "segment_clusters",
                "segment_category_dominance"
            ],
            "Temporel": [
                "time_seasonality",
                "time_trend",
                "time_volatility",
                "time_cycles"
            ],
            "Comparaison": [
                "compare_to_average",
                "compare_to_target",
                "compare_to_period",
                "compare_to_category"
            ]
        }
        
        # Filtrer les KPI qui ne sont pas pertinents pour ce DataFrame
        result = {}
        for category, kpis in kpi_categories.items():
            applicable_kpis = []
            
            for kpi in kpis:
                if (kpi.startswith("time_") and not self.date_cols):
                    # Ne pas inclure les KPI temporels s'il n'y a pas de colonnes de date
                    continue
                elif (kpi.startswith("correlation_") and len(self.numeric_cols) < 2):
                    # Ne pas inclure les KPI de corrélation s'il n'y a pas assez de colonnes numériques
                    continue
                elif (kpi.startswith("distribution_") and not self.numeric_cols):
                    # Ne pas inclure les KPI de distribution s'il n'y a pas de colonnes numériques
                    continue
                elif (kpi.startswith("segment_") and not self.categorical_cols and not self.numeric_cols):
                    # Ne pas inclure les KPI de segmentation s'il n'y a pas de colonnes catégorielles ou numériques
                    continue
                else:
                    applicable_kpis.append(kpi)
            
            if applicable_kpis:
                result[category] = applicable_kpis
        
        return result
    
    def get_kpi_metadata(self, kpi_type: str) -> Dict[str, Any]:
        """
        Renvoie les métadonnées d'un type de KPI spécifique
        
        Args:
            kpi_type: Le type de KPI
            
        Returns:
            Métadonnées du KPI (nom d'affichage, description, paramètres requis)
        """
        kpi_metadata = {
            # Distribution
            "distribution_normality": {
                "name": "Test de Normalité",
                "description": "Évalue si les données suivent une distribution normale",
                "icon": "fas fa-bell-curve",
                "color": "primary",
                "parameters": ["column"],
                "value_type": "score"  # Renvoie un score entre 0 et 100
            },
            "distribution_skewness": {
                "name": "Asymétrie (Skewness)",
                "description": "Mesure l'asymétrie de la distribution des données",
                "icon": "fas fa-balance-scale-left",
                "color": "info",
                "parameters": ["column"],
                "value_type": "indicator"  # Renvoie un indicateur directionnel (-1 à +1)
            },
            "distribution_kurtosis": {
                "name": "Aplatissement (Kurtosis)",
                "description": "Mesure le degré de concentration des données autour de la moyenne",
                "icon": "fas fa-compress-alt",
                "color": "info",
                "parameters": ["column"],
                "value_type": "indicator"
            },
            "distribution_outliers": {
                "name": "Détection d'Anomalies",
                "description": "Pourcentage de valeurs considérées comme aberrantes",
                "icon": "fas fa-exclamation-triangle",
                "color": "warning",
                "parameters": ["column"],
                "value_type": "percentage"
            },
            "distribution_range": {
                "name": "Amplitude",
                "description": "Étendue des valeurs (max - min)",
                "icon": "fas fa-arrows-alt-h",
                "color": "primary",
                "parameters": ["column"],
                "value_type": "value"
            },
            
            # Tendance
            "trend_central_tendency": {
                "name": "Tendance Centrale",
                "description": "Comparaison entre moyenne et médiane",
                "icon": "fas fa-bullseye",
                "color": "success",
                "parameters": ["column"],
                "value_type": "ratio"  # Renvoie un ratio (moyenne/médiane)
            },
            "trend_variance": {
                "name": "Variance Relative",
                "description": "Coefficient de variation (écart-type/moyenne)",
                "icon": "fas fa-chart-line",
                "color": "info",
                "parameters": ["column"],
                "value_type": "percentage"
            },
            "trend_growth_rate": {
                "name": "Taux de Croissance",
                "description": "Taux de croissance sur la période",
                "icon": "fas fa-chart-line",
                "color": "success",
                "parameters": ["column", "date_column"],
                "value_type": "percentage"
            },
            
            # Corrélation
            "correlation_strength": {
                "name": "Force de Corrélation",
                "description": "Mesure la force de corrélation entre deux variables",
                "icon": "fas fa-link",
                "color": "primary",
                "parameters": ["column1", "column2"],
                "value_type": "correlation"  # -1 à +1
            },
            "correlation_matrix": {
                "name": "Matrice de Corrélation",
                "description": "Force moyenne des corrélations dans le dataset",
                "icon": "fas fa-th",
                "color": "info",
                "parameters": [],
                "value_type": "percentage"
            },
            "correlation_top_pairs": {
                "name": "Meilleures Corrélations",
                "description": "Paires de variables les plus corrélées",
                "icon": "fas fa-star",
                "color": "warning",
                "parameters": [],
                "value_type": "list"
            },
            
            # Qualité
            "quality_completeness": {
                "name": "Complétude",
                "description": "Pourcentage de données non manquantes",
                "icon": "fas fa-check-circle",
                "color": "success",
                "parameters": ["column"],
                "value_type": "percentage"
            },
            "quality_consistency": {
                "name": "Cohérence",
                "description": "Évalue la cohérence des données",
                "icon": "fas fa-tasks",
                "color": "primary",
                "parameters": ["column1", "column2"],
                "value_type": "score"
            },
            "quality_duplicates": {
                "name": "Duplicatas",
                "description": "Pourcentage de lignes dupliquées",
                "icon": "fas fa-copy",
                "color": "warning",
                "parameters": [],
                "value_type": "percentage"
            },
            "quality_anomalies": {
                "name": "Anomalies Globales",
                "description": "Score global d'anomalies détectées",
                "icon": "fas fa-exclamation-circle",
                "color": "danger",
                "parameters": [],
                "value_type": "score"
            },
            
            # Segmentation
            "segment_pareto": {
                "name": "Analyse Pareto",
                "description": "% des données représentant 80% du total",
                "icon": "fas fa-percentage",
                "color": "primary",
                "parameters": ["category_column", "value_column"],
                "value_type": "percentage"
            },
            "segment_clusters": {
                "name": "Clusters Naturels",
                "description": "Nombre de groupes distincts détectés",
                "icon": "fas fa-object-group",
                "color": "info",
                "parameters": ["column"],
                "value_type": "count"
            },
            "segment_category_dominance": {
                "name": "Dominance Catégorielle",
                "description": "Pourcentage de la catégorie dominante",
                "icon": "fas fa-chart-pie",
                "color": "warning",
                "parameters": ["column"],
                "value_type": "percentage"
            },
            
            # Temporel
            "time_seasonality": {
                "name": "Saisonnalité",
                "description": "Force de la tendance saisonnière",
                "icon": "fas fa-calendar-alt",
                "color": "primary",
                "parameters": ["column", "date_column"],
                "value_type": "score"
            },
            "time_trend": {
                "name": "Tendance Temporelle",
                "description": "Direction et force de la tendance dans le temps",
                "icon": "fas fa-long-arrow-alt-up",
                "color": "success",
                "parameters": ["column", "date_column"],
                "value_type": "indicator"
            },
            "time_volatility": {
                "name": "Volatilité",
                "description": "Niveau de variabilité dans le temps",
                "icon": "fas fa-chart-line",
                "color": "warning",
                "parameters": ["column", "date_column"],
                "value_type": "score"
            },
            "time_cycles": {
                "name": "Cycles",
                "description": "Détection de cycles périodiques",
                "icon": "fas fa-sync",
                "color": "info",
                "parameters": ["column", "date_column"],
                "value_type": "days"  # Nombre de jours du cycle principal
            },
            
            # Comparaison
            "compare_to_average": {
                "name": "Écart à la Moyenne",
                "description": "Écart relatif à la moyenne globale",
                "icon": "fas fa-arrows-alt-v",
                "color": "primary",
                "parameters": ["column", "filter_column", "filter_value"],
                "value_type": "percentage"
            },
            "compare_to_target": {
                "name": "Atteinte d'Objectif",
                "description": "Pourcentage d'atteinte d'une valeur cible",
                "icon": "fas fa-bullseye",
                "color": "success",
                "parameters": ["column", "target_value"],
                "value_type": "percentage"
            },
            "compare_to_period": {
                "name": "Évolution Périodique",
                "description": "Évolution par rapport à la période précédente",
                "icon": "fas fa-calendar-week",
                "color": "info",
                "parameters": ["column", "date_column", "period"],
                "value_type": "percentage"
            },
            "compare_to_category": {
                "name": "Comparaison Catégorielle",
                "description": "Comparaison à une catégorie de référence",
                "icon": "fas fa-not-equal",
                "color": "warning",
                "parameters": ["column", "category_column", "reference_category"],
                "value_type": "percentage"
            }
        }
        
        return kpi_metadata.get(kpi_type, {
            "name": kpi_type,
            "description": "Type de KPI non reconnu",
            "icon": "fas fa-question",
            "color": "secondary",
            "parameters": [],
            "value_type": "unknown"
        })
    
    def calculate_kpi(self, kpi_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calcule un KPI spécifique avec les paramètres fournis
        
        Args:
            kpi_type: Le type de KPI à calculer
            parameters: Les paramètres requis par ce type de KPI
            
        Returns:
            Résultat du KPI avec métadonnées
        """
        # Si le DataFrame est vide, renvoyer une erreur
        if self.df.empty:
            return {
                "success": False,
                "error": "DataFrame vide",
                "value": None
            }
            
        # Récupérer les métadonnées du KPI
        metadata = self.get_kpi_metadata(kpi_type)
        
        # Si les paramètres ne sont pas fournis, initialiser un dictionnaire vide
        if parameters is None:
            parameters = {}
            
        try:
            # Dispatcher vers la méthode correspondante
            method_name = f"_calculate_{kpi_type}"
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                result = method(parameters)
                
                # Ajouter les métadonnées au résultat
                result.update({
                    "kpi_type": kpi_type,
                    "name": metadata["name"],
                    "description": metadata["description"],
                    "icon": metadata["icon"],
                    "color": metadata["color"],
                    "value_type": metadata["value_type"]
                })
                
                return result
            else:
                return {
                    "success": False,
                    "error": f"Méthode non implémentée pour le KPI: {kpi_type}",
                    "kpi_type": kpi_type,
                    "name": metadata["name"],
                    "value": None
                }
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "kpi_type": kpi_type,
                "name": metadata["name"],
                "value": None
            }
    
    def suggest_kpis(self, max_suggestions: int = 5) -> List[Dict[str, Any]]:
        """
        Suggère automatiquement des KPI pertinents basés sur le contenu du DataFrame
        
        Args:
            max_suggestions: Nombre maximum de suggestions
            
        Returns:
            Liste de KPI suggérés avec paramètres
        """
        suggestions = []
        
        # Si le DataFrame est vide, pas de suggestions
        if self.df.empty:
            return suggestions
            
        # 1. Distribution des valeurs numériques (si disponibles)
        if self.numeric_cols:
            # Suggérer la distribution de la première colonne numérique
            suggestions.append({
                "kpi_type": "distribution_normality",
                "parameters": {"column": self.numeric_cols[0]},
                "reason": "Comprendre la distribution des données numériques"
            })
            
            # Pour la première colonne numérique, vérifier les outliers
            suggestions.append({
                "kpi_type": "distribution_outliers",
                "parameters": {"column": self.numeric_cols[0]},
                "reason": "Identifier les valeurs aberrantes"
            })
        
        # 2. Corrélation si plusieurs colonnes numériques
        if len(self.numeric_cols) >= 2:
            suggestions.append({
                "kpi_type": "correlation_strength",
                "parameters": {"column1": self.numeric_cols[0], "column2": self.numeric_cols[1]},
                "reason": "Identifier les relations entre variables"
            })
            
            suggestions.append({
                "kpi_type": "correlation_top_pairs",
                "parameters": {},
                "reason": "Découvrir les corrélations les plus fortes"
            })
        
        # 3. Qualité des données
        suggestions.append({
            "kpi_type": "quality_completeness",
            "parameters": {"column": self.df.columns[0]},
            "reason": "Évaluer la qualité et complétude des données"
        })
        
        if len(self.df) > 100:  # Seulement pour les datasets suffisamment grands
            suggestions.append({
                "kpi_type": "quality_duplicates",
                "parameters": {},
                "reason": "Identifier les duplications de données"
            })
        
        # 4. Segmentation pour les données catégorielles
        if self.categorical_cols:
            suggestions.append({
                "kpi_type": "segment_category_dominance",
                "parameters": {"column": self.categorical_cols[0]},
                "reason": "Analyser la distribution des catégories"
            })
            
            # Si nous avons aussi des données numériques
            if self.numeric_cols:
                suggestions.append({
                    "kpi_type": "segment_pareto",
                    "parameters": {
                        "category_column": self.categorical_cols[0],
                        "value_column": self.numeric_cols[0]
                    },
                    "reason": "Identifier les catégories qui dominent la distribution"
                })
        
        # 5. Analyse temporelle si des colonnes de date sont détectées
        if self.date_cols and self.numeric_cols:
            suggestions.append({
                "kpi_type": "time_trend",
                "parameters": {
                    "column": self.numeric_cols[0],
                    "date_column": self.date_cols[0]
                },
                "reason": "Analyser l'évolution temporelle des données"
            })
            
            suggestions.append({
                "kpi_type": "time_seasonality",
                "parameters": {
                    "column": self.numeric_cols[0],
                    "date_column": self.date_cols[0]
                },
                "reason": "Détecter les patterns saisonniers"
            })
        
        # Limiter au nombre maximum de suggestions
        return suggestions[:max_suggestions]
    
    # IMPLÉMENTATIONS DES MÉTHODES DE CALCUL DE KPI
    
    # Distribution
    def _calculate_distribution_normality(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le test de normalité (Shapiro-Wilk ou approximation)"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        # Échantillonner pour les grands datasets (Shapiro-Wilk limité à 5000 points)
        sample = self.df[column].dropna()
        if len(sample) > 5000:
            sample = sample.sample(5000)
        
        try:
            from scipy import stats
            # Test de Shapiro-Wilk
            statistic, p_value = stats.shapiro(sample)
            
            # Convertir la p-valeur en score de normalité (0-100)
            # Plus la p-valeur est élevée, plus les données sont normales
            normality_score = min(100, p_value * 100)
            
            interpretation = ""
            if p_value < 0.05:
                interpretation = "Les données ne suivent probablement pas une distribution normale."
            else:
                interpretation = "Les données suivent probablement une distribution normale."
            
            return {
                "success": True,
                "value": normality_score,
                "raw_value": p_value,
                "sample_size": len(sample),
                "interpretation": interpretation
            }
        except Exception as e:
            # Fallback: utiliser le skewness et kurtosis pour approximer la normalité
            try:
                skewness = abs(sample.skew())
                kurtosis = abs(sample.kurtosis())
                
                # Plus les valeurs sont proches de 0, plus c'est normal
                # Skewness: 0 est idéal, >1 est non-normal
                # Kurtosis: 0 est idéal pour une distribution normale, >1 est non-normal
                skew_score = max(0, 100 - skewness * 50)
                kurt_score = max(0, 100 - kurtosis * 25)
                
                # Score combiné
                normality_score = (skew_score + kurt_score) / 2
                
                interpretation = ""
                if normality_score < 50:
                    interpretation = "Les données semblent s'écarter significativement d'une distribution normale."
                elif normality_score < 75:
                    interpretation = "Les données présentent une distribution proche de la normale avec quelques écarts."
                else:
                    interpretation = "Les données semblent suivre une distribution approximativement normale."
                
                return {
                    "success": True,
                    "value": normality_score,
                    "skewness": skewness,
                    "kurtosis": kurtosis,
                    "sample_size": len(sample),
                    "interpretation": interpretation,
                    "note": "Approximation basée sur l'asymétrie et l'aplatissement"
                }
            except:
                return {"success": False, "error": f"Erreur lors du calcul de normalité: {str(e)}", "value": 0}
    
    def _calculate_distribution_skewness(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule l'asymétrie (skewness) d'une distribution"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        try:
            sample = self.df[column].dropna()
            skewness = sample.skew()
            
            interpretation = ""
            if abs(skewness) < 0.5:
                interpretation = "Distribution approximativement symétrique."
            elif skewness < 0:
                interpretation = "Distribution asymétrique négative (queue à gauche)."
            else:
                interpretation = "Distribution asymétrique positive (queue à droite)."
                
            abs_skew = abs(skewness)
            severity = ""
            if abs_skew < 0.5:
                severity = "faible"
            elif abs_skew < 1:
                severity = "modérée"
            else:
                severity = "forte"
                
            return {
                "success": True,
                "value": skewness,
                "direction": "negative" if skewness < 0 else "positive",
                "severity": severity,
                "interpretation": interpretation
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur lors du calcul d'asymétrie: {str(e)}", "value": 0}
    
    def _calculate_distribution_kurtosis(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule l'aplatissement (kurtosis) d'une distribution"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        try:
            sample = self.df[column].dropna()
            kurtosis = sample.kurtosis()
            
            interpretation = ""
            if abs(kurtosis) < 0.5:
                interpretation = "Distribution avec un aplatissement proche de la normale (mésokurtique)."
            elif kurtosis < 0:
                interpretation = "Distribution plus aplatie que la normale (platykurtique), moins de valeurs extrêmes."
            else:
                interpretation = "Distribution plus pointue que la normale (leptokurtique), plus de valeurs extrêmes."
                
            abs_kurt = abs(kurtosis)
            severity = ""
            if abs_kurt < 0.5:
                severity = "proche de la normale"
            elif abs_kurt < 2:
                severity = "modérément différent de la normale"
            else:
                severity = "très différent de la normale"
                
            return {
                "success": True,
                "value": kurtosis,
                "type": "platykurtique" if kurtosis < 0 else "leptokurtique",
                "severity": severity,
                "interpretation": interpretation
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur lors du calcul d'aplatissement: {str(e)}", "value": 0}
    
    def _calculate_distribution_outliers(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le pourcentage de valeurs aberrantes"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        try:
            sample = self.df[column].dropna()
            
            # Calcul des quartiles et IQR
            q1 = sample.quantile(0.25)
            q3 = sample.quantile(0.75)
            iqr = q3 - q1
            
            # Définition des seuils pour les valeurs aberrantes
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # Détection des outliers
            outliers = sample[(sample < lower_bound) | (sample > upper_bound)]
            outlier_count = len(outliers)
            outlier_percentage = (outlier_count / len(sample)) * 100 if len(sample) > 0 else 0
            
            interpretation = ""
            if outlier_percentage < 1:
                interpretation = "Très peu de valeurs aberrantes. Distribution très propre."
            elif outlier_percentage < 5:
                interpretation = "Présence limitée de valeurs aberrantes. Distribution assez propre."
            elif outlier_percentage < 10:
                interpretation = "Présence modérée de valeurs aberrantes. Peut nécessiter un traitement."
            else:
                interpretation = "Forte présence de valeurs aberrantes. Nécessite un traitement ou investigation."
                
            return {
                "success": True,
                "value": outlier_percentage,
                "outlier_count": outlier_count,
                "sample_size": len(sample),
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "interpretation": interpretation
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur lors du calcul des outliers: {str(e)}", "value": 0}
    
    def _calculate_distribution_range(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule l'amplitude (range) d'une distribution"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        try:
            sample = self.df[column].dropna()
            min_val = sample.min()
            max_val = sample.max()
            range_val = max_val - min_val
            
            # Rapport entre range et écart-type
            std_dev = sample.std()
            range_to_std = range_val / std_dev if std_dev > 0 else 0
            
            interpretation = ""
            if range_to_std < 4:
                interpretation = "Distribution compacte, peu étalée."
            elif range_to_std < 6:
                interpretation = "Distribution d'amplitude normale."
            else:
                interpretation = "Distribution très étalée, grande variabilité."
                
            return {
                "success": True,
                "value": range_val,
                "min": min_val,
                "max": max_val,
                "range_to_std_ratio": range_to_std,
                "interpretation": interpretation
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur lors du calcul de l'amplitude: {str(e)}", "value": 0}
    
    # Tendance
    def _calculate_trend_central_tendency(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le ratio moyenne/médiane"""
        column = parameters.get("column")
        
        if not column or column not in self.numeric_cols:
            return {"success": False, "error": "Colonne numérique valide requise", "value": 0}
        
        try:
            sample = self.df[column].dropna()
            mean = sample.mean()
            median = sample.median()
            
            # Rapport entre moyenne et médiane
            ratio = mean / median if median != 0 else 1
            
            # Écart relatif
            relative_diff = ((mean - median) / median) * 100 if median != 0 else 0
            
            interpretation = ""
            if abs(relative_diff) < 5:
                interpretation = "Distribution symétrique, moyenne et médiane très proches."
            elif relative_diff > 0:
                interpretation = "Présence de valeurs élevées influençant la moyenne à la hausse."
            else:
                interpretation = "Présence de valeurs basses influençant la moyenne à la baisse."
                
            return {
                "success": True,
                "value": ratio,
                "mean": mean,
                "median": median,
                "relative_difference": relative_diff,
                "interpretation": interpretation
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur lors du calcul de tendance centrale: {str(e)}", "value": 0}