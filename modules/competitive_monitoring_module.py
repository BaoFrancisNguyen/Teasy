import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import json
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompetitiveMonitoring:
    """
    Classe pour la veille concurrentielle : scraping des prix et promotions
    """
    
    def __init__(self, storage_dir: str = 'data/competitive_monitoring'):
        """
        Initialise le module de veille concurrentielle
        
        Args:
            storage_dir: Répertoire pour stocker les résultats de la veille
        """
        self.logger = logging.getLogger(f"{__name__}.CompetitiveMonitoring")
        self.storage_dir = storage_dir
        
        # Créer le répertoire si nécessaire
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Headers pour simuler un navigateur (éviter d'être bloqué)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'DNT': '1',  # Do Not Track
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Configuration des sites disponibles pour le scraping
        self.available_sites = {
            'carrefour': {
                'base_url': 'https://www.carrefour.fr',
                'categories': {
                    'epicerie': '/rayon/epicerie-sucree',
                    'produits-frais': '/rayon/produits-frais',
                    'boissons': '/rayon/boissons',
                    'bio': '/rayon/bio-et-ecologie',
                    'hygiene': '/rayon/hygiene-et-beaute'
                },
                'selector': {
                    'product': '.product-card',
                    'name': '.product-card-title',
                    'price': '.product-card-price',
                    'old_price': '.product-card-old-price',
                    'promo': '.product-card-promo'
                }
            },
            'auchan': {
                'base_url': 'https://www.auchan.fr',
                'categories': {
                    'epicerie': '/rayon/epicerie',
                    'frais': '/rayon/produits-frais',
                    'boissons': '/rayon/boissons-alcoolisees-et-sans-alcool',
                    'bio': '/rayon/produits-bio',
                    'hygiene': '/rayon/hygiene-beaute-parapharmacie'
                },
                'selector': {
                    'product': '.product-thumbnail',
                    'name': '.product-thumbnail__title',
                    'price': '.product-price__amount',
                    'old_price': '.product-price__old-amount',
                    'promo': '.product-price__discount-percentage'
                }
            },
            'monoprix': {
                'base_url': 'https://www.monoprix.fr',
                'categories': {
                    'epicerie': '/courses-en-ligne/rayon/epicerie-sucree',
                    'frais': '/courses-en-ligne/rayon/produits-frais',
                    'boissons': '/courses-en-ligne/rayon/boissons',
                    'bio': '/courses-en-ligne/rayon/bio',
                    'hygiene': '/courses-en-ligne/rayon/beaute-hygiene'
                },
                'selector': {
                    'product': '.product-item',
                    'name': '.product-item-name',
                    'price': '.price',
                    'old_price': '.old-price',
                    'promo': '.product-badge'
                }
            }
        }
    
    def _get_page_content(self, url: str, retry: int = 3) -> Optional[str]:
        """
        Récupère le contenu d'une page web
        
        Args:
            url: URL de la page à scraper
            retry: Nombre de tentatives en cas d'échec
        
        Returns:
            Contenu de la page ou None en cas d'échec
        """
        for attempt in range(retry):
            try:
                # Ajouter un délai aléatoire pour éviter d'être bloqué
                if attempt > 0:
                    time.sleep(random.uniform(2, 5))
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
                
                return response.text
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Erreur lors de la requête (tentative {attempt+1}/{retry}): {e}")
        
        self.logger.error(f"Échec après {retry} tentatives pour l'URL: {url}")
        return None
    
    def scrape_category(self, site_name: str, category: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Scrape les produits d'une catégorie donnée pour un site spécifique
        
        Args:
            site_name: Nom du site à scraper (carrefour, auchan, monoprix)
            category: Catégorie à scraper
            max_pages: Nombre maximum de pages à scraper
        
        Returns:
            Liste de produits avec leurs informations
        """
        if site_name not in self.available_sites:
            self.logger.error(f"Site non supporté: {site_name}")
            return []
        
        site_config = self.available_sites[site_name]
        
        if category not in site_config['categories']:
            self.logger.error(f"Catégorie non supportée pour {site_name}: {category}")
            return []
        
        category_url = site_config['base_url'] + site_config['categories'][category]
        
        all_products = []
        
        for page in range(1, max_pages + 1):
            # Construire l'URL de la page
            page_url = f"{category_url}?page={page}"
            self.logger.info(f"Scraping de la page {page}/{max_pages} de {site_name} - {category}: {page_url}")
            
            # Récupérer le contenu de la page
            page_content = self._get_page_content(page_url)
            if not page_content:
                break
            
            # Parser le contenu HTML
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Récupérer les produits
            products = soup.select(site_config['selector']['product'])
            
            if not products:
                self.logger.warning(f"Aucun produit trouvé sur la page {page}")
                break
            
            # Extraire les informations de chaque produit
            for product in products:
                try:
                    product_data = {
                        'site': site_name,
                        'category': category,
                        'scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Extraire le nom
                    name_element = product.select_one(site_config['selector']['name'])
                    if name_element:
                        product_data['name'] = name_element.get_text().strip()
                    else:
                        continue  # Ignorer le produit si pas de nom
                    
                    # Extraire le prix actuel
                    price_element = product.select_one(site_config['selector']['price'])
                    if price_element:
                        price_text = price_element.get_text().strip()
                        # Extraire le prix (en supposant un format comme "12,99 €")
                        price_match = re.search(r'(\d+[,.]\d+|\d+)', price_text)
                        if price_match:
                            price = price_match.group(1).replace(',', '.')
                            product_data['price'] = float(price)
                    
                    # Extraire l'ancien prix (si en promotion)
                    old_price_element = product.select_one(site_config['selector']['old_price'])
                    if old_price_element:
                        old_price_text = old_price_element.get_text().strip()
                        old_price_match = re.search(r'(\d+[,.]\d+|\d+)', old_price_text)
                        if old_price_match:
                            old_price = old_price_match.group(1).replace(',', '.')
                            product_data['old_price'] = float(old_price)
                    
                    # Extraire la promotion
                    promo_element = product.select_one(site_config['selector']['promo'])
                    if promo_element:
                        product_data['promotion'] = promo_element.get_text().strip()
                    
                    # Calculer le pourcentage de réduction si on a l'ancien prix
                    if 'old_price' in product_data and 'price' in product_data:
                        discount = (product_data['old_price'] - product_data['price']) / product_data['old_price'] * 100
                        product_data['discount_percentage'] = round(discount, 2)
                    
                    # Ajouter le produit à la liste
                    all_products.append(product_data)
                    
                except Exception as e:
                    self.logger.error(f"Erreur lors de l'extraction des données du produit: {e}")
            
            # Attendre entre les pages pour éviter d'être bloqué
            if page < max_pages:
                time.sleep(random.uniform(1, 3))
        
        self.logger.info(f"Scraping terminé: {len(all_products)} produits récupérés")
        return all_products
    
    def scrape_multiple_categories(self, site_name: str, categories: List[str], max_pages: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scrape plusieurs catégories pour un site donné
        
        Args:
            site_name: Nom du site à scraper
            categories: Liste des catégories à scraper
            max_pages: Nombre maximum de pages par catégorie
        
        Returns:
            Dictionnaire avec les catégories comme clés et les listes de produits comme valeurs
        """
        results = {}
        
        for category in categories:
            self.logger.info(f"Scraping de la catégorie {category} sur {site_name}")
            products = self.scrape_category(site_name, category, max_pages)
            results[category] = products
            
            # Attendre entre les catégories
            if category != categories[-1]:
                time.sleep(random.uniform(2, 5))
        
        return results
    
    def compare_sites(self, category: str, max_pages: int = 2) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Compare les prix entre différents sites pour une catégorie donnée
        
        Args:
            category: Catégorie à comparer
            max_pages: Nombre maximum de pages par site
        
        Returns:
            DataFrame avec les produits et métadonnées de comparaison
        """
        # Récupérer les données pour chaque site
        all_data = []
        site_stats = {}
        
        for site_name in self.available_sites.keys():
            if category in self.available_sites[site_name]['categories']:
                products = self.scrape_category(site_name, category, max_pages)
                all_data.extend(products)
                
                # Calculer des statistiques par site
                if products:
                    prices = [p['price'] for p in products if 'price' in p]
                    site_stats[site_name] = {
                        'count': len(products),
                        'avg_price': round(sum(prices) / len(prices), 2) if prices else 0,
                        'min_price': min(prices) if prices else 0,
                        'max_price': max(prices) if prices else 0,
                        'promo_count': sum(1 for p in products if 'promotion' in p),
                        'scrape_date': products[0]['scrape_date'] if products else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
        
        # Créer un DataFrame à partir des données
        df = pd.DataFrame(all_data)
        
        # Calculer des statistiques globales
        metadata = {
            'category': category,
            'total_products': len(df),
            'sites': site_stats,
            'top_promotions': self._get_top_promotions(df),
            'scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return df, metadata
    
    def _get_top_promotions(self, df: pd.DataFrame, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les meilleures promotions du DataFrame
        
        Args:
            df: DataFrame des produits
            top_n: Nombre de promotions à récupérer
            
        Returns:
            Liste des meilleures promotions
        """
        if 'discount_percentage' not in df.columns or df.empty:
            return []
        
        # Filtrer les produits avec une promotion
        promo_df = df[df['discount_percentage'].notna()].copy()
        
        if promo_df.empty:
            return []
        
        # Trier par pourcentage de réduction décroissant
        promo_df = promo_df.sort_values('discount_percentage', ascending=False)
        
        # Récupérer les meilleures promotions
        top_promotions = []
        for _, row in promo_df.head(top_n).iterrows():
            promo = {
                'name': row['name'],
                'site': row['site'],
                'price': row['price'],
                'old_price': row.get('old_price', None),
                'discount_percentage': row['discount_percentage'],
                'promotion': row.get('promotion', f"-{row['discount_percentage']}%")
            }
            top_promotions.append(promo)
        
        return top_promotions
    
    def save_results(self, df: pd.DataFrame, metadata: Dict[str, Any], filename_prefix: str) -> str:
        """
        Sauvegarde les résultats dans des fichiers CSV et JSON
        
        Args:
            df: DataFrame des produits
            metadata: Métadonnées de l'analyse
            filename_prefix: Préfixe pour les noms de fichiers
            
        Returns:
            Chemin vers le fichier CSV
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder le DataFrame en CSV
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        csv_path = os.path.join(self.storage_dir, csv_filename)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # Sauvegarder les métadonnées en JSON
        json_filename = f"{filename_prefix}_{timestamp}_metadata.json"
        json_path = os.path.join(self.storage_dir, json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Résultats sauvegardés: {csv_path} et {json_path}")
        return csv_path
    
    def analyze_price_trends(self, product_name: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Analyse les tendances de prix pour un produit donné
        
        Args:
            product_name: Nom du produit à analyser
            days_back: Nombre de jours à analyser en arrière
            
        Returns:
            Dictionnaire avec les analyses de tendances
        """
        # Cette fonction simule l'analyse des tendances à partir des fichiers sauvegardés
        # Dans une implémentation réelle, elle analyserait les données historiques stockées
        
        return {
            'product': product_name,
            'price_evolution': [
                {'date': '2023-01-01', 'price': 12.99, 'site': 'carrefour'},
                {'date': '2023-01-15', 'price': 11.99, 'site': 'carrefour'},
                {'date': '2023-02-01', 'price': 13.99, 'site': 'carrefour'}
            ],
            'average_price': 12.99,
            'min_price': {'value': 11.99, 'date': '2023-01-15', 'site': 'carrefour'},
            'max_price': {'value': 13.99, 'date': '2023-02-01', 'site': 'carrefour'},
            'current_best_deal': {'price': 11.50, 'site': 'auchan', 'promotion': '-20%'}
        }
    
    def get_available_categories(self) -> Dict[str, List[str]]:
        """
        Récupère les catégories disponibles pour chaque site
        
        Returns:
            Dictionnaire avec les sites comme clés et les catégories comme valeurs
        """
        categories = {}
        
        for site_name, site_config in self.available_sites.items():
            categories[site_name] = list(site_config['categories'].keys())
        
        return categories
    
    def get_category_name(self, site_name: str, category_key: str) -> str:
        """
        Récupère le nom lisible d'une catégorie à partir de sa clé
        
        Args:
            site_name: Nom du site
            category_key: Clé de la catégorie
        
        Returns:
            Nom lisible de la catégorie
        """
        # Cette fonction extrait un nom lisible à partir de l'URL de la catégorie
        if site_name in self.available_sites and category_key in self.available_sites[site_name]['categories']:
            category_url = self.available_sites[site_name]['categories'][category_key]
            # Extraire le dernier segment de l'URL et remplacer les tirets par des espaces
            name = category_url.split('/')[-1].replace('-', ' ').title()
            return name
        
        return category_key.capitalize()

# Fonction pour tester le module
def test_monitoring():
    monitor = CompetitiveMonitoring()
    
    # Tester la récupération des catégories disponibles
    categories = monitor.get_available_categories()
    print("Catégories disponibles:", categories)
    
    # Tester le scraping d'une catégorie
    products = monitor.scrape_category('carrefour', 'boissons', max_pages=1)
    print(f"Nombre de produits récupérés: {len(products)}")
    
    if products:
        print("Premier produit:", products[0])
    
    # Tester la comparaison entre sites
    df, metadata = monitor.compare_sites('epicerie', max_pages=1)
    print(f"Comparaison entre sites - Produits: {len(df)}")
    print("Métadonnées:", metadata)
    
    # Sauvegarder les résultats
    csv_path = monitor.save_results(df, metadata, 'epicerie_comparison')
    print(f"Résultats sauvegardés dans: {csv_path}")

if __name__ == "__main__":
    test_monitoring()
