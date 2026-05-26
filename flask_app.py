import hashlib
import hmac
import json
import requests
import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

app = Flask(__name__, template_folder='templates')
app.secret_key = "LEUMAS_ELITE_2026_KEY"

# ── API Keys (test mode) ──
FINNHUB_KEY      = "d8av7e9r01qk20sov2c0d8av7e9r01qk20sov2cg"
TWELVE_DATA_KEY  = "328e9cd1a74d423388a476242245196a"
NEWSDATA_KEY     = "pub_1874805f4b9b49918f2bcf483ccf0896"
NOW_API_KEY      = "6fb55841-e292-460a-929c-409fb2e38504"
IPN_SECRET       = "3bhjNVqO0QahhOvwvYbqfZPgJMeEzs9+"
PLAN_ID          = 1359323711
ADMIN_EMAILS     = ["f4216653@gmail.com"]

# Simple in-memory user store (replace with a database for production)
users = {}

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('index'))

    user = users.get(email)
    if not user or not user.get("paid"):
        return redirect(url_for('index'))

    role = user.get("role", "Premium")
    return render_template('dashboard.html', role=role, email=email)


@app.route('/subscription')
def subscription():
    return render_template('subscription.html')


# ─────────────────────────────────────────
# AUTH / PAYMENT
# ─────────────────────────────────────────

@app.route('/api/pay', methods=['POST'])
def create_payment():
    data = request.get_json(silent=True) or {}
    email_input = data.get('email', '').lower().strip()

    if not email_input:
        return jsonify({"error": "Email required"}), 400

    session['user_email'] = email_input

    # Admin bypass
    if email_input in ADMIN_EMAILS:
        users[email_input] = {"paid": True, "role": "admin"}
        return jsonify({"status": "success", "redirect": "/dashboard", "is_admin": True})

    # NOWPayments subscription
    url = "https://api.nowpayments.io/v1/subscriptions"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}
    payload = {
        "subscription_plan_id": PLAN_ID,
        "email": email_input,
        "order_description": email_input
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code != 200:
            return jsonify({"error": "Payment API failed", "details": res.text}), 500
        return jsonify(res.json())
    except Exception as e:
        return jsonify({"error": "Sync Error", "details": str(e)}), 500


# NOWPayments webhook
@app.route('/ipn', methods=['POST'])
def ipn():
    data = request.get_json(silent=True) or {}
    received_hmac = request.headers.get('x-nowpayments-sig')

    calculated_hmac = hmac.new(
        IPN_SECRET.encode(),
        json.dumps(data, separators=(',', ':')).encode(),
        hashlib.sha512
    ).hexdigest()

    if received_hmac != calculated_hmac:
        return "Invalid signature", 400

    if data.get("payment_status") == "finished":
        email = data.get("order_description")
        if email:
            users[email] = {"paid": True, "role": "Premium"}

    return "OK", 200


# ─────────────────────────────────────────
# MARKET DATA — Finnhub
# ─────────────────────────────────────────

FINNHUB_SYMBOLS = {
    # Crypto
    "BTC/USD":  ("crypto", "BINANCE:BTCUSDT"),
    "ETH/USD":  ("crypto", "BINANCE:ETHUSDT"),
    "SOL/USD":  ("crypto", "BINANCE:SOLUSDT"),
    "XRP/USD":  ("crypto", "BINANCE:XRPUSDT"),
    # Forex
    "EUR/USD":  ("forex",  "OANDA:EUR_USD"),
    "GBP/USD":  ("forex",  "OANDA:GBP_USD"),
    "USD/JPY":  ("forex",  "OANDA:USD_JPY"),
    "AUD/USD":  ("forex",  "OANDA:AUD_USD"),
    # Stocks
    "AAPL":     ("stock",  "AAPL"),
    "TSLA":     ("stock",  "TSLA"),
    "NVDA":     ("stock",  "NVDA"),
    "MSFT":     ("stock",  "MSFT"),
    # Commodities via ETF proxies
    "XAU/USD":  ("stock",  "GLD"),
    "XAG/USD":  ("stock",  "SLV"),
    "OIL":      ("stock",  "USO"),
}

def fetch_quote(symbol_type, finnhub_symbol):
    """Fetch a single quote from Finnhub."""
    try:
        if symbol_type == "crypto":
            url = f"https://finnhub.io/api/v1/crypto/candle?symbol={finnhub_symbol}&resolution=1&count=2&token={FINNHUB_KEY}"
            r = requests.get(url, timeout=6)
            d = r.json()
            if d.get("s") == "ok" and d.get("c"):
                price = d["c"][-1]
                prev  = d["c"][0]
                chg   = price - prev
                pct   = (chg / prev * 100) if prev else 0
                return {"price": price, "change": round(chg, 4), "pct": round(pct, 2)}

        else:  # stock or forex
            url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={FINNHUB_KEY}"
            r = requests.get(url, timeout=6)
            d = r.json()
            price = d.get("c", 0)
            prev  = d.get("pc", price)
            chg   = price - prev
            pct   = (chg / prev * 100) if prev else 0
            return {"price": price, "change": round(chg, 4), "pct": round(pct, 2)}

    except Exception:
        pass
    return {"price": 0, "change": 0, "pct": 0}


@app.route('/api/market-data')
def get_market_data():
    result = {}
    for label, (sym_type, finnhub_sym) in FINNHUB_SYMBOLS.items():
        result[label] = fetch_quote(sym_type, finnhub_sym)
    return jsonify(result)


# ─────────────────────────────────────────
# NEWS — Newsdata.io
# ─────────────────────────────────────────

@app.route('/api/news')
def get_news():
    category = request.args.get("category", "business")
    url = (
        f"https://newsdata.io/api/1/news"
        f"?apikey={NEWSDATA_KEY}"
        f"&category={category}"
        f"&language=en"
        f"&q=finance OR forex OR crypto OR stocks OR fed OR inflation"
    )
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        articles = data.get("results", [])[:12]
        cleaned = [
            {
                "title":       a.get("title", ""),
                "source":      a.get("source_id", ""),
                "published":   a.get("pubDate", ""),
                "link":        a.get("link", "#"),
                "description": a.get("description", ""),
            }
            for a in articles
        ]
        return jsonify({"articles": cleaned})
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500


# ─────────────────────────────────────────
# FINNHUB MARKET NEWS (backup / extra feed)
# ─────────────────────────────────────────

@app.route('/api/finnhub-news')
def get_finnhub_news():
    category = request.args.get("category", "general")  # general, forex, crypto, merger
    url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_KEY}"
    try:
        res = requests.get(url, timeout=8)
        items = res.json()[:10]
        cleaned = [
            {
                "title":    i.get("headline", ""),
                "source":   i.get("source", ""),
                "summary":  i.get("summary", ""),
                "link":     i.get("url", "#"),
                "time":     i.get("datetime", 0),
                "image":    i.get("image", ""),
            }
            for i in items
        ]
        return jsonify({"articles": cleaned})
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500


# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


        


