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
    return yf.download(ticker, interval=interval, period=period, progress=False)

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

        support_14 = df_day['Low'].rolling(14).min().iloc[-1]
        support_30 = df_day['Low'].rolling(30).min().iloc[-1]
        support_90 = df_day['Low'].rolling(90).min().iloc[-1]

        stoch_alert = k > d and k < 0.2 and d < 0.2
        trend_macd_day = "Uptrend" if macd_day > macd_sig_day else "Downtrend"
        trend_macd_week = "Uptrend" if macd_week > macd_sig_week else "Downtrend"

        if ema50 > ema100 > close > ema200:
            ema_status = f"EMA50 ({ema50:.2f}) > EMA100 ({ema100:.2f}) > Close ({close:.2f}) > EMA200 ({ema200:.2f})"
        else:
            ema_status = "Mixed EMA Structure"

        if stoch_alert:
            message = f"📈 **DCA Alert: {ticker}**\n"
            message += f"🟢 %K ({k:.2f}) ตัดขึ้น %D ({d:.2f}) ใต้ระดับ 20\n"
            message += f"📊 MACD: {trend_macd_day} (Day), {trend_macd_week} (Week)\n"
            message += f"📉 EMA: {ema_status}\n"
            message += f"🔻 แนวรับ: ${support_14:.2f} / ${support_30:.2f} / ${support_90:.2f}"
            return message
    except Exception as e:
        print(f"Error in {ticker}: {e}")
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
