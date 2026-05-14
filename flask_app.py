import hashlib
import hmac
import json
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "LEUMAS_SUPER_SECRET_SESSION_KEY" # Needed for admin login session

# --- CREDENTIALS ---
TWELVE_DATA_KEY = "328e9cd1a74d423388a476242245196a"
NOW_API_KEY = "6fb55841-e292-460a-929c-409fb2e38504"
IPN_SECRET = "3bhjNVqO0QahhOvwvYbqfZPgJMeEzs9+"
PLAN_ID = 1359323711

# --- ADMIN RECOGNITION ---
ADMIN_EMAILS = ["your-email@gmail.com"] # REPLACE THIS with your actual email

# --- 10+ LIVE ASSETS ---
ASSETS = "BTC/USD,ETH/USD,XAU/USD,XAG/USD,EUR/USD,GBP/USD,USD/JPY,TSLA,AAPL,NVDA"

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/subscription')
def subscription():
    return render_template('subscription.html')

# Admin & Subscription Check for Dashboard
@app.route('/dashboard')
def dashboard():
    user_email = session.get('user_email')
    
    # 1. Check if user is an Admin (Fletcher/Sosu)
    if user_email in ADMIN_EMAILS:
        return render_template('dashboard.html', role="Admin")
    
    # 2. Add your logic here to check if a regular user has paid
    # For now, we will allow access if the session is active
    if user_email:
        return render_template('dashboard.html', role="Premium")
        
    return redirect(url_for('login'))

@app.route('/api/market-data')
def get_market_data():
    url = f"https://api.twelvedata.com/price?symbol={ASSETS}&apikey={TWELVE_DATA_KEY}"
    data = requests.get(url).json()
    return jsonify(data)

@app.route('/api/pay', methods=['POST'])
def create_payment():
    user_email = request.json.get('email')
    session['user_email'] = user_email # Store email in session
    
    # If it's Fletcher, don't create a real invoice, just redirect
    if user_email in ADMIN_EMAILS:
        return jsonify({"admin_bypass": True, "redirect": url_for('dashboard')})

    url = "https://api.nowpayments.io/v1/subscriptions"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}
    payload = {"subscription_plan_id": PLAN_ID, "email": user_email}
    res = requests.post(url, json=payload, headers=headers)
    return jsonify(res.json())

@app.route('/webhook', methods=['POST'])
def webhook():
    sig = request.headers.get('x-nowpayments-sig')
    data = request.get_data()
    sorted_data = json.dumps(json.loads(data), separators=(',', ':'), sort_keys=True)
    hmac_check = hmac.new(IPN_SECRET.encode(), sorted_data.encode(), hashlib.sha512).hexdigest()

    if hmac_check == sig:
        payload = request.json
        if payload.get('payment_status') == 'finished':
            # This is where your code "unlocks" the user permanently in a database
            print(f"Access Granted: {payload.get('customer_email')}")
        return "OK", 200
    return "Verify Failed", 401

if __name__ == "__main__":
    app.run()






        
      
