import yfinance as yf


def get_stock_data(symbol: str):
    try:
        ticker = yf.Ticker(symbol)

        # Get recent daily data
        hist = ticker.history(period="30d", interval="1d")

        if hist.empty or len(hist) < 20:
            print(f"Not enough data for {symbol}")
            return None

        latest = hist.iloc[-1]
        previous = hist.iloc[-2]

        current_price = float(latest["Close"])
        current_volume = int(latest["Volume"])
        prev_close = float(previous["Close"])

        last_20 = hist.tail(20)

        avg_price_20 = float(last_20["Close"].mean())
        avg_volume_20 = float(last_20["Volume"].mean())

        daily_change_pct = ((current_price - prev_close) / prev_close) * 100

        return {
            "price": current_price,
            "volume": current_volume,
            "avg_price_20": avg_price_20,
            "avg_volume_20": avg_volume_20,
            "daily_change_pct": daily_change_pct
        }

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None