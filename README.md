# Projet d'Analyse de Données avec Clustering et IA

## Description

Ce projet est une application web d'analyse de données fournissant des fonctionnalités avancées de clustering avec intégration d'intelligence artificielle. L'application permet de charger des données, de les prétraiter, d'appliquer différents algorithmes de clustering, puis d'analyser et visualiser les résultats.

## Fonctionnalités principales

### Gestion des données
- Import de données CSV et via base de données SQLite
- Prévisualisation et exploration des données
- Prétraitement et transformation des données

### Clustering
- Algorithmes implémentés:
  - K-Means
  - DBSCAN
  - Clustering hiérarchique
- Paramétrage avancé des algorithmes
- Méthode du coude pour déterminer le nombre optimal de clusters
- Métriques d'évaluation (score silhouette, score Calinski-Harabasz, inertie)
- Visualisations 2D via PCA

### Analyse IA
- Interprétation automatique des clusters via IA
- Contextualisation des résultats
- Suggestions de noms pour les clusters
- Propositions d'actions basées sur la segmentation

### Visualisations
- Graphiques interactifs
- Statistiques détaillées par cluster
- Carte géographique des clients (module de cartographie)
- Calendrier d'achats

### Exportation des résultats
- Export en CSV/Excel
- Enregistrement des clusters dans les données
- Génération de rapports PDF

## Architecture technique

### Backend
- Flask (Python)
- SQLite pour le stockage des données
- Modules scientifiques:
  - scikit-learn pour les algorithmes de clustering
  - pandas pour la manipulation des données
  - numpy pour les calculs
  - PCA pour la réduction de dimensionnalité

### Frontend
- Bootstrap pour l'interface responsive
- Plotly.js pour les graphiques interactifs
- JavaScript pour les interactions dynamiques

### Modules principaux
- `clustering_module.py`: Implémentation des algorithmes de clustering
- `clustering_ai_integration.py`: Extension pour l'analyse IA des clusters
- `data_processor_module.py`: Traitement et transformation des données
- `app_routes.py`: Routes de l'application Flask

## Classe principale de clustering

La classe `ClusteringProcessor` fournit toutes les fonctionnalités de clustering:
- Application des algorithmes (K-Means, DBSCAN, Hiérarchique)
- Méthode du coude pour K-Means
- Calcul des métriques d'évaluation
- Génération de résumés textuels

L'extension `AIEnhancedClusteringProcessor` ajoute des capacités d'analyse IA:
- Interprétation des clusters avec IA locale
- Suggestions basées sur les caractéristiques des clusters
- Personnalisation de l'analyse via contexte utilisateur

## Installation

1. Cloner le dépôt:
```bash
git clone https://github.com/BaoFrancisNguyen/Teasy.git

```

2. Créer et activer un environnement virtuel:
```bash
python -m venv venv
source venv/bin/activate  # Pour Linux/Mac
venv\Scripts\activate     # Pour Windows
```

3. Installer les dépendances:
```bash
pip install -r requirements.txt
```

4. Configurer la base de données:
```bash
python init_database.py
```

5. Lancer l'application:
```bash
python app.py
```
6. Ouvrez un navigateur et aller sur http://localhost:5000/
   
## Utilisation

1. **Charger des données**:
   - Depuis un fichier CSV
   - Ou via la base de données de fidélité

2. **Explorer les données**:
   - Prévisualiser les données
   - Analyser les statistiques descriptives
   - Transformer et nettoyer si nécessaire

3. **Configurer et lancer le clustering**:
   - Choisir l'algorithme (K-Means, DBSCAN, Hiérarchique)
   - Sélectionner les colonnes pertinentes
   - Définir les paramètres ou utiliser la méthode du coude
   - Lancer le clustering

4. **Analyser les résultats**:
   - Visualiser les clusters via PCA
   - Examiner les statistiques par cluster
   - Demander une analyse IA des clusters
   - Exporter ou sauvegarder les résultats

## Fonctionnalités avancées

### Programme de fidélité
Le projet intègre également un module de gestion de programme de fidélité:
- Définition de règles de fidélité
- Génération automatique d'offres
- Planification des tâches de fidélité
- Suivi des points et récompenses

### Analyse géographique
- Visualisation des points de vente sur une carte
- Analyse des ventes par région
- Mise à jour des géolocalisations

### Analyse des sentiments
- Traitement des avis clients
- Segmentation de la clientèle
- Comparaison entre segments

## Contribution

Pour contribuer au projet:
1. Forker le dépôt
2. Créer une branche (`git checkout -b feature/nom-fonctionnalite`)
3. Faire les modifications
4. Commiter les changements (`git commit -m 'Ajout de fonctionnalité X'`)
5. Pousser vers la branche (`git push origin feature/nom-fonctionnalite`)
6. Ouvrir une Pull Request

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier `LICENSE` pour plus d'informations.

## Contact

Pour toute question ou suggestion, veuillez contacter: contact@example.com
