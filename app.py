from flask import Flask, jsonify, render_template
import os
import time
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# ======================
# ARIHANT LIVE FEED
# ======================
ARIHANT_URL = "https://bcast.arihantspot.com:7768/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/arihant"

_CACHE = {"ts": 0, "data": None}

def fetch_arihant_rates():
    """
    Returns dict, NEVER throws (so API never becomes 500).
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.arihantspot.in/",
            "Accept": "*/*",
        }
        r = requests.get(ARIHANT_URL, headers=headers, timeout=10)
        r.raise_for_status()

        root = ET.fromstring(r.text.strip())
        raw = {}
        last_symbol = None

        for node in root.iter():
            tag = (node.tag or "").lower()

            if tag.endswith("symbol"):
                last_symbol = (node.text or "").strip()

            if tag.endswith("rate") and last_symbol:
                val = (node.text or "").strip()
                try:
                    raw[last_symbol] = float(val)
                except:
                    pass

        return {
            "gold_999": raw.get("GOLD999"),
            "gold_995": raw.get("GOLD995"),
            "silver_999": raw.get("SILVER999"),
            "raw": raw,
            "error": None
        }

    except Exception as e:
        return {
            "gold_999": None,
            "gold_995": None,
            "silver_999": None,
            "raw": {},
            "error": str(e)
        }

def get_arihant_cached():
    # refresh every 5 seconds
    now = time.time()
    if _CACHE["data"] is None or (now - _CACHE["ts"] > 5):
        _CACHE["data"] = fetch_arihant_rates()
        _CACHE["ts"] = now
    return _CACHE["data"]

# ======================
# TABLE CONFIG
# ======================
SITES = ["Arihant", "Safari", "Mandev", "Auric", "Raksha", "RSBL", "dP GOLD"]

# For now: Arihant cost comes LIVE from GOLD999.
# Others can be static OR later we’ll fetch live from their APIs.
BASE_COST_BY_SITE = {
    "Arihant": None,      # LIVE (GOLD999)
    "Safari": 137933,
    "Mandev": 137933,
    "Auric": 137933,
    "Raksha": 137933,
    "RSBL": None,         # TODO: fetch live later
    "dP GOLD": 137933,
}

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

def safe_int(x):
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except:
        return None

def build_tables():
    ar = get_arihant_cached()
    ari_cost = ar.get("gold_999")  # base = GOLD999

    sell995_rows = []
    sell999_rows = []

    for site in SITES:
        cost = BASE_COST_BY_SITE.get(site)

        if site == "Arihant":
            cost = ari_cost

        # 995 table
        off995 = SELL_995_OFFSET.get(site)
        if cost is None or off995 is None:
            s995 = None
            d995 = None
        else:
            s995 = float(cost) + float(off995)
            d995 = s995 - float(cost)

        sell995_rows.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(s995),
            "diff": safe_int(d995),
        })

        # 999 table
        off999 = SELL_999_OFFSET.get(site)
        if cost is None or off999 is None:
            s999 = None
            d999 = None
        else:
            s999 = float(cost) + float(off999)
            d999 = s999 - float(cost)

        sell999_rows.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(s999),
            "diff": safe_int(d999),
        })

    return {
        "updatedAt": int(time.time()),
        "arihant": {
            "gold_999": ar.get("gold_999"),
            "gold_995": ar.get("gold_995"),
            "silver_999": ar.get("silver_999"),
            "error": ar.get("error")
        },
        "sell995": sell995_rows,
        "sell999": sell999_rows
    }

# ======================
# ROUTES
# ======================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def api_prices():
    return jsonify(build_tables())

@app.route("/debug/arihant")
def debug_arihant():
    return jsonify(get_arihant_cached())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # IMPORTANT for Render
    app.run(host="0.0.0.0", port=port)
