from flask import send_file
from flask import Flask, request, jsonify
from db import get_connection, init_db
import os
from dotenv import load_dotenv
from flask_cors import CORS
import time
from datetime import datetime, timedelta
import bcrypt
import smtplib
import random
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import pytz
import logging

load_dotenv()

app = Flask(__name__)
CORS(app)

# NOTE: scheduler will be initialised after we read APP_TIMEZONE and DB_URL

# Logging de base
logging.basicConfig(level=logging.INFO)

# Replace ZoneInfo usage with pytz
API_KEY=os.getenv("API_KEY")
EMAIL=os.getenv("EMAIL")
PASS=os.getenv("PASS")
# Fuseau horaire de l'application (défini dans .env). Par défaut UTC.
APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'UTC')
try:
    APP_TZ = pytz.timezone(APP_TIMEZONE)
except Exception:
    logging.exception(f"Fuseau horaire invalide '{APP_TIMEZONE}', utilisation de UTC")
    APP_TZ = pytz.timezone('UTC')

# Database URL pour SQLAlchemyJobStore (doit être défini dans .env)
DB_URL = os.getenv('DB_URL')

# Initialisation du scheduler avec persistance SQLAlchemyJobStore si DB_URL fournie
if DB_URL:
    try:
        jobstores = {'default': SQLAlchemyJobStore(url=DB_URL)}
        scheduler = BackgroundScheduler(jobstores=jobstores, timezone=APP_TZ)
        scheduler.start()
        logging.info(f"APScheduler initialisé avec jobstore SQLAlchemy ({DB_URL})")
    except Exception as e:
        logging.exception(f"Impossible d'initialiser SQLAlchemyJobStore, fallback en mémoire: {e}")
        scheduler = BackgroundScheduler(timezone=APP_TZ)
        scheduler.start()
else:
    logging.warning("DB_URL non fournie — APScheduler utilisera un jobstore en mémoire (non persistant)")
    scheduler = BackgroundScheduler(timezone=APP_TZ)
    scheduler.start()

def is_authorized(req):
    return req.headers.get("x-api-key")==API_KEY

##--Route Connexion--
@app.route("/login", methods=["POST"])
def login():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    data=request.get_json()
    username=data.get("username")
    motpass=data.get("motpass")

    conn=get_connection()
    cursor=conn.cursor()

    try:
        cursor.execute('SELECT nom, statut, motpasse FROM users WHERE username = %s OR email = %s', (username, username))
        user = cursor.fetchall()
        if user:
            for result in user:
                nom, statut, password = result
            if bcrypt.checkpw(motpass.encode('utf-8'), bytes(password)):
                return jsonify({
                    "user": nom,
                    "statut": statut}), 200
            else:
                return jsonify({'Erreur': 'Mot de passe invalide'}), 500
        else:
            return jsonify({'Erreur': 'Id invalide'}), 500
        
    except Exception as ex:
        return jsonify({"Erreur":ex}),500
    
