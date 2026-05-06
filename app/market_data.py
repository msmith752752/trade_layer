import yfinance as yf


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

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "volume": current_volume,
            "avg_price_20": round(avg_price_20, 2),
            "avg_price_50": round(avg_price_50, 2),
            "avg_volume_20": int(avg_volume_20),
            "daily_change_pct": round(daily_change_pct, 2)
        }

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None