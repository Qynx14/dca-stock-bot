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
    """Download historical data for a ticker from Yahoo Finance."""
    try:
        df = yf.download(
            ticker,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=False  # Explicit to avoid default change warning
        )
        logging.info(f"Fetched {len(df)} rows for {ticker} ({interval}, {period})")
        return df
    except Exception as e:
        logging.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

# ------------------ INDICATORS ------------------
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Stochastic RSI, EMA, and MACD indicators."""
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

    # EMA50/100/200
    for span in [50, 100, 200]:
        df[f'EMA{span}'] = df['Close'].ewm(span=span, adjust=False).mean()

    # MACD & Signal
    macd_fast = df['Close'].ewm(span=12, adjust=False).mean()
    macd_slow = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = macd_fast - macd_slow
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    return df.dropna()

# ------------------ SIGNAL CHECK ------------------
def check_signals(df_day: pd.DataFrame, df_week: pd.DataFrame, ticker: str) -> str:
    """Return a Discord-formatted message when ticker passes StochRSI DCA condition."""
    latest = df_day.iloc[-1]
    # Ensure scalar values
    k = float(latest['%K'])
    d = float(latest['%D'])
    # Step 1: StochRSI check
    if (k > d) and (k < 0.2) and (d < 0.2):
        price = float(latest['Close'])
        ema50 = float(latest['EMA50'])
        ema100 = float(latest['EMA100'])
        ema200 = float(latest['EMA200'])
        macd_d = float(latest['MACD'])
        sig_d = float(latest['Signal'])
        macd_w = float(df_week['MACD'].iloc[-1])
        sig_w = float(df_week['Signal'].iloc[-1])
        trend_day = "ขาขึ้น" if macd_d > sig_d else "ขาลง"
        trend_week = "ขาขึ้น" if macd_w > sig_w else "ขาลง"
        ema_status = (
            "EMA50>EMA100>ราคา>EMA200"
            if ema50 > ema100 > price > ema200
            else "โครงสร้าง EMA ไม่ตรงตามเกณฑ์"
        )
        msg = (
            f"📣 **{ticker}** เข้าเงื่อนไข DCA\n"
            f"• StochRSI: %K={k:.2f}, %D={d:.2f}\n"
            f"• ราคา: ${price:.2f}\n"
            f"• MACD: Day({trend_day}), Week({trend_week})\n"
            f"• EMA Structure: {ema_status}\n"
        )
        return msg
    return ""

# ------------------ DISCORD NOTIFIER ------------------
def send_to_discord(message: str):
    """Send a message payload to Discord webhook."""
    if not WEBHOOK_URL:
        logging.error("DISCORD_WEBHOOK_URL not set")
        return
    payload = {"content": message}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        logging.info("Message sent to Discord")
    except Exception as e:
        logging.error(f"Failed to send Discord message: {e}")

# ------------------ MAIN ------------------
def main():
    messages = []
    for ticker in TICKERS:
        df_day = calculate_indicators(fetch_data(ticker, "1d", "2y"))
        df_week = calculate_indicators(fetch_data(ticker, "1wk", "5y"))
        if df_day.empty or df_week.empty:
            continue
        message = check_signals(df_day, df_week, ticker)
        if message:
            messages.append(message)
    if not messages:
        send_to_discord("📭 วันนี้ไม่มีหุ้นเข้าเงื่อนไข DCA")
    else:
        for msg in messages:
            send_to_discord(msg)

if __name__ == "__main__":
    main()
