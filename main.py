from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os
import math

app = Flask(__name__)

# Credentials from environment
API_KEY = os.environ.get("KITE_API_KEY")
API_SECRET = os.environ.get("KITE_API_SECRET")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

@app.route("/", methods=["GET", "POST"])
def home_or_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)

        # Parse stocks and trigger_prices as lists
        stocks_str = data.get("stocks", "")
        prices_str = data.get("trigger_prices", "")
        symbols = [s.strip() for s in stocks_str.split(",") if s.strip()]
        trigger_prices = [float(p.strip()) for p in prices_str.split(",") if p.strip()]

        if not symbols:
            return jsonify({"error": "No stocks found in payload"}), 400

        action = "BUY"
        results = []

        for symbol in symbols:
            try:
                ltp_data = kite.ltp(f"NSE:{symbol}")
                price = ltp_data[f"NSE:{symbol}"]["last_price"]
                quantity = max(1, math.floor(10000 / price))
                order = kite.place_order(
                    tradingsymbol=symbol,
                    exchange="NSE",
                    transaction_type=action,
                    quantity=quantity,
                    order_type="MARKET",
                    product="CNC"
                )
                results.append({
                    "symbol": symbol,
                    "status": f"{action} placed",
                    "order_id": order,
                    "quantity": quantity
                })
            except Exception as e:
                results.append({"symbol": symbol, "error": str(e)})

        return jsonify(results)

    # Handle GET
    return "Stock Agent Running with Multi-Stock Support!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
