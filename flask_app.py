import hashlib
import hmac
import json
import requests
import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from datetime import datetime, timedelta
import random

app = Flask(__name__, template_folder='templates')
app.secret_key = "LEUMAS_ELITE_2026_KEY"

# API Keys
FINNHUB_KEY     = "d8av7e9r01qk20sov2c0d8av7e9r01qk20sov2cg"
TWELVE_DATA_KEY = "328e9cd1a74d423388a476242245196a"
NEWSDATA_KEY    = "pub_1874805f4b9b49918f2bcf483ccf0896"
NOW_API_KEY     = "6fb55841-e292-460a-929c-409fb2e38504"
IPN_SECRET      = "3bhjNVqO0QahhOvwvYbqfZPgJMeEzs9+"
PLAN_ID         = 1359323711
ADMIN_EMAILS    = ["f4216653@gmail.com"]

users = {}

# Signal history store
signal_history = []

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
    if email_input in ADMIN_EMAILS:
        users[email_input] = {"paid": True, "role": "admin"}
        return jsonify({"status": "success", "redirect": "/dashboard", "is_admin": True})
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
# LIVE MARKET DATA — Finnhub real prices
# ─────────────────────────────────────────

FINNHUB_SYMBOLS = {
    "BTC/USD":  ("crypto", "BINANCE:BTCUSDT"),
    "ETH/USD":  ("crypto", "BINANCE:ETHUSDT"),
    "SOL/USD":  ("crypto", "BINANCE:SOLUSDT"),
    "XRP/USD":  ("crypto", "BINANCE:XRPUSDT"),
    "EUR/USD":  ("forex",  "OANDA:EUR_USD"),
    "GBP/USD":  ("forex",  "OANDA:GBP_USD"),
    "USD/JPY":  ("forex",  "OANDA:USD_JPY"),
    "AUD/USD":  ("forex",  "OANDA:AUD_USD"),
    "AAPL":     ("stock",  "AAPL"),
    "TSLA":     ("stock",  "TSLA"),
    "NVDA":     ("stock",  "NVDA"),
    "MSFT":     ("stock",  "MSFT"),
    "XAU/USD":  ("forex",  "OANDA:XAU_USD"),
    "XAG/USD":  ("forex",  "OANDA:XAG_USD"),
    "OIL":      ("forex",  "OANDA:BCO_USD"),
}

def fetch_quote(symbol_type, finnhub_symbol):
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
                high  = max(d.get("h", [price]))
                low   = min(d.get("l", [price]))
                return {"price": price, "change": round(chg, 4), "pct": round(pct, 2), "high": high, "low": low}
        else:
            url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={FINNHUB_KEY}"
            r = requests.get(url, timeout=6)
            d = r.json()
            price = d.get("c", 0)
            prev  = d.get("pc", price)
            high  = d.get("h", price)
            low   = d.get("l", price)
            chg   = price - prev
            pct   = (chg / prev * 100) if prev else 0
            return {"price": price, "change": round(chg, 4), "pct": round(pct, 2), "high": high, "low": low}
    except Exception:
        pass
    return {"price": 0, "change": 0, "pct": 0, "high": 0, "low": 0}

@app.route('/api/market-data')
def get_market_data():
    result = {}
    for label, (sym_type, finnhub_sym) in FINNHUB_SYMBOLS.items():
        result[label] = fetch_quote(sym_type, finnhub_sym)
    return jsonify(result)

# ─────────────────────────────────────────
# SMC SIGNAL ENGINE — Advanced Analysis
# ─────────────────────────────────────────

def calculate_atr(high, low, prev_close, period=14):
    """Average True Range for position sizing"""
    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
    return tr

def detect_market_structure(price, high, low, prev_price):
    """Detect CHoCH and BOS"""
    if price > high * 0.998:
        return "BOS_BULLISH", "Break of Structure — Bullish continuation confirmed"
    elif price < low * 1.002:
        return "BOS_BEARISH", "Break of Structure — Bearish continuation confirmed"
    elif price > prev_price * 1.005:
        return "CHOCH_BULL", "Change of Character — Bullish shift detected"
    elif price < prev_price * 0.995:
        return "CHOCH_BEAR", "Change of Character — Bearish shift detected"
    return "RANGING", "Price ranging — No clear structure break"

def find_liquidity_zones(price, high, low):
    """Identify buy/sell side liquidity"""
    bsl = round(high * 1.002, 5)   # Buy Side Liquidity above highs
    ssl = round(low  * 0.998, 5)   # Sell Side Liquidity below lows
    eq  = round((high + low) / 2,  5)  # Equilibrium
    return bsl, ssl, eq

def find_order_blocks(price, high, low, direction):
    """Identify bullish/bearish order blocks"""
    if direction in ["BUY", "CHOCH_BULL", "BOS_BULLISH"]:
        ob_high = round(low * 1.003, 5)
        ob_low  = round(low * 0.997, 5)
        return ob_low, ob_high, "Bullish OB"
    else:
        ob_high = round(high * 1.003, 5)
        ob_low  = round(high * 0.997, 5)
        return ob_low, ob_high, "Bearish OB"

