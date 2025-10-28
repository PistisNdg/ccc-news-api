import os
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_db_url():
    # En développement, utilisez les variables d'environnement locales
    # En production sur Render, utilisez l'URL de la base de données fournie
    return os.getenv('DB_URL')

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Création de la table users si elle n'existe pas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            userid TEXT PRIMARY KEY,
            nom TEXT,
            prenom TEXT,
            sexe TEXT,
            email TEXT UNIQUE,
            username TEXT UNIQUE,
            motpasse BYTEA,
            statut TEXT
        )
    ''')
    
    # Création de la table news si elle n'existe pas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            newsid TEXT NOT NULL PRIMARY KEY,
            dateredaction DATE,
            titreavantvalidation TEXT NOT NULL,
            contenuavantvalidation TEXT NOT NULL,
            destinataire TEXT NOT NULL,
            importance TEXT NOT NULL,
            datedepublication DATE,
            statut TEXT NOT NULL DEFAULT 'En attente de validation',
            validateur TEXT NOT NULL DEFAULT 'Inconnu',
            datevalidation DATE DEFAULT NULL,
            titreapresvalidation TEXT NOT NULL DEFAULT 'Vide',
            contenuapresvalidation TEXT NOT NULL DEFAULT 'Vide',
            motifinvalidation TEXT NOT NULL DEFAULT 'Vide'
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

def get_connection():
    # Obtenir l'URL de la base de données
    database_url = get_db_url()
    
    if not database_url:
        raise Exception("DATABASE_URL n'est pas définie dans les variables d'environnement")
    
    return psycopg2.connect(database_url)

def get_engine():
    # Pour les opérations plus complexes nécessitant SQLAlchemy
    return create_engine(get_db_url())

init_db()