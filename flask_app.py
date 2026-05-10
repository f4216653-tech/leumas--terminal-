import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_institutional_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///terminal.db'

# Initialize Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    token = data.get('idToken')
    try:
        # Verify the Google token with Firebase
        decoded_token = auth.verify_id_token(token)
        email = decoded_token['email']
        
        user = User.query.filter_by(email=email).first()
        if not user:
            # Auto-register new users
            user = User(username=email.split('@')[0], email=email)
            db.session.add(user)
            db.session.commit()
            
        login_user(user)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
      
