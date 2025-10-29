from flask import send_file
from flask import Flask, request, jsonify
from db import get_connection, init_db
import os
import base64
from dotenv import load_dotenv
from flask_cors import CORS
import time
import bcrypt
import smtplib
import random

load_dotenv()

app = Flask(__name__)
CORS(app)

API_KEY=os.getenv("API_KEY")
EMAIL=os.getenv("EMAIL")
PASS=os.getenv("PASS")

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
    
def envoie_mail(to_,title,contenu):
        s=smtplib.SMTP("smtp.gmail.com",587)
        s.starttls()
        email_=EMAIL
        pass_=PASS
        s.login(email_,pass_)
        subj="Univ News : "+title
        msg=contenu
        msg="Subject:{}\n\n{}".format(subj,msg)
        s.sendmail(email_,to_,msg)
        chk=s.ehlo()
        if chk[0]==250:
            return 's'
        else:
            return 'f'
            
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

    conn=get_connection()
    cursor=conn.cursor()

    if date_publication!=time.strftime("%Y-%m-%d"):
        status="Validée (Programmé)"
    else:
        status="Publiée"
        cursor.execute("SELECT email FROM users WHERE statut='Etudiant'")
        rows=cursor.fetchall()
        for row in rows:
            to_=row[0]
            envoie_mail(to_,titre,contenu)
            
    try:
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
                (time.strftime("%Y-%m-%d"),status,date_publication, titre, contenu, destinataire,
                 importance, "Modérateur", newsid)
            )
        cursor.close()
        conn.commit()
        conn.close()
        
        return jsonify("Success"),200
    except Exception as e:
        return jsonify ({"Erreur":e}),500
    
    try:
        pass
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8181)