##--Routes Users-----
@app.route("/add_user",methods=["POST"])
def add_user():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    data=request.get_json()
    userid=("User" + str(random.randint(100000, 999999)))
    nom=data.get("nom")
    prenom=data.get("prenom")
    sexe=data.get("sexe")
    email=data.get("email")
    username=data.get("username")
    statut=data.get("statut") if data.get("statut") else "Etudiant" 
    motpass=data.get("motpasse").encode('utf-8')
    password=bcrypt.hashpw(motpass,bcrypt.gensalt())

    conn=get_connection()
    cursor=conn.cursor()
    try:
        cursor.execute("SELECT username, email FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchall():
            return jsonify({'Erreur': 'Ce compte existe déjà'}), 500
        else:
            cursor.execute(
                """INSERT INTO users (userid, nom, prenom, sexe, email, username, motpasse, statut)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (userid, nom, prenom, sexe, email, username, password, statut)
            )
            cursor.close()
            conn.commit()
            conn.close()
        
            return jsonify("Success"), 200
    
    except Exception as ex:
        return jsonify({"Erreur":ex}),500

@app.route("/search_user", methods=["POST"])
def search_user():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    data = request.get_json()
    query = data.get("query")
    
    conn=get_connection()
    cursor=conn.cursor()

    sql = """
                SELECT userid, nom, prenom, sexe, email, username, statut
                FROM users
                WHERE LOWER(userid) LIKE %s
                    OR LOWER(nom) LIKE %s
                    OR LOWER(prenom) LIKE %s
                    OR LOWER(email) LIKE %s
                    OR LOWER(username) LIKE %s
                ORDER BY nom
            """
    q = f'%{query.lower()}%'
    try:
        cursor.execute(sql, (q, q, q, q, q))
        response = cursor.fetchall()
        conn.close()
        retour=[]
        
        for res in response:
            userid, nom, prenom, sexe, email, username, statut =res
            user=[userid, nom, prenom, sexe, email, username, statut]
            retour.append(user)

        return jsonify(retour), 200
    except Exception as ex:
        return jsonify({"Erreur":str(ex)}), 500
    
@app.route("/delete_user", methods=["POST"])
def delete_user():
    if not is_authorized:
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        userid = data.get("userid")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE userid = %s", (userid,))
        conn.commit()
        conn.close()
        return jsonify("success"),200
    
    except Exception as e:
        return jsonify({"Erreur": str(e)}), 500
############################################################--End User

##--Routes News
@app.route("/create_news", methods=["POST"])
def create_news():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    data=request.get_json()
    titre=data.get("titre")
    destinataire=data.get("destinataire")
    date_publication=data.get("date")
    importance=data.get("importance")
    contenu=data.get("contenu")
    date_redaction=time.strftime("%Y-%m-%d")
    newsid=("news"+str(random.randint(100000, 999999)))

    conn=get_connection()
    cursor=conn.cursor()

    try:
        cursor.execute(
                '''INSERT INTO news(
                    newsid, dateredaction, titreavantvalidation,
                    contenuavantvalidation, destinataire,
                    importance, datedepublication, 
                    statut, validateur, datevalidation,
                    titreapresvalidation, contenuapresvalidation,
                    motifinvalidation
                ) 
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    'En attente de validation', 'Inconnu', NULL,
                    'Vide', 'Vide', 'Vide'
                )''',
                (newsid, date_redaction, titre, contenu, 
                 destinataire, importance, date_publication)
            )
        cursor.close()
        conn.commit()
        conn.close()
        
        return jsonify("Success"),200
    except Exception as e:
        return jsonify ({"Erreur":e}),500
    
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


def send_and_mark_published(titre, contenu, newsid=None, destinataire=None, importance=None, date_publication=None):
    """Envoie les mails puis met à jour la news en base comme publiée.
    Cette fonction est appelée par le scheduler (ou par le fallback threading.Timer).
    """
    try:
        logging.info(f"Lancement de l'envoi de mails pour newsid={newsid}")
        envoie_mail_to_all(titre, contenu)

        if newsid:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    '''update news set
                        datevalidation=%s,
                        statut=%s,
                        datedepublication=%s,
                        titreapresvalidation=%s,
                        contenuapresvalidation=%s,
                        destinataire=%s,
                        importance=%s,
                        validateur=%s
                    where newsid=%s''',
                    (time.strftime("%Y-%m-%d"), "Publiée", date_publication, titre, contenu, destinataire,
                     importance, "Modérateur", newsid)
                )
                conn.commit()
                cursor.close()
                conn.close()
                logging.info(f"News {newsid} marquée comme Publiée après envoi")
            except Exception as e:
                logging.exception(f"Erreur lors de la mise à jour de la news {newsid}: {e}")
        return True
    except Exception as e:
        logging.exception(f"Erreur dans send_and_mark_published: {e}")
        return False

def programmer_envoi_mail(titre, contenu, date_envoi, newsid=None, destinataire=None, importance=None, date_publication=None):
    """Fonction pour programmer l'envoi des mails et la mise à jour de la news
    Les paramètres facultatifs permettent de mettre à jour la ligne news une fois l'envoi réalisé.
    """
    job_id = f"mail_job_{int(time.time())}"
    # Calculer le délai en secondes entre maintenant et la date d'envoi
    try:
        now = datetime.now(tz=APP_TZ)
    except Exception:
        now = datetime.now()

    try:
        # Ensure date_envoi is timezone-aware; if naive assume APP_TZ
        if date_envoi.tzinfo is None:
            date_envoi = date_envoi.replace(tzinfo=APP_TZ)
        delay = max(0, (date_envoi - now).total_seconds())
    except Exception:
        delay = 0

    try:
        # Essayer d'ajouter la tâche au scheduler APScheduler
        scheduler.add_job(
            func=send_and_mark_published,
            trigger='date',
            run_date=date_envoi,
            args=[titre, contenu, newsid, destinataire, importance, date_publication],
            id=job_id,
            replace_existing=True,
        )
        logging.info(f"Scheduled email job {job_id} at {date_envoi}")
    except Exception as e:
        # Si APScheduler échoue pour une raison quelconque, on utilise un fallback
        logging.exception(f"APScheduler failed to schedule job {job_id}, falling back to threading.Timer: {e}")
        try:
            import threading
            t = threading.Timer(delay, send_and_mark_published, args=[titre, contenu, newsid, destinataire, importance, date_publication])
            t.daemon = True
            t.start()
            logging.info(f"Fallback threading.Timer scheduled for job {job_id} in {delay} seconds")
        except Exception:
            logging.exception(f"Failed to schedule fallback timer for job {job_id}")

    # Retourner l'ID de la tâche (même si le fallback est utilisé)
    return job_id
            
@app.route("/validate_news", methods=["POST"])
def validate_news():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    data=request.get_json()
    titre=data.get("titre")
    destinataire=data.get("destinataire")
    date_publication=data.get("date")
    importance=data.get("importance")
    contenu=data.get("contenu")
    newsid=data.get("newsid")

    try:

        # Convertir la date de publication (interprétée dans le fuseau APP_TZ)
        date_pub_date = datetime.strptime(date_publication, "%Y-%m-%d").date()
        now_tz = datetime.now(tz=APP_TZ)

        # Si la date demandée est aujourd'hui (dans le fuseau APP_TZ), programmer dans 10 minutes
        if date_pub_date == now_tz.date():
            date_envoi = now_tz + timedelta(minutes=3)
            status = "Validée (Programmé)"
        else:
            # Pour une date future, programmer à 06:00 dans le fuseau APP_TZ
            date_envoi = datetime(date_pub_date.year, date_pub_date.month, date_pub_date.day, 6, 0, 0, tzinfo=APP_TZ)
            status = "Validée (Programmé)"

        # Programmer l'envoi des mails (on lui passe aussi l'id de la news pour mise à jour après envoi)
        job_id = programmer_envoi_mail(titre, contenu, date_envoi, newsid=newsid, destinataire=destinataire, importance=importance, date_publication=date_publication)

        return jsonify("Success"),200
    except Exception as e:
        return jsonify ({"Erreur":e}),500

@app.route("/get_news", methods=["GET"])
def get_news():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                newsid, dateredaction, titreavantvalidation, 
                contenuavantvalidation, destinataire, importance, 
                datedepublication, statut, validateur, 
                datevalidation, titreapresvalidation, 
                contenuapresvalidation, motifinvalidation
            FROM news WHERE statut='Publiée'
            ORDER BY dateredaction DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            (newsid, dateredaction, titreavantvalidation,
             contenuavantvalidation, destinataire, importance, 
             datedepublication, statut, validateur, datevalidation,
             titreapresvalidation, contenuapresvalidation, motifinvalidation) = row
            result.append({
                "newsid": newsid,
                "dateredaction": dateredaction.strftime('%d-%m-%Y') if dateredaction else None,
                "titreavantvalidation": titreavantvalidation,
                "contenuavantvalidation": contenuavantvalidation,
                "destinataire": destinataire,
                "importance": importance,
                "datedepublication": datedepublication.strftime('%Y-%m-%d') if datedepublication else None,
                "statut": statut,
                "validateur": validateur,
                "datevalidation": datevalidation.strftime('%Y-%m-%d') if datevalidation else None,
                "titreapresvalidation": titreapresvalidation,
                "contenuapresvalidation": contenuapresvalidation,
                "motifinvalidation": motifinvalidation
            })

        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"Erreur": str(ex)}), 500
    
@app.route("/moderation_news", methods=["GET"])
def moderation_news():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                newsid, dateredaction, titreavantvalidation, 
                contenuavantvalidation, destinataire, importance, 
                datedepublication, statut, validateur, 
                datevalidation, titreapresvalidation, 
                contenuapresvalidation, motifinvalidation
            FROM news
            ORDER BY dateredaction DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            (newsid, dateredaction, titreavantvalidation,
             contenuavantvalidation, destinataire, importance, 
             datedepublication, statut, validateur, datevalidation,
             titreapresvalidation, contenuapresvalidation, motifinvalidation) = row
            result.append({
                "newsid": newsid,
                "dateredaction": dateredaction.strftime('%d-%m-%Y') if dateredaction else None,
                "titreavantvalidation": titreavantvalidation,
                "contenuavantvalidation": contenuavantvalidation,
                "destinataire": destinataire,
                "importance": importance,
                "datedepublication": datedepublication.strftime('%Y-%m-%d') if datedepublication else None,
                "statut": statut,
                "validateur": validateur,
                "datevalidation": datevalidation.strftime('%Y-%m-%d') if datevalidation else None,
                "titreapresvalidation": titreapresvalidation,
                "contenuapresvalidation": contenuapresvalidation,
                "motifinvalidation": motifinvalidation
            })

        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"Erreur": str(ex)}), 500

@app.route('/scheduled_jobs', methods=['GET'])
def scheduled_jobs():
    """Retourne les jobs programmés (utile pour debug sur Render)."""
    try:
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'next_run_time': str(job.next_run_time),
                'func': str(job.func),
            })
        return jsonify(jobs), 200
    except Exception as e:
        logging.exception(f"Erreur en listant les jobs: {e}")
        return jsonify({'Erreur': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8181)