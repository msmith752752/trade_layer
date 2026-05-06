from app.options_engine import get_options_pressure


def generate_trade_signal(symbol: str, data: dict):

    price = data["price"]
    volume = data["volume"]
    avg_price_20 = data["avg_price_20"]
    avg_price_50 = data["avg_price_50"]
    avg_volume_20 = data["avg_volume_20"]
    daily_change = data["daily_change_pct"]

    conditions = {
        "price_range": 20 < price < 500,
        "above_20_ma": price > avg_price_20,
        "above_50_ma": price > avg_price_50,
        "bullish_trend_structure": avg_price_20 > avg_price_50,
        "volume_spike": volume > (1.5 * avg_volume_20),
        "momentum": daily_change > 1,
        "liquidity": avg_volume_20 > 1_000_000
    }

    entry = round(price, 2)
    stop_loss = round(price * 0.98, 2)
    target = round(price * 1.03, 2)

    # -----------------------------
    # Technical score
    # -----------------------------
    technical_score = 0

    if conditions["price_range"]:
        technical_score += 15

    if conditions["above_20_ma"]:
        technical_score += 15

    if conditions["above_50_ma"]:
        technical_score += 15

    if conditions["bullish_trend_structure"]:
        technical_score += 15

    if conditions["liquidity"]:
        technical_score += 15

    if conditions["momentum"]:
        technical_score += 15

    if conditions["volume_spike"]:
        technical_score += 10

    # Bonus points for stronger momentum
    if daily_change > 2:
        technical_score += 5

    if daily_change > 5:
        technical_score += 5

    # -----------------------------
    # Overextension penalty
    # -----------------------------
    overextended = False

    if daily_change > 8:
        technical_score -= 10
        overextended = True

    # -----------------------------
    # Options pressure score
    # -----------------------------
    options_data = get_options_pressure(symbol, price)
    options_score = options_data.get("options_pressure_score", 0)

    # Final score
    score = technical_score + options_score

    # Risk / reward
    risk = entry - stop_loss
    reward = target - entry

    if risk > 0:
        risk_reward = round(reward / risk, 2)
    else:
        risk_reward = None

    # Signal classification
    core_long_conditions = (
        conditions["price_range"]
        and conditions["above_20_ma"]
        and conditions["above_50_ma"]
        and conditions["bullish_trend_structure"]
        and conditions["momentum"]
        and conditions["liquidity"]
    )

    strong_long_conditions = (
        core_long_conditions
        and conditions["volume_spike"]
    )

    watchlist_conditions = (
        conditions["price_range"]
        and conditions["above_20_ma"]
        and conditions["above_50_ma"]
        and conditions["liquidity"]
    )

    if strong_long_conditions:
        signal_type = "strong_long"
        confidence = "high"
        trade_suggestion = True
        reason = "Strong long setup: bullish trend structure, momentum, liquidity, and volume confirmation all pass."

    elif core_long_conditions:
        signal_type = "long"
        confidence = "medium"
        trade_suggestion = True
        reason = "Long setup: bullish trend structure, momentum, and liquidity pass. Volume spike is not confirmed."

    elif watchlist_conditions:
        signal_type = "watchlist"
        confidence = "low"
        trade_suggestion = False
        reason = "Watchlist setup: trend and liquidity pass, but momentum or volume confirmation is missing."

    else:
        signal_type = "avoid"
        confidence = "low"
        trade_suggestion = False
        reason = "Avoid: setup does not meet minimum trend and momentum conditions."

    # -----------------------------
    # Trade timeframe guidance
    # -----------------------------
    if overextended:
        trade_timeframe = "same_day_only"
        expected_hold = "Hours to 1 trading day"
        exit_rule = "Avoid chasing strength. Consider faster profit-taking due to elevated volatility."

    elif strong_long_conditions:
        trade_timeframe = "short_swing"
        expected_hold = "1 to 3 trading days"
        exit_rule = "Exit at target, stop loss, or if momentum weakens."

    elif core_long_conditions:
        trade_timeframe = "swing_trade"
        expected_hold = "2 to 5 trading days"
        exit_rule = "Exit at target, stop loss, or if price loses trend structure."

    elif watchlist_conditions:
        trade_timeframe = "watchlist"
        expected_hold = "Wait for confirmation"
        exit_rule = "Monitor for momentum and/or volume confirmation before entry."

    else:
        trade_timeframe = "no_trade"
        expected_hold = "No position suggested"
        exit_rule = "Avoid entering until conditions improve."

    if signal_type == "strong_long":
        rank_reason = "Highest quality setup: trend, momentum, liquidity, volume, and options overlay evaluated."
    elif signal_type == "long":
        rank_reason = "Good setup: bullish trend and momentum pass, but volume spike is missing."
    elif signal_type == "watchlist":
        rank_reason = "Close setup: trend/liquidity pass, but missing momentum and/or volume confirmation."
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
        "technical_score": technical_score,
        "options_score": options_score,
        "risk_reward": risk_reward,

        # Trade timeframe guidance
        "trade_timeframe": trade_timeframe,
        "expected_hold": expected_hold,
        "exit_rule": exit_rule,
        "overextended": overextended,

        # Trend data
        "avg_price_20": round(avg_price_20, 2),
        "avg_price_50": round(avg_price_50, 2),

        # Options positioning data
        "options_pressure": options_data.get("options_pressure"),
        "options_pressure_score": options_data.get("options_pressure_score"),
        "options_summary": options_data.get("options_summary"),
        "put_call_volume_ratio": options_data.get("put_call_volume_ratio"),
        "total_call_volume": options_data.get("total_call_volume"),
        "total_put_volume": options_data.get("total_put_volume"),
        "total_call_open_interest": options_data.get("total_call_open_interest"),
        "total_put_open_interest": options_data.get("total_put_open_interest"),
        "largest_call_oi_strike": options_data.get("largest_call_oi_strike"),
        "largest_put_oi_strike": options_data.get("largest_put_oi_strike"),
        "options_expiration_used": options_data.get("expiration_used"),

        # Trade plan context fields
        "entry_type": "market",
        "strategy": "momentum continuation with options-positioning overlay",
        "trade_plan_quality": "trend_momentum_options_pressure_model",

        "rank_reason": rank_reason,
        "conditions": conditions,
        "daily_change_pct": round(daily_change, 2),
        "avg_volume_20": int(avg_volume_20),
        "reason": reason
    }