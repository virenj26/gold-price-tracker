from flask import Flask, jsonify, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/prices")
def prices():
    return jsonify({
        "gold": {
            "sell999": 62000,
            "sell995": 61800
        },
        "silver": {
            "sell999": 75000
        }
    })

if __name__ == "__main__":
    app.run()
