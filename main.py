from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os

app = Flask(__name__)

# Credentials from environment (Render will provide)
API_KEY = os.environ.get("KITE_API_KEY")
API_SECRET = os.environ.get("KITE_API_SECRET")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    symbol = data.get("symbol")
    action = data.get("action")

    if not symbol or not action:
        return jsonify({"error": "Invalid payload"}), 400

    try:
        if action.upper() == "BUY":
            order = kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type="BUY",
                quantity=1,
                order_type="MARKET",
                product="CNC"
            )
            return jsonify({"status": "BUY placed", "order_id": order})
        elif action.upper() == "SELL":
            order = kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type="SELL",
                quantity=1,
                order_type="MARKET",
                product="CNC"
            )
            return jsonify({"status": "SELL placed", "order_id": order})
        else:
            return jsonify({"error": "Unknown action"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "Stock Agent Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
