"""
TradeLayer Market Data - Schwab API Edition

Replaces yfinance with the Schwab API via schwab-py.
Same function signatures as the original — drop-in replacement.

Falls back to yfinance automatically if Schwab is unavailable,
so nothing breaks during the transition.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SCHWAB_APP_KEY = os.getenv("SCHWAB_APP_KEY")
SCHWAB_APP_SECRET = os.getenv("SCHWAB_APP_SECRET")
SCHWAB_CALLBACK_URL = "https://127.0.0.1:8182"
SCHWAB_TOKEN_PATH = "schwab_token.json"


def _get_schwab_client():
    """
    Returns an authenticated Schwab client.
    Returns None if credentials are missing or token is invalid.
    """
    if not SCHWAB_APP_KEY or not SCHWAB_APP_SECRET:
        return None

    if not Path(SCHWAB_TOKEN_PATH).exists():
        return None

    try:
        import schwab
        client = schwab.auth.client_from_token_file(
            token_path=SCHWAB_TOKEN_PATH,
            api_key=SCHWAB_APP_KEY,
            app_secret=SCHWAB_APP_SECRET,
        )
        return client
    except Exception as e:
        print(f"Schwab client init failed: {e}")
        return None


def _candles_to_ohlcv(candles: list) -> list:
    """Convert Schwab candle format to simple dicts."""
    result = []
    for c in candles:
        try:
            result.append({
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": int(c["volume"]),
                "datetime": c["datetime"],
            })
        except Exception:
            continue
    return result


def _get_schwab_history(symbol: str, period_days: int = 90) -> list:
    """
    Fetch daily OHLCV history from Schwab.
    Returns list of candle dicts or empty list on failure.
    """
    client = _get_schwab_client()
    if client is None:
        return []

    try:
        # Use convenience method — avoids enum complexity
        resp = client.get_price_history_every_day(symbol.upper())

        if resp.status_code != 200:
            print(f"Schwab history error for {symbol}: {resp.status_code}")
            return []

        data = resp.json()
        candles = data.get("candles", [])
        return _candles_to_ohlcv(candles)

    except Exception as e:
        print(f"Schwab history fetch failed for {symbol}: {e}")
        return []


def _get_schwab_quote(symbol: str) -> dict:
    """
    Fetch live quote from Schwab.
    Returns dict with price info or empty dict on failure.
    """
    client = _get_schwab_client()
    if client is None:
        return {}

    try:
        resp = client.get_quote(symbol.upper())

        if resp.status_code != 200:
            return {}

        data = resp.json()
        quote = data.get(symbol.upper(), {})
        quote_data = quote.get("quote", {})

        return {
            "last_price": quote_data.get("lastPrice") or quote_data.get("closePrice"),
            "close_price": quote_data.get("closePrice"),
            "open_price": quote_data.get("openPrice"),
            "high_price": quote_data.get("highPrice"),
            "low_price": quote_data.get("lowPrice"),
            "volume": quote_data.get("totalVolume"),
            "net_change": quote_data.get("netChange"),
            "net_change_pct": quote_data.get("netPercentChange"),
        }

    except Exception as e:
        print(f"Schwab quote fetch failed for {symbol}: {e}")
        return {}


# ─────────────────────────────────────────────
# yfinance fallback
# ─────────────────────────────────────────────

def _yfinance_current_price(symbol: str):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None)
        if fast_info:
            last_price = fast_info.get("last_price")
            if last_price:
                return round(float(last_price), 2)
        hist = ticker.history(period="5d", interval="1d")
        if hist.empty:
            return None
        return round(float(hist.iloc[-1]["Close"]), 2)
    except Exception as e:
        print(f"yfinance current price error for {symbol}: {e}")
        return None


def _yfinance_daily_change(symbol: str):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="10d", interval="1d")
        if hist.empty or len(hist) < 2:
            return None
        current = float(hist.iloc[-1]["Close"])
        prev = float(hist.iloc[-2]["Close"])
        return round(((current - prev) / prev) * 100, 2)
    except Exception as e:
        print(f"yfinance daily change error for {symbol}: {e}")
        return None


def _yfinance_market_data(symbol: str):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="90d", interval="1d")
        if hist.empty or len(hist) < 50:
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]
        current_price = float(latest["Close"])
        current_volume = int(latest["Volume"])
        prev_close = float(previous["Close"])

        last_20 = hist.tail(20)
        last_50 = hist.tail(50)

        return {
            "price": round(current_price, 2),
            "volume": current_volume,
            "avg_price_20": round(float(last_20["Close"].mean()), 2),
            "avg_price_50": round(float(last_50["Close"].mean()), 2),
            "avg_volume_20": int(float(last_20["Volume"].mean())),
            "daily_change_pct": round(((current_price - prev_close) / prev_close) * 100, 2),
        }
    except Exception as e:
        print(f"yfinance market data error for {symbol}: {e}")
        return None


# ─────────────────────────────────────────────
# Public API — same signatures as before
# ─────────────────────────────────────────────

def get_current_price(symbol: str):
    """
    Lightweight current/latest price fetch.
    Tries Schwab first, falls back to yfinance.
    """
    symbol = symbol.upper().strip()

    # Try Schwab live quote
    quote = _get_schwab_quote(symbol)
    if quote:
        price = quote.get("last_price") or quote.get("close_price")
        if price:
            return round(float(price), 2)

    # Fallback to yfinance
    return _yfinance_current_price(symbol)


def get_daily_change(symbol: str):
    """
    Fetches the latest daily percentage change.
    Tries Schwab first, falls back to yfinance.
    """
    symbol = symbol.upper().strip()

    # Try Schwab live quote
    quote = _get_schwab_quote(symbol)
    if quote and quote.get("net_change_pct") is not None:
        return round(float(quote["net_change_pct"]), 2)

    # Fallback to yfinance
    return _yfinance_daily_change(symbol)


def get_market_data(symbol: str):
    """
    Full market data fetch for the scanner.
    Tries Schwab first, falls back to yfinance.
    Returns same structure as original.
    """
    symbol = symbol.upper().strip()

    # Try Schwab
    candles = _get_schwab_history(symbol, period_days=90)

    if candles and len(candles) >= 50:
        try:
            closes = [c["close"] for c in candles]
            volumes = [c["volume"] for c in candles]

            current_price = closes[-1]
            prev_close = closes[-2]
            current_volume = volumes[-1]

            last_20_closes = closes[-20:]
            last_50_closes = closes[-50:]
            last_20_volumes = volumes[-20:]

            avg_price_20 = sum(last_20_closes) / len(last_20_closes)
            avg_price_50 = sum(last_50_closes) / len(last_50_closes)
            avg_volume_20 = sum(last_20_volumes) / len(last_20_volumes)

            daily_change_pct = ((current_price - prev_close) / prev_close) * 100

            # Relative strength vs SPY
            spy_daily_change_pct = get_daily_change("SPY")

            if spy_daily_change_pct is not None:
                relative_strength_vs_spy = round(daily_change_pct - spy_daily_change_pct, 2)
            else:
                relative_strength_vs_spy = None

            if relative_strength_vs_spy is None:
                relative_strength_label = "unknown"
                relative_strength_score = 0
            elif relative_strength_vs_spy >= 2:
                relative_strength_label = "strong_outperformer"
                relative_strength_score = 10
            elif relative_strength_vs_spy >= 1:
                relative_strength_label = "outperformer"
                relative_strength_score = 5
            elif relative_strength_vs_spy <= -2:
                relative_strength_label = "strong_underperformer"
                relative_strength_score = -10
            elif relative_strength_vs_spy <= -1:
                relative_strength_label = "underperformer"
                relative_strength_score = -5
            else:
                relative_strength_label = "market_performer"
                relative_strength_score = 0

            return {
                "symbol": symbol,
                "price": round(current_price, 2),
                "volume": current_volume,
                "avg_price_20": round(avg_price_20, 2),
                "avg_price_50": round(avg_price_50, 2),
                "avg_volume_20": int(avg_volume_20),
                "daily_change_pct": round(daily_change_pct, 2),
                "spy_daily_change_pct": spy_daily_change_pct,
                "relative_strength_vs_spy": relative_strength_vs_spy,
                "relative_strength_label": relative_strength_label,
                "relative_strength_score": relative_strength_score,
                "data_source": "schwab",
            }

        except Exception as e:
            print(f"Schwab data processing error for {symbol}: {e}")

    # Fallback to yfinance
    print(f"Falling back to yfinance for {symbol}")
    yf_data = _yfinance_market_data(symbol)

    if yf_data is None:
        print(f"Error fetching data for {symbol}")
        return None

    # Get relative strength vs SPY
    spy_daily_change_pct = get_daily_change("SPY")
    daily_change_pct = yf_data["daily_change_pct"]

    if spy_daily_change_pct is not None:
        relative_strength_vs_spy = round(daily_change_pct - spy_daily_change_pct, 2)
    else:
        relative_strength_vs_spy = None

    if relative_strength_vs_spy is None:
        relative_strength_label = "unknown"
        relative_strength_score = 0
    elif relative_strength_vs_spy >= 2:
        relative_strength_label = "strong_outperformer"
        relative_strength_score = 10
    elif relative_strength_vs_spy >= 1:
        relative_strength_label = "outperformer"
        relative_strength_score = 5
    elif relative_strength_vs_spy <= -2:
        relative_strength_label = "strong_underperformer"
        relative_strength_score = -10
    elif relative_strength_vs_spy <= -1:
        relative_strength_label = "underperformer"
        relative_strength_score = -5
    else:
        relative_strength_label = "market_performer"
        relative_strength_score = 0

    return {
        "symbol": symbol,
        **yf_data,
        "spy_daily_change_pct": spy_daily_change_pct,
        "relative_strength_vs_spy": relative_strength_vs_spy,
        "relative_strength_label": relative_strength_label,
        "relative_strength_score": relative_strength_score,
        "data_source": "yfinance_fallback",
    }
