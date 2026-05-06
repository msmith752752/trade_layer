import yfinance as yf


def get_options_pressure(symbol: str, current_price: float):
    """
    Options-positioning analysis for TradeLayer V2.

    Purpose:
    Options data should CONFIRM price action, not overpower it.

    Phase 2 metrics:
    - total call volume
    - total put volume
    - put/call volume ratio
    - largest call open-interest strike
    - largest put open-interest strike
    - balanced options pressure score
    """

    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options

        if not expirations:
            return _empty_options_result("No options expirations found.")

        nearest_expiration = expirations[0]
        chain = ticker.option_chain(nearest_expiration)

        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return _empty_options_result("Options chain was empty.")

        total_call_volume = int(calls["volume"].fillna(0).sum())
        total_put_volume = int(puts["volume"].fillna(0).sum())

        total_call_oi = int(calls["openInterest"].fillna(0).sum())
        total_put_oi = int(puts["openInterest"].fillna(0).sum())

        if total_call_volume > 0:
            put_call_volume_ratio = round(total_put_volume / total_call_volume, 2)
        else:
            put_call_volume_ratio = None

        largest_call_row = calls.sort_values("openInterest", ascending=False).head(1)
        largest_put_row = puts.sort_values("openInterest", ascending=False).head(1)

        largest_call_oi_strike = (
            float(largest_call_row.iloc[0]["strike"])
            if not largest_call_row.empty
            else None
        )

        largest_put_oi_strike = (
            float(largest_put_row.iloc[0]["strike"])
            if not largest_put_row.empty
            else None
        )

        score = 0
        pressure = "neutral"
        summary = "Options positioning is neutral or mixed."

        # -----------------------------
        # Volume-based options pressure
        # -----------------------------
        # Lower put/call ratio = more call-heavy = bullish.
        # Higher put/call ratio = more put-heavy = bearish.
        # Keep this score modest so options flow confirms price action
        # instead of overpowering it.

        if put_call_volume_ratio is not None:
            if put_call_volume_ratio < 0.5:
                score += 15
                pressure = "strong_bullish"
                summary = "Options flow is strongly bullish: call volume is far higher than put volume."

            elif put_call_volume_ratio < 0.7:
                score += 10
                pressure = "bullish"
                summary = "Options flow is bullish: call volume is meaningfully higher than put volume."

            elif put_call_volume_ratio > 1.5:
                score -= 15
                pressure = "strong_bearish"
                summary = "Options flow is strongly bearish: put volume is far higher than call volume."

            elif put_call_volume_ratio > 1.2:
                score -= 10
                pressure = "bearish"
                summary = "Options flow is bearish: put volume is meaningfully higher than call volume."

        # -----------------------------
        # Open-interest confirmation
        # -----------------------------
        # OI is slower-moving than volume, so give it a smaller weight.

        if total_call_oi > total_put_oi * 1.5:
            score += 5
        elif total_put_oi > total_call_oi * 1.5:
            score -= 5

        return {
            "has_options_data": True,
            "expiration_used": nearest_expiration,
            "options_pressure": pressure,
            "options_pressure_score": score,
            "options_summary": summary,
            "put_call_volume_ratio": put_call_volume_ratio,
            "total_call_volume": total_call_volume,
            "total_put_volume": total_put_volume,
            "total_call_open_interest": total_call_oi,
            "total_put_open_interest": total_put_oi,
            "largest_call_oi_strike": largest_call_oi_strike,
            "largest_put_oi_strike": largest_put_oi_strike,
            "current_price": round(current_price, 2),
        }

    except Exception as e:
        return _empty_options_result(f"Options data unavailable: {str(e)}")


def _empty_options_result(reason: str):
    return {
        "has_options_data": False,
        "expiration_used": None,
        "options_pressure": "unavailable",
        "options_pressure_score": 0,
        "options_summary": reason,
        "put_call_volume_ratio": None,
        "total_call_volume": 0,
        "total_put_volume": 0,
        "total_call_open_interest": 0,
        "total_put_open_interest": 0,
        "largest_call_oi_strike": None,
        "largest_put_oi_strike": None,
        "current_price": None,
    }