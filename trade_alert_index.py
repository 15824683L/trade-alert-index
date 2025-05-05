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

def ema_breakout_strategy(df):
    if len(df) < 3:
        return "NO SIGNAL", None, None, None, None, None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # BUY setup
    if prev['close'] > prev['21ema'] and last['high'] > prev['high']:
        entry = round(prev['high'], 2)
        sl = round(prev['low'], 2)
        tp = round(entry + (entry - sl) * 2, 2)
        tsl = round(entry + (entry - sl) * 1.5, 2)
        return "BUY", entry, sl, tp, tsl, "🟢"

    # SELL setup
    if prev['close'] < prev['21ema'] and last['low'] < prev['low']:
        entry = round(prev['low'], 2)
        sl = round(prev['high'], 2)
        tp = round(entry - (sl - entry) * 2, 2)
        tsl = round(entry - (sl - entry) * 1.5, 2)
        return "SELL", entry, sl, tp, tsl, "🔴"

    return "NO SIGNAL", None, None, None, None, None

# MAIN LOOP
while True:
    signal_found = False

    for stock in INDIAN_STOCKS:
        df = fetch_data(stock)
        if df is not None and not df.empty:
            signal, entry, sl, tp, tsl, emoji = ema_breakout_strategy(df)

            if signal != "NO SIGNAL" and stock not in active_trades:
                signal_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg = (
                    f"{emoji} *{signal} Signal for {stock}*\n"
                    f"Time: `{signal_time}`\n"
                    f"Entry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                )
                send_telegram_message(msg, TELEGRAM_CHAT_ID)
                send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)

                active_trades[stock] = {
                    "signal_time": signal_time,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "direction": signal
                }
                signal_found = True

        # Check existing trade hit TP or SL
        if stock in active_trades:
            last_price = df['close'].iloc[-1]
            trade = active_trades[stock]
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M')

            if trade['direction'] == "BUY":
                if last_price >= trade['tp']:
                    send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_CHAT_ID)
                    del active_trades[stock]
                elif last_price <= trade['sl']:
                    send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_CHAT_ID)
                    del active_trades[stock]

            elif trade['direction'] == "SELL":
                if last_price <= trade['tp']:
                    send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_CHAT_ID)
                    del active_trades[stock]
                elif last_price >= trade['sl']:
                    send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`", TELEGRAM_CHAT_ID)
                    del active_trades[stock]

    if not signal_found and (time.time() - last_signal_time > 3600):
        send_telegram_message("⚠️ No Signal in the Last 1 Hour (21 EMA Breakout)", TELEGRAM_CHAT_ID)
        last_signal_time = time.time()

    time.sleep(60)
    print("Bot running with 21 EMA strategy only...")
