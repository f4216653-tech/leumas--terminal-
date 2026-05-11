import os
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)

# Initialize Firebase - Ensure serviceAccountKey.json is in your root folder
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/login/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    id_token = data.get('idToken')
    
    try:
        decoded_token = auth.verify_id_token(id_token)
        email = decoded_token.get('email')
        
        # Admin recognition logic
        is_premium = False
        if email == "f4216653@gmail.com":
            is_premium = True
            
        return jsonify({
            "status": "success", 
            "is_premium": is_premium,
            "email": email
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 401

if __name__ == '__main__':
    app.run(debug=True)



        
      
