import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)

# Initialize Firebase Admin with your uploaded key
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

@app.route('/')
def home():
    # In a full version, check for session cookies here
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/login/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    id_token = data.get('idToken')
    
    try:
        # Verifies the token sent from the browser
        decoded_token = auth.verify_id_token(id_token)
        email = decoded_token.get('email')
        
        # Success: Redirect logic happens in the frontend
        return jsonify({"status": "success", "email": email}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 401

if __name__ == '__main__':
    app.run(debug=True)



        
      
