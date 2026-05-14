import hashlib
import hmac
import json
import requests
import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

app = Flask(__name__, template_folder='templates')
app.secret_key = "LEUMAS_ELITE_2026_KEY"

TWELVE_DATA_KEY = "328e9cd1a74d423388a476242245196a"
NOW_API_KEY = "6fb55841-e292-460a-929c-409fb2e38504"
IPN_SECRET = "3bhjNVqO0QahhOvwvYbqfZPgJMeEzs9+"
PLAN_ID = 1359323711
ADMIN_EMAILS = ["f4216653@gmail.com"]

# simple in-memory user tracker
users = {}

@app.route('/')
def index():
    return render_template('login.html')


@app.route('/api/pay', methods=['POST'])
def create_payment():
    data = request.get_json(silent=True) or {}
    email_input = data.get('email', '').lower().strip()

    if not email_input:
        return jsonify({"error": "Email required"}), 400

    session['user_email'] = email_input

    if email_input in ADMIN_EMAILS:
        users[email_input] = {"paid": True, "role": "admin"}
        return jsonify({"status": "success", "redirect": "/dashboard", "is_admin": True})

    url = "https://api.nowpayments.io/v1/subscriptions"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}
    payload = {
        "subscription_plan_id": PLAN_ID,
        "email": email_input,
        "order_description": email_input  # used later in IPN
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)

        if res.status_code != 200:
            return jsonify({"error": "Payment API failed", "details": res.text}), 500

        return jsonify(res.json())

    except Exception:
        return jsonify({"error": "Sync Error"}), 500


@app.route('/dashboard')
def dashboard():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('index'))

    user = users.get(email)

    # restrict access unless paid/admin
    if not user or not user.get("paid"):
        return redirect(url_for('index'))

    role = user.get("role", "Premium")
    return render_template('dashboard.html', role=role)


@app.route('/api/market-data')
def get_market_data():
    assets = "BTC/USD,ETH/USD,XAU/USD,XAG/USD,EUR/USD,GBP/USD,USD/JPY,TSLA,AAPL,NVDA"
    url = f"https://api.twelvedata.com/price?symbol={assets}&apikey={TWELVE_DATA_KEY}"

    try:
        res = requests.get(url, timeout=10)
        return jsonify(res.json())
    except Exception:
        return jsonify({"error": "Market data failed"}), 500


# 🔥 NOWPAYMENTS IPN (Webhook for payment confirmation)
@app.route('/ipn', methods=['POST'])
def ipn():
    data = request.get_json(silent=True) or {}

    received_hmac = request.headers.get('x-nowpayments-sig')

    # generate signature
    calculated_hmac = hmac.new(
        IPN_SECRET.encode(),
        json.dumps(data, separators=(',', ':')).encode(),
        hashlib.sha512
    ).hexdigest()

    if received_hmac != calculated_hmac:
        return "Invalid signature", 400

    # payment success
    if data.get("payment_status") == "finished":
        email = data.get("order_description")

        if email:
            users[email] = {"paid": True, "role": "Premium"}

    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

        


