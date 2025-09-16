import logging
from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import openai
import os
import math

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

API_KEY = os.environ.get("KITE_API_KEY")
API_SECRET = os.environ.get("KITE_API_SECRET")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)
openai.api_key = OPENAI_API_KEY

# Prompt for AI stock analysis and recommendation
AI_PROMPT = (
    "I will give you a stock ticker symbol. Analyze it and give me a final clear recommendation: either BUY or SELL (answer must be only one word — ‘BUY’ or ‘SELL,’ no explanations or neutral choices).\n"
    "Your analysis should include:\n"
    "Technical Analysis: Focus on recent price action, moving averages, RSI, MACD, support/resistance levels, and trend direction, all within a swing trading timeframe of 1-3 months.\n"
    "Fundamental Analysis: Look for indicators relevant to shorter-term market movements (e.g., earnings reports, short-term revenue/profitability trends, near-term valuation changes).\n"
    "News & Sentiment: Check for any impactful recent news, controversies, or changes in sentiment that could influence the stock in the next 1-3 months.\n"
    "After analyzing all three aspects, respond with only one word: either ‘BUY’ or ‘SELL’.\n"
    "The analysis is for swing trading and with a timeframe of 1-3 months."
)

def get_ai_recommendation(symbol):
    prompt = f"{AI_PROMPT}\nStock: {symbol}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        answer = response.choices[0].message.content.strip().upper()
        if "BUY" in answer:
            return "BUY"
        elif "SELL" in answer:
            return "SELL"
        else:
            return None
    except Exception as e:
        logging.error("OpenAI API error for %s: %s", symbol, e)
        return None

@app.route("/", methods=["GET", "POST"])
def home_or_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        logging.info("Received POST data: %s", data)

        stocks_str = data.get("stocks", "")
        symbols = [s.strip().upper() for s in stocks_str.split(",") if s.strip()]

        if not symbols:
            return jsonify({"error": "No stocks found in payload"}), 400

        results = []

        try:
            holdings = kite.holdings()
            held_symbols = {h["tradingsymbol"].strip().upper() for h in holdings}
            holdings_map = {h["tradingsymbol"].strip().upper(): h for h in holdings}
            positions = kite.positions()["net"]
            position_symbols = {p["tradingsymbol"].strip().upper() for p in positions if p["quantity"] != 0}
            positions_map = {p["tradingsymbol"].strip().upper(): p for p in positions if p["quantity"] != 0}
            all_held_symbols = held_symbols | position_symbols
        except Exception as e:
            logging.error("Failed to fetch holdings or positions: %s", e)
            return jsonify({"error": "Failed to fetch holdings or positions"}), 500

        for symbol in symbols:
            nse_symbol = f"NSE:{symbol}"
            ai_action = get_ai_recommendation(nse_symbol)
            if not ai_action:
                msg = f"AI could not determine action for {symbol}"
                logging.warning(msg)
                results.append({"symbol": symbol, "status": msg})
                continue

            if ai_action == "BUY":
                if symbol in all_held_symbols:
                    msg = f"{symbol} already in holdings or positions, skipping buy"
                    logging.info(msg)
                    results.append({"symbol": symbol, "status": msg})
                    continue
                try:
                    ltp_data = kite.ltp(f"NSE:{symbol}")
                    price = ltp_data[f"NSE:{symbol}"]["last_price"]
                    quantity = max(1, math.floor(1000 / price))
                    order = kite.place_order(
                        variety="regular",
                        tradingsymbol=symbol,
                        exchange="NSE",
                        transaction_type=ai_action,
                        quantity=quantity,
                        order_type="MARKET",
                        product="CNC",
                        validity="DAY"
                    )
                    results.append({
                        "symbol": symbol,
                        "status": f"{ai_action} placed",
                        "order_id": order,
                        "quantity": quantity
                    })
                except Exception as e:
                    results.append({"symbol": symbol, "error": str(e)})
            elif ai_action == "SELL":
                available_qty = 0
                if symbol in holdings_map:
                    available_qty += holdings_map[symbol].get("quantity", 0)
                if symbol in positions_map:
                    available_qty += positions_map[symbol].get("quantity", 0)
                if available_qty <= 0:
                    msg = f"{symbol} not in holdings or positions, skipping sell"
                    results.append({"symbol": symbol, "status": msg})
                    continue
                try:
                    order = kite.place_order(
                        variety="regular",
                        tradingsymbol=symbol,
                        exchange="NSE",
                        transaction_type=ai_action,
                        quantity=available_qty,
                        order_type="MARKET",
                        product="CNC",
                        validity="DAY"
                    )
                    results.append({
                        "symbol": symbol,
                        "status": f"{ai_action} placed",
                        "order_id": order,
                        "quantity": available_qty
                    })
                except Exception as e:
                    results.append({"symbol": symbol, "error": str(e)})

        return jsonify(results)

    return "Stock Agent Running with AI Validation!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)