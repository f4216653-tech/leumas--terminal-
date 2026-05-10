import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
app.config['SECRET_KEY'] = 'institutional_access_only_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leumas_terminal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 1. Initialize Firebase Master Key
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Firebase Init Error: {e}")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 2. Secure User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CORE ROUTES ---

@app.route('/')
@login_required
def dashboard():
    # This is the "Secure Area"
    return render_template('dashboard.html', user=current_user)

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    token = data.get('idToken')
    try:
        # Secure Handshake with Google/Firebase
        decoded_token = auth.verify_id_token(token)
        email = decoded_token['email']
        
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, username=email.split('@')[0])
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
        
      