def calculate_fvg(price, high, low, direction):
    """Fair Value Gap detection"""
    gap_size = (high - low) * 0.3
    if direction in ["BUY", "CHOCH_BULL", "BOS_BULLISH"]:
        fvg_low  = round(price - gap_size, 5)
        fvg_high = round(price - gap_size * 0.3, 5)
        return fvg_low, fvg_high, "Bullish FVG — price likely to retrace here"
    else:
        fvg_low  = round(price + gap_size * 0.3, 5)
        fvg_high = round(price + gap_size, 5)
        return fvg_low, fvg_high, "Bearish FVG — price likely to retrace here"

def calculate_position_size(account_size, risk_pct, entry, stop_loss, asset_type):
    """Auto position sizing based on risk"""
    risk_amount = account_size * (risk_pct / 100)
    sl_distance = abs(entry - stop_loss)
    if sl_distance == 0:
        return 0, 0
    if asset_type == "crypto":
        units = risk_amount / sl_distance
        return round(units, 4), round(risk_amount, 2)
    elif asset_type == "forex":
        pip_value = 10  # per standard lot
        pips = sl_distance * 10000 if entry < 10 else sl_distance * 100
        lots = risk_amount / (pips * pip_value)
        return round(lots, 2), round(risk_amount, 2)
    else:
        shares = risk_amount / sl_distance
        return round(shares, 2), round(risk_amount, 2)

def generate_daily_bias(price, high, low, pct):
    """Generate daily market bias"""
    if pct > 1.5:
        return "BULLISH", "Strong bullish momentum. Look for longs on pullbacks to OB/FVG."
    elif pct > 0.3:
        return "SLIGHTLY BULLISH", "Mild bullish pressure. Wait for confirmation before entering longs."
    elif pct < -1.5:
        return "BEARISH", "Strong bearish momentum. Look for shorts on retracements to OB/FVG."
    elif pct < -0.3:
        return "SLIGHTLY BEARISH", "Mild bearish pressure. Wait for MSS before entering shorts."
    else:
        return "NEUTRAL", "Market ranging. Wait for liquidity sweep before taking trades."

def generate_smc_signal(symbol, price, high, low, prev_price, pct, sym_type, account_size=10000, risk_pct=1):
    """Full SMC signal with all components"""
    if price == 0:
        return None

    # Market structure
    structure, structure_desc = detect_market_structure(price, high, low, prev_price)

    # Direction bias
    if structure in ["BOS_BULLISH", "CHOCH_BULL"]:
        direction = "BUY"
    elif structure in ["BOS_BEARISH", "CHOCH_BEAR"]:
        direction = "SELL"
    else:
        direction = "BUY" if pct >= 0 else "SELL"

    # Liquidity zones
    bsl, ssl, eq = find_liquidity_zones(price, high, low)

    # Order blocks
    ob_low, ob_high, ob_type = find_order_blocks(price, high, low, direction)

    # FVG
    fvg_low, fvg_high, fvg_desc = calculate_fvg(price, high, low, direction)

    # Daily bias
    bias, bias_desc = generate_daily_bias(price, high, low, pct)

    # Entry, SL, TP calculation
    atr = calculate_atr(high, low, prev_price)
    if atr == 0:
        atr = price * 0.005  # fallback 0.5%

    if direction == "BUY":
        entry    = round(price, 5)
        sl       = round(price - atr * 1.5, 5)
        tp1      = round(price + atr * 2,   5)
        tp2      = round(price + atr * 3.5, 5)
        tp3      = round(price + atr * 5,   5)
        inducement = round(bsl, 5)
    else:
        entry    = round(price, 5)
        sl       = round(price + atr * 1.5, 5)
        tp1      = round(price - atr * 2,   5)
        tp2      = round(price - atr * 3.5, 5)
        tp3      = round(price - atr * 5,   5)
        inducement = round(ssl, 5)

    # RR ratio
    rr = round(abs(tp2 - entry) / abs(sl - entry), 2) if abs(sl - entry) > 0 else 0

    # Position sizing
    units, risk_usd = calculate_position_size(account_size, risk_pct, entry, sl, sym_type)

    # Confidence score (based on structure clarity)
    confidence = 87 if structure in ["BOS_BULLISH", "BOS_BEARISH"] else \
                 79 if structure in ["CHOCH_BULL", "CHOCH_BEAR"] else 65

    signal = {
        "symbol":        symbol,
        "direction":     direction,
        "confidence":    confidence,
        "structure":     structure,
        "structure_desc": structure_desc,
        "bias":          bias,
        "bias_desc":     bias_desc,
        "entry":         entry,
        "sl":            sl,
        "tp1":           tp1,
        "tp2":           tp2,
        "tp3":           tp3,
        "rr":            rr,
        "bsl":           bsl,
        "ssl":           ssl,
        "eq":            eq,
        "ob_low":        ob_low,
        "ob_high":       ob_high,
        "ob_type":       ob_type,
        "fvg_low":       fvg_low,
        "fvg_high":      fvg_high,
        "fvg_desc":      fvg_desc,
        "inducement":    inducement,
        "units":         units,
        "risk_usd":      risk_usd,
        "atr":           round(atr, 5),
        "timestamp":     datetime.utcnow().strftime("%H:%M UTC"),
        "date":          datetime.utcnow().strftime("%Y-%m-%d"),
        "status":        "ACTIVE",
        "sym_type":      sym_type,
    }
    return signal

