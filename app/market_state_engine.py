def classify_market_state(data: dict):

    price = data["price"]
    avg_price_20 = data["avg_price_20"]
    avg_price_50 = data["avg_price_50"]
    daily_change = data["daily_change_pct"]

    # ---------------------------------
    # Trend structure
    # ---------------------------------
    above_20 = price > avg_price_20
    above_50 = price > avg_price_50
    bullish_structure = avg_price_20 > avg_price_50

    # ---------------------------------
    # Basic market state classification
    # ---------------------------------

    market_state = "neutral"
    environment_score = 50
    state_reason = "No strong market condition detected."

    # ---------------------------------
    # Overextended / chasing
    # ---------------------------------
    if daily_change > 8:
        market_state = "overextended_chase"
        environment_score = 20
        state_reason = (
            "Price is significantly extended intraday. "
            "Elevated chase risk and volatility expansion detected."
        )

    # ---------------------------------
    # Strong trend continuation
    # ---------------------------------
    elif (
        above_20
        and above_50
        and bullish_structure
        and daily_change > 1
    ):
        market_state = "trend_continuation"
        environment_score = 85
        state_reason = (
            "Bullish trend structure and momentum continuation detected."
        )

    # ---------------------------------
    # Breakout expansion
    # ---------------------------------
    elif (
        above_20
        and above_50
        and daily_change > 4
    ):
        market_state = "breakout_expansion"
        environment_score = 75
        state_reason = (
            "Momentum expansion and directional breakout conditions detected."
        )

    # ---------------------------------
    # Range-bound / compression
    # ---------------------------------
    elif abs(daily_change) < 1:
        market_state = "volatility_compression"
        environment_score = 70
        state_reason = (
            "Price action appears compressed with limited directional movement."
        )

    # ---------------------------------
    # Weak / unstable
    # ---------------------------------
    elif (
        price < avg_price_20
        and price < avg_price_50
    ):
        market_state = "unstable_high_risk"
        environment_score = 25
        state_reason = (
            "Weak trend structure detected. Higher risk environment."
        )

    return {
        "market_state": market_state,
        "environment_score": environment_score,
        "state_reason": state_reason
    }