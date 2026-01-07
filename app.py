from flask import Flask, jsonify, render_template
import time
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# ======================
# 1) ARIHANT LIVE FEED
# ======================
ARIHANT_URL = (
    "https://bcast.arihantspot.com:7768/"
    "VOTSBroadcastStreaming/Services/xml/"
    "GetLiveRateByTemplateID/arihant"
)

_ARIHANT_CACHE = {"ts": 0, "data": None}

def fetch_arihant_rates():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.arihantspot.in/",
        "Accept": "*/*",
    }

    r = requests.get(ARIHANT_URL, headers=headers, timeout=10)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    rates = {}

    last_symbol = None
    for node in root.iter():
        tag = (node.tag or "").lower()

        if tag.endswith("symbol"):
            last_symbol = (node.text or "").strip()

        if tag.endswith("rate") and last_symbol:
            try:
                rates[last_symbol] = float((node.text or "").strip())
            except:
                pass

    return {
        "gold_999": rates.get("GOLD999"),
        "gold_995": rates.get("GOLD995"),
        "silver_999": rates.get("SILVER999"),
    }

def get_arihant_cached():
    # cache 10 seconds
    if time.time() - _ARIHANT_CACHE["ts"] > 10:
        _ARIHANT_CACHE["data"] = fetch_arihant_rates()
        _ARIHANT_CACHE["ts"] = time.time()
    return _ARIHANT_CACHE["data"]


# ======================
# 2) YOUR MULTI-SITE TABLE SETUP
# ======================
SITES = ["Arihant", "Safari", "Mandev", "Auric", "Raksha", "RSBL", "dP GOLD"]

# Base cost (Arihant will be LIVE; others dummy for now)
BASE_COST_BY_SITE = {
    "Arihant": None,     # ✅ LIVE from Arihant API
    "Safari": 137933,
    "Mandev": 137933,
    "Auric": 137933,
    "Raksha": 137933,
    "RSBL": None,
    "dP GOLD": 137933,
}

# Offsets (same as your screenshot logic)
SELL_995_OFFSET = {
    "Arihant": -2100,
    "Safari": -2100,
    "Mandev": -2100,
    "Auric": -2100,
    "Raksha": -2050,
    "RSBL": None,
    "dP GOLD": None,
}

SELL_999_OFFSET = {
    "Arihant": -1500,
    "Safari": -1500,
    "Mandev": -1500,
    "Auric": None,
    "Raksha": -1375,
    "RSBL": None,
    "dP GOLD": -1455,
}

def build_tables():
    sell995 = []
    sell999 = []

    for site in SITES:
        cost = BASE_COST_BY_SITE.get(site)

        # ✅ STEP 3: Inject Arihant LIVE rate here
        if site == "Arihant":
            try:
                ar = get_arihant_cached()
                cost = ar["gold_999"]  # using GOLD999 as base cost
            except:
                cost = None

        # 995 table
        off995 = SELL_995_OFFSET.get(site)
        if cost is None or off995 is None:
            sell = None
            diff = None
        else:
            sell = cost + off995
            diff = sell - cost

        sell995.append({
            "site": site,
            "cost": int(cost) if cost is not None else None,
            "sell": int(sell) if sell is not None else None,
            "diff": int(diff) if diff is not None else None,
        })

        # 999 table
        off999 = SELL_999_OFFSET.get(site)
        if cost is None or off999 is None:
            sell2 = None
            diff2 = None
        else:
            sell2 = cost + off999
            diff2 = sell2 - cost

        sell999.append({
            "site": site,
            "cost": int(cost) if cost is not None else None,
            "sell": int(sell2) if sell2 is not None else None,
            "diff": int(diff2) if diff2 is not None else None,
        })

    return {
        "updatedAt": int(time.time()),
        "sell995": sell995,
        "sell999": sell999
    }


# ======================
# 3) ROUTES
# ======================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def api_prices():
    return jsonify(build_tables())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
