import yfinance as yf


def get_daily_change(symbol: str):
    """
    Fetches the latest daily percentage change for a symbol.
    Used for SPY comparison / relative strength.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="10d", interval="1d")

        if hist.empty or len(hist) < 2:
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]

        current_price = float(latest["Close"])
        prev_close = float(previous["Close"])

        daily_change_pct = ((current_price - prev_close) / prev_close) * 100
        return round(daily_change_pct, 2)

    except Exception as e:
        print(f"Error fetching daily change for {symbol}: {e}")
        return None


def get_market_data(symbol: str):
    try:
        symbol = symbol.upper().strip()
        ticker = yf.Ticker(symbol)

        # Get enough daily data for 20-day and 50-day trend checks
        hist = ticker.history(period="90d", interval="1d")

        if hist.empty or len(hist) < 50:
            print(f"Not enough data for {symbol}")
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]

        current_price = float(latest["Close"])
        current_volume = int(latest["Volume"])
        prev_close = float(previous["Close"])

        last_20 = hist.tail(20)
        last_50 = hist.tail(50)

        avg_price_20 = float(last_20["Close"].mean())
        avg_price_50 = float(last_50["Close"].mean())
        avg_volume_20 = float(last_20["Volume"].mean())

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

            # New relative strength fields
            "spy_daily_change_pct": spy_daily_change_pct,
            "relative_strength_vs_spy": relative_strength_vs_spy,
            "relative_strength_label": relative_strength_label,
            "relative_strength_score": relative_strength_score,
        }

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None