import hashlib
import hmac
import json
import requests
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "LEUMAS_ELITE_2026_KEY" # High-security session key

# --- INTEGRATED CREDENTIALS ---
TWELVE_DATA_KEY = "328e9cd1a74d423388a476242245196a"
NOW_API_KEY = "6fb55841-e292-460a-929c-409fb2e38504"
IPN_SECRET = "3bhjNVqO0QahhOvwvYbqfZPgJMeEzs9+"
PLAN_ID = 1359323711

# --- ADMIN RECOGNITION (FLETCHER / SOSU) ---
ADMIN_EMAILS = ["f4216653@gmail.com"]

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/api/pay', methods=['POST'])
def create_payment():
    email_input = request.json.get('email', '').lower().strip()
    session['user_email'] = email_input
    
    # ADMIN BYPASS: Instant redirect for your Gmail
    if email_input in ADMIN_EMAILS:
        return jsonify({"status": "success", "redirect": "/dashboard", "is_admin": True})

    # NOWPayments Subscription Flow for Customers
    url = "https://api.nowpayments.io/v1/subscriptions"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}
    payload = {"subscription_plan_id": PLAN_ID, "email": email_input}
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        return jsonify(res.json()) 
    except Exception as e:
        return jsonify({"error": "Gateway Timeout"}), 500

@app.route('/dashboard')
def dashboard():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    
    role = "Admin" if email in ADMIN_EMAILS else "Premium"
    return render_template('dashboard.html', role=role)

@app.route('/api/market-data')
def get_market_data():
    # Elite Terminal Asset Selection (10 Assets: Crypto, Forex, Tech)
    assets = "BTC/USD,ETH/USD,XAU/USD,XAG/USD,EUR/USD,GBP/USD,USD/JPY,TSLA,AAPL,NVDA"
    url = f"https://api.twelvedata.com/price?symbol={assets}&apikey={TWELVE_DATA_KEY}"
    return jsonify(requests.get(url).json())

@app.route('/webhook', methods=['POST'])
def webhook():
    sig = request.headers.get('x-nowpayments-sig')
    data = request.get_data()
    sorted_data = json.dumps(json.loads(data), separators=(',', ':'), sort_keys=True)
    hmac_check = hmac.new(IPN_SECRET.encode(), sorted_data.encode(), hashlib.sha512).hexdigest()

    if hmac_check == sig:
        payload = request.json
        if payload.get('payment_status') == 'finished':
            print(f"PAYMENT CONFIRMED: {payload.get('customer_email')}")
        return "OK", 200
    return "Verification Failed", 401

if __name__ == "__main__":
    app.run(debug=True)

