import os
import requests
from flask import Flask, render_template_string, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'leumas_institutional_key_2026')
# For Render's free tier, we use SQLite. Note: Data resets on redeploy unless using Render Postgres.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ASSETS & API ---
NEWS_API_KEY = "e4045aaaa3594ca5bbcd67908e19e450"
# Current Test Link - Update to Live URL once Lemon Squeezy approves your store
CHECKOUT_URL = "https://leumas-institutional.lemonsqueezy.com/checkout/buy/eb356f78-8db1-45b9-8aed-6b857cdebef0"

market_data = {
    "XAUUSD": {"name": "Gold", "query": "Gold price Federal Reserve", "bias": "BULLISH", "levels": "2310.50 - 2315.00"},
    "BTCUSD": {"name": "Bitcoin", "query": "Bitcoin price BTC", "bias": "BEARISH", "levels": "62,400 - 63,100"},
    "USDJPY": {"name": "USD/JPY", "query": "USD JPY Bank of Japan", "bias": "NEUTRAL", "levels": "148.20 - 149.00"},
    "GBPUSD": {"name": "GBP/USD", "query": "Pound Sterling BOE", "bias": "BULLISH", "levels": "1.2540 - 1.2565"},
    "EURUSD": {"name": "EUR/USD", "query": "Euro price ECB", "bias": "BEARISH", "levels": "1.0720 - 1.0745"},
    "NAS100": {"name": "Nasdaq 100 Tech", "query": "Nasdaq 100 NDX", "bias": "BULLISH", "levels": "17850 - 17920"},
    "ETHUSD": {"name": "Ethereum", "query": "Ethereum price ETH", "bias": "NEUTRAL", "levels": "3120 - 3155"}
}

def get_live_news(query):
    try:
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=2&apiKey={NEWS_API_KEY}"
        r = requests.get(url).json()
        return r.get('articles', [])
    except:
        return []

