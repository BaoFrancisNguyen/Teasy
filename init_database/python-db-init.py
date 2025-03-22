#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'initialisation de la base de données de fidélité client
avec données d'exemple pour tester le système.
"""

import sqlite3
import os
import uuid
import random
import datetime
from dateutil.relativedelta import relativedelta
import json

# Configuration
DB_PATH = 'fidelity_db.sqlite'
IMG_STORAGE_PATH = 'ticket_images'

# Créer le dossier pour stocker les images de tickets si nécessaire
os.makedirs(IMG_STORAGE_PATH, exist_ok=True)

# Supprimer la base de données existante si elle existe
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

def create_database():
    """Crée la base de données avec le schéma défini"""
    
    # Charger le schéma SQL depuis un fichier
    with open('schema.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Se connecter à la base de données et exécuter le schéma
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print(f"Base de données créée: {DB_PATH}")

def generate_sample_data():
    """Génère des données d'exemple pour la base de données"""

    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Désactiver les contraintes de clé étrangère pendant l'insertion des données
    cursor.execute("PRAGMA foreign_keys = OFF")
    
    # Date actuelle pour les calculs
    now = datetime.datetime.now()
    
    # --- Générer des magasins ---
    stores = [
        ("Boutique Paris Centre", "flagship", "12 Rue de Rivoli", "75001", "Paris", "France", "01 23 45 67 89", "paris@exemple.com", "Lun-Sam: 10h-20h", 48.856614, 2.3522219),
        ("Boutique Lyon", "franchise", "45 Rue de la République", "69002", "Lyon", "France", "04 56 78 90 12", "lyon@exemple.com", "Lun-Sam: 9h30-19h30", 45.764043, 4.835659),
        ("Boutique Marseille", "franchise", "125 La Canebière", "13001", "Marseille", "France", "04 91 23 45 67", "marseille@exemple.com", "Lun-Sam: 10h-19h", 43.296482, 5.369780),
        ("Boutique Lille", "corner", "Centre Commercial Euralille", "59777", "Lille", "France", "03 20 12 34 56", "lille@exemple.com", "Lun-Sam: 9h-20h", 50.637222, 3.075000),
        ("Boutique Bordeaux", "franchise", "56 Rue Sainte-Catherine", "33000", "Bordeaux", "France", "05 56 12 34 56", "bordeaux@exemple.com", "Lun-Sam: 10h-19h", 44.837789, -0.579180),
        ("Boutique Online", "online", None, None, None, "France", "0800 123 456", "online@exemple.com", "24/7", None, None),
    ]
    
    cursor.executemany("""
        INSERT INTO points_vente (
            nom, type, adresse, code_postal, ville, pays, 
            telephone, email, horaires, latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, stores)
    
    print(f"Ajout de {len(stores)} magasins")
    
    # --- Générer des catégories de produits ---
    categories = [
        ("Vêtements", "Tous types de vêtements", None, 1.0),
        ("Chaussures", "Tous types de chaussures", None, 1.0),
        ("Accessoires", "Accessoires de mode", None, 1.2),
        ("Bijoux", "Bijoux et montres", None, 1.5),
        ("Collections Limitées", "Éditions limitées et collections spéciales", None, 2.0),
        ("Homme", "Vêtements pour homme", 1, 1.0),
        ("Femme", "Vêtements pour femme", 1, 1.0),
        ("Enfant", "Vêtements pour enfant", 1, 1.0),
        ("Sport", "Vêtements et accessoires de sport", 1, 1.1),
        ("Baskets", "Chaussures de sport et de ville", 2, 1.1),
        ("Chaussures Ville", "Chaussures élégantes", 2, 1.0),
        ("Chaussures Confort", "Chaussures de confort et de marche", 2, 1.0),
        ("Sacs", "Sacs à main et bagages", 3, 1.2),
        ("Ceintures", "Ceintures et accessoires en cuir", 3, 1.0),
        ("Écharpes", "Écharpes et foulards", 3, 1.0),
        ("Lunettes", "Lunettes de soleil et optiques", 3, 1.1),
        ("Montres", "Montres de luxe et casual", 4, 1.5),
        ("Bracelets", "Bracelets et gourmettes", 4, 1.3),
        ("Bagues", "Bagues et alliances", 4, 1.3),
        ("Édition Limitée", "Produits exclusifs en série limitée", 5, 2.0),
        ("Collaborations", "Collaborations avec des artistes", 5, 2.0),
    ]
    
    cursor.executemany("""
        INSERT INTO categories_produits (
            nom, description, categorie_parent_id, multiplicateur_points
        ) VALUES (?, ?, ?, ?)
    """, categories)
    
    print(f"Ajout de {len(categories)} catégories de produits")
    
    # --- Générer des produits ---
    products = []
    
    # Vêtements Homme
    for i in range(1, 11):
        products.append((
            f"VH{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"T-shirt Homme Classic {i}", f"T-shirt en coton bio, coupe regular, coloris {random.choice(['noir', 'blanc', 'bleu', 'gris'])}",
            6, None, "MaMarque", round(random.uniform(19.99, 39.99), 2), 1.0, "actif", None
        ))
    
    for i in range(1, 6):
        products.append((
            f"VH{i+10:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Pantalon Homme Style {i}", f"Pantalon chino, coupe droite, coloris {random.choice(['noir', 'beige', 'bleu marine', 'gris'])}",
            6, None, "MaMarque", round(random.uniform(49.99, 79.99), 2), 1.0, "actif", None
        ))
    
    # Vêtements Femme
    for i in range(1, 11):
        products.append((
            f"VF{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Robe Femme Élégance {i}", f"Robe mi-longue, matière fluide, coloris {random.choice(['noir', 'rouge', 'bleu', 'vert'])}",
            7, None, "MaMarque", round(random.uniform(59.99, 99.99), 2), 1.0, "actif", None
        ))
    
    for i in range(1, 6):
        products.append((
            f"VF{i+10:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Top Femme Fashion {i}", f"Top léger, décolleté rond, coloris {random.choice(['blanc', 'noir', 'rose', 'jaune'])}",
            7, None, "MaMarque", round(random.uniform(29.99, 49.99), 2), 1.0, "actif", None
        ))
    
    # Chaussures
    for i in range(1, 8):
        products.append((
            f"CH{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Sneakers Urban {i}", f"Baskets tendance, semelle confort, coloris {random.choice(['noir', 'blanc', 'multicolore'])}",
            10, None, "MaMarque", round(random.uniform(69.99, 129.99), 2), 1.1, "actif", None
        ))
    
    # Accessoires
    for i in range(1, 6):
        products.append((
            f"AC{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Sac Trendy {i}", f"Sac à main format moyen, cuir véritable, coloris {random.choice(['noir', 'marron', 'camel'])}",
            13, None, "MaMarque", round(random.uniform(99.99, 199.99), 2), 1.2, "actif", None
        ))
    
    for i in range(1, 4):
        products.append((
            f"LU{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Lunettes Solaires {i}", f"Lunettes de soleil protection UV, monture acétate, coloris {random.choice(['noir', 'écaille', 'transparent'])}",
            16, None, "MaMarque", round(random.uniform(89.99, 149.99), 2), 1.1, "actif", None
        ))
    
    # Bijoux
    for i in range(1, 4):
        products.append((
            f"MO{i:03d}", f"EAN13{random.randint(1000000000000, 9999999999999)}",
            f"Montre Classique {i}", f"Montre analogique, bracelet {random.choice(['cuir', 'métal', 'silicone'])}, cadran {random.choice(['noir', 'blanc', 'bleu'])}",
            17, None, "MaMarque", round(random.uniform(149.99, 299.99), 2), 1.5, "actif", None
        ))
    
    # Collection Limitée
    products.append((
        "EL001", f"EAN13{random.randint(1000000000000, 9999999999999)}",
        "Série Limitée Designer", "Pièce exclusive, édition numérotée, collaboration designer renommé",
        20, None, "MaMarque", 499.99, 2.0, "actif", None
    ))
    
    cursor.executemany("""
        INSERT INTO produits (
            reference, code_barres, nom, description, categorie_id, 
            sous_categorie_id, marque, prix_standard, multiplicateur_points, 
            statut, image_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, products)
    
    print(f"Ajout de {len(products)} produits")
    
    # --- Générer des clients ---
    clients = []
    client_anonymized = []
    cartes = []
    
    # Noms et prénoms pour générer des clients aléatoires
    prenoms = ["Jean", "Marie", "Pierre", "Sophie", "Thomas", "Isabelle", "Éric", "Nathalie", 
               "Philippe", "Catherine", "Michel", "Sylvie", "Laurent", "Valérie", "Nicolas", 
               "Stéphanie", "Patrick", "Christine", "Thierry", "Sandrine"]
    
    noms = ["Martin", "Bernard", "Durand", "Dubois", "Moreau", "Laurent", "Lefebvre", "Leroy", 
            "Roux", "Morel", "Simon", "Michel", "Blanc", "Rousseau", "Girard", "Fournier", 
            "Lambert", "Dupont", "Vincent", "Fontaine"]
    
    # 100 clients avec leurs cartes
    for i in range(1, 101):
        client_uuid = str(uuid.uuid4())
        prenom = random.choice(prenoms)
        nom = random.choice(noms)
        genre = "homme" if prenom in ["Jean", "Pierre", "Thomas", "Éric", "Philippe", "Michel", 
                                    "Laurent", "Nicolas", "Patrick", "Thierry"] else "femme"
        
        # Date de naissance entre 18 et 80 ans
        years_back = random.randint(18, 80)
        date_naissance = (now - relativedelta(years=years_back, 
                                             days=random.randint(0, 365))).strftime("%Y-%m-%d")
        
        # Date d'inscription entre 5 ans et 1 mois
        days_back = random.randint(30, 1825)
        date_inscription = (now - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Adresse
        code_postal = random.choice(["75001", "75002", "75003", "75004", "75005", "75006", "75007", 
                                    "69001", "69002", "69003", "13001", "13002", "13003", "59000", 
                                    "33000", "44000", "31000", "67000", "06000", "34000"])
        
        ville = {
            "75": "Paris", "69": "Lyon", "13": "Marseille", "59": "Lille", 
            "33": "Bordeaux", "44": "Nantes", "31": "Toulouse", "67": "Strasbourg", 
            "06": "Nice", "34": "Montpellier"
        }.get(code_postal[:2], "Autre")
        
        adresse = f"{random.randint(1, 100)} rue {random.choice(['des Fleurs', 'de Paris', 'Victor Hugo', 'du Commerce', 'de la Paix', 'des Lilas', 'de la République', 'de la Gare', 'des Écoles', 'du Moulin'])}"
        
        # Email
        email = f"{prenom.lower()}.{nom.lower()}{random.randint(1, 999)}@{random.choice(['gmail.com', 'yahoo.fr', 'hotmail.com', 'outlook.fr', 'orange.fr', 'free.fr', 'sfr.fr'])}"
        
        # Téléphone
        telephone = f"0{random.randint(6, 7)}{random.randint(10000000, 99999999)}"
        
        # Statut et segment
        statut = random.choices(["actif", "inactif"], weights=[95, 5])[0]
        segment = random.choices(["standard", "premium", "vip"], weights=[70, 25, 5])[0]
        
        # Consentements
        consentement_marketing = random.choices([0, 1], weights=[30, 70])[0]
        consentement_data = random.choices([0, 1], weights=[20, 80])[0]
        
        # Canal d'acquisition
        canal_acquisition = random.choice(["magasin", "en_ligne", "parrainage", "événement", "publicité"])
        
        clients.append((
            client_uuid, nom, prenom, date_naissance, genre, adresse, code_postal, ville, "France",
            telephone, email, date_inscription, consentement_marketing, consentement_data, 
            date_inscription, statut, segment, canal_acquisition
        ))
        
        # Créer une carte de fidélité pour chaque client
        numero_carte = f"FID{i:06d}"
        date_emission = date_inscription
        
        # Date d'expiration (3 ans après émission)
        date_expiration = (datetime.datetime.strptime(date_emission, "%Y-%m-%d %H:%M:%S") + 
                           relativedelta(years=3)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculer un nombre de points en fonction de l'ancienneté et du segment
        points_base = random.randint(100, 5000)
        points_multiplicateur = {"standard": 1, "premium": 2, "vip": 4}[segment]
        anciennete_factor = max(1, (now - datetime.datetime.strptime(date_inscription, "%Y-%m-%d %H:%M:%S")).days / 365)
        
        points_actuels = int(points_base * points_multiplicateur * anciennete_factor)
        
        # Déterminer le niveau en fonction des points
        if points_actuels < 1000:
            niveau = "bronze"
        elif points_actuels < 5000:
            niveau = "argent"
        elif points_actuels < 10000:
            niveau = "or"
        else:
            niveau = "platine"
        
        cartes.append((i, numero_carte, date_emission, date_expiration, "active", niveau, points_actuels))
    
    cursor.executemany("""
        INSERT INTO clients (
            uuid, nom, prenom, date_naissance, genre, adresse, 
            code_postal, ville, pays, telephone, email, date_inscription, 
            consentement_marketing, consentement_data_processing, date_consentement, 
            statut, segment, canal_acquisition
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, clients)
    
    # Insérer les cartes de fidélité
    cursor.executemany("""
        INSERT INTO cartes_fidelite (
            client_id, numero_carte, date_emission, date_expiration, 
            statut, niveau_fidelite, points_actuels
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, cartes)
    
    print(f"Ajout de {len(clients)} clients et cartes de fidélité")
    
    # --- Générer des transactions ---
    transactions = []
    details_transactions = []
    transaction_id = 1
    detail_id = 1
    
    # Pour chaque client
    for client_id in range(1, 101):
        # Nombre de transactions par client (variable selon l'ancienneté)
        nb_transactions = random.randint(3, 20)
        
        for t in range(nb_transactions):
            # Date de la transaction (entre la date d'inscription et aujourd'hui)
            client_inscription = cursor.execute(
                "SELECT date_inscription FROM clients WHERE client_id = ?", 
                (client_id,)
            ).fetchone()[0]
            
            jours_client = (now - datetime.datetime.strptime(client_inscription, "%Y-%m-%d %H:%M:%S")).days
            jours_transaction = random.randint(0, jours_client)
            
            date_transaction = (now - datetime.timedelta(days=jours_transaction))
            
            # Trier par date pour avoir un ordre chronologique
            date_transaction -= datetime.timedelta(minutes=random.randint(0, 1440))
            
            date_transaction_str = date_transaction.strftime("%Y-%m-%d %H:%M:%S")
            
            # Magasin aléatoire (préférence pour magasin local selon code postal)
            magasin_id = random.randint(1, 6)
            
            # Type de paiement
            type_paiement = random.choice(["cb", "espèces", "cb", "cb", "mobile"])
            
            # Canal de vente
            canal_vente = "en_ligne" if magasin_id == 6 else "magasin"
            
            # Numéro de facture
            numero_facture = f"F{date_transaction.strftime('%Y%m%d')}-{transaction_id:06d}"
            
            # Nombre d'articles dans cette transaction
            nb_articles = random.randint(1, 8)
            
            # Montant total (sera calculé à partir des détails)
            montant_total = 0
            montant_ht = 0
            tva_montant = 0
            points_gagnes = 0
            
            # Détails de la transaction
            transaction_details = []
            
            for a in range(nb_articles):
                # Produit aléatoire
                produit_id = random.randint(1, len(products))
                
                # Récupérer le prix du produit
                prix_unitaire = cursor.execute(
                    "SELECT prix_standard FROM produits WHERE produit_id = ?", 
                    (produit_id,)
                ).fetchone()[0]
                
                # Quantité
                quantite = random.choices([1, 2, 3], weights=[70, 25, 5])[0]
                
                # Remise éventuelle
                remise_pourcentage = random.choices([0, 10, 20, 30, 40, 50], 
                                                  weights=[70, 10, 10, 5, 3, 2])[0]
                remise_montant = prix_unitaire * (remise_pourcentage / 100) * quantite
                
                # Montant ligne
                montant_ligne = (prix_unitaire * quantite) - remise_montant
                
                # Calcul des points (à ajuster en fonction des multiplicateurs plus tard)
                points_ligne = int(montant_ligne)
                
                # Ajouter au montant total
                montant_total += montant_ligne
                montant_ht += montant_ligne / 1.2  # Supposant une TVA de 20%
                tva_montant += montant_ligne - (montant_ligne / 1.2)
                points_gagnes += points_ligne
                
                transaction_details.append((
                    transaction_id, produit_id, quantite, prix_unitaire, 
                    remise_pourcentage, remise_montant, montant_ligne, points_ligne
                ))
            
            # Arrondir les montants
            montant_total = round(montant_total, 2)
            montant_ht = round(montant_ht, 2)
            tva_montant = round(tva_montant, 2)
            
            # Ajouter la transaction
            transactions.append((
                client_id, client_id, magasin_id, None, date_transaction_str, 
                montant_total, montant_ht, tva_montant, type_paiement, 
                numero_facture, canal_vente, points_gagnes, 0, None
            ))
            
            # Ajouter les détails de la transaction
            for detail in transaction_details:
                details_transactions.append(detail)
                detail_id += 1
            
            transaction_id += 1
    
    # Insérer les transactions
    cursor.executemany("""
        INSERT INTO transactions (
            client_id, carte_id, magasin_id, employe_id, date_transaction, 
            montant_total, montant_ht, tva_montant, type_paiement, 
            numero_facture, canal_vente, points_gagnes, points_utilises, commentaire
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transactions)
    
    # Insérer les détails des transactions
    cursor.executemany("""
        INSERT INTO details_transactions (
            transaction_id, produit_id, quantite, prix_unitaire, 
            remise_pourcentage, remise_montant, montant_ligne, points_ligne
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, details_transactions)
    
    print(f"Ajout de {len(transactions)} transactions avec {len(details_transactions)} détails")
    
    # --- Générer des tickets de caisse OCR ---
    tickets_ocr = []
    extractions_ocr = []
    ticket_id = 1
    
    # Exemple de tickets pour les 20 premières transactions
    for transaction_id in range(1, 21):
        # Récupérer les infos de la transaction
        transaction_info = cursor.execute("""
            SELECT t.date_transaction, t.montant_total, t.numero_facture, 
                   m.nom as magasin, c.prenom, c.nom
            FROM transactions t
            JOIN points_vente m ON t.magasin_id = m.magasin_id
            JOIN clients c ON t.client_id = c.client_id
            WHERE t.transaction_id = ?
        """, (transaction_id,)).fetchone()
        
        if transaction_info:
            date_transaction, montant_total, numero_facture, magasin, prenom, nom = transaction_info
            
            # Simuler un upload de ticket (fichier virtuel)
            image_path = f"{IMG_STORAGE_PATH}/ticket_{transaction_id}.jpg"
            
            # Date d'upload (un peu après la transaction)
            date_upload = (datetime.datetime.strptime(date_transaction, "%Y-%m-%d %H:%M:%S") + 
                           datetime.timedelta(minutes=random.randint(10, 60))).strftime("%Y-%m-%d %H:%M:%S")
            
            # Statut de traitement
            statut_traitement = random.choice(["traité", "vérifié"])
            
            # Date de traitement
            date_traitement = (datetime.datetime.strptime(date_upload, "%Y-%m-%d %H:%M:%S") + 
                              datetime.timedelta(minutes=random.randint(1, 5))).strftime("%Y-%m-%d %H:%M:%S")
            
            # Texte OCR simulé
            texte_ocr = f"""
{magasin}
----------------------------------------
FACTURE N° {numero_facture}
DATE: {date_transaction}
----------------------------------------
CLIENT: {prenom} {nom}

ARTICLES:
"""
            
            # Récupérer les détails de la transaction pour le ticket
            details = cursor.execute("""
                SELECT p.nom, d.quantite, d.prix_unitaire, d.remise_pourcentage, d.montant_ligne
                FROM details_transactions d
                JOIN produits p ON d.produit_id = p.produit_id
                WHERE d.transaction_id = ?
            """, (transaction_id,)).fetchall()
            
            for nom_produit, quantite, prix_unitaire, remise, montant in details:
                texte_ocr += f"{nom_produit[:20]}... x{quantite}  {prix_unitaire:.2f}€"
                if remise > 0:
                    texte_ocr += f" (-{remise}%)"
                texte_ocr += f" {montant:.2f}€\n"
            
            texte_ocr += f"""
----------------------------------------
TOTAL TTC: {montant_total:.2f}€
----------------------------------------
MERCI DE VOTRE VISITE!
"""
            
            # Métadonnées JSON
            metadonnees = json.dumps({
                "image_quality": random.uniform(0.7, 1.0),
                "confidence_score": random.uniform(0.8, 0.98),
                "processing_time_ms": random.randint(500, 2000),
                "detected_items": len(details)
            })
            
            # Ajouter le ticket
            tickets_ocr.append((
                transaction_id % 100 + 1,  # client_id
                transaction_id,
                date_upload,
                image_path,
                statut_traitement,
                texte_ocr,
                metadonnees,
                date_traitement
            ))
            
            # Ajouter des extractions OCR
            extractions = [
                ("date", date_transaction, random.uniform(0.8, 0.98), 1),
                ("montant_total", str(montant_total), random.uniform(0.9, 0.99), 2),
                ("numero_facture", numero_facture, random.uniform(0.85, 0.95), 3),
                ("magasin", magasin, random.uniform(0.8, 0.9), 4),
            ]
            
            for champ, valeur, confiance, regle_id in extractions:
                extractions_ocr.append((
                    ticket_id, champ, valeur, confiance, regle_id, 1
                ))
            
            ticket_id += 1
    
    # Insérer les tickets
    cursor.executemany("""
        INSERT INTO tickets_caisse (
            client_id, transaction_id, date_upload, image_path,
            statut_traitement, texte_ocr, metadonnees, date_traitement
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, tickets_ocr)
    
    # Insérer les extractions OCR
    cursor.executemany("""
        INSERT INTO extractions_ocr (
            ticket_id, champ, valeur, confiance, regle_id, verifie
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, extractions_ocr)
    
    print(f"Ajout de {len(tickets_ocr)} tickets OCR avec {len(extractions_ocr)} extractions")
    
    # --- Générer des récompenses ---
    recompenses = [
        ("Bon d'achat 10€", "Bon d'achat de 10€ à valoir sur votre prochain achat", "remise", 1000, 10.0),
        ("Bon d'achat 25€", "Bon d'achat de 25€ à valoir sur votre prochain achat", "remise", 2000, 25.0),
        ("Bon d'achat 50€", "Bon d'achat de 50€ à valoir sur votre prochain achat", "remise", 4000, 50.0),
        ("Carte cadeau 100€", "Carte cadeau d'une valeur de 100€", "remise", 8000, 100.0),
        ("Produit offert", "Un produit offert parmi une sélection", "produit", 3000, 30.0),
        ("Frais de livraison offerts", "Livraison gratuite pour votre prochaine commande", "service", 500, 5.0),
        ("Accès VIP Soldes", "Accès anticipé aux soldes", "experience", 5000, 0.0),
        ("Atelier personnalisé", "Invitation à un atelier exclusif", "experience", 7000, 70.0),
        ("Coffret cadeau", "Coffret cadeau premium", "produit", 6000, 60.0),
        ("Réduction partenaire", "Réduction de 30% chez notre partenaire spa", "partenaire", 3500, 35.0),
    ]
    
    # Ajouter des dates et quotas pour les récompenses
    complete_recompenses = []
    for nom, description, categorie, points, valeur in recompenses:
        date_debut = (now - datetime.timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d")
        date_fin = (now + datetime.timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d")
        quota_total = random.randint(50, 500)
        quota_restant = random.randint(0, quota_total)
        statut = "active" if quota_restant > 0 and datetime.datetime.strptime(date_fin, "%Y-%m-%d") > now else "inactive"
        
        complete_recompenses.append((
            nom, description, categorie, points, valeur, 
            date_debut, date_fin, statut, quota_total, quota_restant, None
        ))
    
    cursor.executemany("""
        INSERT INTO recompenses (
            nom, description, categorie, points_necessaires, valeur_monetaire,
            date_debut, date_fin, statut, quota_total, quota_restant, image_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, complete_recompenses)
    
    print(f"Ajout de {len(complete_recompenses)} récompenses")
    
    # --- Générer des utilisations de récompenses ---
    utilisations = []
    
    # Pour un sous-ensemble de clients avec suffisamment de points
    clients_points = cursor.execute("""
        SELECT c.client_id, cf.carte_id, cf.points_actuels
        FROM clients c
        JOIN cartes_fidelite cf ON c.client_id = cf.client_id
        WHERE cf.points_actuels > 1000
    """).fetchall()
    
    # Récupérer les récompenses disponibles
    recompenses_dispo = cursor.execute("""
        SELECT recompense_id, points_necessaires
        FROM recompenses
        WHERE statut = 'active'
    """).fetchall()
    
    if recompenses_dispo:
        for client_id, carte_id, points in clients_points:
            # 50% de chance d'utiliser une récompense
            if random.random() < 0.5:
                # Choisir des récompenses que le client peut se permettre
                recompenses_accessibles = [(rid, pts) for rid, pts in recompenses_dispo if pts <= points]
                
                if recompenses_accessibles:
                    # Choisir une récompense aléatoire
                    recompense_id, points_necessaires = random.choice(recompenses_accessibles)
                    
                    # Date de demande (dans les 3 derniers mois)
                    date_demande = (now - datetime.timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Code unique
                    code_unique = f"REWARD-{client_id}-{recompense_id}-{random.randint(1000, 9999)}"
                    
                    # Statut (70% utilisé, 20% réservé, 10% expiré)
                    statut = random.choices(["utilisée", "réservée", "expirée"], weights=[70, 20, 10])[0]
                    
                    # Date d'utilisation (si utilisée)
                    date_utilisation = None
                    if statut == "utilisée":
                        date_utilisation = (datetime.datetime.strptime(date_demande, "%Y-%m-%d %H:%M:%S") + 
                                           datetime.timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Transaction liée (pour certaines récompenses utilisées)
                    transaction_id = None
                    if statut == "utilisée" and random.random() < 0.7:
                        # Trouver une transaction récente de ce client
                        recent_transaction = cursor.execute("""
                            SELECT transaction_id FROM transactions
                            WHERE client_id = ? AND date_transaction > ?
                            ORDER BY date_transaction DESC LIMIT 1
                        """, (client_id, date_demande)).fetchone()
                        
                        if recent_transaction:
                            transaction_id = recent_transaction[0]
                    
                    utilisations.append((
                        client_id, carte_id, recompense_id, date_demande, date_utilisation,
                        points_necessaires, code_unique, statut, transaction_id, None
                    ))
    
    cursor.executemany("""
        INSERT INTO utilisation_recompenses (
            client_id, carte_id, recompense_id, date_demande, date_utilisation,
            points_depenses, code_unique, statut, transaction_id, commentaire
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, utilisations)
    
    print(f"Ajout de {len(utilisations)} utilisations de récompenses")
    
    # --- Générer des campagnes marketing ---
    campagnes = [
        ("Soldes d'été", "Profitez de nos soldes d'été exclusives", "email", 
         "Clients premium et VIP", "segment IN ('premium', 'vip')", 
         "Jusqu'à 50% de réduction", 1.5),
        ("Bienvenue nouveaux clients", "Offre de bienvenue pour nos nouveaux adhérents", "email", 
         "Clients récents", "DATEDIFF(date_inscription, CURRENT_DATE) <= 30", 
         "10% sur votre premier achat", 2.0),
        ("Joyeux anniversaire", "Offre spéciale pour votre anniversaire", "email", 
         "Clients avec anniversaire ce mois", "MONTH(date_naissance) = MONTH(CURRENT_DATE)", 
         "Un cadeau surprise en magasin", 1.0),
        ("Réactivation", "Réactivez votre compte et profitez d'avantages exclusifs", "sms", 
         "Clients inactifs", "client_id NOT IN (SELECT client_id FROM transactions WHERE date_transaction >= date('now', '-6 month'))", 
         "15% de réduction sur votre prochain achat", 1.0),
        ("Vente flash weekend", "48h de prix exceptionnels", "notification", 
         "Tous clients actifs", "statut = 'actif'", 
         "Vente flash ce weekend uniquement", 2.0),
        ("Lancement collection", "Découvrez notre nouvelle collection en avant-première", "email", 
         "Clients VIP", "segment = 'vip'", 
         "Accès exclusif avant tout le monde", 1.5)
    ]
    
    complete_campagnes = []
    for nom, description, type_campagne, public, criteres, offre, multiplicateur in campagnes:
        # Dates de la campagne (certaines passées, d'autres en cours, d'autres futures)
        scenario = random.choice(["passée", "en_cours", "future"])
        
        if scenario == "passée":
            date_debut = (now - datetime.timedelta(days=random.randint(60, 180))).strftime("%Y-%m-%d")
            date_fin = (datetime.datetime.strptime(date_debut, "%Y-%m-%d") + 
                       datetime.timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d")
            statut = "terminée"
        elif scenario == "en_cours":
            date_debut = (now - datetime.timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d")
            date_fin = (now + datetime.timedelta(days=random.randint(1, 20))).strftime("%Y-%m-%d")
            statut = "active"
        else:  # future
            date_debut = (now + datetime.timedelta(days=random.randint(10, 60))).strftime("%Y-%m-%d")
            date_fin = (datetime.datetime.strptime(date_debut, "%Y-%m-%d") + 
                       datetime.timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d")
            statut = "planifiée"
        
        budget = random.randint(500, 5000)
        
        complete_campagnes.append((
            nom, description, type_campagne, date_debut, date_fin,
            public, criteres, offre, multiplicateur, budget, statut,
            now.strftime("%Y-%m-%d %H:%M:%S"), "admin"
        ))
    
    cursor.executemany("""
        INSERT INTO campagnes_marketing (
            nom, description, type, date_debut, date_fin,
            public_cible, criteres_selection, offre, multiplicateur_points, budget, statut,
            creation_date, creation_user
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, complete_campagnes)
    
    print(f"Ajout de {len(complete_campagnes)} campagnes marketing")
    
    # --- Générer les participations aux campagnes ---
    participations = []
    
    # Pour chaque campagne terminée ou active
    campagnes_actives = cursor.execute("""
        SELECT campagne_id, criteres_selection, statut
        FROM campagnes_marketing
        WHERE statut IN ('terminée', 'active')
    """).fetchall()
    
    for campagne_id, criteres, statut in campagnes_actives:
        # Sélectionner aléatoirement entre 10 et 50 clients (en pratique on utiliserait les critères)
        nb_clients = random.randint(10, 50)
        clients_ids = [random.randint(1, 100) for _ in range(nb_clients)]
        
        for client_id in clients_ids:
            # Date d'envoi (selon le statut de la campagne)
            if statut == "terminée":
                # Pour une campagne terminée, date dans le passé
                days_ago = random.randint(30, 180)
                date_envoi = (now - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Pour une campagne active, date récente
                days_ago = random.randint(0, 15)
                date_envoi = (now - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Canal d'envoi
            canal = random.choice(["email", "sms", "notification", "courrier"])
            
            # Statut de l'envoi
            statut_envoi = random.choices(["envoyé", "ouvert", "cliqué"], weights=[30, 40, 30])[0]
            
            # Date de réponse (si ouvert ou cliqué)
            date_reponse = None
            if statut_envoi in ["ouvert", "cliqué"]:
                minutes_after = random.randint(10, 1440)  # Entre 10 min et 24h après
                date_reponse = (datetime.datetime.strptime(date_envoi, "%Y-%m-%d %H:%M:%S") + 
                               datetime.timedelta(minutes=minutes_after)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Conversion (si cliqué)
            conversion = 0
            transaction_id = None
            if statut_envoi == "cliqué" and random.random() < 0.3:  # 30% de conversion
                conversion = 1
                
                # Trouver une transaction potentielle après la date de réponse
                if date_reponse:
                    recent_transaction = cursor.execute("""
                        SELECT transaction_id FROM transactions
                        WHERE client_id = ? AND date_transaction > ?
                        ORDER BY date_transaction ASC LIMIT 1
                    """, (client_id, date_reponse)).fetchone()
                    
                    if recent_transaction:
                        transaction_id = recent_transaction[0]
            
            participations.append((
                campagne_id, client_id, date_envoi, canal, statut_envoi,
                date_reponse, conversion, transaction_id
            ))
    
    cursor.executemany("""
        INSERT INTO participation_campagnes (
            campagne_id, client_id, date_envoi, canal, statut,
            date_reponse, conversion, transaction_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, participations)
    
    print(f"Ajout de {len(participations)} participations aux campagnes")
    
    # --- Générer des feedbacks clients ---
    feedbacks = []
    
    # Sélectionner des transactions récentes pour les feedbacks
    transactions_recentes = cursor.execute("""
        SELECT transaction_id, client_id, date_transaction
        FROM transactions
        WHERE date_transaction >= date('now', '-3 month')
        ORDER BY date_transaction DESC
        LIMIT 200
    """).fetchall()
    
    # Générer un feedback pour environ 25% des transactions récentes
    for transaction_id, client_id, date_transaction in random.sample(transactions_recentes, len(transactions_recentes) // 4):
        # Date du feedback (1 à 7 jours après la transaction)
        date_feedback = (datetime.datetime.strptime(date_transaction, "%Y-%m-%d %H:%M:%S") + 
                         datetime.timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d %H:%M:%S")
        
        # Canal
        canal = random.choice(["email", "app", "web", "sms", "en_magasin"])
        
        # Scores (tendance positive)
        score_nps = random.choices(range(0, 11), weights=[1, 1, 1, 2, 2, 3, 5, 10, 25, 25, 25])[0]
        score_satisfaction = random.choices(range(1, 6), weights=[1, 2, 5, 40, 52])[0]
        
        # Commentaire
        commentaires_positifs = [
            "Très satisfait du service!",
            "Produit de très bonne qualité.",
            "Personnel accueillant et professionnel.",
            "Je recommande vivement!",
            "Excellent rapport qualité/prix."
        ]
        
        commentaires_neutres = [
            "Service correct mais pourrait être amélioré.",
            "Qualité du produit correcte.",
            "Temps d'attente un peu long.",
            "Prix un peu élevés mais produits de qualité."
        ]
        
        commentaires_negatifs = [
            "Déçu de la qualité du produit.",
            "Service client à revoir.",
            "Trop cher pour la qualité proposée.",
            "Attente trop longue en caisse."
        ]
        
        if score_satisfaction >= 4:
            commentaire = random.choice(commentaires_positifs)
        elif score_satisfaction >= 3:
            commentaire = random.choice(commentaires_neutres)
        else:
            commentaire = random.choice(commentaires_negatifs)
        
        # Domaines concernés
        domaines_possibles = ["produit", "service", "prix", "magasin", "livraison", "application"]
        nb_domaines = random.randint(1, 3)
        domaines = json.dumps(random.sample(domaines_possibles, nb_domaines))
        
        # Contact souhaité (surtout pour les scores bas)
        contact_souhaite = 1 if score_satisfaction <= 2 and random.random() < 0.7 else 0
        
        # Traité ou non
        traite = 1 if (contact_souhaite == 1 and random.random() < 0.8) or random.random() < 0.5 else 0
        
        feedbacks.append((
            client_id, transaction_id, date_feedback, canal,
            score_nps, score_satisfaction, commentaire, domaines,
            contact_souhaite, traite
        ))
    
    cursor.executemany("""
        INSERT INTO feedback_clients (
            client_id, transaction_id, date_feedback, canal,
            score_nps, score_satisfaction, commentaire, domaines,
            contacts_souhaites, traite
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, feedbacks)
    
    print(f"Ajout de {len(feedbacks)} feedbacks clients")
    
    # --- Générer des règles OCR ---
    regles_ocr = [
        ("Date", "\\b(\\d{1,2}[/-]\\d{1,2}[/-]\\d{2,4})\\b", "date", 10),
        ("Montant total", "\\bTOTAL\\s*:?\\s*(\\d+[.,]\\d{2})\\b", "montant_total", 10),
        ("Numéro facture", "\\bFACTURE\\s*N°\\s*([A-Z0-9-]+)\\b", "numero_facture", 5),
        ("Nom magasin", "^([A-Za-z\\s]+)\\n", "magasin", 5),
    ]
    
    cursor.executemany("""
        INSERT INTO regles_ocr (
            nom, pattern, champ_cible, priorite, est_active, description
        ) VALUES (?, ?, ?, ?, 1, 'Règle extraite automatiquement')
    """, regles_ocr)
    
    print(f"Ajout de {len(regles_ocr)} règles OCR")
    
    # --- Générer des logs d'accès aux données ---
    logs_acces = []
    
    # Actions possibles
    actions = ["lecture", "modification", "suppression", "export"]
    tables = ["clients", "cartes_fidelite", "transactions", "details_transactions", 
              "feedback_clients", "campagnes_marketing", "tickets_caisse"]
    utilisateurs = ["admin", "data_analyst", "marketing", "service_client", "caisse"]
    
    # Générer 100 logs aléatoires
    for _ in range(100):
        action = random.choice(actions)
        table = random.choice(tables)
        utilisateur = random.choice(utilisateurs)
        
        # ID concerné (dépend de la table)
        id_max = {
            "clients": 100,
            "cartes_fidelite": 100,
            "transactions": len(transactions),
            "details_transactions": len(details_transactions),
            "feedback_clients": len(feedbacks),
            "campagnes_marketing": len(complete_campagnes),
            "tickets_caisse": len(tickets_ocr)
        }.get(table, 50)
        
        identifiant = random.randint(1, id_max)
        
        # Date d'accès (dans les 30 derniers jours)
        date_acces = (now - datetime.timedelta(days=random.randint(0, 30), 
                                              hours=random.randint(0, 23),
                                              minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S")
        
        # Détails
        details = f"{action.capitalize()} de données {table} (ID: {identifiant})"
        
        # IP
        ip = f"192.168.1.{random.randint(2, 254)}"
        
        logs_acces.append((
            utilisateur, date_acces, action, table, identifiant, details, ip
        ))
    
    cursor.executemany("""
        INSERT INTO logs_acces_donnees (
            utilisateur, date_acces, action, table_concernee, 
            identifiant, details, ip_address
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, logs_acces)
    
    print(f"Ajout de {len(logs_acces)} logs d'accès aux données")
    
    # --- Mettre à jour l'historique des points pour chaque client ---
    # Récupérer toutes les transactions avec points gagnés
    transactions_points = cursor.execute("""
        SELECT transaction_id, client_id, carte_id, date_transaction, points_gagnes
        FROM transactions
        WHERE points_gagnes > 0
        ORDER BY date_transaction
    """).fetchall()
    
    historique_points = []
    
    for transaction_id, client_id, carte_id, date_transaction, points in transactions_points:
        # Récupérer le solde actuel pour ce client
        solde_query = cursor.execute("""
            SELECT points_actuels FROM cartes_fidelite
            WHERE client_id = ? AND carte_id = ?
        """, (client_id, carte_id)).fetchone()
        
        if solde_query:
            solde = solde_query[0]
            historique_points.append((
                client_id, carte_id, date_transaction, "gain", points,
                transaction_id, None, "Points gagnés lors d'un achat", solde
            ))
    
    # Ajouter quelques ajustements et bonus
    for i in range(20):
        client_id = random.randint(1, 100)
        # Récupérer la carte du client
        carte_query = cursor.execute("""
            SELECT carte_id, points_actuels FROM cartes_fidelite
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        
        if carte_query:
            carte_id, solde = carte_query
            
            # Type d'opération
            type_operation = random.choice(["ajustement", "bonus"])
            
            # Points (ajustement peut être négatif)
            if type_operation == "ajustement":
                points = random.randint(-500, 500)
                description = "Ajustement manuel de points"
            else:
                points = random.randint(50, 500)
                description = "Bonus de fidélité"
            
            # Date (dans les 6 derniers mois)
            date_operation = (now - datetime.timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d %H:%M:%S")
            
            historique_points.append((
                client_id, carte_id, date_operation, type_operation, points,
                None, None, description, solde
            ))
    
    cursor.executemany("""
        INSERT INTO historique_points (
            client_id, carte_id, date_operation, type_operation, points,
            transaction_id, recompense_id, description, solde_apres
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, historique_points)
    
    print(f"Ajout de {len(historique_points)} entrées d'historique de points")
    
    # Finaliser la connexion
    conn.commit()
    # Réactiver les contraintes de clé étrangère
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.close()
    
    print("Initialisation de la base de données terminée avec succès!")

if __name__ == "__main__":
    create_database()
    generate_sample_data()