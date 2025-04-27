import yfinance as yf
import pandas as pd
import numpy as np
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

# ------------------ CHECK STEP 1 ------------------
def check_stoch_rsi(df, timeframe):
    try:
        k = df['%K'].iloc[-1]
        d = df['%D'].iloc[-1]
        if k > d and k < 0.2 and d < 0.2:
            return True, f"🟢 Stochastic RSI ผ่าน ({timeframe}) - %K ({k:.2f}) > %D ({d:.2f}) ต่ำกว่า 20"
        else:
            return False, None
    except Exception as e:
        print(f"Error in StochRSI check ({timeframe}): {e}")
        return False, None

# ------------------ CHECK STEP 2 ------------------
def analyze_stock(df_day, df_week, ticker):
    try:
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

        if macd_day <= macd_sig_day or macd_week <= macd_sig_week:
            return None

        if not (ema50 > ema100 > close > ema200):
            return None

        message = f"🚀 **DCA Confirmed: {ticker}**\n"
        message += f"📈 MACD: Uptrend (Day & Week)\n"
        message += f"📊 EMA Structure: EMA50 ({ema50:.2f}) > EMA100 ({ema100:.2f}) > Close ({close:.2f}) > EMA200 ({ema200:.2f})\n"
        message += f"🔻 Supports: 14d=${support_14:.2f}, 30d=${support_30:.2f}, 90d=${support_90:.2f}\n"
        return message
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

# ------------------ DISCORD ------------------
def send_to_discord(content):
    if not WEBHOOK_URL:
        print("Webhook URL not set.")
        return
    payload = {"content": content}
    requests.post(WEBHOOK_URL, json=payload)

# ------------------ MAIN ------------------
for ticker in TICKERS:
    df_day = calculate_indicators(get_data(ticker, interval="1d", period="2y"))
    df_week = calculate_indicators(get_data(ticker, interval="1wk", period="5y"))

    messages = []

    day_pass, day_message = check_stoch_rsi(df_day, "Day")
    week_pass, week_message = check_stoch_rsi(df_week, "Week")

    if day_pass:
        messages.append(f"📣 {ticker} - {day_message}")
    if week_pass:
        messages.append(f"📣 {ticker} - {week_message}")

    if day_pass or week_pass:
        analysis_message = analyze_stock(df_day, df_week, ticker)
        if analysis_message:
            messages.append(analysis_message)

    for msg in messages:
        send_to_discord(msg)
