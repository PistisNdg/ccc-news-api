import threading
import time
import logging
import os
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import smtplib
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Replace ZoneInfo usage with pytz
API_KEY=os.getenv("API_KEY")
EMAIL=os.getenv("EMAIL")
PASS=os.getenv("PASS")

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

def send_notification(title, message):    
    firebase_service_account_json = os.getenv("FIREBASE_KEY")
    firebase_config = json.loads(firebase_service_account_json)
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)
    # Construire le message
    message = messaging.Message(
        notification=messaging.Notification(
            title='Nouvelle News !',
            body=title,
        ),
        # Le nom du sujet doit correspondre à celui auquel les clients s'abonnent
        topic='allUsers',
        # Vous pouvez ajouter des données personnalisées si nécessaire
    )

    # Envoyer le message
    try:
        response = messaging.send(message)
        logging.info('Message envoyé avec succès:', response)
    except Exception as e:
        logging.error(f'Erreur lors de l\'envoi du message: {e}')
    
def envoie_mail_to_all(titre, contenu):
    """Fonction pour envoyer des mails à tous les étudiants"""
    success_count = 0
    error_count = 0
    
    try:
        # Connexion à la base de données
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE statut='Etudiant'")
        rows = cursor.fetchall()
        conn.close()

        # Connexion au serveur SMTP
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(EMAIL, PASS)

        # Préparation du message
        subj = "Univ News : " + titre
        msg = f"Subject: {subj}\nContent-Type: text/plain; charset=utf-8\n\n{contenu}"
        encoded_msg = msg.encode('utf-8')

        # Envoi à chaque destinataire
        for row in rows:
            to_ = row[0]
            try:
                s.sendmail(EMAIL, to_, encoded_msg)
                logging.info(f"Mail envoyé avec succès à {to_}")
                success_count += 1
            except smtplib.SMTPRecipientsRefused:
                error_msg = f"Email invalide ou refusé : {to_}"
                logging.error(error_msg)
                error_count += 1
            except Exception as e:
                error_msg = f"Erreur lors de l'envoi à {to_} : {str(e)}"
                logging.error(error_msg)
                error_count += 1

        # Fermeture de la connexion SMTP
        s.quit()
        
        # Résumé des envois
        logging.info(f"Résumé des envois - Succès: {success_count}, Échecs: {error_count}")
        return success_count > 0  # Retourne True si au moins un email a été envoyé

    except Exception as e:
        error_msg = f"Erreur générale d'envoi de mail : {str(e)}"
        logging.error(error_msg)
        return False
    
def verifier_et_envoyer():
    #logging.info("Démarrage du service de vérification des news")
    while True:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                            SELECT newsid, datedepublication, titreapresvalidation, contenuapresvalidation 
                            FROM news 
                            WHERE statut='Validée (Programmé)'
            """)
            result = cursor.fetchall()
            current_date = str(time.strftime("%Y-%m-%d"))
            if result:
                for row in result:
                    newsid, date, titre, contenu = row
                    if str(date) == str(current_date):
                        cursor.execute("UPDATE news SET statut='Publiée' WHERE newsid=%s", (newsid,))
                        envoie_mail_to_all(titre, contenu)
                        send_notification(titre, contenu)
                        conn.commit()
                        time.sleep(60)
                #conn.close()
                    else:
                        pass
                        time.sleep(30)  # Attendre 5 minutes avant la prochaine vérification
                
            else:
                conn.close()
            time.sleep(30)  # Attendre 5 minutes avant la prochaine vérification
        except Exception as e:
            logging.error(f"Erreur dans le vérificateur de news : {str(e)}")

            #logging.info(f"News {newsid} publiée avec succès")


# Lancer le vérificateur en parallèle du serveur Flask
thread = threading.Thread(target=verifier_et_envoyer, daemon=False)
thread.start()
