import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import requests
import matplotlib.pyplot as plt
import os

plt.switch_backend('agg')  # สำหรับรันบน server ที่ไม่มี GUI

# ตั้งค่าหุ้นที่ต้องการ
TICKERS = ["NVDA", "AMZN", "RKLB", "TSM", "LLY", "AVGO", "HIMS", "PLTR", "TMDX", "ASML", "ARQT", "V", "META", "ABBV"]

def get_data(ticker):
    end = dt.datetime.now()
    start = end - dt.timedelta(days=365*2)
    df = yf.download(ticker, start=start, end=end)
    return df

def calculate_indicators(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    stoch_rsi = (rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())
    df['StochRSI'] = stoch_rsi
    df['%K'] = df['StochRSI'].rolling(3).mean()
    df['%D'] = df['%K'].rolling(3).mean()

    for ema in [50, 100, 200]:
        df[f'EMA{ema}'] = df['Close'].ewm(span=ema).mean()
    return df

def check_signal(df):
    try:
        k, d = df['%K'].iloc[-1], df['%D'].iloc[-1]
        stoch_condition = k > d and k < 0.2 and d < 0.2
        ema_condition = df['Close'].iloc[-1] > df['EMA50'].iloc[-1] > df['EMA100'].iloc[-1] > df['EMA200'].iloc[-1]
        return stoch_condition, ema_condition, stoch_condition and ema_condition
    except:
        return False, False, False

def plot_chart(df, ticker):
    plt.figure(figsize=(10, 6))
    plt.plot(df['Close'], label='Close')
    plt.plot(df['EMA50'], label='EMA50')
    plt.plot(df['EMA100'], label='EMA100')
    plt.plot(df['EMA200'], label='EMA200')
    plt.title(ticker)
    plt.legend()
    filename = f"{ticker}.png"
    plt.savefig(filename)
    return filename

def send_to_discord(message, files=[]):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("No Discord webhook URL set.")
        return
    payload = {"content": message}
    files_data = [('file', open(f, 'rb')) for f in files]
    requests.post(webhook_url, data=payload, files=files_data)
    for f in files:
        os.remove(f)

summary = []
for ticker in TICKERS:
    df = get_data(ticker)
    df = calculate_indicators(df)
    stoch, ema, buy = check_signal(df)
    if buy:
        chart_file = plot_chart(df, ticker)
        summary.append((ticker, chart_file))

if summary:
    for ticker, chart in summary:
        send_to_discord(f"📈 DCA Signal: {ticker}", files=[chart])
else:
    print("No buy signals found.")
