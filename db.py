import logging
import os
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
logging.basicConfig(level=logging.INFO)

def get_db_url():
    return os.getenv('DB_URL')

def get_connection():
    database_url = get_db_url()
    
    if not database_url:
        raise Exception("DATABASE_URL n'est pas définie dans les variables d'environnement")
    
    return psycopg2.connect(database_url)

def get_engine():
    return create_engine(get_db_url())
