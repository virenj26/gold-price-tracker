import requests
import xml.etree.ElementTree as ET
import time

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
        tag = node.tag.lower()
        if tag.endswith("symbol"):
            last_symbol = node.text
        if tag.endswith("rate") and last_symbol:
            try:
                rates[last_symbol] = float(node.text)
            except:
                pass

    return {
        "gold_999": rates.get("GOLD999"),
        "gold_995": rates.get("GOLD995"),
        "silver_999": rates.get("SILVER999"),
    }

def get_arihant_cached():
    if time.time() - _ARIHANT_CACHE["ts"] > 10:
        _ARIHANT_CACHE["data"] = fetch_arihant_rates()
        _ARIHANT_CACHE["ts"] = time.time()
    return _ARIHANT_CACHE["data"]
