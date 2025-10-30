from flask import Flask, request, jsonify
from db import get_connection
import os
from dotenv import load_dotenv
from flask_cors import CORS
import time
from datetime import datetime, timedelta
import bcrypt
import smtplib
import json
import random
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import logging
import threading

load_dotenv()

app = Flask(__name__)
CORS(app)

#NOTE: scheduler will be initialised after we read APP_TIMEZONE and DB_URL

# Logging de base
logging.basicConfig(level=logging.INFO)

# Replace ZoneInfo usage with pytz
API_KEY=os.getenv("API_KEY")
EMAIL=os.getenv("EMAIL")
PASS=os.getenv("PASS")

def is_authorized(req):
    return req.headers.get("x-api-key")==API_KEY

@app.route("/")
def home():
    return "Bienvenue sur l'API de gestion des news et des utilisateurs.", 200

@app.route("/init_accueil", methods=["GET"])
def init_accueil():
    if not is_authorized(request):
        return jsonify({"Erreur": "Unauthorized"}), 403
    
    conn=get_connection()
    cursor=conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM news WHERE statut='Validée (Programmé)' AND datedepublication=%s", (time.strftime("%Y-%m-%d"),))
        valid_count=cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM news WHERE statut='Publiée' AND datedepublication=%s", (time.strftime("%Y-%m-%d"),))
        news_count=cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM news WHERE statut='En attente de validation' AND datedepublication>=%s", (time.strftime("%Y-%m-%d"),))
        pending_count=cursor.fetchone()[0]

        conn.close()

        return jsonify({
            "valid_count": valid_count,
            "news_count": news_count,
            "pending_count": pending_count
        }),200
    except Exception as ex:
        return jsonify({"Erreur":str(ex)}),500
    
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

def send_notification(title, message):    
    firebase_service_account_json = os.getenv("FIREBASE_KEY")
    firebase_config = json.loads(firebase_service_account_json)
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)
    # Construire le message
    message = messaging.Message(
        notification=messaging.Notification(
            title='Nouvelle Annonce !',
            body="Découvrez les dernières nouveautés de notre application. C'est génial !",
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
        logging.info(f'Erreur lors de l\'envoi du message: {e}')
    
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
            subj = "Univ News : " + "Test"
            msg = f"Subject: {subj}\nContent-Type: text/plain; charset=utf-8\n\nPitié, faite que ça marche"
            s.sendmail(EMAIL, to_, msg.encode('utf-8'))
            logging.info(f"Mail envoyé à {to_}")

    except Exception as e:
        logging.info(f"Erreur d'envoi de mail : {str(e)}")
        return False
    
def verifier_et_envoyer():
    #logging.info("Démarrage du service de vérification des news")
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
                        #logging.info(f"Traitement de la news {newsid} pour publication")
                        if envoie_mail_to_all(titre, contenu):
                            send_notification(titre, contenu)
                            cursor.execute("UPDATE news SET statut='Publiée' WHERE newsid=%s", (newsid,))
                            conn.commit()
                            #logging.info(f"News {newsid} publiée avec succès")
                        else:
                            logging.error(f"Échec de l'envoi des notifications pour la news {newsid}")
                
            except Exception as e:
                logging.error(f"Erreur lors de la vérification des news: {str(e)}")
                if conn and not conn.closed:
                    conn.rollback()
            
            finally:
                if cursor:
                    cursor.close()
                if conn and not conn.closed:
                    conn.close()
                    
            # Attendre 5 minutes avant la prochaine vérification
            time.sleep(300)
            
        except Exception as e:
            logging.error(f"Erreur critique dans la boucle principale: {str(e)}")
            # En cas d'erreur critique, attendre 1 minute avant de réessayer
            time.sleep(60)
            
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
    
    commentaire=data.get("commentaire") if data.get("commentaire") else "Aucun"

    try:
        # Si la date demandée est aujourd'hui (dans le fuseau APP_TZ), programmer dans 10 minutes
        if commentaire=="Aucun":
            status = "Validée (Programmé)"
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
                (time.strftime("%Y-%m-%d"), status, date_publication, titre, contenu, destinataire,
                importance, "Modérateur", newsid)
            )
            firebase_service_account_json = os.getenv("FIREBASE_KEY")
            firebase_config = json.loads(firebase_service_account_json)
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
            # Construire le message
            message = messaging.Message(
                notification=messaging.Notification(
                    title='Nouvelle Annonce !',
                    body="Découvrez les dernières nouveautés de notre application. C'est génial !",
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
                logging.info(f'Erreur lors de l\'envoi du message: {e}')
            conn.commit()
            cursor.close()
            conn.close()
        else:
            status = "Invalidée"
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
                    validateur=%s,
                    motifinvalidation=%s
                where newsid=%s''',
                (time.strftime("%Y-%m-%d"), status, date_publication, titre, contenu, destinataire,
                importance, "Modérateur", commentaire, newsid)
            )

        conn.commit()
        cursor.close()
        conn.close()
        
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
        data=request.get_json()
        importance=data.get("importance") if data.get("importance") else "Faible"
        statut=data.get("statut") if data.get("statut") else "En attente de validation"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                newsid, dateredaction, titreavantvalidation, 
                contenuavantvalidation, destinataire, importance, 
                datedepublication, statut, validateur, 
                datevalidation, titreapresvalidation, 
                contenuapresvalidation, motifinvalidation
            FROM news WHERE importance=%s AND statut=%s
            ORDER BY dateredaction DESC
        """,(importance,statut,))
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8181)
