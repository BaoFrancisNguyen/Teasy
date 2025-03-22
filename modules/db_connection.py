import sqlite3
import os
import pandas as pd
import logging
from typing import Optional, List, Dict, Any, Tuple

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Classe pour gérer les connexions et opérations avec la base de données SQLite"""
    
    def __init__(self, db_path: str = 'database/tickets.db'):
        """
        Initialise le gestionnaire de base de données
        
        Args:
            db_path: Chemin vers le fichier de base de données SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(f"{__name__}.DatabaseManager")
        
        # Créer le répertoire pour la base de données s'il n'existe pas
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Vérifier si la base de données existe, sinon la créer
        self._init_database()
    
    def _init_database(self):
        """Initialise la base de données si elle n'existe pas"""
        try:
            # Vérifier si le fichier existe déjà
            if not os.path.exists(self.db_path):
                self.logger.info(f"Création de la base de données: {self.db_path}")
                
                # Créer une connexion pour la nouvelle base de données
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Créer les tables nécessaires si elles n'existent pas
                schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
                if os.path.exists(schema_file):
                    with open(schema_file, 'r') as f:
                        schema_sql = f.read()
                    
                    # Exécuter le script SQL
                    cursor.executescript(schema_sql)
                    conn.commit()
                    self.logger.info("Schéma de base de données créé avec succès")
                else:
                    self._create_schema(cursor)
                    conn.commit()
                    self.logger.info("Schéma de base de données créé en interne")
                
                conn.close()
            else:
                self.logger.info(f"Base de données existante: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
    
    def _create_schema(self, cursor):
        """Crée le schéma de base de données en interne"""
        # Tickets de caisse
        cursor.execute('''
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_achat DATE NOT NULL,
            heure_achat TIME,
            magasin_id INTEGER NOT NULL,
            montant_total DECIMAL(10, 2) NOT NULL,
            moyen_paiement VARCHAR(50),
            numero_ticket VARCHAR(50),
            FOREIGN KEY (magasin_id) REFERENCES magasins(id)
        )
        ''')
        
        # Articles des tickets
        cursor.execute('''
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            nom_article VARCHAR(100) NOT NULL,
            quantite INTEGER NOT NULL,
            prix_unitaire DECIMAL(10, 2) NOT NULL,
            categorie_id INTEGER,
            code_barre VARCHAR(50),
            FOREIGN KEY (ticket_id) REFERENCES tickets(id),
            FOREIGN KEY (categorie_id) REFERENCES categories(id)
        )
        ''')
        
        # Magasins
        cursor.execute('''
        CREATE TABLE magasins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom VARCHAR(100) NOT NULL,
            adresse VARCHAR(255),
            ville VARCHAR(100),
            code_postal VARCHAR(20),
            enseigne VARCHAR(100),
            type VARCHAR(50)
        )
        ''')
        
        # Catégories d'articles
        cursor.execute('''
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom VARCHAR(100) NOT NULL,
            description VARCHAR(255)
        )
        ''')
        
        # Index pour améliorer les performances
        cursor.execute('CREATE INDEX idx_tickets_date ON tickets(date_achat)')
        cursor.execute('CREATE INDEX idx_tickets_magasin ON tickets(magasin_id)')
        cursor.execute('CREATE INDEX idx_articles_ticket ON articles(ticket_id)')
        cursor.execute('CREATE INDEX idx_articles_categorie ON articles(categorie_id)')
    
    def get_connection(self):
        """Obtient une connexion à la base de données"""
        try:
            conn = sqlite3.connect(self.db_path)
            # Pour avoir les résultats sous forme de dictionnaire
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Erreur de connexion à la base de données: {e}")
            raise e
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Exécute une requête SQL et retourne les résultats
        
        Args:
            query: Requête SQL à exécuter
            params: Paramètres pour la requête
            
        Returns:
            Liste de dictionnaires représentant les lignes retournées
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Récupérer les noms de colonnes
            column_names = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convertir les résultats en liste de dictionnaires
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(column_names, row)))
            
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Erreur lors de l'exécution de la requête: {e}")
            self.logger.error(f"Requête: {query}")
            if params:
                self.logger.error(f"Paramètres: {params}")
            raise e
        finally:
            if conn:
                conn.close()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        Exécute une requête de mise à jour (INSERT, UPDATE, DELETE)
        
        Args:
            query: Requête SQL à exécuter
            params: Paramètres pour la requête
            
        Returns:
            Nombre de lignes affectées
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Erreur lors de l'exécution de la mise à jour: {e}")
            self.logger.error(f"Requête: {query}")
            if params:
                self.logger.error(f"Paramètres: {params}")
            raise e
        finally:
            if conn:
                conn.close()
    
    def get_tickets_dataframe(self, filters: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Récupère les tickets de caisse sous forme de DataFrame pandas
        
        Args:
            filters: Dictionnaire de filtres à appliquer (ex: {'date_debut': '2023-01-01', 'date_fin': '2023-01-31'})
            
        Returns:
            DataFrame pandas contenant les tickets
        """
        base_query = """
        SELECT 
            t.id, t.date_achat, t.heure_achat, t.montant_total, t.moyen_paiement, t.numero_ticket,
            m.nom as magasin, m.ville, m.enseigne
        FROM tickets t
        JOIN magasins m ON t.magasin_id = m.id
        """
        
        query_conditions = []
        params = []
        
        if filters:
            if 'date_debut' in filters and filters['date_debut']:
                query_conditions.append("t.date_achat >= ?")
                params.append(filters['date_debut'])
            
            if 'date_fin' in filters and filters['date_fin']:
                query_conditions.append("t.date_achat <= ?")
                params.append(filters['date_fin'])
            
            if 'magasin_id' in filters and filters['magasin_id']:
                query_conditions.append("t.magasin_id = ?")
                params.append(filters['magasin_id'])
            
            if 'moyen_paiement' in filters and filters['moyen_paiement']:
                query_conditions.append("t.moyen_paiement = ?")
                params.append(filters['moyen_paiement'])
        
        if query_conditions:
            base_query += " WHERE " + " AND ".join(query_conditions)
        
        base_query += " ORDER BY t.date_achat DESC"
        
        try:
            # Exécuter la requête
            results = self.execute_query(base_query, tuple(params) if params else None)
            
            # Convertir en DataFrame
            if results:
                df = pd.DataFrame(results)
                
                # Convertir les types de données
                if 'date_achat' in df.columns:
                    df['date_achat'] = pd.to_datetime(df['date_achat'])
                
                if 'montant_total' in df.columns:
                    df['montant_total'] = pd.to_numeric(df['montant_total'])
                
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tickets: {e}")
            return pd.DataFrame()
    
    def get_articles_dataframe(self, ticket_id: Optional[int] = None) -> pd.DataFrame:
        """
        Récupère les articles des tickets sous forme de DataFrame pandas
        
        Args:
            ticket_id: ID du ticket spécifique (None pour tous les articles)
            
        Returns:
            DataFrame pandas contenant les articles
        """
        base_query = """
        SELECT 
            a.id, a.ticket_id, a.nom_article, a.quantite, a.prix_unitaire, a.code_barre,
            c.nom as categorie,
            t.date_achat, t.montant_total,
            m.nom as magasin, m.enseigne
        FROM articles a
        JOIN tickets t ON a.ticket_id = t.id
        JOIN magasins m ON t.magasin_id = m.id
        LEFT JOIN categories c ON a.categorie_id = c.id
        """
        
        params = None
        if ticket_id is not None:
            base_query += " WHERE a.ticket_id = ?"
            params = (ticket_id,)
        
        base_query += " ORDER BY t.date_achat DESC, a.id"
        
        try:
            # Exécuter la requête
            results = self.execute_query(base_query, params)
            
            # Convertir en DataFrame
            if results:
                df = pd.DataFrame(results)
                
                # Convertir les types de données
                if 'date_achat' in df.columns:
                    df['date_achat'] = pd.to_datetime(df['date_achat'])
                
                if 'prix_unitaire' in df.columns:
                    df['prix_unitaire'] = pd.to_numeric(df['prix_unitaire'])
                
                if 'quantite' in df.columns:
                    df['quantite'] = pd.to_numeric(df['quantite'])
                
                if 'montant_total' in df.columns:
                    df['montant_total'] = pd.to_numeric(df['montant_total'])
                
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des articles: {e}")
            return pd.DataFrame()
    
    def get_all_articles_dataframe(self) -> pd.DataFrame:
        """
        Récupère tous les articles de tous les tickets sous forme de DataFrame pandas
        
        Returns:
            DataFrame pandas contenant tous les articles
        """
        return self.get_articles_dataframe()
    
    def get_transactions(self, filters: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Récupère les transactions avec les informations des clients depuis la base de données
        
        Args:
            filters: Dictionnaire de filtres à appliquer (ex: {'date_debut': '2023-01-01', 'date_fin': '2023-01-31', 'genre': 'homme'})
            
        Returns:
            DataFrame pandas contenant les transactions avec infos client
        """
        base_query = """
        SELECT 
            t.transaction_id as id, 
            t.date_transaction, 
            t.montant_total, 
            t.numero_facture, 
            t.type_paiement as moyen_paiement, 
            t.canal_vente, 
            t.points_gagnes,
            pv.nom as magasin, 
            pv.email as enseigne,
            c.genre,
            strftime('%Y', 'now') - strftime('%Y', c.date_naissance) as age,
            c.code_postal,
            c.ville as ville_client,
            c.segment as segment_client
        FROM transactions t
        JOIN points_vente pv ON t.magasin_id = pv.magasin_id
        JOIN clients c ON t.client_id = c.client_id
        """
        
        # Ajout des jointures conditionnelles pour les filtres produits/catégories
        if filters and (filters.get('categorie_id', '') or filters.get('produit_id', '')):
            base_query += """
            JOIN details_transactions dt ON t.transaction_id = dt.transaction_id
            JOIN produits p ON dt.produit_id = p.produit_id
            """
        
        query_conditions = []
        params = []
        
        if filters:
            if 'date_debut' in filters and filters['date_debut']:
                query_conditions.append("t.date_transaction >= ?")
                params.append(filters['date_debut'])
            
            if 'date_fin' in filters and filters['date_fin']:
                query_conditions.append("t.date_transaction <= ?")
                params.append(filters['date_fin'])
            
            if 'magasin_id' in filters and filters['magasin_id']:
                query_conditions.append("t.magasin_id = ?")
                params.append(filters['magasin_id'])
            
            if 'enseigne' in filters and filters['enseigne']:
                query_conditions.append("pv.email = ?")
                params.append(filters['enseigne'])
            
            if 'ville' in filters and filters['ville']:
                query_conditions.append("pv.ville = ?")
                params.append(filters['ville'])
            
            if 'categorie_id' in filters and filters['categorie_id']:
                query_conditions.append("p.categorie_id = ?")
                params.append(filters['categorie_id'])
            
            if 'produit_id' in filters and filters['produit_id']:
                query_conditions.append("dt.produit_id = ?")
                params.append(filters['produit_id'])
            
            if 'moyen_paiement' in filters and filters['moyen_paiement']:
                query_conditions.append("t.type_paiement = ?")
                params.append(filters['moyen_paiement'])
            
            # Filtres client
            if 'genre' in filters and filters['genre']:
                query_conditions.append("c.genre = ?")
                params.append(filters['genre'])
            
            if 'segment_client' in filters and filters['segment_client']:
                query_conditions.append("c.segment = ?")
                params.append(filters['segment_client'])
            
            # Filtres d'âge
            if 'age_range' in filters and filters['age_range'] != 'all':
                age_range = filters['age_range']
                if age_range == "0-18":
                    query_conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) < 19")
                elif age_range == "19-25":
                    query_conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 19 AND 25")
                elif age_range == "26-35":
                    query_conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 26 AND 35")
                elif age_range == "36-50":
                    query_conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) BETWEEN 36 AND 50")
                elif age_range == "51+":
                    query_conditions.append("(strftime('%Y', 'now') - strftime('%Y', c.date_naissance)) > 50")
            
            # Filtres de montant
            if 'montant_min' in filters and filters['montant_min']:
                query_conditions.append("t.montant_total >= ?")
                params.append(float(filters['montant_min']))
            
            if 'montant_max' in filters and filters['montant_max']:
                query_conditions.append("t.montant_total <= ?")
                params.append(float(filters['montant_max']))
        
        if query_conditions:
            base_query += " WHERE " + " AND ".join(query_conditions)
        
        # Gestion des doublons si on a des filtres sur les produits/catégories
        if filters and (filters.get('categorie_id', '') or filters.get('produit_id', '')):
            base_query += " GROUP BY t.transaction_id"
        
        base_query += " ORDER BY t.date_transaction DESC LIMIT 5000"
        
        try:
            # Exécuter la requête
            results = self.execute_query(base_query, tuple(params) if params else None)
            
            # Convertir en DataFrame
            if results:
                df = pd.DataFrame(results)
                
                # Convertir les types de données
                if 'date_transaction' in df.columns:
                    df['date_transaction'] = pd.to_datetime(df['date_transaction'])
                
                if 'montant_total' in df.columns:
                    df['montant_total'] = pd.to_numeric(df['montant_total'])
                
                if 'age' in df.columns:
                    df['age'] = pd.to_numeric(df['age'])
                
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des transactions: {e}")
            return pd.DataFrame()
    
    def get_transactions_with_articles(self, filters: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Récupère les transactions avec leurs articles, enrichies avec les informations client
        
        Args:
            filters: Dictionnaire de filtres à appliquer
            
        Returns:
            DataFrame pandas contenant les transactions avec leurs articles et les infos client
        """
        # Récupérer d'abord les transactions
        transactions_df = self.get_transactions(filters)
        
        if transactions_df.empty:
            return pd.DataFrame()
        
        # Récupérer les identifiants de transaction
        transaction_ids = transactions_df['id'].tolist()
        
        # Requête pour obtenir les articles
        articles_query = """
        SELECT 
            dt.transaction_id, 
            p.nom as nom_article, 
            dt.quantite, 
            dt.prix_unitaire, 
            dt.remise_pourcentage, 
            dt.montant_ligne, 
            cp.nom as categorie
        FROM details_transactions dt
        JOIN produits p ON dt.produit_id = p.produit_id
        LEFT JOIN categories_produits cp ON p.categorie_id = cp.categorie_id
        WHERE dt.transaction_id IN ({})
        """.format(','.join(['?' for _ in transaction_ids]))
        
        try:
            # Exécuter la requête pour les articles
            articles_results = self.execute_query(articles_query, tuple(transaction_ids))
            
            if not articles_results:
                # Pas d'articles trouvés, retourner les transactions telles quelles
                return transactions_df
            
            # Convertir les résultats des articles en DataFrame
            articles_df = pd.DataFrame(articles_results)
            
            # Convertir les types de données
            if 'prix_unitaire' in articles_df.columns:
                articles_df['prix_unitaire'] = pd.to_numeric(articles_df['prix_unitaire'])
            
            if 'quantite' in articles_df.columns:
                articles_df['quantite'] = pd.to_numeric(articles_df['quantite'])
            
            if 'montant_ligne' in articles_df.columns:
                articles_df['montant_ligne'] = pd.to_numeric(articles_df['montant_ligne'])
            
            # Créer un dictionnaire d'articles groupés par transaction_id
            articles_grouped = articles_df.groupby('transaction_id')
            
            # Décomposer les transactions par article
            decomposed_transactions = []
            
            for _, transaction in transactions_df.iterrows():
                transaction_id = transaction['id']
                
                # Vérifier si cette transaction a des articles
                if transaction_id in articles_grouped.groups:
                    # Récupérer tous les articles de cette transaction
                    transaction_articles = articles_grouped.get_group(transaction_id)
                    
                    for _, article in transaction_articles.iterrows():
                        # Créer un dictionnaire pour cette ligne
                        transaction_row = transaction.to_dict()
                        
                        # Ajouter les détails de l'article
                        transaction_row.update({
                            'nom_article': article['nom_article'],
                            'quantite': article['quantite'],
                            'prix_unitaire': article['prix_unitaire'],
                            'remise_pourcentage': article['remise_pourcentage'],
                            'montant_ligne': article['montant_ligne'],
                            'categorie': article['categorie']
                        })
                        
                        decomposed_transactions.append(transaction_row)
                else:
                    # Pas d'articles pour cette transaction
                    transaction_row = transaction.to_dict()
                    transaction_row.update({
                        'nom_article': None,
                        'quantite': None,
                        'prix_unitaire': None,
                        'remise_pourcentage': None,
                        'montant_ligne': None,
                        'categorie': None
                    })
                    decomposed_transactions.append(transaction_row)
            
            # Créer un nouveau DataFrame à partir des transactions décomposées
            result_df = pd.DataFrame(decomposed_transactions)
            
            return result_df
        
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des transactions avec articles: {e}")
            return transactions_df
    
    def import_csv_to_database(self, csv_file: str, table_type: str = 'tickets') -> Tuple[bool, str]:
        """
        Importe un fichier CSV dans la base de données
        
        Args:
            csv_file: Chemin vers le fichier CSV
            table_type: Type de table ('tickets', 'articles', 'magasins', 'categories')
            
        Returns:
            Tuple (succès, message)
        """
        try:
            # Lire le fichier CSV
            df = pd.read_csv(csv_file)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if table_type == 'tickets':
                # Vérification des colonnes nécessaires
                required_columns = ['date_achat', 'magasin_id', 'montant_total']
                if not all(col in df.columns for col in required_columns):
                    return False, f"Colonnes manquantes. Colonnes requises: {', '.join(required_columns)}"
                
                # Insérer chaque ligne dans la table tickets
                for _, row in df.iterrows():
                    cursor.execute('''
                    INSERT INTO tickets (date_achat, heure_achat, magasin_id, montant_total, moyen_paiement, numero_ticket)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        row['date_achat'], 
                        row.get('heure_achat'), 
                        row['magasin_id'], 
                        row['montant_total'], 
                        row.get('moyen_paiement'), 
                        row.get('numero_ticket')
                    ))
            
            elif table_type == 'articles':
                # Vérification des colonnes nécessaires
                required_columns = ['ticket_id', 'nom_article', 'quantite', 'prix_unitaire']
                if not all(col in df.columns for col in required_columns):
                    return False, f"Colonnes manquantes. Colonnes requises: {', '.join(required_columns)}"
                
                # Insérer chaque ligne dans la table articles
                for _, row in df.iterrows():
                    cursor.execute('''
                    INSERT INTO articles (ticket_id, nom_article, quantite, prix_unitaire, categorie_id, code_barre)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        row['ticket_id'], 
                        row['nom_article'], 
                        row['quantite'], 
                        row['prix_unitaire'], 
                        row.get('categorie_id'), 
                        row.get('code_barre')
                    ))
            
            elif table_type == 'magasins':
                # Vérification des colonnes nécessaires
                required_columns = ['nom']
                if not all(col in df.columns for col in required_columns):
                    return False, f"Colonnes manquantes. Colonnes requises: {', '.join(required_columns)}"
                
                # Insérer chaque ligne dans la table magasins
                for _, row in df.iterrows():
                    cursor.execute('''
                    INSERT INTO magasins (nom, adresse, ville, code_postal, enseigne, type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        row['nom'], 
                        row.get('adresse'), 
                        row.get('ville'), 
                        row.get('code_postal'), 
                        row.get('enseigne'), 
                        row.get('type')
                    ))
            
            elif table_type == 'categories':
                # Vérification des colonnes nécessaires
                required_columns = ['nom']
                if not all(col in df.columns for col in required_columns):
                    return False, f"Colonnes manquantes. Colonnes requises: {', '.join(required_columns)}"
                
                # Insérer chaque ligne dans la table categories
                for _, row in df.iterrows():
                    cursor.execute('''
                    INSERT INTO categories (nom, description)
                    VALUES (?, ?)
                    ''', (
                        row['nom'], 
                        row.get('description')
                    ))
            
            else:
                return False, f"Type de table inconnu: {table_type}"
            
            conn.commit()
            conn.close()
            
            return True, f"Importation réussie dans la table {table_type}"
        
        except Exception as e:
            self.logger.error(f"Erreur lors de l'importation du fichier CSV: {e}")
            return False, f"Erreur: {str(e)}"