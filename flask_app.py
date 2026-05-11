import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
app.config['SECRET_KEY'] = 'leumas_terminal_private_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///terminal.db'

# Initialize Firebase with your uploaded key
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    is_premium = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def dashboard():
    # BYPASS LOGIC: If it's your email, skip the paywall.
    if current_user.email == "f4216653@gmail.com" or current_user.is_premium:
        return render_template('dashboard.html')
    return redirect(url_for('subscription'))

@app.route('/login/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    token = data.get('idToken')
    try:
        decoded_token = auth.verify_id_token(token)
        email = decoded_token['email']
        user = User.query.filter_by(email=email).first()
        
        # New users start non-premium unless it's you
        is_admin = (email == "f4216653@gmail.com")
        
        if not user:
            user = User(email=email, is_premium=is_admin)
            db.session.add(user)
            db.session.commit()
            
        login_user(user)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/subscription')
@login_required
def subscription(): return render_template('subscription.html')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)

        
      
