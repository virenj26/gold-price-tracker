from flask import Flask, jsonify, render_template
import os, time

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

@app.get("/error")
def error():
    # show whether templates/index.html exists on Render
    exists = os.path.exists("templates/index.html")
    files = []
    for root, dirs, fs in os.walk("."):
        for f in fs:
            if "index.html" in f or "templates" in root:
                files.append(os.path.join(root, f))
    return jsonify({
        "cwd": os.getcwd(),
        "templates_index_exists": exists,
        "matching_files": files[:200],
    })

@app.get("/")
def home():
    # if template missing, show a readable message instead of blank
    if not os.path.exists("templates/index.html"):
        return (
            "<h2>templates/index.html NOT FOUND on server</h2>"
            "<p>Fix: commit/push templates/index.html to GitHub and redeploy Render.</p>"
            "<p>Open /error to verify files.</p>",
            500
        )
    return render_template("index.html")

@app.get("/api/prices")
def api_prices():
    return jsonify({"updatedAt": int(time.time()), "sell995": [], "sell999": []})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
