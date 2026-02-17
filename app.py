from flask import Flask, jsonify, render_template
import os
import time
import re
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# -------------------------
# CONFIG (Sites + Endpoints)
# -------------------------
VENDOR_XML_BASE = "https://bcast.arihantspot.com:7768/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/{}"

SITES = {
    "Arihant": {
        "base": "https://www.arihantspot.in",
        "ajax_path": "/arihant",          # confirmed working (from your Network tab)
        "xml_template": "arihant",        # fallback
        "referer": "https://www.arihantspot.in/",
    },
    "Safari": {
        "base": "https://www.safaribullions.com",
        "ajax_path": "/safari",           # common pattern; if not, XML fallback may work
        "xml_template": "safari",
        "referer": "https://www.safaribullions.com/",
    },
    "Mandev": {
        "base": "https://shreemandevbullion.in",
        "ajax_path": "/mandev",
        "xml_template": "mandev",
        "referer": "https://shreemandevbullion.in/",
    },
    "Auric": {
        "base": "https://auricbullion.com",
        "ajax_path": "/auric",
        "xml_template": "auric",
        "referer": "https://auricbullion.com/",
    },
    "Raksha": {
        "base": "https://rakshabullion.com",
        "ajax_path": "/raksha",
        "xml_template": "raksha",
        "referer": "https://rakshabullion.com/",
    },
    "RSBL": {
        "base": "https://www.rsbl.in",
        "ajax_path": "/rsbl",
        "xml_template": "rsbl",
        "referer": "https://www.rsbl.in/live-rates/",
    },
    "dP GOLD": {
        "base": "https://www.dpgold.com",
        "ajax_path": "/dpgold",
        "xml_template": "dpgold",
        "referer": "https://www.dpgold.com/",
    },
}

# -------------
# Caching
# -------------
CACHE_SECONDS = 5
_CACHE = {}  # site -> {"ts":..., "data":...}

# -------------
# Helpers
# -------------
_num_re = re.compile(r"^-?\d+(?:\.\d+)?$")

def safe_int(x):
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except:
        return None

def extract_last_number(line: str):
    """
    Returns last numeric token in the line (SELL is usually last).
    Example line end: "... 156305 156504 158759 155129" -> returns 155129
    """
    toks = [t for t in line.replace(",", "").split() if _num_re.match(t)]
    return float(toks[-1]) if toks else None

def parse_ajax_text(text: str):
    """
    Parses the AJAX plain-text table (like you saw in Response tab).
    We pick:
      - GOLD 995 (1kg) ... -> gold_995 (sell = last number)
      - GOLD 999 WITH GST ... OR GOLD 999 ... -> gold_999 (sell = last number)
      - SILVER 999 ... -> silver_999 (sell = last number) if present
    """
    gold_995 = None
    gold_999 = None
    silver_999 = None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Prefer "WITH GST" rows if available (more consistent with many sites)
    for ln in lines:
        up = ln.upper()

        # GOLD 995 (1KG)
        if ("GOLD" in up and "995" in up and "(1KG" in up):
            v = extract_last_number(ln)
            if v is not None:
                gold_995 = v

        # GOLD 999 (prefer WITH GST / IMP / etc)
        if "GOLD" in up and "999" in up:
            # if WITH GST exists, take it
            if "WITH GST" in up:
                v = extract_last_number(ln)
                if v is not None:
                    gold_999 = v
            # else keep as fallback only if gold_999 not set
            elif gold_999 is None:
                v = extract_last_number(ln)
                if v is not None:
                    gold_999 = v

        # SILVER 999
        if "SILVER" in up and "999" in up:
            v = extract_last_number(ln)
            if v is not None:
                silver_999 = v

    return {"gold_999": gold_999, "gold_995": gold_995, "silver_999": silver_999}

def fetch_ajax(site_name: str, cfg: dict):
    """
    Fetches live rates from site's AJAX endpoint (like /arihant).
    """
    url = cfg["base"].rstrip("/") + cfg["ajax_path"]
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": cfg.get("referer", cfg["base"]),
        "Accept": "*/*",
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()

    parsed = parse_ajax_text(r.text)
    return {
        "source": "ajax",
        "url": url,
        "gold_999": parsed["gold_999"],
        "gold_995": parsed["gold_995"],
        "silver_999": parsed["silver_999"],
        "error": None
    }

def parse_vendor_xml(xml_text: str):
    root = ET.fromstring(xml_text.strip())
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

    return raw

def fetch_xml(site_name: str, cfg: dict):
    """
    Fetches live rates from vendor XML endpoint as fallback.
    """
    template = cfg["xml_template"]
    url = VENDOR_XML_BASE.format(template)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": cfg.get("referer", cfg["base"]),
        "Accept": "*/*",
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()

    raw = parse_vendor_xml(r.text)
    return {
        "source": "xml",
        "url": url,
        "gold_999": raw.get("GOLD999"),
        "gold_995": raw.get("GOLD995"),
        "silver_999": raw.get("SILVER999"),
        "error": None
    }

def get_site_live(site_name: str):
    """
    Cached fetch:
      1) Try AJAX
      2) Fallback to XML
      3) Never crash
    """
    now = time.time()
    c = _CACHE.get(site_name)
    if c and (now - c["ts"] <= CACHE_SECONDS):
        return c["data"]

    cfg = SITES[site_name]
    data = None

    # Try AJAX first
    try:
        data = fetch_ajax(site_name, cfg)
        # If ajax returns no gold_999, treat as not working and fallback
        if data.get("gold_999") is None and data.get("gold_995") is None:
            raise Exception("AJAX returned no rates")
    except Exception as e_ajax:
        # Fallback to XML
        try:
            data = fetch_xml(site_name, cfg)
            if data.get("gold_999") is None and data.get("gold_995") is None:
                data["error"] = f"XML returned no rates (AJAX err: {str(e_ajax)})"
        except Exception as e_xml:
            data = {
                "source": "none",
                "url": None,
                "gold_999": None,
                "gold_995": None,
                "silver_999": None,
                "error": f"AJAX failed: {str(e_ajax)} | XML failed: {str(e_xml)}"
            }

    _CACHE[site_name] = {"ts": now, "data": data}
    return data

def build_tables_live():
    sell995 = []
    sell999 = []

    for site in SITES.keys():
        d = get_site_live(site)

        # For LIVE tables:
        cost = d.get("gold_999")        # cost = gold 999
        s995 = d.get("gold_995")        # sell995 = gold 995 (if site provides)
        s999 = d.get("gold_999")        # sell999 = gold 999

        diff995 = (s995 - cost) if (s995 is not None and cost is not None) else None
        diff999 = (s999 - cost) if (s999 is not None and cost is not None) else None

        sell995.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(s995),
            "diff": safe_int(diff995),
        })

        sell999.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(s999),
            "diff": safe_int(diff999),
        })

    return {
        "updatedAt": int(time.time()),
        "sell995": sell995,
        "sell999": sell999,
    }

# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def api_prices():
    return jsonify(build_tables_live())

# Debug any site
# Example: /debug/site/Arihant
@app.route("/debug/site/<site_name>")
def debug_site(site_name):
    if site_name not in SITES:
        return jsonify({"error": "Unknown site"}), 404
    return jsonify(get_site_live(site_name))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
