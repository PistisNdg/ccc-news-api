import sqlite3
import os
from dotenv import load_dotenv 

load_dotenv()

def get_connection():
    return sqlite3.connect("db_ccc.db")