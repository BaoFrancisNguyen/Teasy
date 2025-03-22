"""
Module de scraping pour les avis Amazon.
Extrait les avis clients et les métadonnées des produits d'Amazon.
"""

import os
import time
import random
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AmazonScraper:
    """Scraper pour les avis clients sur Amazon"""
    
    def __init__(self, 
                 use_selenium: bool = True, 
                 headless: bool = True,
                 proxy: Optional[str] = None,
                 user_agent: Optional[str] = None):
        """
        Initialise le scraper Amazon.
        
        Args:
            use_selenium: Utiliser Selenium au lieu de requests (recommandé pour éviter les blocages)
            headless: Mode headless pour Selenium (sans interface graphique)
            proxy: Proxy à utiliser pour les requêtes (format 'ip:port')
            user_agent: User agent à utiliser pour les requêtes
        """
        self.use_selenium = use_selenium
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        
        # User agent par défaut si non spécifié
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        # Session requests si mode selenium désactivé
        self.session = requests.Session() if not use_selenium else None
        
        if not use_selenium and self.session:
            self.session.headers.update({
                'User-Agent': self.user_agent,
                'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive'
            })
            
            if proxy:
                self.session.proxies.update({
                    'http': f'http://{proxy}',
                    'https': f'https://{proxy}'
                })
    
    def initialize_driver(self):
        """Initialise le driver Selenium si nécessaire"""
        if self.use_selenium and not self.driver:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument('--headless')
                
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'user-agent={self.user_agent}')
            
            if self.proxy:
                chrome_options.add_argument(f'--proxy-server={self.proxy}')
            
            # Ajouter des préférences pour éviter la détection de bot
            prefs = {
                "profile.managed_default_content_settings.images": 2,  # Désactiver le chargement des images
                "profile.default_content_setting_values.notifications": 2,  # Désactiver les notifications
                "profile.managed_default_content_settings.plugins": 1,
                "profile.default_content_setting_values.cookies": 1  # Accepter les cookies
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Désactiver webdriver pour éviter la détection
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.user_agent})
            
            # Réduire la fenêtre pour économiser les ressources si non headless
            if not self.headless:
                self.driver.set_window_size(1366, 768)
                
            logger.info("Driver Selenium initialisé")
    
    def close(self):
        """Ferme le driver Selenium"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Driver Selenium fermé")
    
    def get_product_details(self, product_url: str) -> Dict[str, Any]:
        """
        Récupère les détails d'un produit Amazon.
        
        Args:
            product_url: URL du produit Amazon
            
        Returns:
            Dictionnaire contenant les détails du produit
        """
        if self.use_selenium:
            self.initialize_driver()
            return self._get_product_details_selenium(product_url)
        else:
            return self._get_product_details_requests(product_url)
    
    def _get_product_details_selenium(self, product_url: str) -> Dict[str, Any]:
        """Version Selenium de l'extraction des détails du produit"""
        try:
            self.driver.get(product_url)
            time.sleep(random.uniform(2, 4))  # Attente aléatoire pour éviter la détection
            
            # Extraction du titre du produit
            try:
                product_title = self.driver.find_element(By.ID, 'productTitle').text.strip()
            except NoSuchElementException:
                product_title = "Unknown Product"
            
            # Extraction de l'ID du produit (ASIN)
            try:
                product_id = product_url.split('/dp/')[1].split('/')[0]
            except (IndexError, AttributeError):
                product_id = "Unknown"
            
            # Extraction de la marque
            try:
                product_brand = self.driver.find_element(By.ID, 'bylineInfo').text
                product_brand = product_brand.replace('Visit the ', '').replace(' Store', '').strip()
            except NoSuchElementException:
                try:
                    product_brand = self.driver.find_element(By.CSS_SELECTOR, '.po-brand .po-break-word').text.strip()
                except NoSuchElementException:
                    product_brand = "Unknown Brand"
            
            # Extraction de la catégorie
            try:
                breadcrumbs = self.driver.find_elements(By.CSS_SELECTOR, '#wayfinding-breadcrumbs_feature_div ul li')
                categories = [crumb.text.strip() for crumb in breadcrumbs if crumb.text.strip()]
                product_category = categories[-1] if categories else "Unknown Category"
            except (NoSuchElementException, IndexError):
                product_category = "Unknown Category"
            
            # Extraction de la note moyenne
            try:
                rating_text = self.driver.find_element(By.CSS_SELECTOR, '.a-star-medium-4 .a-icon-alt').text
                average_rating = float(rating_text.split(' ')[0].replace(',', '.'))
            except (NoSuchElementException, ValueError, IndexError):
                try:
                    rating_text = self.driver.find_element(By.CSS_SELECTOR, '#acrPopover .a-icon-alt').text
                    average_rating = float(rating_text.split(' ')[0].replace(',', '.'))
                except (NoSuchElementException, ValueError, IndexError):
                    average_rating = None
            
            # Extraction du nombre d'avis
            try:
                review_count_text = self.driver.find_element(By.ID, 'acrCustomerReviewText').text
                review_count = int(''.join(filter(str.isdigit, review_count_text)))
            except (NoSuchElementException, ValueError):
                review_count = 0
            
            # Extraction du prix
            try:
                price_whole = self.driver.find_element(By.CSS_SELECTOR, '.a-price-whole').text
                price_fraction = self.driver.find_element(By.CSS_SELECTOR, '.a-price-fraction').text
                price = float(f"{price_whole.replace(',', '')}.{price_fraction}")
            except (NoSuchElementException, ValueError):
                try:
                    # Suite de la méthode _get_product_details_selenium
                    price_text = self.driver.find_element(By.CSS_SELECTOR, '.a-offscreen').get_attribute('textContent')
                    price = float(price_text.strip('€$£¥').replace(',', '.'))
                except (NoSuchElementException, ValueError):
                    price = None
            
            # Extraire les caractéristiques du produit
            features = []
            try:
                feature_elements = self.driver.find_elements(By.CSS_SELECTOR, '#feature-bullets .a-list-item')
                features = [feature.text.strip() for feature in feature_elements if feature.text.strip()]
            except NoSuchElementException:
                pass
            
            return {
                'product_id': product_id,
                'product_name': product_title,
                'product_brand': product_brand,
                'product_category': product_category,
                'average_rating': average_rating,
                'review_count': review_count,
                'price': price,
                'features': features,
                'url': product_url
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des détails du produit: {e}")
            return {
                'product_id': "Error",
                'product_name': "Error",
                'product_brand': "Error",
                'product_category': "Error",
                'average_rating': None,
                'review_count': 0,
                'price': None,
                'features': [],
                'url': product_url
            }
    
    def _get_product_details_requests(self, product_url: str) -> Dict[str, Any]:
        """Version requests de l'extraction des détails du produit"""
        try:
            response = self.session.get(product_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraction du titre du produit
            product_title_element = soup.find(id='productTitle')
            product_title = product_title_element.text.strip() if product_title_element else "Unknown Product"
            
            # Extraction de l'ID du produit (ASIN)
            try:
                product_id = product_url.split('/dp/')[1].split('/')[0]
            except (IndexError, AttributeError):
                product_id = "Unknown"
            
            # Extraction de la marque
            brand_element = soup.find(id='bylineInfo')
            if brand_element:
                product_brand = brand_element.text.strip()
                product_brand = product_brand.replace('Visit the ', '').replace(' Store', '').strip()
            else:
                brand_element = soup.select_one('.po-brand .po-break-word')
                product_brand = brand_element.text.strip() if brand_element else "Unknown Brand"
            
            # Extraction de la catégorie
            breadcrumbs = soup.select('#wayfinding-breadcrumbs_feature_div ul li')
            categories = [crumb.text.strip() for crumb in breadcrumbs if crumb.text.strip()]
            product_category = categories[-1] if categories else "Unknown Category"
            
            # Extraction de la note moyenne
            rating_element = soup.select_one('#acrPopover .a-icon-alt')
            if rating_element:
                try:
                    rating_text = rating_element.text
                    average_rating = float(rating_text.split(' ')[0].replace(',', '.'))
                except (ValueError, IndexError):
                    average_rating = None
            else:
                average_rating = None
            
            # Extraction du nombre d'avis
            review_count_element = soup.find(id='acrCustomerReviewText')
            if review_count_element:
                try:
                    review_count_text = review_count_element.text
                    review_count = int(''.join(filter(str.isdigit, review_count_text)))
                except ValueError:
                    review_count = 0
            else:
                review_count = 0
            
            # Extraction du prix
            price_element = soup.select_one('.a-price .a-offscreen')
            if price_element:
                try:
                    price_text = price_element.text
                    price = float(price_text.strip('€$£¥').replace(',', '.'))
                except ValueError:
                    price = None
            else:
                price = None
            
            # Extraire les caractéristiques du produit
            feature_elements = soup.select('#feature-bullets .a-list-item')
            features = [feature.text.strip() for feature in feature_elements if feature.text.strip()]
            
            return {
                'product_id': product_id,
                'product_name': product_title,
                'product_brand': product_brand,
                'product_category': product_category,
                'average_rating': average_rating,
                'review_count': review_count,
                'price': price,
                'features': features,
                'url': product_url
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des détails du produit: {e}")
            return {
                'product_id': "Error",
                'product_name': "Error",
                'product_brand': "Error",
                'product_category': "Error",
                'average_rating': None,
                'review_count': 0,
                'price': None,
                'features': [],
                'url': product_url
            }
    
    def get_reviews(self, product_url: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        Récupère les avis d'un produit Amazon.
        
        Args:
            product_url: URL du produit Amazon
            max_pages: Nombre maximum de pages d'avis à scraper
            
        Returns:
            Liste d'avis clients
        """
        if self.use_selenium:
            self.initialize_driver()
            return self._get_reviews_selenium(product_url, max_pages)
        else:
            return self._get_reviews_requests(product_url, max_pages)
    
    def _get_reviews_selenium(self, product_url: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Version Selenium de l'extraction des avis"""
        reviews = []
        product_details = self.get_product_details(product_url)
        
        # Construire l'URL des avis
        if '/dp/' in product_url:
            product_id = product_url.split('/dp/')[1].split('/')[0]
            reviews_url = f"https://www.amazon.com/product-reviews/{product_id}"
        else:
            logger.error(f"Format d'URL de produit invalide: {product_url}")
            return []
        
        try:
            self.driver.get(reviews_url)
            time.sleep(random.uniform(2, 3))
            
            for page in range(1, max_pages + 1):
                logger.info(f"Scraping de la page d'avis {page} pour {product_details['product_name']}")
                
                # Attendre que les avis soient chargés
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]'))
                    )
                except TimeoutException:
                    logger.warning("Délai d'attente dépassé pour le chargement des avis.")
                    break
                
                # Extraire tous les avis de la page
                review_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]')
                
                if not review_elements:
                    logger.warning("Aucun avis trouvé sur cette page.")
                    break
                
                for review_element in review_elements:
                    try:
                        # Extraire les informations de l'avis
                        profile_element = review_element.find_element(By.CSS_SELECTOR, '.a-profile-name')
                        reviewer_name = profile_element.text.strip() if profile_element else "Unknown"
                        
                        # Générer un ID pour le reviewer basé sur son nom pour la démo
                        # Dans un environnement de production, vous devriez essayer de trouver un identifiant plus stable
                        reviewer_id = f"amazon_{hash(reviewer_name) % 10000000}"
                        
                        title_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-title"]')
                        review_title = title_element.text.strip() if title_element else ""
                        
                        body_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-body"]')
                        review_text = body_element.text.strip() if body_element else ""
                        
                        # Combiner le titre et le texte
                        full_review_text = f"{review_title}\n\n{review_text}" if review_title else review_text
                        
                        # Extraire la note
                        rating_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-star-rating"]')
                        rating_text = rating_element.text if rating_element else "0 sur 5 étoiles"
                        try:
                            rating = float(rating_text.split(' ')[0].replace(',', '.'))
                        except (ValueError, IndexError):
                            rating = None
                        
                        # Extraire la date
                        date_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-date"]')
                        date_text = date_element.text if date_element else ""
                        
                        # Transformation en date (le format peut varier selon la région et la langue)
                        try:
                            date_str = date_text.split('on')[-1].strip() if 'on' in date_text else date_text
                            review_date = datetime.strptime(date_str, '%B %d, %Y').strftime('%Y-%m-%d')
                        except ValueError:
                            try:
                                date_str = date_text.split('le')[-1].strip() if 'le' in date_text else date_text
                                review_date = datetime.strptime(date_str, '%d %B %Y').strftime('%Y-%m-%d')
                            except ValueError:
                                review_date = datetime.now().strftime('%Y-%m-%d')
                        
                        # Vérifier si c'est un achat vérifié
                        verified_element = review_element.find_elements(By.CSS_SELECTOR, '[data-hook="avp-badge"]')
                        verified_purchase = len(verified_element) > 0
                        
                        reviews.append({
                            'source': 'amazon',
                            'product_id': product_details['product_id'],
                            'product_name': product_details['product_name'],
                            'product_category': product_details['product_category'],
                            'product_brand': product_details['product_brand'],
                            'reviewer_id': reviewer_id,
                            'reviewer_name': reviewer_name,
                            'review_title': review_title,
                            'review_text': full_review_text,
                            'rating': rating,
                            'review_date': review_date,
                            'verified_purchase': verified_purchase
                        })
                    
                    except Exception as e:
                        logger.error(f"Erreur lors de l'extraction d'un avis: {e}")
                        continue
                
                # Attendre un délai aléatoire entre les pages pour éviter la détection
                time.sleep(random.uniform(3, 5))
                
                # Passer à la page suivante si ce n'est pas la dernière
                if page < max_pages:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, '.a-pagination .a-last a')
                        next_button.click()
                        time.sleep(random.uniform(2, 3))
                    except (NoSuchElementException, Exception) as e:
                        logger.warning(f"Impossible de passer à la page suivante: {e}")
                        break
            
            return reviews
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping des avis: {e}")
            return []
    
    def _get_reviews_requests(self, product_url: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Version requests de l'extraction des avis"""
        reviews = []
        product_details = self.get_product_details(product_url)
        
        # Construire l'URL des avis
        if '/dp/' in product_url:
            product_id = product_url.split('/dp/')[1].split('/')[0]
            reviews_url = f"https://www.amazon.com/product-reviews/{product_id}"
        else:
            logger.error(f"Format d'URL de produit invalide: {product_url}")
            return []
        
        try:
            current_url = reviews_url
            
            for page in range(1, max_pages + 1):
                logger.info(f"Scraping de la page d'avis {page} pour {product_details['product_name']}")
                
                response = self.session.get(current_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extraire tous les avis de la page
                review_elements = soup.select('[data-hook="review"]')
                
                if not review_elements:
                    logger.warning("Aucun avis trouvé sur cette page.")
                    break
                
                for review_element in review_elements:
                    try:
                        # Extraire les informations de l'avis
                        profile_element = review_element.select_one('.a-profile-name')
                        reviewer_name = profile_element.text.strip() if profile_element else "Unknown"
                        
                        # Générer un ID pour le reviewer basé sur son nom pour la démo
                        reviewer_id = f"amazon_{hash(reviewer_name) % 10000000}"
                        
                        title_element = review_element.select_one('[data-hook="review-title"]')
                        review_title = title_element.text.strip() if title_element else ""
                        
                        body_element = review_element.select_one('[data-hook="review-body"]')
                        review_text = body_element.text.strip() if body_element else ""
                        
                        # Combiner le titre et le texte
                        full_review_text = f"{review_title}\n\n{review_text}" if review_title else review_text
                        
                        # Extraire la note
                        rating_element = review_element.select_one('[data-hook="review-star-rating"]')
                        rating_text = rating_element.text if rating_element else "0 sur 5 étoiles"
                        try:
                            rating = float(rating_text.split(' ')[0].replace(',', '.'))
                        except (ValueError, IndexError):
                            rating = None
                        
                        # Extraire la date
                        date_element = review_element.select_one('[data-hook="review-date"]')
                        date_text = date_element.text if date_element else ""
                        
                        # Transformation en date (le format peut varier selon la région et la langue)
                        try:
                            date_str = date_text.split('on')[-1].strip() if 'on' in date_text else date_text
                            review_date = datetime.strptime(date_str, '%B %d, %Y').strftime('%Y-%m-%d')
                        except ValueError:
                            try:
                                date_str = date_text.split('le')[-1].strip() if 'le' in date_text else date_text
                                review_date = datetime.strptime(date_str, '%d %B %Y').strftime('%Y-%m-%d')
                            except ValueError:
                                review_date = datetime.now().strftime('%Y-%m-%d')
                        
                        # Vérifier si c'est un achat vérifié
                        verified_element = review_element.select('[data-hook="avp-badge"]')
                        verified_purchase = len(verified_element) > 0
                        
                        reviews.append({
                            'source': 'amazon',
                            'product_id': product_details['product_id'],
                            'product_name': product_details['product_name'],
                            'product_category': product_details['product_category'],
                            'product_brand': product_details['product_brand'],
                            'reviewer_id': reviewer_id,
                            'reviewer_name': reviewer_name,
                            'review_title': review_title,
                            'review_text': full_review_text,
                            'rating': rating,
                            'review_date': review_date,
                            'verified_purchase': verified_purchase
                        })
                    
                    except Exception as e:
                        logger.error(f"Erreur lors de l'extraction d'un avis: {e}")
                        continue
                
                # Attendre un délai aléatoire entre les pages pour éviter la détection
                time.sleep(random.uniform(1, 3))
                
                # Passer à la page suivante si ce n'est pas la dernière
                if page < max_pages:
                    next_link = soup.select_one('.a-pagination .a-last a')
                    if next_link and 'href' in next_link.attrs:
                        next_url = next_link['href']
                        if not next_url.startswith('http'):
                            next_url = 'https://www.amazon.com' + next_url
                        current_url = next_url
                    else:
                        logger.warning("Lien vers la page suivante non trouvé")
                        break
            
            return reviews
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping des avis: {e}")
            return []
    
    def search_products(self, keywords: str, category: str = None, max_products: int = 10) -> List[Dict[str, Any]]:
        """
        Recherche des produits sur Amazon.
        
        Args:
            keywords: Mots-clés de recherche
            category: Catégorie de produit (optionnel)
            max_products: Nombre maximum de produits à récupérer
            
        Returns:
            Liste de produits
        """
        if self.use_selenium:
            self.initialize_driver()
            return self._search_products_selenium(keywords, category, max_products)
        else:
            return self._search_products_requests(keywords, category, max_products)
    
    def _search_products_selenium(self, keywords: str, category: str = None, max_products: int = 10) -> List[Dict[str, Any]]:
        """Version Selenium de la recherche de produits"""
        products = []
        
        try:
            # Construire l'URL de recherche
            search_url = "https://www.amazon.com/s?k=" + keywords.replace(' ', '+')
            if category:
                # Format simplifié, à adapter selon les catégories Amazon
                search_url += f"&i={category}"
            
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 3))
            
            # Attendre que les résultats de recherche se chargent
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-component-type="s-search-result"]'))
                )
            except TimeoutException:
                logger.warning("Délai d'attente dépassé pour le chargement des résultats de recherche.")
                return []
            
            # Extraire les résultats de recherche
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-component-type="s-search-result"]')
            
            for i, product_element in enumerate(product_elements):
                if i >= max_products:
                    break
                
                try:
                    # Extraire l'URL du produit
                    link_element = product_element.find_element(By.CSS_SELECTOR, '.a-link-normal.s-underline-text')
                    product_url = link_element.get_attribute('href')
                    
                    # Si l'URL n'est pas au format attendu, ignorer ce produit
                    if '/dp/' not in product_url:
                        continue
                    
                    # Extraire les détails du produit
                    product_details = self.get_product_details(product_url)
                    products.append(product_details)
                    
                    # Attendre entre chaque récupération de détails pour éviter la détection
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction des détails d'un produit: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de produits: {e}")
            return []
    
    def _search_products_requests(self, keywords: str, category: str = None, max_products: int = 10) -> List[Dict[str, Any]]:
        """Version requests de la recherche de produits"""
        products = []
        
        try:
            # Construire l'URL de recherche
            search_url = "https://www.amazon.com/s?k=" + keywords.replace(' ', '+')
            if category:
                search_url += f"&i={category}"
            
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraire les résultats de recherche
            product_elements = soup.select('[data-component-type="s-search-result"]')
            
            for i, product_element in enumerate(product_elements):
                if i >= max_products:
                    break
                
                try:
                    # Extraire l'URL du produit
                    link_element = product_element.select_one('.a-link-normal.s-underline-text')
                    if not link_element or 'href' not in link_element.attrs:
                        continue
                        
                    product_url = link_element['href']
                    
                    # Compléter l'URL si nécessaire
                    if not product_url.startswith('http'):
                        product_url = 'https://www.amazon.com' + product_url
                    
                    # Si l'URL n'est pas au format attendu, ignorer ce produit
                    if '/dp/' not in product_url:
                        continue
                    
                    # Extraire les détails du produit
                    product_details = self.get_product_details(product_url)
                    products.append(product_details)
                    
                    # Attendre entre chaque récupération de détails pour éviter la détection
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction des détails d'un produit: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de produits: {e}")
            return []