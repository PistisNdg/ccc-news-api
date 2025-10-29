
from db import get_connection
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import smtplib
from pyfcm import FCMNotification
import logging
import threading
from email.mime.text import MIMEText

load_dotenv()

#scheduler will be initialised after we read APP_TIMEZONE and DB_URL

# Logging de base
logging.basicConfig(level=logging.INFO)

# Replace ZoneInfo usage with pytz
API_KEY=os.getenv("API_KEY")
EMAIL=os.getenv("EMAIL")
PASS=os.getenv("PASS")
FCM_API_KEY="AIzaSyAGzgIONkH1yfvtn-6lRthaBKapv0KTTto"
push_service = FCMNotification(FCM_API_KEY)
user_tokens = []

def send_notification(title, message):    
    if not user_tokens:
        print({"Erreur": "No registered tokens"})
    
    try:
        result = push_service.notify_multiple_devices(
            registration_ids=user_tokens,
            message_title=title,
            message_body=message
        )
        print(result)
    except Exception as e:
        print({"Erreur": str(e)})
    
def envoie_mail_to_all(titre, contenu):
    """Fonction pour envoyer des mails à tous les étudiants"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE statut='Etudiant'")
        rows = cursor.fetchall()
        conn.close()

        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(EMAIL, PASS)

        for row in rows:
            to_ = row[0]
            subj = "Univ News : " + titre
            msg = "Subject:{}\n\n{}".format(subj, contenu)
            s.sendmail(EMAIL, to_, msg)

        s.quit()
        return True
    except Exception as e:
        print(f"Erreur d'envoi de mail : {str(e)}")
        return False
    
def verifier_et_envoyer():
    while True:
        try:
            conn = None
            cursor = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT newsid, datedepublication, titreapresvalidation, contenuapresvalidation 
                    FROM news 
                    WHERE statut='Validée (Programmé)'
                """)
                result = cursor.fetchall()
                
                current_date = time.strftime("%Y-%m-%d")
                for row in result:
                    newsid, date, titre, contenu = row
                    if date == current_date:
                        if envoie_mail_to_all(titre, contenu):
                            send_notification(titre, contenu)
                            cursor.execute("UPDATE news SET statut='Publiée' WHERE newsid=%s", (newsid,))
                            conn.commit()
                            print(f"News {newsid} publiée avec succès")
                        else:
                            print(f"Échec de l'envoi des notifications pour la news {newsid}")
                
            except Exception as e:
                print(f"Erreur lors de la vérification des news: {str(e)}")
                if conn and not conn.closed:
                    conn.rollback()
            
            finally:
                if cursor:
                    cursor.close()
                if conn and not conn.closed:
                    conn.close()
                    
            # Attendre 5 minutes avant la prochaine vérification
            time.sleep(100)
            
        except Exception as e:
            print(f"Erreur critique dans la boucle principale: {str(e)}")
            # En cas d'erreur critique, attendre 1 minute avant de réessayer
            time.sleep(60)

verifier_et_envoyer()