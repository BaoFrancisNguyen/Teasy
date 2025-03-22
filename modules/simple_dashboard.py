import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output, State, ALL, MATCH
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
import numpy as np
import json
import random
import sys
import traceback
from modules.kpi_dashboard import DashboardKPI

# Variable de débogage globale
DEBUG = True  # Mettre à True pour activer les messages de débogage

class MultiDashboard:
    def __init__(self, app, datafile):
        self.app = app

        if DEBUG:
            print("\n\n=== INITIALISATION DU DASHBOARD ===")
            print(f"Type de datafile: {type(datafile)}")
        
        # Vérifier si l'app est correctement initialisée
        if self.app is None:
            print("ERREUR: L'application Dash est None!")
            
        self.df = pd.DataFrame()  # DataFrame vide par défaut
        self.numeric_cols = []  # Initialisation à une liste vide
        self.categorical_cols = []
        
        # Charger les données
        try:
            if isinstance(datafile, str):
                try:
                    print(f"Tentative de chargement du fichier: {datafile}")
                    self.df = pd.read_csv(datafile)
                    print(f"Fichier CSV chargé avec succès: {datafile}, shape: {self.df.shape}")
                except Exception as e:
                    print(f"ERREUR lors du chargement du CSV: {e}")
                    try:
                        # Essayer avec un délimiteur différent
                        self.df = pd.read_csv(datafile, sep=';')
                        print(f"Fichier CSV chargé avec délimiteur ';': {datafile}, shape: {self.df.shape}")
                    except Exception as e2:
                        print(f"ERREUR lors de la seconde tentative: {e2}")
                        self.df = pd.DataFrame()
            elif isinstance(datafile, pd.DataFrame):
                self.df = datafile
                print(f"DataFrame passé directement, shape: {self.df.shape}")
            else:
                print(f"ATTENTION: Type de données non reconnu: {type(datafile)}")
                self.df = pd.DataFrame()
        except Exception as e:
            print(f"ERREUR CRITIQUE lors du chargement des données: {e}")
            traceback.print_exc()
            self.df = pd.DataFrame()
        
        # Initialiser le générateur de KPI
        self.kpi_generator = DashboardKPI(self.df)
        
        # Vérification explicite du DataFrame
        if self.df.empty:
            print("ATTENTION: Le DataFrame est vide!")
        else:
            print(f"DataFrame chargé avec succès: {self.df.shape[0]} lignes, {self.df.shape[1]} colonnes")
            print(f"Premières colonnes: {self.df.columns[:5].tolist()}")
            print(f"Types de données: {self.df.dtypes.value_counts().to_dict()}")
        
        # Identifier les colonnes
        if not self.df.empty:
            self.numeric_cols = self.df.select_dtypes(include=[np.number]).columns.tolist()
            self.categorical_cols = self.df.select_dtypes(include=['object']).columns.tolist()
            print(f"Colonnes numériques: {len(self.numeric_cols)}, Colonnes catégorielles: {len(self.categorical_cols)}")
        else:
            self.numeric_cols = []
            self.categorical_cols = []
            print("Aucune colonne détectée (DataFrame vide)")
        
        # Définir plusieurs palettes de couleurs
        self.color_palettes = {
            'Plotly': px.colors.qualitative.Plotly,
            'Pastel': px.colors.qualitative.Pastel,
            'Vif': px.colors.qualitative.Bold,
            'Foncé': px.colors.qualitative.Dark24,
            'Safe': px.colors.qualitative.Safe,
            'Vivid': px.colors.qualitative.Vivid
        }
        
        # Pour les variables numériques (échelles continues)
        self.continuous_color_scales = {
            'Viridis': 'Viridis',
            'Plasma': 'Plasma',
            'Inferno': 'Inferno',
            'Bleu-Rouge': 'RdBu',
            'Bleu-Vert': 'BuGn',
            'Jaune-Vert': 'YlGn',
            'Rouge-Jaune': 'YlOrRd',
            'Bleus': 'Blues',
            'Turquoise': 'Turbo'
        }
        
        # Styles de graphique prédéfinis (fond et grille)
        self.chart_styles = {
            'Classique': {
                'light': {'bg': 'white', 'grid': 'lightgray'},
                'dark': {'bg': '#333', 'grid': '#555'}
            },
            'Minimaliste': {
                'light': {'bg': '#f8f9fa', 'grid': '#e9ecef'},
                'dark': {'bg': '#212529', 'grid': '#495057'}
            },
            'Pastel': {
                'light': {'bg': '#f0f8ff', 'grid': '#d6eaff'},
                'dark': {'bg': '#282c34', 'grid': '#3e4451'}
            },
            'Dégradé': {
                'light': {'bg': '#ffffff', 'grid': '#e0e0e0'},
                'dark': {'bg': '#1a1a1a', 'grid': '#3d3d3d'}
            },
            'Professionnel': {
                'light': {'bg': '#eef2f5', 'grid': '#d8e1e8'},
                'dark': {'bg': '#2c3035', 'grid': '#41464b'}
            }
        }
        
        # Couleurs personnalisées pour les cards
        self.card_colors = {
            'header': '#1a3a5f',              # Bleu marine pour les en-têtes
            'kpi_bg': '#f5f9ff',              # Bleu très clair pour les KPI
            'analysis_bg': '#f0f7ff',         # Bleu-gris clair pour les cartes d'analyse
            'chart_bg': '#f8faff',            # Bleu pâle pour les cartes de graphiques
            'stats_bg': '#edf6ff',            # Bleu très pâle pour les statistiques
            'text_light': 'white',            # Texte clair
            'text_dark': '#333',              # Texte foncé
            'main_bg': '#f5f7fa'              # Couleur de fond principale
        }
        
        # Créer le layout
        print("Création du layout...")
        self.layout = self.create_layout()
        
        # Enregistrer les callbacks
        print("Enregistrement des callbacks...")
        self.register_callbacks()
        self.register_kpi_callbacks()
        print("Initialisation complète du dashboard.")
    
    # Méthodes d'assistance pour les KPI
    def _create_kpi_params_helper(self, kpi_type, i):
        """Méthode d'assistance pour créer les paramètres d'un KPI"""
        if not kpi_type:
            return []
        
        if kpi_type == "global_percentage":
            return [
                dbc.InputGroup([
                    dbc.InputGroupText("Colonne"),
                    dbc.Select(
                        id=f"kpi-column-{i}",
                        options=[{"label": col, "value": col} for col in self.df.columns]
                    )
                ], className="mb-2"),
                dbc.InputGroup([
                    dbc.InputGroupText("Valeur"),
                    dbc.Select(
                        id=f"kpi-value-filter-{i}",
                        placeholder="Sélectionnez une valeur",
                        options=[]
                    )
                ], className="mb-2")
            ]
        elif kpi_type == "count":
            return [
                dbc.InputGroup([
                    dbc.InputGroupText("Colonne"),
                    dbc.Select(
                        id=f"kpi-column-{i}",
                        options=[{"label": col, "value": col} for col in self.df.columns]
                    )
                ], className="mb-2"),
                dbc.InputGroup([
                    dbc.InputGroupText("Valeur"),
                    dbc.Select(
                        id=f"kpi-value-filter-{i}",
                        placeholder="Sélectionnez une valeur",
                        options=[]
                    )
                ], className="mb-2")
            ]
        elif kpi_type == "dominant_value":
            return [
                dbc.InputGroup([
                    dbc.InputGroupText("Colonne"),
                    dbc.Select(
                        id=f"kpi-column-{i}",
                        options=[{"label": col, "value": col} for col in self.df.columns]
                    )
                ], className="mb-2")
            ]
        elif kpi_type == "comparison":
            return [
                dbc.InputGroup([
                    dbc.InputGroupText("Colonne principale"),
                    dbc.Select(
                        id=f"kpi-column-{i}",
                        options=[{"label": col, "value": col} for col in self.df.columns]
                    )
                ], className="mb-2"),
                dbc.InputGroup([
                    dbc.InputGroupText("Valeur"),
                    dbc.Select(
                        id=f"kpi-value-filter-{i}",
                        placeholder="Sélectionnez une valeur",
                        options=[]
                    )
                ], className="mb-2"),
                dbc.InputGroup([
                    dbc.InputGroupText("Colonne secondaire"),
                    dbc.Select(
                        id=f"kpi-column-compare-{i}",
                        options=[{"label": col, "value": col} for col in self.df.columns]
                    )
                ], className="mb-2"),
                dbc.InputGroup([
                    dbc.InputGroupText("Valeur secondaire"),
                    dbc.Select(
                        id=f"kpi-value-compare-{i}",
                        placeholder="Sélectionnez une valeur",
                        options=[]
                    )
                ], className="mb-2")
            ]
        return []

    def _get_column_options_helper(self, column):
        """Méthode d'assistance pour obtenir les options d'une colonne"""
        if not column or column not in self.df.columns:
            return []
        
        try:
            # Récupérer les valeurs uniques
            unique_values = self.df[column].dropna().unique()
            
            # Limiter le nombre de valeurs
            max_values = 100
            if len(unique_values) > max_values:
                value_counts = self.df[column].value_counts().nlargest(max_values)
                unique_values = value_counts.index.tolist()
                
            # Convertir en options pour le dropdown
            options = [{"label": str(val), "value": str(val)} for val in unique_values]
            return options
        except Exception as e:
            print(f"Erreur lors de la récupération des valeurs uniques pour la colonne {column}: {e}")
            return []
    
    def create_layout(self):
        layout = html.Div([
            dbc.Container([
                # Titre principal et thème
                dbc.Row([
                    dbc.Col(html.H1("Dashboard Analytique Avancé", className="my-4"), width=9),
                    dbc.Col([
                        html.Div([
                            dbc.Label("Thème:", html_for="theme-switch", className="mr-2"),
                            dbc.Switch(
                                id="theme-switch",
                                label="Sombre",
                                value=False
                            )
                        ], className="d-flex align-items-center mt-4")
                    ], width=3)
                ]),
                
                # Section KPI personnalisables
                html.Div([
                    html.H4([
                        html.I(className="fas fa-chart-line mr-2"),
                        "Indicateurs clés de performance"
                    ], className="border-bottom pb-2 mb-3"),
                    
                    # Contrôles pour configurer les KPI
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("Configurer les KPI", id="config-kpi-button", color="primary", className="mb-3")
                        ], width=12)
                    ]),
                    
                    # Modal pour configurer les KPI
                    dbc.Modal([
                        dbc.ModalHeader("Configuration des KPI"),
                        dbc.ModalBody([
                            # Configuration des 6 emplacements de KPI
                            html.Div([
                                html.H5(f"KPI #{i+1}"),
                                dbc.InputGroup([
                                    dbc.InputGroupText("Titre"),  # Remplace InputGroupAddon
                                    dbc.Input(id=f"kpi-title-{i}", placeholder="Titre du KPI")
                                ], className="mb-2"),
                                dbc.InputGroup([
                                    dbc.InputGroupText("Type"),  # Remplace InputGroupAddon
                                    dbc.Select(
                                        id=f"kpi-type-{i}",
                                        options=[
                                            {"label": "Pourcentage global", "value": "global_percentage"},
                                            {"label": "Comptage simple", "value": "count"},
                                            {"label": "Valeur dominante", "value": "dominant_value"},
                                            {"label": "Comparaison", "value": "comparison"}
                                        ]
                                    )
                                ], className="mb-2"),
                                html.Div(id=f"kpi-params-{i}")
                            ], className="mb-4") for i in range(6)
                        ]),
                        dbc.ModalFooter(
                            dbc.Button("Appliquer", id="apply-kpi-config", className="ml-auto")
                        )
                    ], id="kpi-config-modal", size="lg"),
                    
                    # Rangée de KPIs personnalisés
                    dbc.Row([
                        # KPI 1-6: Emplacements personnalisables
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H3(id=f"kpi-value-{i}", className="text-center text-primary mb-0"),
                                    html.P(id=f"kpi-label-{i}", className="text-center text-muted mb-0"),
                                    dbc.Progress(id=f"kpi-progress-{i}", color="primary", className="mt-2", style={"height": "4px"})
                                ], style={"backgroundColor": self.card_colors['kpi_bg']})
                            ], className="shadow-sm text-center")
                        ], width=2) for i in range(6)
                    ], className="mb-4")
                ], className="mb-4 p-3 rounded shadow-sm", style={"backgroundColor": "white"}),
                
                # Section pour l'analyse approfondie
                dbc.Row([
                    # Sélecteur de colonne numérique pour analyse approfondie
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Analyse approfondie", className="text-white", style={"backgroundColor": self.card_colors['header']}),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Sélectionnez une colonne numérique:"),
                                        dcc.Dropdown(
                                            id="numeric-column-selector",
                                            options=[{"label": col, "value": col} for col in self.numeric_cols],
                                            value=self.numeric_cols[0] if self.numeric_cols else None,
                                            clearable=False
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        html.Label("Comparer avec:"),
                                        dcc.Dropdown(
                                            id="compare-column-selector",
                                            options=[{"label": col, "value": col} for col in self.numeric_cols],
                                            value=self.numeric_cols[1] if len(self.numeric_cols) > 1 else None,
                                            placeholder="Sélectionnez une colonne..."
                                        )
                                    ], width=6)
                                ]),
                                html.Div(id="numeric-analysis-output", className="mt-3")
                            ], style={"backgroundColor": self.card_colors['analysis_bg']})
                        ], className="shadow-sm")
                    ], width=6),
                    
                    # Carte de corrélation
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Matrice de corrélation", className="text-white", style={"backgroundColor": self.card_colors['header']}),
                            dbc.CardBody([
                                html.Div([
                                    html.P("Top corrélations détectées:", className="mb-2"),
                                    html.Div(id="correlation-matrix-summary")
                                ])
                            ], style={"backgroundColor": self.card_colors['analysis_bg']})
                        ], className="shadow-sm h-100")
                    ], width=6)
                ]),
                
                # Graphique de test statique
                html.Div([
                    html.H4("Graphique de test statique", className="mt-4"),
                    dcc.Graph(
                        id="static-test-chart",
                        figure=self.create_static_test_figure(),
                        style={"height": "400px", "border": "1px solid #ddd", "borderRadius": "8px"}
                    )
                ], className="mb-4"),
                
                # Bouton d'ajout de graphique
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-plus mr-2"), "Ajouter un graphique"], 
                            id="add-chart", 
                            color="primary", 
                            className="mb-3",
                            style={"borderRadius": "5px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}
                        )
                    ], width=12)
                ]),
                
                # Conteneur pour tous les graphiques
                html.Div(id="charts-container", children=[
                    # Premier graphique par défaut
                    self.create_chart_div(0)
                ])
            ], fluid=True)
        ], id="main-container", style={"backgroundColor": self.card_colors['main_bg'], "padding": "20px", "minHeight": "100vh"})
        
        return layout
    
    def create_static_test_figure(self):
        """Crée une figure de test statique pour vérifier le rendu"""
        # Données de test
        x = list(range(1, 11))
        y = [i*i for i in x]
        
        # Créer une figure simple
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines+markers',
            name='Test Data',
            marker=dict(
                color='rgba(52, 152, 219, 0.8)',
                size=10
            )
        ))
        
        # Titre et axes
        fig.update_layout(
            title="Graphique de test statique",
            xaxis_title="Valeur X",
            yaxis_title="Valeur Y (x²)",
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=40, r=40, t=60, b=40),
        )
        
        return fig
    
    def create_chart_div(self, index):
        """Crée un div contenant un graphique et ses contrôles"""
        return html.Div([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col([
                            # Titre personnalisable
                            dbc.Input(
                                id={"type": "chart-title", "index": index},
                                type="text",
                                placeholder=f"Titre du graphique {index + 1}",
                                value=f"Graphique {index + 1}",
                                className="border-0 bg-transparent font-weight-bold h4",
                                style={"color": self.card_colors['text_light']}
                            )
                        ], width=8),
                        dbc.Col([
                            # Boutons d'action
                            dbc.Button(
                                html.I(className="fas fa-download"),
                                id={"type": "export-btn", "index": index},
                                color="primary", 
                                size="sm",
                                className="float-right ml-2",
                                title="Exporter en PNG"
                            ),
                            dbc.Button(
                                html.I(className="fas fa-trash"),
                                id={"type": "remove-btn", "index": index},
                                color="danger", 
                                size="sm",
                                className="float-right",
                                title="Supprimer ce graphique"
                            )
                        ], width=4)
                    ])
                ], className="text-white", style={"backgroundColor": self.card_colors['header']}),
                dbc.CardBody([
                    # Contrôles
                    dbc.Row([
                        dbc.Col([
                            html.Label("Variable X"),
                            dcc.Dropdown(
                                id={"type": "x-var", "index": index},
                                options=[{"label": col, "value": col} for col in self.df.columns],
                                value=self.numeric_cols[0] if self.numeric_cols else None
                            )
                        ], width=3),
                        dbc.Col([
                            html.Label("Variable Y"),
                            dcc.Dropdown(
                                id={"type": "y-var", "index": index},
                                options=[{"label": col, "value": col} for col in self.numeric_cols],
                                value=self.numeric_cols[1] if len(self.numeric_cols) > 1 else None
                            )
                        ], width=3),
                        dbc.Col([
                            html.Label("Couleur (optionnel)"),
                            dcc.Dropdown(
                                id={"type": "color-var", "index": index},
                                options=[{"label": "Aucune", "value": None}] + 
                                        [{"label": col, "value": col} for col in self.df.columns],
                                value=None
                            )
                        ], width=3),
                        dbc.Col([
                            html.Label("Type de graphique"),
                            dcc.Dropdown(
                                id={"type": "chart-type", "index": index},
                                options=[
                                    {"label": "Nuage de points", "value": "scatter"},
                                    {"label": "Ligne", "value": "line"},
                                    {"label": "Barres", "value": "bar"},
                                    {"label": "Boîte à moustaches", "value": "box"},
                                    {"label": "Violon", "value": "violin"},
                                    {"label": "Histogramme", "value": "histogram"},
                                    {"label": "Camembert", "value": "pie"},
                                    {"label": "Heatmap", "value": "heatmap"}
                                ],
                                value="scatter"
                            )
                        ], width=3)
                    ]),
                    
                    # Options d'apparence
                    dbc.Row([
                        dbc.Col([
                            html.Label("Palette de couleurs"),
                            dcc.Dropdown(
                                id={"type": "color-palette", "index": index},
                                options=[{"label": name, "value": name} for name in self.color_palettes.keys()],
                                value="Plotly"
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Échelle continue"),
                            dcc.Dropdown(
                                id={"type": "color-scale", "index": index},
                                options=[{"label": name, "value": scale} for name, scale in self.continuous_color_scales.items()],
                                value="Viridis"
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Style de graphique"),
                            dcc.Dropdown(
                                id={"type": "chart-style", "index": index},
                                options=[{"label": name, "value": name} for name in self.chart_styles.keys()],
                                value="Classique"
                            )
                        ], width=4)
                    ], className="mt-3"),
                    
                    # Graphique
                    html.Div([
                        dcc.Graph(
                            id={"type": "chart", "index": index},
                            figure=self.create_empty_figure("Sélectionnez les variables pour créer un graphique"),
                            style={"height": "500px", "borderRadius": "8px", "overflow": "hidden"},
                            className="shadow-sm"
                        )
                    ], className="mt-3 p-2 rounded", style={"backgroundColor": "white"}),
                    
                    # Statistiques
                    html.Div(
                        id={"type": "stats-panel", "index": index},
                        className="mt-3"
                    )
                ], style={"backgroundColor": self.card_colors['chart_bg']})
            ], className="mb-4 shadow")
        ], id={"type": "chart-div", "index": index})
    
    def create_empty_figure(self, message="Aucune donnée à afficher", dark_mode=False):
        """
        Crée une figure vide avec un message
        
        Args:
            message: Message à afficher
            dark_mode: Si True, applique le thème sombre
            
        Returns:
            dict: Figure Plotly vide avec un message
        """
        # Couleurs selon le mode
        bg_color = "#343a40" if dark_mode else "white"
        text_color = "white" if dark_mode else "#212529"
        
        fig = go.Figure()
        fig.update_layout(
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": message,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {
                        "color": text_color,
                        "size": 16
                    }
                }
            ],
            plot_bgcolor=bg_color,
            paper_bgcolor=bg_color,
            margin={"t": 30, "b": 30, "l": 30, "r": 30},
            height=400
        )
        return fig
    
    def debug_figure_creation(self, x_var, y_var, data):
        """
        Aide à déboguer la création de figures en produisant une figure très basique
        
        Args:
            x_var: Variable X
            y_var: Variable Y
            data: DataFrame
            
        Returns:
            Figure Plotly basique
        """
        # Créer un graphique simple
        fig = go.Figure()
        
        # Ajouter une série de données (scatter plot)
        fig.add_trace(go.Scatter(
            x=data[x_var],
            y=data[y_var],
            mode='markers',
            marker=dict(color='blue', size=8)
        ))
        
        # Titre et axes
        fig.update_layout(
            title=f"{x_var} vs {y_var}",
            xaxis_title=x_var,
            yaxis_title=y_var,
            margin=dict(l=40, r=40, t=60, b=40),
            height=400
        )
        
        return fig
    
    def register_kpi_callbacks(self):
        """Enregistrer les callbacks pour les KPI"""
        # Callback pour ouvrir la modale de configuration des KPI
        @self.app.callback(
            Output("kpi-config-modal", "is_open"),
            [Input("config-kpi-button", "n_clicks"), 
             Input("apply-kpi-config", "n_clicks")],
            [State("kpi-config-modal", "is_open")],
            prevent_initial_call=True
        )
        def toggle_kpi_modal(n1, n2, is_open):
            if n1 or n2:
                return not is_open
            return is_open
        
        # Callbacks pour les paramètres des KPI
        for i in range(6):
            @self.app.callback(
                Output(f"kpi-params-{i}", "children"),
                Input(f"kpi-type-{i}", "value")
            )
            def update_kpi_params(value, i=i):
                print(f"Updating KPI params for KPI #{i+1} with value {value}")
                return self._create_kpi_params_helper(value, i)
            
            # Callback pour les valeurs des listes déroulantes
            @self.app.callback(
                Output(f"kpi-value-filter-{i}", "options"),
                Input(f"kpi-column-{i}", "value")
            )
            def update_kpi_values_options(column, i=i):
                print(f"Updating KPI value options for KPI #{i+1} with column {column}")
                return self._get_column_options_helper(column)
            
            # Pour les KPI de type comparaison
            @self.app.callback(
                Output(f"kpi-value-compare-{i}", "options"),
                Input(f"kpi-column-compare-{i}", "value")
            )
            def update_kpi_compare_options(column, i=i):
                print(f"Updating KPI compare options for KPI #{i+1} with column {column}")
                return self._get_column_options_helper(column)
        
        # Callback pour appliquer la configuration des KPI
        @self.app.callback(
            [Output(f"kpi-value-{i}", "children") for i in range(6)] +
            [Output(f"kpi-label-{i}", "children") for i in range(6)] +
            [Output(f"kpi-progress-{i}", "value") for i in range(6)],
            Input("apply-kpi-config", "n_clicks"),
            [State(f"kpi-title-{i}", "value") for i in range(6)] +
            [State(f"kpi-type-{i}", "value") for i in range(6)] +
            [State(f"kpi-column-{i}", "value") for i in range(6)] +
            [State(f"kpi-value-filter-{i}", "value") for i in range(6)],
            prevent_initial_call=True
        )
        def apply_kpi_config(n_clicks, *args):
            if n_clicks is None:
                return [None] * 18
            
            print(f"Applying KPI config, n_clicks: {n_clicks}, args: {args}")
            
            # Extraire les arguments
            titles = args[:6]
            types = args[6:12]
            columns = args[12:18]
            values = args[18:24]
            
            # Préparer les retours
            kpi_values = []
            kpi_labels = []
            kpi_progress = []
            
            for i in range(6):
                try:
                    # Titre par défaut si non spécifié
                    label = titles[i] if titles[i] else f"KPI #{i+1}"
                    
                    # Valeur du KPI
                    kpi_type = types[i]
                    column = columns[i]
                    
                    if not kpi_type or not column:
                        # Cas où le KPI n'est pas configuré
                        kpi_values.append("--")
                        kpi_labels.append(label)
                        kpi_progress.append(0)
                        continue
                    
                    # Calculer la valeur selon le type
                    if kpi_type == "global_percentage":
                        if values[i]:
                            # Pourcentage d'une valeur spécifique
                            count = len(self.df[self.df[column] == values[i]])
                            total = len(self.df)
                            percentage = (count / total) * 100 if total > 0 else 0
                            kpi_values.append(f"{percentage:.1f}%")
                            kpi_progress.append(percentage)
                        else:
                            # Taux de remplissage
                            non_null = self.df[column].dropna().count()
                            total = len(self.df)
                            percentage = (non_null / total) * 100 if total > 0 else 0
                            kpi_values.append(f"{percentage:.1f}%")
                            kpi_progress.append(percentage)
                    
                    elif kpi_type == "count":
                        if values[i]:
                            # Compte d'une valeur spécifique
                            count = len(self.df[self.df[column] == values[i]])
                            kpi_values.append(str(count))
                            kpi_progress.append(min(100, (count / len(self.df)) * 100) if len(self.df) > 0 else 0)
                        else:
                            # Nombre total d'éléments non nuls
                            count = self.df[column].dropna().count()
                            kpi_values.append(str(count))
                            kpi_progress.append(min(100, (count / len(self.df)) * 100) if len(self.df) > 0 else 0)
                    
                    elif kpi_type == "dominant_value":
                        # Valeur la plus fréquente
                        value_counts = self.df[column].value_counts()
                        if not value_counts.empty:
                            top_value = value_counts.index[0]
                            count = value_counts.iloc[0]
                            percentage = (count / len(self.df)) * 100 if len(self.df) > 0 else 0
                            kpi_values.append(str(top_value))
                            kpi_progress.append(percentage)
                        else:
                            kpi_values.append("N/A")
                            kpi_progress.append(0)
                    
                    elif kpi_type == "comparison":
                        # Pas encore implémenté
                        kpi_values.append("TODO")
                        kpi_progress.append(50)
                    
                    else:
                        # Type non reconnu
                        kpi_values.append("?")
                        kpi_progress.append(0)
                    
                    kpi_labels.append(label)
                
                except Exception as e:
                    print(f"Erreur lors du calcul du KPI #{i+1}: {e}")
                    kpi_values.append("Erreur")
                    kpi_labels.append(f"KPI #{i+1}")
                    kpi_progress.append(0)
            
            return kpi_values + kpi_labels + kpi_progress
    
    def register_callbacks(self):
        print("=== Enregistrement des callbacks principaux ===")
        
        # Callback pour le thème
        @self.app.callback(
            [Output("main-container", "style"),
             Output("add-chart", "color")],
            Input("theme-switch", "value")
        )
        def toggle_theme(dark_mode):
            print(f"Callback toggle_theme déclenché: {dark_mode}")
            if dark_mode:
                return {
                    "backgroundColor": "#343a40", 
                    "color": "white", 
                    "padding": "20px",
                    "minHeight": "100vh"
                }, "info"
            else:
                return {
                    "backgroundColor": self.card_colors['main_bg'], 
                    "color": "#212529", 
                    "padding": "20px",
                    "minHeight": "100vh"
                }, "primary"
        
        # Callback pour ajouter un graphique
        @self.app.callback(
            Output("charts-container", "children"),
            Input("add-chart", "n_clicks"),
            State("charts-container", "children"),
            prevent_initial_call=True
        )
        def add_chart(n_clicks, children):
            print(f"Callback add_chart déclenché: n_clicks={n_clicks}")
            if n_clicks is None:
                return children
            
            new_index = len(children)
            return children + [self.create_chart_div(new_index)]
        
        # Callback pour mettre à jour un graphique
        @self.app.callback(
            Output({"type": "chart", "index": MATCH}, "figure"),
            [Input({"type": "x-var", "index": MATCH}, "value"),
             Input({"type": "y-var", "index": MATCH}, "value"),
             Input({"type": "color-var", "index": MATCH}, "value"),
             Input({"type": "chart-type", "index": MATCH}, "value"),
             Input({"type": "color-palette", "index": MATCH}, "value"),
             Input({"type": "color-scale", "index": MATCH}, "value"),
             Input({"type": "chart-style", "index": MATCH}, "value"),
             Input({"type": "chart-title", "index": MATCH}, "value"),
             Input("theme-switch", "value")]
        )
        def update_chart(x_var, y_var, color_var, chart_type, color_palette, color_scale, chart_style, chart_title, dark_mode):
            print(f"Callback update_chart déclenché: x={x_var}, y={y_var}, type={chart_type}")
            
            # Récupérer le style de graphique
            style_theme = 'dark' if dark_mode else 'light'
            if chart_style in self.chart_styles:
                style_config = self.chart_styles[chart_style][style_theme]
                
                # Définir les couleurs selon le style
                if isinstance(style_config['bg'], list):
                    paper_bg = style_config['bg'][0]
                    plot_bg = style_config['bg'][0]  # Utiliser une couleur solide pour éviter les problèmes
                else:
                    paper_bg = style_config['bg']
                    plot_bg = style_config['bg']
                
                grid_color = style_config['grid']
            else:
                # Fallback sur des couleurs standards
                paper_bg = "#495057" if dark_mode else "white"
                plot_bg = "#495057" if dark_mode else "white"
                grid_color = "#6c757d" if dark_mode else "lightgray"
            
            # Couleur du texte
            text_color = "white" if dark_mode else "#212529"
            
            # Vérifications de base
            if self.df.empty:
                return self.create_empty_figure("Le DataFrame est vide", dark_mode)
                
            if not x_var or (not y_var and chart_type != "histogram"):
                return self.create_empty_figure("Veuillez sélectionner les variables X et Y", dark_mode)
                
            if x_var not in self.df.columns or (y_var and y_var not in self.df.columns):
                return self.create_empty_figure(f"Variables non trouvées: {x_var} ou {y_var}", dark_mode)
            
            # Débogage détaillé
            print(f"DEBUG: DataFrame dimensions: {self.df.shape}")
            print(f"DEBUG: x_var: {x_var}, y_var: {y_var}, chart_type: {chart_type}")
            
            try:
                # Échantillonnage pour performance si nécessaire
                if len(self.df) > 5000:
                    df_plot = self.df.sample(5000).copy()
                else:
                    df_plot = self.df.copy()
                
                # Vérifier les colonnes avant de les utiliser
                missing_cols = []
                if x_var not in df_plot.columns:
                    missing_cols.append(x_var)
                if y_var and y_var not in df_plot.columns:
                    missing_cols.append(y_var)
                
                if missing_cols:
                    error_msg = f"Colonnes non trouvées: {', '.join(missing_cols)}"
                    print(f"ERROR: {error_msg}")
                    return self.create_empty_figure(error_msg, dark_mode)
                
                # Vérifier les types de données et la présence de NaN
                print(f"DEBUG: Type x_var: {df_plot[x_var].dtype}, NaN: {df_plot[x_var].isna().sum()}")
                if y_var:
                    print(f"DEBUG: Type y_var: {df_plot[y_var].dtype}, NaN: {df_plot[y_var].isna().sum()}")
                
                # Supprimer les lignes avec valeurs manquantes pour x_var et y_var si nécessaire
                if y_var:
                    df_plot = df_plot.dropna(subset=[x_var, y_var])
                else:
                    df_plot = df_plot.dropna(subset=[x_var])
                
                print(f"DEBUG: DataFrame après filtrage NaN: {df_plot.shape}")
                
                if df_plot.empty:
                    return self.create_empty_figure("Aucune donnée valide après filtrage des valeurs manquantes", dark_mode)
                
                # En cas de problème, utiliser une méthode de débogage pour créer une figure simple
                if chart_type == "debug":
                    return self.debug_figure_creation(x_var, y_var, df_plot)
                
                # Définir les arguments de couleur
                color_args = {}
                if color_var:
                    if color_var in self.numeric_cols:
                        color_args = {"color": color_var, "color_continuous_scale": color_scale}
                    else:
                        color_args = {"color": color_var, "color_discrete_sequence": self.color_palettes[color_palette]}
                
                # Utiliser le titre personnalisé ou générer un titre par défaut si vide
                title_text = chart_title if chart_title else f"{x_var} vs {y_var}" if y_var else f"Distribution de {x_var}"
                
                # Création du graphique selon le type
                if chart_type == "scatter":
                    fig = px.scatter(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                elif chart_type == "line":
                    fig = px.line(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                elif chart_type == "bar":
                    # Pour les barres, limiter le nombre de catégories si x est catégoriel
                    if x_var in self.categorical_cols:
                        # Prendre les 20 catégories les plus fréquentes
                        top_cats = df_plot[x_var].value_counts().nlargest(20).index.tolist()
                        df_filtered = df_plot[df_plot[x_var].isin(top_cats)]
                        fig = px.bar(df_filtered, x=x_var, y=y_var, title=title_text, **color_args)
                    else:
                        fig = px.bar(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                elif chart_type == "box":
                    fig = px.box(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                elif chart_type == "violin":
                    fig = px.violin(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                elif chart_type == "histogram":
                    fig = px.histogram(df_plot, x=x_var, title=title_text, **color_args)
                elif chart_type == "pie":
                    if x_var in self.categorical_cols and y_var in self.numeric_cols:
                        # Agrégation pour le camembert
                        agg_df = df_plot.groupby(x_var)[y_var].sum().reset_index()
                        # Limiter à 10 catégories maximum pour la lisibilité
                        if len(agg_df) > 10:
                            top_values = agg_df.sort_values(y_var, ascending=False).iloc[:9]
                            other_value = pd.DataFrame({
                                x_var: ['Autres'],
                                y_var: [agg_df.iloc[9:][y_var].sum()]
                            })
                            agg_df = pd.concat([top_values, other_value])
                        
                        fig = px.pie(
                            agg_df, names=x_var, values=y_var,
                            title=title_text,
                            color_discrete_sequence=self.color_palettes[color_palette]
                        )
                    else:
                        return self.create_empty_figure("Le camembert nécessite une variable catégorielle (X) et une variable numérique (Y)", dark_mode)
                elif chart_type == "heatmap":
                    try:
                        # Créer un tableau croisé pour la heatmap
                        pivot_df = pd.pivot_table(
                            df_plot, values=y_var, index=x_var,
                            columns=color_var if color_var else None,
                            aggfunc='mean'
                        )
                        
                        # Limiter la taille du tableau croisé si nécessaire
                        if pivot_df.shape[0] > 20 or pivot_df.shape[1] > 20:
                            if pivot_df.shape[0] > 20:
                                pivot_df = pivot_df.iloc[:20, :]
                            if pivot_df.shape[1] > 20:
                                pivot_df = pivot_df.iloc[:, :20]
                        
                        fig = px.imshow(
                            pivot_df,
                            title=title_text,
                            color_continuous_scale=color_scale
                        )
                    except Exception as pivot_error:
                        return self.create_empty_figure(f"Erreur lors de la création de la heatmap: {str(pivot_error)}", dark_mode)
                else:
                    # Type par défaut
                    fig = px.scatter(df_plot, x=x_var, y=y_var, title=title_text, **color_args)
                
                # Mettre à jour le style selon le thème
                fig.update_layout(
                    plot_bgcolor=plot_bg,
                    paper_bgcolor=paper_bg,
                    font=dict(color=text_color),
                    title=dict(
                        text=title_text,
                        font=dict(size=16, color=text_color),
                        x=0.5  # Centrer le titre
                    ),
                    margin=dict(l=40, r=40, t=60, b=40),
                    xaxis=dict(
                        title=dict(text=x_var, font=dict(size=14, color=text_color)),
                        gridcolor=grid_color,
                        showgrid=True
                    ),
                    yaxis=dict(
                        title=dict(text=y_var if y_var else "", font=dict(size=14, color=text_color)),
                        gridcolor=grid_color,
                        showgrid=True
                    ),
                    height=500  # Définir une hauteur fixe
                )
                
                return fig
            
            except Exception as e:
                print(f"Erreur dans update_chart: {e}")
                traceback.print_exc()
                return self.create_empty_figure(f"Erreur: {str(e)}", dark_mode)
        
        # Callback pour mettre à jour les statistiques du graphique
        @self.app.callback(
            Output({"type": "stats-panel", "index": MATCH}, "children"),
            [Input({"type": "chart", "index": MATCH}, "figure"),
             Input({"type": "x-var", "index": MATCH}, "value"),
             Input({"type": "y-var", "index": MATCH}, "value")]
        )
        def update_stats_panel(figure, x_var, y_var):
            print(f"Callback update_stats_panel déclenché: x={x_var}, y={y_var}")
            
            if not x_var or not figure:
                return html.Div("Sélectionnez des variables pour voir les statistiques")
            
            try:
                # Calculer des statistiques basiques pour x et y
                stats_x = {}
                if x_var in self.df.columns:
                    if pd.api.types.is_numeric_dtype(self.df[x_var]):
                        data_x = self.df[x_var].dropna()
                        stats_x = {
                            "min": data_x.min(),
                            "max": data_x.max(),
                            "mean": data_x.mean(),
                            "median": data_x.median(),
                            "std": data_x.std()
                        }
                    else:
                        # Pour les données catégorielles
                        data_x = self.df[x_var].dropna()
                        value_counts = data_x.value_counts()
                        most_common = value_counts.idxmax() if not value_counts.empty else "N/A"
                        
                        stats_x = {
                            "unique_values": data_x.nunique(),
                            "most_common": most_common,
                            "most_common_count": value_counts.max() if not value_counts.empty else 0
                        }
                
                stats_y = {}
                if y_var and y_var in self.df.columns:
                    if pd.api.types.is_numeric_dtype(self.df[y_var]):
                        data_y = self.df[y_var].dropna()
                        stats_y = {
                            "min": data_y.min(),
                            "max": data_y.max(),
                            "mean": data_y.mean(),
                            "median": data_y.median(),
                            "std": data_y.std()
                        }
                    else:
                        # Pour les données catégorielles
                        data_y = self.df[y_var].dropna()
                        value_counts = data_y.value_counts()
                        most_common = value_counts.idxmax() if not value_counts.empty else "N/A"
                        
                        stats_y = {
                            "unique_values": data_y.nunique(),
                            "most_common": most_common,
                            "most_common_count": value_counts.max() if not value_counts.empty else 0
                        }
                
                # Calculer la corrélation si les deux variables sont numériques
                correlation = None
                if y_var and x_var in self.numeric_cols and y_var in self.numeric_cols:
                    correlation = self.df[[x_var, y_var]].corr().iloc[0, 1]
                
                # Créer des cartes pour afficher les statistiques
                cards = []
                
                # Statistiques pour X
                x_card = dbc.Card([
                    dbc.CardHeader(f"Statistiques: {x_var}"),
                    dbc.CardBody([
                        html.Div([
                            html.Span(f"{k}: ", className="font-weight-bold"),
                            html.Span(f"{v:.2f}" if isinstance(v, (int, float)) else str(v))
                        ]) for k, v in stats_x.items()
                    ])
                ], className="mb-3")
                cards.append(x_card)
                
                # Statistiques pour Y
                if y_var:
                    y_card = dbc.Card([
                        dbc.CardHeader(f"Statistiques: {y_var}"),
                        dbc.CardBody([
                            html.Div([
                                html.Span(f"{k}: ", className="font-weight-bold"),
                                html.Span(f"{v:.2f}" if isinstance(v, (int, float)) else str(v))
                            ]) for k, v in stats_y.items()
                        ])
                    ], className="mb-3")
                    cards.append(y_card)
                
                # Afficher la corrélation si disponible
                if correlation is not None:
                    corr_card = dbc.Card([
                        dbc.CardHeader("Corrélation"),
                        dbc.CardBody([
                            html.Div([
                                html.Span("Coefficient de Pearson: ", className="font-weight-bold"),
                                html.Span(f"{correlation:.4f}")
                            ]),
                            html.Div([
                                html.Span("Interprétation: ", className="font-weight-bold"),
                                html.Span(self._interpret_correlation(correlation))
                            ])
                        ])
                    ], className="mb-3")
                    cards.append(corr_card)
                
                return dbc.Row([dbc.Col(card, width=12) for card in cards])
            
            except Exception as e:
                print(f"Erreur lors de la mise à jour des statistiques: {e}")
                traceback.print_exc()
                return html.Div(f"Erreur lors du calcul des statistiques: {str(e)}")
    
    def _interpret_correlation(self, correlation):
        """Interprète le coefficient de corrélation"""
        abs_corr = abs(correlation)
        if abs_corr < 0.3:
            strength = "faible"
        elif abs_corr < 0.7:
            strength = "modérée"
        else:
            strength = "forte"
        
        direction = "positive" if correlation >= 0 else "négative"
        return f"Corrélation {strength} {direction}"
    
    def add_static_test_chart(self):
    """
    Ajoute un graphique de test statique pour vérifier que le rendu fonctionne
    à ajouter à la méthode create_layout juste avant le return
    """
    import plotly.graph_objs as go
    
    # Créer des données de test
    x = [1, 2, 3, 4, 5]
    y = [10, 11, 12, 13, 14]
    
    # Créer une figure de test
    fig = go.Figure(data=[go.Scatter(x=x, y=y, mode='lines+markers')])
    fig.update_layout(
        title="Graphique de test",
        xaxis_title="X",
        yaxis_title="Y",
        plot_bgcolor="white",
        paper_bgcolor="white"
    )
    
    # Ajouter le graphique au layout
    test_chart = html.Div([
        html.H5("Graphique de test statique"),
        dcc.Graph(
            id="test-chart",
            figure=fig,
            style={"height": "300px"}
        )
    ], className="mt-3 p-2 rounded", style={"backgroundColor": "white"})
    
    return test_chart