import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import requests
import os

# ------------------ CONFIG ------------------
TICKERS = ["NVDA", "AMZN", "RKLB", "TSM", "LLY", "AVGO", "HIMS", "PLTR", "TMDX", "ASML", "ARQT", "V", "META", "ABBV", "COST", "IONQ", "MSFT", "SNOW", "TEM", "VST", "CRWD"]
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ------------------ DATA FETCH ------------------
def get_data(ticker, interval="1d", period="2y"):
    return yf.download(ticker, interval=interval, period=period)

# ------------------ INDICATORS ------------------
def calculate_indicators(df):
    # StochRSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    stoch_rsi = (rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())
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
    return df

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

        stoch_alert = k > d and k < 0.2 and d < 0.2
        trend_macd_day = "Uptrend" if macd_day > macd_sig_day else "Downtrend"
        trend_macd_week = "Uptrend" if macd_week > macd_sig_week else "Downtrend"

        ema_status = f"EMA50 ({ema50:.2f}) > EMA100 ({ema100:.2f}) > Close ({close:.2f}) > EMA200 ({ema200:.2f})" if ema50 > ema100 > close > ema200 else "Mixed EMA Structure"

        if stoch_alert:
            message = f"**DCA Alert: {ticker}**\n"
            message += f"- %K ({k:.2f}) ตัดขึ้น %D ({d:.2f}) ใต้ระดับ 20\n"
            message += f"- MACD Day: {trend_macd_day}, MACD Week: {trend_macd_week}\n"
            message += f"- EMA Structure: {ema_status}"
            return message
    except:
        pass
    return None

# ------------------ DISCORD ------------------
def send_to_discord(content):
    if not WEBHOOK_URL:
        print("Webhook URL not set.")
        return
    payload = {"content": content}
    requests.post(WEBHOOK_URL, json=payload)

# ------------------ MAIN ------------------
all_messages = []
for ticker in TICKERS:
    df_day = calculate_indicators(get_data(ticker, interval="1d", period="2y"))
    df_week = calculate_indicators(get_data(ticker, interval="1wk", period="5y"))
    signal_msg = check_signals(df_day, df_week, ticker)
    if signal_msg:
        all_messages.append(signal_msg)

if all_messages:
    for msg in all_messages:
        send_to_discord(msg)
else:
    send_to_discord("📭 วันนี้ไม่มีหุ้นเข้าเงื่อนไข DCA")
