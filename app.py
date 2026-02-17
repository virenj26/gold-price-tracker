from flask import Flask, jsonify, render_template
import os
import time
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# -----------------
# HEALTH (for Render)
# -----------------
@app.get("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

# -----------------
# HOME
# -----------------
@app.get("/")
def home():
    return render_template("index.html")

# -----------------
# ARIHANT LIVE (AJAX first, XML fallback)
# -----------------
ARIHANT_AJAX_URL = "https://www.arihantspot.in/arihant"
ARIHANT_XML_URL = "https://bcast.arihantspot.com:7768/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/arihant"

CACHE = {"ts": 0, "data": None}
CACHE_SECONDS = 5

def safe_int(x):
    try:
        return None if x is None else int(round(float(x)))
    except:
        return None

def extract_last_number(line: str):
    toks = []
    for t in line.replace(",", " ").split():
        try:
            toks.append(float(t))
        except:
            pass
    return toks[-1] if toks else None

def fetch_arihant_ajax():
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.arihantspot.in/"}
    r = requests.get(ARIHANT_AJAX_URL, headers=headers, timeout=10)
    r.raise_for_status()

    gold999 = None
    gold995 = None

    for ln in r.text.splitlines():
        up = ln.upper()
        # GOLD 995 (1kg) -> take last number
        if "GOLD" in up and "995" in up and "(1KG" in up:
            v = extract_last_number(ln)
            if v is not None:
                gold995 = v

        # GOLD 999 (prefer WITH GST)
        if "GOLD" in up and "999" in up:
            if "WITH GST" in up:
                v = extract_last_number(ln)
                if v is not None:
                    gold999 = v
            elif gold999 is None:
                v = extract_last_number(ln)
                if v is not None:
                    gold999 = v

    return {"gold_999": gold999, "gold_995": gold995}

def fetch_arihant_xml():
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.arihantspot.in/"}
    r = requests.get(ARIHANT_XML_URL, headers=headers, timeout=10)
    r.raise_for_status()

    root = ET.fromstring(r.text.strip())
    raw = {}
    last_symbol = None

    for node in root.iter():
        tag = (node.tag or "").lower()
        if tag.endswith("symbol"):
            last_symbol = (node.text or "").strip()
        if tag.endswith("rate") and last_symbol:
            try:
                raw[last_symbol] = float((node.text or "").strip())
            except:
                pass

    return {"gold_999": raw.get("GOLD999"), "gold_995": raw.get("GOLD995")}

def get_arihant_cached():
    now = time.time()
    if CACHE["data"] and (now - CACHE["ts"] <= CACHE_SECONDS):
        return CACHE["data"]

    data = {"gold_999": None, "gold_995": None, "error": None, "source": None}

    try:
        a = fetch_arihant_ajax()
        data.update(a)
        data["source"] = "ajax"
        if data["gold_999"] is None and data["gold_995"] is None:
            raise Exception("AJAX returned empty")
    except Exception as e_ajax:
        try:
            x = fetch_arihant_xml()
            data.update(x)
            data["source"] = "xml"
            if data["gold_999"] is None and data["gold_995"] is None:
                data["error"] = f"XML empty (AJAX err: {e_ajax})"
        except Exception as e_xml:
            data["error"] = f"AJAX failed: {e_ajax} | XML failed: {e_xml}"

    CACHE["data"] = data
    CACHE["ts"] = now
    return data

@app.get("/api/prices")
def api_prices():
    # IMPORTANT: never crash here, always return JSON
    ar = get_arihant_cached()
    cost = ar.get("gold_999")
    sell995 = ar.get("gold_995")

    payload = {
        "updatedAt": int(time.time()),
        "sell995": [{
            "site": "Arihant",
            "cost": safe_int(cost),
            "sell": safe_int(sell995),
            "diff": safe_int((sell995 - cost) if (sell995 is not None and cost is not None) else None)
        }],
        "sell999": [{
            "site": "Arihant",
            "cost": safe_int(cost),
            "sell": safe_int(cost),
            "diff": 0 if cost is not None else None
        }],
        "debug": {"source": ar.get("source"), "error": ar.get("error")}
    }
    return jsonify(payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
