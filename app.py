from flask import Flask, jsonify, render_template
import os, time, requests, xml.etree.ElementTree as ET

app = Flask(__name__)

# Common vendor-style endpoint (Arihant already works on this pattern)
BASE_XML = "https://bcast.arihantspot.com:7768/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/{}"

SITES = {
    "Arihant": {
        "referer": "https://www.arihantspot.in/",
        "template_candidates": ["arihant"]
    },
    "Safari": {
        "referer": "https://www.safaribullions.com/",
        "template_candidates": ["safari", "safaribullions", "safari1", "safaribullion"]
    },
    "Mandev": {
        "referer": "https://shreemandevbullion.in/",
        "template_candidates": ["mande", "mandev", "shreemandev", "shreemandevbullion"]
    },
    "Auric": {
        "referer": "https://auricbullion.com/",
        "template_candidates": ["auric", "auricbullion", "auric1"]
    },
    "Raksha": {
        "referer": "https://rakshabullion.com/",
        "template_candidates": ["raksha", "rakshabullion", "raksha1"]
    },
    "RSBL": {
        "referer": "https://www.rsbl.in/live-rates/",
        "template_candidates": ["rsbl", "rsbl1", "rsblbullion", "rsblrates"]
    },
    "dP GOLD": {
        "referer": "https://www.dpgold.com/",
        "template_candidates": ["dpgold", "dp", "dpgold1", "dpgoldbullion"]
    }
}

CACHE = {}  # per site cache: {site: {"ts":..., "data":...}}
CACHE_SECONDS = 5

def parse_vendor_xml(xml_text: str):
    """
    Parses vendor XML into dict like {"GOLD999": 152879.0, ...}
    """
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

def fetch_live_by_template(template_id: str, referer: str):
    """
    Returns dict: {"raw":..., "gold_999":..., "gold_995":..., "silver_999":..., "error":...}
    """
    try:
        url = BASE_XML.format(template_id)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
            "Accept": "*/*",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        raw = parse_vendor_xml(r.text)
        return {
            "template": template_id,
            "raw": raw,
            "gold_999": raw.get("GOLD999"),
            "gold_995": raw.get("GOLD995"),
            "silver_999": raw.get("SILVER999"),
            "error": None
        }
    except Exception as e:
        return {
            "template": template_id,
            "raw": {},
            "gold_999": None,
            "gold_995": None,
            "silver_999": None,
            "error": str(e)
        }

def discover_and_fetch(site_name: str):
    """
    Tries candidates until it finds GOLD999 (or any usable symbol).
    """
    cfg = SITES[site_name]
    referer = cfg["referer"]

    best = None
    for tid in cfg["template_candidates"]:
        data = fetch_live_by_template(tid, referer)
        # If this template returns GOLD999, we accept it immediately
        if data.get("gold_999") is not None:
            return data
        # Keep the least-bad result for debugging
        if best is None:
            best = data
    return best

def get_site_live(site_name: str):
    now = time.time()
    c = CACHE.get(site_name)
    if (c is None) or (now - c["ts"] > CACHE_SECONDS):
        data = discover_and_fetch(site_name)
        CACHE[site_name] = {"ts": now, "data": data}
    return CACHE[site_name]["data"]

def safe_int(x):
    try:
        if x is None: return None
        return int(round(float(x)))
    except:
        return None

def build_tables_live():
    """
    LIVE tables:
      - Cost = site GOLD999
      - Sell995 = site GOLD995 (if provided by feed)
      - Sell999 = site GOLD999 (same as cost)
    If a site feed provides only GOLD999 and not GOLD995, then Sell995 becomes None.
    """
    sell995 = []
    sell999 = []

    for site in SITES.keys():
        d = get_site_live(site)

        cost = d.get("gold_999")          # live cost (999)
        sell_995 = d.get("gold_995")      # live 995 (if provided)
        sell_999 = d.get("gold_999")      # live 999

        # diffs
        diff995 = (sell_995 - cost) if (sell_995 is not None and cost is not None) else None
        diff999 = (sell_999 - cost) if (sell_999 is not None and cost is not None) else None

        sell995.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(sell_995),
            "diff": safe_int(diff995),
            "template": d.get("template"),
            "error": d.get("error")
        })

        sell999.append({
            "site": site,
            "cost": safe_int(cost),
            "sell": safe_int(sell_999),
            "diff": safe_int(diff999),
            "template": d.get("template"),
            "error": d.get("error")
        })

    return {
        "updatedAt": int(time.time()),
        "sell995": sell995,
        "sell999": sell999
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def api_prices():
    return jsonify(build_tables_live())

@app.route("/debug/site/<site_name>")
def debug_site(site_name):
    # Example: /debug/site/Safari
    if site_name not in SITES:
        return jsonify({"error": "Unknown site"}), 404
    return jsonify(get_site_live(site_name))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
