import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def print_table_info(cursor, table_name):
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
    print(f"\nColonnes de la table {table_name}:")
    for desc in cursor.description:
        print(f"- {desc[0]}")

from datetime import datetime

def convert_date(date_str):
    if not date_str or date_str == 'Vide':
        return None
    try:
        # Convertir de 'DD-MM-YYYY' à 'YYYY-MM-DD'
        date_obj = datetime.strptime(date_str, '%d-%m-%Y')
        return date_obj.strftime('%Y-%m-%d')
    except:
        return None

def migrate_data():
    # Connexion à SQLite
    sqlite_conn = sqlite3.connect('db_ccc.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connexion à PostgreSQL
    pg_conn = psycopg2.connect(os.getenv('DB_URL'))
    pg_cursor = pg_conn.cursor()
    
    # Configurer le style de date PostgreSQL
    pg_cursor.execute("SET datestyle TO 'ISO, YMD'")
    
    # Afficher la structure des tables
    print("\nStructure SQLite:")
    print_table_info(sqlite_cursor, 'news')
    
    print("\nStructure PostgreSQL:")
    print_table_info(pg_cursor, 'news')
    
    try:
        # Migration des utilisateurs
        sqlite_cursor.execute('SELECT * FROM users')
        users = sqlite_cursor.fetchall()
        
        for user in users:
            pg_cursor.execute('''
                INSERT INTO users (userid, nom, prenom, sexe, email, username, motpasse, statut)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (userid) DO NOTHING
            ''', user)
        
        # Migration des news
        sqlite_cursor.execute('SELECT * FROM news')
        news = sqlite_cursor.fetchall()
        
        for news_item in news:
            # Convertir les dates dans le bon format
            news_data = list(news_item)  # Convertir le tuple en liste pour pouvoir modifier les valeurs
            news_data[1] = convert_date(news_data[1])  # dateredaction
            news_data[6] = convert_date(news_data[6])  # datedepublication
            if len(news_data) > 9:  # Si datevalidation existe
                news_data[9] = convert_date(news_data[9])  # datevalidation
            
            pg_cursor.execute('''
                INSERT INTO news (
                    newsid, dateredaction, titreavantvalidation, contenuavantvalidation,
                    destinataire, importance, datedepublication, statut, validateur,
                    datevalidation, titreapresvalidation, contenuapresvalidation, motifinvalidation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (newsid) DO NOTHING
            ''', tuple(news_data))
        
        pg_conn.commit()
        print("Migration réussie!")
        
    except Exception as e:
        pg_conn.rollback()
        print(f"Erreur lors de la migration: {e}")
        
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()

if __name__ == '__main__':
    migrate_data()