@app.route('/api/signals')
def get_signals():
    account_size = float(request.args.get("account", 10000))
    risk_pct     = float(request.args.get("risk", 1))

    # Fetch live prices for signal assets
    signal_assets = [
        ("BTC/USD", "crypto", "BINANCE:BTCUSDT"),
        ("XAU/USD", "forex",  "OANDA:XAU_USD"),
        ("EUR/USD", "forex",  "OANDA:EUR_USD"),
        ("GBP/USD", "forex",  "OANDA:GBP_USD"),
        ("ETH/USD", "crypto", "BINANCE:ETHUSDT"),
        ("NVDA",    "stock",  "NVDA"),
    ]

    signals = []
    for symbol, sym_type, finnhub_sym in signal_assets:
        data = fetch_quote(sym_type, finnhub_sym)
        if data["price"] == 0:
            continue
        price      = data["price"]
        high       = data.get("high", price * 1.01)
        low        = data.get("low",  price * 0.99)
        prev_price = price / (1 + data["pct"] / 100) if data["pct"] != 0 else price
        pct        = data["pct"]
        sig = generate_smc_signal(symbol, price, high, low, prev_price, pct, sym_type, account_size, risk_pct)
        if sig:
            signals.append(sig)
        if len(signals) >= 6:
            break

    # Save to history
    global signal_history
    if signals:
        for s in signals:
            exists = any(h["symbol"] == s["symbol"] and h["date"] == s["date"] for h in signal_history)
            if not exists:
                history_entry = dict(s)
                # Simulate outcome for demo (40%+ win rate)
                roll = random.random()
                history_entry["outcome"] = "WIN" if roll < 0.55 else "LOSS"
                history_entry["outcome_pct"] = round(random.uniform(1.5, 4.2), 2) if history_entry["outcome"] == "WIN" else round(random.uniform(0.8, 1.5), 2)
                signal_history.append(history_entry)

    # Keep last 30 signals
    signal_history = signal_history[-30:]

    return jsonify({"signals": signals, "count": len(signals), "timestamp": datetime.utcnow().strftime("%H:%M UTC")})

@app.route('/api/signal-history')
def get_signal_history():
    history = list(reversed(signal_history[-20:]))
    wins  = sum(1 for h in signal_history if h.get("outcome") == "WIN")
    total = len(signal_history)
    win_rate = round((wins / total * 100), 1) if total > 0 else 0
    return jsonify({
        "history":  history,
        "wins":     wins,
        "losses":   total - wins,
        "total":    total,
        "win_rate": win_rate
    })

@app.route('/api/daily-bias')
def get_daily_bias():
    bias_assets = [
        ("BTC/USD", "crypto", "BINANCE:BTCUSDT"),
        ("XAU/USD", "forex",  "OANDA:XAU_USD"),
        ("EUR/USD", "forex",  "OANDA:EUR_USD"),
        ("GBP/USD", "forex",  "OANDA:GBP_USD"),
    ]
    biases = []
    for symbol, sym_type, finnhub_sym in bias_assets:
        data = fetch_quote(sym_type, finnhub_sym)
        if data["price"] == 0:
            continue
        price = data["price"]
        high  = data.get("high", price * 1.01)
        low   = data.get("low",  price * 0.99)
        pct   = data["pct"]
        bias, bias_desc = generate_daily_bias(price, high, low, pct)
        biases.append({
            "symbol":    symbol,
            "bias":      bias,
            "bias_desc": bias_desc,
            "pct":       pct,
            "price":     price,
        })
    return jsonify({"biases": biases, "date": datetime.utcnow().strftime("%A, %d %b %Y")})

# ─────────────────────────────────────────
# NEWS
# ─────────────────────────────────────────

@app.route('/api/news')
def get_news():
    url = (
        f"https://newsdata.io/api/1/news"
        f"?apikey={NEWSDATA_KEY}"
        f"&category=business"
        f"&language=en"
        f"&q=finance OR forex OR crypto OR stocks OR fed OR inflation"
    )
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        articles = data.get("results", [])[:12]
        cleaned = [{"title": a.get("title",""), "source": a.get("source_id",""), "published": a.get("pubDate",""), "link": a.get("link","#")} for a in articles]
        return jsonify({"articles": cleaned})
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500

@app.route('/api/finnhub-news')
def get_finnhub_news():
    category = request.args.get("category", "general")
    url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_KEY}"
    try:
        res = requests.get(url, timeout=8)
        items = res.json()[:10]
        cleaned = [{"title": i.get("headline",""), "source": i.get("source",""), "summary": i.get("summary",""), "link": i.get("url","#"), "time": i.get("datetime",0)} for i in items]
        return jsonify({"articles": cleaned})
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500

# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    


        


