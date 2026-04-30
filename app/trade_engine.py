def generate_trade_signal(symbol: str, data: dict):

    price = data["price"]
    volume = data["volume"]
    avg_price_20 = data["avg_price_20"]
    avg_volume_20 = data["avg_volume_20"]
    daily_change = data["daily_change_pct"]

    conditions = {
        "price_range": 20 < price < 500,
        "above_ma": price > avg_price_20,
        "volume_spike": volume > (1.5 * avg_volume_20),
        "momentum": daily_change > 1,
        "liquidity": avg_volume_20 > 1_000_000
    }

    entry = round(price, 2)
    stop_loss = round(price * 0.98, 2)
    target = round(price * 1.03, 2)

    # Base ranking score
    score = 0

    if conditions["price_range"]:
        score += 20

    if conditions["above_ma"]:
        score += 20

    if conditions["liquidity"]:
        score += 20

    if conditions["momentum"]:
        score += 20

    if conditions["volume_spike"]:
        score += 20

    # Bonus points for stronger momentum
    if daily_change > 2:
        score += 5

    if daily_change > 5:
        score += 5

    # Risk / reward
    risk = entry - stop_loss
    reward = target - entry

    if risk > 0:
        risk_reward = round(reward / risk, 2)
    else:
        risk_reward = None

    if all(conditions.values()):
        signal_type = "strong_long"
        confidence = "high"
        trade_suggestion = True
        reason = "Strong long setup: price, trend, volume, momentum, and liquidity conditions all pass."

    elif (
        conditions["price_range"]
        and conditions["above_ma"]
        and conditions["momentum"]
        and conditions["liquidity"]
    ):
        signal_type = "long"
        confidence = "medium"
        trade_suggestion = True
        reason = "Long setup: price, trend, momentum, and liquidity pass. Volume spike is not confirmed."

    elif (
        conditions["price_range"]
        and conditions["above_ma"]
        and conditions["liquidity"]
    ):
        signal_type = "watchlist"
        confidence = "low"
        trade_suggestion = False
        reason = "Watchlist setup: price, trend, and liquidity pass, but momentum or volume confirmation is missing."

    else:
        signal_type = "avoid"
        confidence = "low"
        trade_suggestion = False
        reason = "Avoid: setup does not meet minimum trade conditions."

    if signal_type == "strong_long":
        rank_reason = "Highest quality setup: all core conditions passed."
    elif signal_type == "long":
        rank_reason = "Good setup, but missing volume spike confirmation."
    elif signal_type == "watchlist":
        rank_reason = "Close setup, but missing momentum and/or volume confirmation."
    else:
        rank_reason = "Weak setup. Does not meet minimum trade criteria."

    return {
        "symbol": symbol.upper(),
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "confidence": confidence,
        "signal_type": signal_type,
        "trade_suggestion": trade_suggestion,
        "score": score,
        "risk_reward": risk_reward,
        "rank_reason": rank_reason,
        "conditions": conditions,
        "daily_change_pct": round(daily_change, 2),
        "avg_volume_20": int(avg_volume_20),
        "reason": reason
    }