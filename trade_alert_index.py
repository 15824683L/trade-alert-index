import time
import yfinance as yf
import requests
import logging
from datetime import datetime
import ssl
import certifi
import os
from keep_alive import keep_alive

keep_alive()
os.environ['SSL_CERT_FILE'] = certifi.where()

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
TELEGRAM_GROUP_CHAT_ID = "-1002689167916"
INDIAN_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "LT.NS", "SBIN.NS", "KOTAKBANK.NS", "ITC.NS",
    "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS", "BAJFINANCE.NS", "BHARTIARTL.NS",
    "ADANIENT.NS", "HCLTECH.NS", "WIPRO.NS", "ULTRACEMCO.NS", "TECHM.NS"
]
timeframe = "15m"

active_trades = {}
last_signal_time = time.time()

logging.basicConfig(filename="ema_bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)

def fetch_data(symbol):
    try:
        df = yf.download(tickers=symbol, period="5d", interval="15m")
        df.reset_index(inplace=True)
        df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        df['21ema'] = df['close'].ewm(span=21).mean()
        return df[['Datetime', 'open', 'high', 'low', 'close', 'volume', '21ema']]
    except Exception as e:
        logging.error(f"Error fetching {symbol} - {e}")
        return None

# ... আগের লাইনের সব ঠিক আছে ...

def ema_combo_strategy(df):
    df['21ema'] = df['close'].ewm(span=21, adjust=False).mean()

    if len(df) < 3:
        return None, None, None, None, None, None  # not enough data

    last = df.iloc[-1]
    prev = df.iloc[-2]

    signal = None
    entry = sl = tp = tsl = emoji = ""

    # ---- Breakout BUY ----
    if float(prev['close']) > float(prev['21ema']) and float(last['high']) > float(prev['high']):
        signal = "BUY"
        entry = float(last['high'])
        sl = float(prev['low'])
        tp = entry + (entry - sl) * 1.5
        tsl = entry + (entry - sl)
        emoji = "🟢"

    # ---- Breakout SELL ----
    elif float(prev['close']) < float(prev['21ema']) and float(last['low']) < float(prev['low']):
        signal = "SELL"
        entry = float(last['low'])
        sl = float(prev['high'])
        tp = entry - (sl - entry) * 1.5
        tsl = entry - (sl - entry)
        emoji = "🔴"

    # ---- Rejection BUY ----
    elif float(prev['low']) < float(prev['21ema']) and float(prev['close']) > float(prev['21ema']) and float(last['high']) > float(prev['high']):
        signal = "BUY"
        entry = float(last['high'])
        sl = float(prev['low'])
        tp = entry + (entry - sl) * 1.5
        tsl = entry + (entry - sl)
        emoji = "🟢"

    # ---- Rejection SELL ----
    elif float(prev['high']) > float(prev['21ema']) and float(prev['close']) < float(prev['21ema']) and float(last['low']) < float(prev['low']):
        signal = "SELL"
        entry = float(last['low'])
        sl = float(prev['high'])
        tp = entry - (sl - entry) * 1.5
        tsl = entry - (sl - entry)
        emoji = "🔴"

    return signal, entry, sl, tp, tsl, emoji
# MAIN LOOP
while True:
    signal_found = False

    for stock in INDIAN_STOCKS:
        df = fetch_data(stock)
        if df is not None and not df.empty:
            signal, entry, sl, tp, tsl, emoji = ema_combo_strategy(df)

            if signal and stock not in active_trades:
                signal_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg = (
                    f"{emoji} *{signal} Signal for {stock}*\n"
                    f"Time: `{signal_time}`\n"
                    f"Entry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                )
                send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)

                active_trades[stock] = {
                    "signal_time": signal_time,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "direction": signal
                }
                signal_found = True

        if stock in active_trades:
            last_price = df['close'].iloc[-1].item()
            trade = active_trades[stock]
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M')

            if trade['direction'] == "BUY":
                if last_price >= trade['tp']:
                    send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[stock]
                elif last_price <= trade['sl']:
                    send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[stock]

            elif trade['direction'] == "SELL":
                if last_price <= trade['tp']:
                    send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[stock]
                elif last_price >= trade['sl']:
                    send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[stock]

    if not signal_found and (time.time() - last_signal_time > 3600):
        send_telegram_message("⚠️ No Signal in the Last 1 Hour (21 EMA Breakout)", TELEGRAM_GROUP_CHAT_ID)
        last_signal_time = time.time()

    time.sleep(60)
    print("Bot running with 21 EMA strategy only...")
