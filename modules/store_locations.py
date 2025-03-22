import pandas as pd
import sqlite3
import os

def update_store_locations(df):
    """
    Met à jour les coordonnées des points de vente dans la base de données 
    à partir des données du DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame contenant les données des points de vente
    
    Returns:
        dict: Statistiques de la mise à jour
    """
    # Colonnes potentielles pour la latitude et la longitude
    latitude_columns = ['latitude', 'lat', 'Latitude', 'Lat']
    longitude_columns = ['longitude', 'lon', 'Longitude', 'Lon']
    
    # Trouver les colonnes de latitude et longitude
    lat_col = None
    lon_col = None
    
    for col in latitude_columns:
        if col in df.columns:
            lat_col = col
            break
    
    for col in longitude_columns:
        if col in df.columns:
            lon_col = col
            break
    
    # Vérifier si les colonnes sont présentes
    if not (lat_col and lon_col):
        print("Aucune colonne de latitude/longitude trouvée.")
        return {
            'success': False,
            'message': 'Colonnes de géolocalisation non trouvées'
        }
    
    # Colonnes à utiliser pour identifier les points de vente
    store_columns = ['nom', 'name', 'store_name', 'magasin', 'store']
    name_col = None
    
    for col in store_columns:
        if col in df.columns:
            name_col = col
            break
    
    # Préparer la connexion à la base de données
    db_path = 'modules/fidelity_db.sqlite'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Statistiques
    stats = {
        'total_stores': 0,
        'updated': 0,
        'failed': 0
    }
    
    try:
        # Parcourir les données et mettre à jour
        for _, row in df.iterrows():
            # Vérifier que les coordonnées sont valides
            if pd.isna(row[lat_col]) or pd.isna(row[lon_col]):
                continue
            
            # Nom du point de vente (optionnel)
            store_name = row[name_col] if name_col and not pd.isna(row.get(name_col)) else 'Non spécifié'
            
            try:
                # Mettre à jour la base de données
                cursor.execute("""
                    UPDATE points_vente 
                    SET latitude = ?, longitude = ?
                    WHERE nom = ? OR nom LIKE ?
                """, (
                    float(row[lat_col]), 
                    float(row[lon_col]), 
                    store_name,
                    f"%{store_name}%"
                ))
                
                # Vérifier si une mise à jour a eu lieu
                if cursor.rowcount > 0:
                    stats['updated'] += 1
                
                stats['total_stores'] += 1
            
            except Exception as e:
                print(f"Erreur lors de la mise à jour de {store_name}: {e}")
                stats['failed'] += 1
        
        # Valider les modifications
        conn.commit()
        
        return {
            'success': True,
            'stats': stats
        }
    
    except Exception as e:
        print(f"Erreur lors de la mise à jour des localisations : {e}")
        return {
            'success': False,
            'message': str(e)
        }
    
    finally:
        # Fermer la connexion
        conn.close()

def verify_store_locations():
    """
    Vérifie les coordonnées des points de vente dans la base de données
    
    Returns:
        dict: Statistiques des localisations
    """
    db_path = 'modules/fidelity_db.sqlite'
    conn = sqlite3.connect(db_path)
    
    try:
        cursor = conn.cursor()
        
        # Compter le nombre total de points de vente
        cursor.execute("SELECT COUNT(*) FROM points_vente")
        total_stores = cursor.fetchone()[0]
        
        # Compter les points de vente avec coordonnées
        cursor.execute("""
            SELECT COUNT(*) 
            FROM points_vente 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
        """)
        stores_with_location = cursor.fetchone()[0]
        
        return {
            'total_stores': total_stores,
            'stores_with_location': stores_with_location,
            'stores_without_location': total_stores - stores_with_location
        }
    
    finally:
        conn.close()

def main():
    """
    Fonction principale pour tester la mise à jour des localisations
    """
    # Charger un exemple de DataFrame (à adapter selon votre source de données)
    # Vous devrez remplacer cette partie par le chargement de votre DataFrame
    example_df = pd.DataFrame([
        {'nom': 'Boutique Paris', 'latitude': 48.8566, 'longitude': 2.3522},
        {'nom': 'Boutique Lyon', 'latitude': 45.7640, 'longitude': 4.8357},
        # Ajoutez d'autres points de vente
    ])
    
    # Vérifier l'état initial
    initial_verification = verify_store_locations()
    print("Vérification initiale :")
    print(f"Total de points de vente : {initial_verification['total_stores']}")
    print(f"Points de vente géolocalisés : {initial_verification['stores_with_location']}")
    
    # Mettre à jour les localisations
    update_result = update_store_locations(example_df)
    
    if update_result['success']:
        stats = update_result['stats']
        print("\nRésultats de la mise à jour :")
        print(f"Total de points de vente traités : {stats['total_stores']}")
        print(f"Points de vente mis à jour : {stats['updated']}")
        print(f"Échecs de mise à jour : {stats['failed']}")
        
        # Vérification finale
        final_verification = verify_store_locations()
        print("\nVérification finale :")
        print(f"Points de vente géolocalisés : {final_verification['stores_with_location']}")
    else:
        print("Échec de la mise à jour :", update_result.get('message', 'Erreur inconnue'))

if __name__ == "__main__":
    main()