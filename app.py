from flask import send_file
from flask import Flask, request, jsonify
from db import get_connection
import os
import base64
from dotenv import load_dotenv
from flask_cors import CORS
import time
import bcrypt
import smtplib
import random

load_dotenv()

app=Flask(__name__)
CORS(app)


API_KEY=os.getenv("API_KEY")

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
        cursor.execute('SELECT nom,statut,motpasse FROM users WHERE username=? or email=?',[username, username,])
        user=cursor.fetchall()
        if user:
            for result in user:
                nom, statut, password = result
            if bcrypt.checkpw(motpass.encode('utf'),password):
                return jsonify({
                    "user":nom,
                    "statut":statut}),200
            else:
                return jsonify({'Erreur':'Mot de passe invalide'}),500
        else:
            return jsonify({'Erreur':'Id invalide'}),500
        
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
        cursor.execute("select username,email from users where username=? or email=?",[username,email,])
        if cursor.fetchall():
            return jsonify({'Erreur':'Ce compte existe déjà'}),500
        else:
            cursor.execute(
                "INSERT INTO users VALUES(?,?,?,?,?,?,?,?)",(
                userid,nom,prenom,sexe,email,username,password,statut)
            )
            cursor.close()
            conn.commit()
            conn.close()
        
            return jsonify("Success"),200
    
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
                WHERE LOWER(userid) LIKE ?
                    OR LOWER(nom) LIKE ?
                    OR LOWER(prenom) LIKE ?
                    OR LOWER(email) LIKE ?
                    OR LOWER(username) LIKE ?
                ORDER BY nom
            """
    q = (f'%{query}%').lower()
    try:
        cursor.execute(sql, (q, q, q, q, q,))
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
        cursor.execute("delete from users where userid=?",(userid,))
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
    date_redaction=time.strftime("%d-%m-%Y")
    newsid=("news"+str(random.randint(100000, 999999)))

    conn=get_connection()
    cursor=conn.cursor()

    try:
        cursor.execute(
                '''INSERT INTO news(
                                    newsid,dateredaction,titreavantvalidation,
                                    contenuavantvalidation,destinataire,
                                    importance,datedepublication) 
                    VALUES(?,?,?,?,?,?,?,?)''',
                    (newsid,date_redaction,titre,contenu,destinataire,importance,date_publication)
            )
        cursor.close()
        conn.commit()
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
        cursor.execute(
            "SELECT newsid, dateredaction, titreavantvalidation, contenuavantvalidation, destinataire, importance, datedepublication FROM news"
        )
        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            (newsid, dateredaction, titreavantvalidation,
             contenuavantvalidation, destinataire, importance, datedepublication) = row
            result.append({
                "newsid": newsid,
                "dateredaction": dateredaction,
                "titreavantvalidation": titreavantvalidation,
                "contenuavantvalidation": contenuavantvalidation,
                "destinataire": destinataire,
                "importance": importance,
                "datedepublication": datedepublication,
            })

        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"Erreur": str(ex)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8181)