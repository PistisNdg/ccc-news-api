import os
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_db_url():
    # En développement, utilisez les variables d'environnement locales
    # En production sur Render, utilisez l'URL de la base de données fournie
    return os.getenv('DB_URL')

def get_connection():
    # Obtenir l'URL de la base de données
    database_url = get_db_url()
    
    if not database_url:
        raise Exception("DATABASE_URL n'est pas définie dans les variables d'environnement")
    
    return psycopg2.connect(database_url)

def get_engine():
    # Pour les opérations plus complexes nécessitant SQLAlchemy
    return create_engine(get_db_url())