# --- ROUTES ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=request.form['username'], password=hashed_pw)
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except:
            flash("User already exists!")
    return render_template_string('''
        <body style="background:#0b0e11;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
            <div style="background:#181a20;padding:30px;border-radius:12px;border:1px solid #2b2f36;width:300px;">
                <h2 style="margin-top:0;color:#fcd535;">Leumas Join</h2>
                <form method="POST">
                    <input name="username" placeholder="Username" required style="width:100%;background:#0b0e11;border:1px solid #2b2f36;color:white;padding:10px;margin-bottom:10px;border-radius:5px;">
                    <input name="password" type="password" placeholder="Password" required style="width:100%;background:#0b0e11;border:1px solid #2b2f36;color:white;padding:10px;margin-bottom:15px;border-radius:5px;">
                    <button type="submit" style="width:100%;background:#fcd535;padding:10px;border:none;border-radius:5px;font-weight:bold;color:black;">Sign Up</button>
                </form>
                <p style="font-size:11px;text-align:center;margin-top:15px;"><a href="/login" style="color:#848e9c;">Already have an account? Login</a></p>
            </div>
        </body>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        flash("Access Denied")
    return render_template_string('''
        <body style="background:#0b0e11;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
            <div style="background:#181a20;padding:30px;border-radius:12px;border:1px solid #2b2f36;width:300px;">
                <h2 style="margin-top:0;color:#fcd535;">Leumas Login</h2>
                <form method="POST">
                    <input name="username" placeholder="Username" required style="width:100%;background:#0b0e11;border:1px solid #2b2f36;color:white;padding:10px;margin-bottom:10px;border-radius:5px;">
                    <input name="password" type="password" placeholder="Password" required style="width:100%;background:#0b0e11;border:1px solid #2b2f36;color:white;padding:10px;margin-bottom:15px;border-radius:5px;">
                    <button type="submit" style="width:100%;background:#fcd535;padding:10px;border:none;border-radius:5px;font-weight:bold;color:black;">Login</button>
                </form>
                <p style="font-size:11px;text-align:center;margin-top:15px;"><a href="/signup" style="color:#848e9c;">New user? Create account</a></p>
            </div>
        </body>
    ''')

@app.route('/')
@login_required
def home():
    selected_symbol = request.args.get('asset', 'XAUUSD')
    asset = market_data.get(selected_symbol)
    news_items = get_live_news(asset['query'])
    
    now_hour = datetime.utcnow().hour
    is_london = "ACTIVE" if 7 <= now_hour <= 10 else "CLOSED"
    is_ny = "ACTIVE" if 13 <= now_hour <= 16 else "CLOSED"

    return render_template_string(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Leumas Terminal</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #0b0e11; color: #eaeaeb; padding: 15px; margin:0; }}
            .container {{ max-width: 500px; margin: auto; }}
            .nav-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }}
            .nav-item {{ background: #181a20; padding: 8px 2px; border-radius: 4px; text-decoration: none; color: #848e9c; border: 1px solid #2b2f36; font-size: 9px; font-weight: bold; text-align: center; }}
            .nav-item.active {{ border-color: #fcd535; color: #fcd535; }}
            .card {{ background: #181a20; border: 1px solid #2b2f36; padding: 15px; border-radius: 10px; margin-bottom: 10px; }}
            .killzone {{ display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 10px; }}
            .status {{ padding: 2px 5px; border-radius: 3px; }}
            .active-status {{ background: #00ff8822; color: #00ff88; }}
            .closed-status {{ background: #ff4d4d22; color: #ff4d4d; }}
            .blur {{ filter: blur(4px); opacity: 0.3; pointer-events: none; }}
            .btn {{ background: #fcd535; color: #000; padding: 12px; display: block; text-align: center; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 10px; }}
            .logout {{ font-size: 10px; color: #ff4d4d; text-decoration: none; float: right; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/logout" class="logout">Logout</a>
            <h4 style="margin: 0 0 15px 0;">Leumas Institutional</h4>

            <div class="killzone">
                <span>London: <b class="status {'active-status' if is_london=='ACTIVE' else 'closed-status'}">{is_london}</b></span>
                <span>New York: <b class="status {'active-status' if is_ny=='ACTIVE' else 'closed-status'}">{is_ny}</b></span>
            </div>

            <div class="nav-grid">
                {" ".join([f'<a href="/?asset={s}" class="nav-item {"active" if selected_symbol==s else ""}">{s}</a>' for s in market_data])}
            </div>

            <div class="card">
                <div style="font-size:10px; color:#848e9c;">{asset['name']} Directional Bias</div>
                <div style="font-size:18px; font-weight:bold; color: #00ff88; margin-top:5px;">{asset['bias']}</div>
                <div style="font-size:10px; color:#848e9c; margin-top:10px;">Institutional Liquidity Levels</div>
                <div style="font-size:14px; font-weight:bold; margin-top:3px;">{asset['levels']}</div>
            </div>

            <div class="card" style="border-color: #fcd535;">
                <div style="color:#fcd535; font-size:10px; font-weight:bold;">ALGO EXECUTION ENGINE</div>
                <div class="blur">
                    <p style="font-size:12px;"><b>Trade Setup:</b> SMC Order Block Mitigation</p>
                    <p style="font-size:12px;"><b>Risk/Reward:</b> 1:5 Targeted Ratio</p>
                </div>
                <a href="{CHECKOUT_URL}" class="btn">Unlock {selected_symbol} Intelligence</a>
            </div>

            <div class="card">
                <div style="font-size:10px; color:#848e9c; margin-bottom:10px;">Market Pulse</div>
                {"".join([f'<div style="font-size:11px; margin-bottom:8px; border-bottom:1px solid #2b2f36; padding-bottom:5px;"><b>{n["source"]["name"]}</b>: {n["title"][:70]}...</div>' for n in news_items]) if news_items else '<div>Scanning institutional feeds...</div>'}
            </div>
        </div>
    </body>
    </html>
    """, selected_symbol=selected_symbol, is_london=is_london, is_ny=is_ny)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# Gunicorn expects 'app' as the entry point
application = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
