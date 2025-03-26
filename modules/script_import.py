# script_import.py
import json
import os
from db_integrator import DatabaseIntegrator

# Chemin vers votre base de données SQLite
DB_PATH = "C:/Users/baofr/Desktop/Workspace/MILAN_ticket/modules/fidelity_db.sqlite" 

# Chemin vers un fichier JSON de ticket
JSON_PATH = "data/json/receipt_20250323_123456.json"  

# Chemin vers l'image du ticket associé
IMAGE_PATH = "data/images/receipt_20250323_123456.jpg"

# Chargement des données du ticket
with open(JSON_PATH, 'r') as f:
    receipt_data = json.load(f)

# Intégration en base de données
db_integrator = DatabaseIntegrator(DB_PATH)
success, transaction_id, message = db_integrator.process_receipt_data(receipt_data, IMAGE_PATH)

if success:
    print(f"Données importées avec succès! Transaction ID: {transaction_id}")
else:
    print(f"Échec de l'importation: {message}")