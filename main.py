import logging
from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os
import math
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

API_KEY = os.environ.get("KITE_API_KEY")
API_SECRET = os.environ.get("KITE_API_SECRET")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

@app.route("/", methods=["GET", "POST"])
def home_or_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        logging.info("Received POST data: %s", data)

        # Parse stocks and trigger_prices as lists, normalize to uppercase
        stocks_str = data.get("stocks", "")
        prices_str = data.get("trigger_prices", "")
        scan_name = data.get("scan_name", "").lower()
        symbols = [s.strip().upper() for s in stocks_str.split(",") if s.strip()]
        trigger_prices = [float(p.strip()) for p in prices_str.split(",") if p.strip()]

        if not symbols:
            return jsonify({"error": "No stocks found in payload"}), 400

        # Determine action based on scan_name
        if "bullish" in scan_name:
            action = "BUY"
        elif "bearish" in scan_name:
            action = "SELL"
        else:
            logging.warning("scan_name must contain 'bullish' or 'bearish'")
            return jsonify({"error": "scan_name must contain 'bullish' or 'bearish'"}), 400

        results = []

        try:
            holdings = kite.holdings()
            held_symbols = {h["tradingsymbol"].strip().upper() for h in holdings}
            holdings_map = {h["tradingsymbol"].strip().upper(): h for h in holdings}
            positions = kite.positions()["net"]
            position_symbols = {p["tradingsymbol"].strip().upper() for p in positions if p["quantity"] != 0}
            positions_map = {p["tradingsymbol"].strip().upper(): p for p in positions if p["quantity"] != 0}
            all_held_symbols = held_symbols | position_symbols
            logging.info("Current holdings: %s", held_symbols)
            logging.info("Current positions: %s", position_symbols)
        except Exception as e:
            logging.error("Failed to fetch holdings or positions: %s", e)
            return jsonify({"error": "Failed to fetch holdings or positions"}), 500

        for symbol in symbols:
            if action == "BUY":
                if symbol in all_held_symbols:
                    msg = f"{symbol} already in holdings or positions, skipping buy"
                    logging.info(msg)
                    results.append({"symbol": symbol, "status": msg})
                    continue
                try:
                    ltp_data = kite.ltp(f"NSE:{symbol}")
                    price = ltp_data[f"NSE:{symbol}"]["last_price"]
                    quantity = max(1, math.floor(1000 / price))
                    logging.info("Placing %s order for %s: qty=%d at price=%.2f", action, symbol, quantity, price)
                    order = kite.place_order(
                        variety="regular",
                        tradingsymbol=symbol,
                        exchange="NSE",
                        transaction_type=action,
                        quantity=quantity,
                        order_type="MARKET",
                        product="CNC",
                        validity="DAY"
                    )
                    logging.info("Order placed for %s: order_id=%s", symbol, order)
                    results.append({
                        "symbol": symbol,
                        "status": f"{action} placed",
                        "order_id": order,
                        "quantity": quantity
                    })
                except Exception as e:
                    logging.error("Error placing order for %s: %s", symbol, e)
                    results.append({"symbol": symbol, "error": str(e)})
            elif action == "SELL":
                # Check if symbol is in holdings or positions and get available quantity
                available_qty = 0
                if symbol in holdings_map:
                    available_qty += holdings_map[symbol].get("quantity", 0)
                if symbol in positions_map:
                    available_qty += positions_map[symbol].get("quantity", 0)
                if available_qty <= 0:
                    msg = f"{symbol} not in holdings or positions, skipping sell"
                    logging.info(msg)
                    results.append({"symbol": symbol, "status": msg})
                    continue
                try:
                    logging.info("Placing %s order for %s: qty=%d", action, symbol, available_qty)
                    order = kite.place_order(
                        variety="regular",
                        tradingsymbol=symbol,
                        exchange="NSE",
                        transaction_type=action,
                        quantity=available_qty,
                        order_type="MARKET",
                        product="CNC",
                        validity="DAY"
                    )
                    logging.info("Order placed for %s: order_id=%s", symbol, order)
                    results.append({
                        "symbol": symbol,
                        "status": f"{action} placed",
                        "order_id": order,
                        "quantity": available_qty
                    })
                except Exception as e:
                    logging.error("Error placing order for %s: %s", symbol, e)
                    results.append({"symbol": symbol, "error": str(e)})

        return jsonify(results)

    logging.info("GET request received")
    return "Stock Agent Running with Multi-Stock Support!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
