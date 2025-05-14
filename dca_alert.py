import os
import logging
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# ------------------ CONFIG ------------------
TICKERS = [
    "NVDA", "AMZN", "RKLB", "TSM", "LLY", "AVGO",
    "HIMS", "PLTR", "TMDX", "ASML", "ARQT", "V",
    "META", "ABBV", "COST", "IONQ", "MSFT", "SNOW",
    "TEM", "VST", "CRWD"
]
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ------------------ LOGGER ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ------------------ DATA FETCH ------------------
def fetch_data(ticker: str, interval: str, period: str) -> pd.DataFrame:
    try:
        return yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False)
    except Exception as e:
        logging.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

# ------------------ INDICATORS ------------------
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Stochastic RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    stoch = (rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())
    df['%K'] = stoch.rolling(3).mean().clip(0, 1)
    df['%D'] = df['%K'].rolling(3).mean().clip(0, 1)
    # EMA
    for span in [50, 100, 200]:
        df[f'EMA{span}'] = df['Close'].ewm(span=span, adjust=False).mean()
    # MACD
    fast = df['Close'].ewm(span=12, adjust=False).mean()
    slow = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = fast - slow
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df.dropna()

# ------------------ EMBED BUILDER ------------------
def build_embed(ticker, k, d, price, trend_d, trend_w, ema_ok):
    # Choose color and EMA field text
    color = 0x00FF00 if ema_ok else 0xFFA500
    ema_text = "50→100→Price→200" if ema_ok else "ไม่เรียงตามเกณฑ์"
    # MACD icons
    icon_d = "🔼" if trend_d == "ขาขึ้น" else "🔽"
    icon_w = "🔼" if trend_w == "ขาขึ้น" else "🔽"
    embed = {
        "title": f"📣 {ticker}",
        "color": color,
        "fields": [
            {"name": "🎯 %K / %D", "value": f"{k:.2f} / {d:.2f}", "inline": True},
            {"name": "💲 Price",     "value": f"${price:.2f}",     "inline": True},
            {"name": "📊 MACD",      "value": f"Day {icon_d} / Week {icon_w}", "inline": True},
            {"name": "📈 EMA",       "value": ema_text,             "inline": False}
        ]
    }
    return embed

# ------------------ SIGNAL CHECK ------------------
def check_signals(df_day, df_week, ticker):
    latest = df_day.iloc[-1]
    k, d = float(latest['%K']), float(latest['%D'])
    # Step 1: Stochastic RSI
    if k > d and k < 0.2 and d < 0.2:
        price = float(latest['Close'])
        macd_d, sig_d = float(latest['MACD']), float(latest['Signal'])
        macd_w, sig_w = float(df_week['MACD'].iloc[-1]), float(df_week['Signal'].iloc[-1])
        trend_d = "ขาขึ้น" if macd_d > sig_d else "ขาลง"
        trend_w = "ขาขึ้น" if macd_w > sig_w else "ขาลง"
        ema50, ema100, ema200 = float(latest['EMA50']), float(latest['EMA100']), float(latest['EMA200'])
        ema_ok = ema50 > ema100 > price > ema200
        return build_embed(ticker, k, d, price, trend_d, trend_w, ema_ok)
    return None

# ------------------ DISCORD NOTIFIER ------------------
def send_to_discord(embeds=None, content=None):
    if not WEBHOOK_URL:
        logging.error("DISCORD_WEBHOOK_URL not set")
        return
    payload = {}
    if content:
        payload['content'] = content
    if embeds:
        payload['embeds'] = embeds
    try:
        r = requests.post(WEBHOOK_URL, json=payload)
        r.raise_for_status()
        logging.info("Sent to Discord")
    except Exception as e:
        logging.error(f"Discord error: {e}")

# ------------------ MAIN ------------------
def main():
    embed_list = []
    for t in TICKERS:
        df_d = calculate_indicators(fetch_data(t, '1d', '2y'))
        df_w = calculate_indicators(fetch_data(t, '1wk', '5y'))
        if df_d.empty or df_w.empty:
            continue
        embed = check_signals(df_d, df_w, t)
        if embed:
            embed_list.append(embed)
    if not embed_list:
        send_to_discord(content="📭 วันนี้ไม่มีหุ้นเข้าเงื่อนไข DCA")
    else:
        for e in embed_list:
            send_to_discord(embeds=[e])

if __name__ == '__main__':
    main()
