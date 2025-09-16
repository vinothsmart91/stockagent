import os
import pandas as pd
import yfinance as yf
from datetime import timedelta
import glob

print("🔹 Starting Trade Automation...")

# === Step 1: Load Buy/Sell signals ===
buy_df = pd.read_csv("buy_signals.csv", usecols=["date", "symbol"])
sell_df = pd.read_csv("sell_signals.csv", usecols=["date", "symbol"])

buy_df['Date'] = pd.to_datetime(buy_df['date'], dayfirst=True)
sell_df['Date'] = pd.to_datetime(sell_df['date'], dayfirst=True)

buy_df['Symbol'] = buy_df['symbol']
sell_df['Symbol'] = sell_df['symbol']

buy_df["Type"] = "BUY"
sell_df["Type"] = "SELL"

buy_df = buy_df[['Date','Symbol','Type']]
sell_df = sell_df[['Date','Symbol','Type']]

signals = pd.concat([buy_df, sell_df]).sort_values("Date").reset_index(drop=True)
print(f"✅ Signals loaded & sorted. Total signals: {len(signals)}")

# === Step 2: Trade simulation (first buy → next sell) ===
trades = []
open_buy = {}

for _, row in signals.iterrows():
    symbol, date, sig_type = row["Symbol"], row["Date"], row["Type"]
    if sig_type == "BUY":
        if symbol not in open_buy:
            open_buy[symbol] = date
    elif sig_type == "SELL":
        if symbol in open_buy:
            trades.append({
                "Symbol": symbol,
                "Buy_Date": open_buy[symbol],
                "Sell_Date": date
            })
            del open_buy[symbol]

trades_df = pd.DataFrame(trades)
print(f"✅ Trade simulation complete. Total trades: {len(trades_df)}")

# === Step 3: Download historical data if not exists ===
symbols = trades_df['Symbol'].unique()
hist_data = {}

for symbol in symbols:
    yf_symbol = symbol + ".NS"  # NSE symbol format for Yahoo Finance
    file_name = f"data_{symbol}.csv"

    if os.path.exists(file_name):
        df = pd.read_csv(file_name, parse_dates=['Date'])
        hist_data[symbol] = df[['Date', 'Close']]
        print(f"ℹ️  File exists. Using cached data: {file_name}")
        continue  # skip download

    start_date = trades_df.loc[trades_df['Symbol'] == symbol, 'Buy_Date'].min() - timedelta(days=5)
    end_date = trades_df.loc[trades_df['Symbol'] == symbol, 'Sell_Date'].max() + timedelta(days=5)

    try:
        df = yf.download(
            yf_symbol,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            progress=False,
            auto_adjust=False
        )
        if not df.empty:
            df.reset_index(inplace=True)
            df[['Date', 'Close']].to_csv(file_name, index=False)
            hist_data[symbol] = df[['Date', 'Close']]
            print(f"✅ Downloaded {symbol} ({len(df)} rows) → {file_name}")
        else:
            print(f"⚠️ No data found for {symbol}")
    except Exception as e:
        print(f"❌ Failed to download {symbol}: {e}")

# === Step 4: Assign Buy & Sell Prices from downloaded data ===
def fetch_price(symbol, date):
    df = hist_data.get(symbol)
    if df is None:
        return None
    date = pd.to_datetime(date)
    for i in range(10):  # look ahead 10 days
        row = df[df['Date'] == date + timedelta(days=i)]
        if not row.empty:
            return float(row['Close'].values[0])
    return None

trades_df['Buy_Price'] = trades_df.apply(lambda x: fetch_price(x['Symbol'], x['Buy_Date']), axis=1)
trades_df['Sell_Price'] = trades_df.apply(lambda x: fetch_price(x['Symbol'], x['Sell_Date']), axis=1)

# === Step 5: Compute % change ===
trades_df['Pct_Change'] = ((trades_df['Sell_Price'] - trades_df['Buy_Price']) / trades_df['Buy_Price']) * 100

# === Step 6: Save final CSV ===
output_file = "buy_sell_trades_final.csv"
trades_df.to_csv(output_file, index=False)
print(f"✅ Trade analysis complete! Output saved → {output_file}")

# === Step 7: Trade summary ===
num_trades = len(trades_df)
num_win = len(trades_df[trades_df['Pct_Change'] > 0])
num_loss = len(trades_df[trades_df['Pct_Change'] <= 0])
total_invested = trades_df['Buy_Price'].sum()
total_sell = trades_df['Sell_Price'].sum()
total_profit_loss = total_sell - total_invested
roi = (total_profit_loss / total_invested) * 100 if total_invested != 0 else 0

print("\n===== Trade Summary =====")
print(f"Total trades       : {num_trades}")
print(f"Winning trades     : {num_win}")
print(f"Losing trades      : {num_loss}")
print(f"Total invested     : ₹{total_invested:,.2f}")
print(f"Total sell value   : ₹{total_sell:,.2f}")
print(f"Total P/L amount   : ₹{total_profit_loss:,.2f}")
print(f"Final ROI          : {roi:.2f}%")

# === Step 8: Clean up intermediate data_*.csv files ===
for file in glob.glob("data_*.csv"):
    try:
        os.remove(file)
        print(f"🗑️ Deleted intermediate file: {file}")
    except Exception as e:
        print(f"❌ Could not delete {file}: {e}")
