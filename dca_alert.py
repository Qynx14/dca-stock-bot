import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import requests
import os
import logging

# ------------------ CONFIG ------------------
TICKERS = [
    "NVDA", "AMZN", "RKLB", "TSM", "LLY", "AVGO", "HIMS", "PLTR",
    "TMDX", "ASML", "ARQT", "V", "META", "ABBV", "COST", "IONQ",
    "MSFT", "SNOW", "TEM", "VST", "CRWD"
]
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ------------------ DATA FETCH ------------------
def get_data(ticker, interval="1d", period="2y"):
    df = yf.download(ticker, interval=interval, period=period, progress=False)
    logging.info(f"Fetched {len(df)} rows for {ticker} ({interval}, {period})")
    return df

# ------------------ INDICATORS ------------------
def calculate_indicators(df):
    df = df.copy()

    # StochRSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    stoch_rsi = ((rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())).clip(0, 1)
    df['%K'] = stoch_rsi.rolling(3).mean()
    df['%D'] = df['%K'].rolling(3).mean()

    # EMA
    for ema in [50, 100, 200]:
        df[f'EMA{ema}'] = df['Close'].ewm(span=ema).mean()

    # MACD
    exp1 = df['Close'].ewm(span=12).mean()
    exp2 = df['Close'].ewm(span=26).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9).mean()

    return df.dropna()

# ------------------ SIGNAL CHECK ------------------
def check_signals(df_day, df_week, ticker):
    try:
        k, d = df_day['%K'].iloc[-1], df_day['%D'].iloc[-1]
        close = df_day['Close'].iloc[-1]
        ema50 = df_day['EMA50'].iloc[-1]
        ema100 = df_day['EMA100'].iloc[-1]
        ema200 = df_day['EMA200'].iloc[-1]
        macd_day = df_day['MACD'].iloc[-1]
        macd_sig_day = df_day['MACD_signal'].iloc[-1]
        macd_week = df_week['MACD'].iloc[-1]
        macd_sig_week = df_week['MACD_signal'].iloc[-1]

        # Step 1: Stochastic RSI
        if k > d and k < 0.2 and d < 0.2:
            macd_day_trend = "🔼" if macd_day > macd_sig_day else "🔽"
            macd_week_trend = "🔼" if macd_week > macd_sig_week else "🔽"

            if ema50 > ema100 > close > ema200:
                ema_structure = (
                    f"✅ EMA50 ({ema50:.2f})\n"
                    f"✅ EMA100 ({ema100:.2f})\n"
                    f"✅ ราคาปิด ({close:.2f})\n"
                    f"✅ EMA200 ({ema200:.2f})"
                )
            else:
                ema_structure = "❌ ยังไม่เข้าเกณฑ์"

            message = f"""
📣 **{ticker}**

🧪 Stochastic RSI
• %K = {k:.2f}
• %D = {d:.2f}

💲 ราคาปิด: ${close:.2f}

📊 MACD
• Day: {macd_day_trend}
• Week: {macd_week_trend}

📈 EMA โครงสร้าง
{ema_structure}
"""
            return message.strip()
    except Exception as e:
        logging.error(f"Error in {ticker}: {e}")
    return None

# ------------------ DISCORD ------------------
def send_to_discord(content):
    if not WEBHOOK_URL:
        print("Webhook URL not set.")
        return
    payload = {"content": content}
    requests.post(WEBHOOK_URL, json=payload)

# ------------------ MAIN ------------------
def main():
    all_messages = []
    for t in TICKERS:
        df_d = calculate_indicators(get_data(t, interval="1d", period="2y"))
        df_w = calculate_indicators(get_data(t, interval="1wk", period="5y"))
        m = check_signals(df_d, df_w, t)
        if m:
            all_messages.append(m)

    if not all_messages:
        send_to_discord("📭 วันนี้ไม่มีหุ้นเข้าเงื่อนไข DCA")
    else:
        for m in all_messages:
            send_to_discord(m)

if __name__ == "__main__":
    main()
