"""
TradeLayer Position Guidance Engine

Purpose:
Evaluate open positions through a risk-control and consistency lens.

This engine is intentionally NOT a prediction engine.
It is a position lifecycle manager.

Core philosophy:
- Preserve capital
- Protect gains
- Avoid unstable environments
- Avoid chasing extended positions
- Favor consistent, repeatable risk-adjusted decisions
"""


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_unrealized_pl(unrealized_pl_percent):
    unrealized_pl_percent = safe_float(unrealized_pl_percent)

    if unrealized_pl_percent >= 10:
        return "large_gain"
    if unrealized_pl_percent >= 5:
        return "moderate_gain"
    if unrealized_pl_percent >= 1:
        return "small_gain"
    if unrealized_pl_percent <= -8:
        return "large_loss"
    if unrealized_pl_percent <= -4:
        return "moderate_loss"
    if unrealized_pl_percent < 0:
        return "small_loss"

    return "flat"


def classify_price_position(entry_price, current_price):
    entry_price = safe_float(entry_price)
    current_price = safe_float(current_price)

    if entry_price <= 0 or current_price <= 0:
        return "unknown"

    move_percent = ((current_price - entry_price) / entry_price) * 100

    if move_percent >= 10:
        return "extended_above_entry"
    if move_percent >= 5:
        return "working_above_entry"
    if move_percent <= -8:
        return "materially_below_entry"
    if move_percent <= -4:
        return "below_entry"

    return "near_entry"


def classify_environment(market_state):
    if not market_state:
        return "unknown"

    normalized = str(market_state).lower()

    if any(term in normalized for term in ["unstable", "panic", "risk-off", "high-risk", "breakdown"]):
        return "hostile"

    if any(term in normalized for term in ["overextended", "chase", "extended"]):
        return "extended"

    if any(term in normalized for term in ["range", "neutral", "compression", "mixed"]):
        return "neutral"

    if any(term in normalized for term in ["trend", "bullish", "breakout", "constructive", "risk-on"]):
        return "supportive"

    return "unknown"


def classify_relative_strength(relative_strength):
    if relative_strength is None:
        return "unknown"

    rs = safe_float(relative_strength)

    if rs >= 2:
        return "strong"
    if rs >= 0.5:
        return "positive"
    if rs <= -2:
        return "weak"
    if rs <= -0.5:
        return "negative"

    return "neutral"


def score_position_risk(
    unrealized_class,
    price_position,
    environment_class,
    relative_strength_class,
):
    risk_score = 0
    reasons = []

    # P/L condition
    if unrealized_class == "large_loss":
        risk_score += 35
        reasons.append("Position is showing a large unrealized loss.")
    elif unrealized_class == "moderate_loss":
        risk_score += 22
        reasons.append("Position is showing a moderate unrealized loss.")
    elif unrealized_class == "large_gain":
        risk_score += 8
        reasons.append("Position has a large unrealized gain that may warrant profit protection.")

    # Price structure
    if price_position == "materially_below_entry":
        risk_score += 30
        reasons.append("Current price is materially below entry.")
    elif price_position == "below_entry":
        risk_score += 18
        reasons.append("Current price is below entry.")
    elif price_position == "extended_above_entry":
        risk_score += 10
        reasons.append("Position is extended above entry; avoid complacency and protect gains.")

    # Environment
    if environment_class == "hostile":
        risk_score += 35
        reasons.append("Market environment appears hostile or unstable.")
    elif environment_class == "extended":
        risk_score += 18
        reasons.append("Market environment appears extended; chasing risk is elevated.")
    elif environment_class == "neutral":
        risk_score += 8
        reasons.append("Market environment is neutral or mixed.")
    elif environment_class == "supportive":
        risk_score -= 8
        reasons.append("Market environment appears supportive.")

    # Relative strength
    if relative_strength_class == "weak":
        risk_score += 25
        reasons.append("Relative strength is weak versus benchmark.")
    elif relative_strength_class == "negative":
        risk_score += 14
        reasons.append("Relative strength is negative versus benchmark.")
    elif relative_strength_class == "strong":
        risk_score -= 10
        reasons.append("Relative strength is strong versus benchmark.")
    elif relative_strength_class == "positive":
        risk_score -= 5
        reasons.append("Relative strength is positive versus benchmark.")

    risk_score = max(0, min(100, risk_score))

    return risk_score, reasons


def classify_risk_level(risk_score):
    if risk_score >= 75:
        return "HIGH"
    if risk_score >= 50:
        return "ELEVATED"
    if risk_score >= 25:
        return "MODERATE"

    return "LOW"


def generate_guidance_action(
    risk_score,
    unrealized_class,
    price_position,
    environment_class,
    relative_strength_class,
):
    if risk_score >= 75:
        return {
            "guidance": "EXIT OR REDUCE",
            "position_status": "BROKEN / HIGH RISK",
            "actionability": "Reduce exposure or exit if the original trade thesis is no longer valid.",
        }

    if risk_score >= 50:
        return {
            "guidance": "TIGHTEN RISK",
            "position_status": "DETERIORATING",
            "actionability": "Review stop level, avoid adding, and consider reducing exposure.",
        }

    if unrealized_class in ["large_gain", "moderate_gain"] and environment_class in ["extended", "hostile"]:
        return {
            "guidance": "TRIM / PROTECT PROFITS",
            "position_status": "PROFIT PROTECTION",
            "actionability": "Consider trimming or raising stop because gains exist while environment risk is elevated.",
        }

    if unrealized_class == "large_gain":
        return {
            "guidance": "HOLD WITH TRAILING STOP",
            "position_status": "WINNER / MANAGE ACTIVELY",
            "actionability": "Keep the winner working, but protect gains with a disciplined trailing stop.",
        }

    if (
        environment_class == "supportive"
        and relative_strength_class in ["strong", "positive"]
        and unrealized_class not in ["moderate_loss", "large_loss"]
        and price_position not in ["materially_below_entry"]
    ):
        return {
            "guidance": "HOLD",
            "position_status": "HEALTHY",
            "actionability": "No adjustment needed. Trend and environment remain acceptable.",
        }

    if unrealized_class in ["small_loss", "flat"] and environment_class in ["neutral", "unknown"]:
        return {
            "guidance": "HOLD / MONITOR",
            "position_status": "NEUTRAL",
            "actionability": "Position is not broken, but there is not enough confirmation to add.",
        }

    if unrealized_class in ["moderate_loss", "large_loss"]:
        return {
            "guidance": "AVOID ADDING",
            "position_status": "UNDER PRESSURE",
            "actionability": "Do not average down unless the broader setup improves and risk is clearly defined.",
        }

    return {
        "guidance": "HOLD / MONITOR",
        "position_status": "WATCH",
        "actionability": "Continue monitoring. No strong adjustment signal detected.",
    }


def build_guidance_reason(
    guidance_action,
    risk_level,
    risk_score,
    risk_reasons,
    unrealized_class,
    price_position,
    environment_class,
    relative_strength_class,
):
    primary_reason = (
        f"TradeLayer classifies this position as {guidance_action['position_status']} "
        f"with {risk_level} risk. Risk score: {risk_score}/100."
    )

    context = (
        f"P/L profile: {unrealized_class}. "
        f"Price position: {price_position}. "
        f"Market environment: {environment_class}. "
        f"Relative strength: {relative_strength_class}."
    )

    if risk_reasons:
        explanation = " ".join(risk_reasons[:4])
    else:
        explanation = "No major risk deterioration signals were detected."

    return f"{primary_reason} {context} {explanation}"


def get_position_guidance(
    symbol,
    entry_price,
    current_price,
    unrealized_pl=None,
    unrealized_pl_percent=None,
    market_state=None,
    relative_strength=None,
):
    """
    Main public function used by the portfolio endpoint.

    Returns a structured guidance object designed for dashboard display.
    """

    symbol = str(symbol or "").upper().strip()
    entry_price = safe_float(entry_price)
    current_price = safe_float(current_price)

    if current_price <= 0 or entry_price <= 0:
        return {
            "guidance": "PRICE UNAVAILABLE",
            "position_status": "UNKNOWN",
            "risk_level": "UNKNOWN",
            "risk_score": None,
            "actionability": "Unable to evaluate position because price data is unavailable.",
            "guidance_reason": "TradeLayer could not calculate position guidance because entry or current price was missing.",
            "time_horizon": "Unknown",
            "exit_strategy": "Wait for valid price data before making position decisions.",
        }

    unrealized_class = classify_unrealized_pl(unrealized_pl_percent)
    price_position = classify_price_position(entry_price, current_price)
    environment_class = classify_environment(market_state)
    relative_strength_class = classify_relative_strength(relative_strength)

    risk_score, risk_reasons = score_position_risk(
        unrealized_class=unrealized_class,
        price_position=price_position,
        environment_class=environment_class,
        relative_strength_class=relative_strength_class,
    )

    risk_level = classify_risk_level(risk_score)

    guidance_action = generate_guidance_action(
        risk_score=risk_score,
        unrealized_class=unrealized_class,
        price_position=price_position,
        environment_class=environment_class,
        relative_strength_class=relative_strength_class,
    )

    if guidance_action["guidance"] in ["EXIT OR REDUCE", "TIGHTEN RISK"]:
        time_horizon = "Short-term risk control"
    elif guidance_action["guidance"] in ["TRIM / PROTECT PROFITS", "HOLD WITH TRAILING STOP"]:
        time_horizon = "Active winner management"
    elif guidance_action["guidance"] == "HOLD":
        time_horizon = "Hold while trend remains intact"
    else:
        time_horizon = "Monitor"

    if guidance_action["guidance"] == "EXIT OR REDUCE":
        exit_strategy = "Exit or reduce if price action confirms thesis failure. Do not wait for a larger loss without a defined reason."
    elif guidance_action["guidance"] == "TIGHTEN RISK":
        exit_strategy = "Tighten stop discipline and avoid adding. Reduce if weakness continues."
    elif guidance_action["guidance"] == "TRIM / PROTECT PROFITS":
        exit_strategy = "Consider taking partial profit and keeping a smaller position with a defined trailing stop."
    elif guidance_action["guidance"] == "HOLD WITH TRAILING STOP":
        exit_strategy = "Let the position work, but trail risk to protect gains."
    elif guidance_action["guidance"] == "HOLD":
        exit_strategy = "Hold while structure remains healthy. Reassess if RS weakens, volatility expands, or price breaks trend."
    else:
        exit_strategy = "Monitor closely. Do not add until structure improves."

    guidance_reason = build_guidance_reason(
        guidance_action=guidance_action,
        risk_level=risk_level,
        risk_score=risk_score,
        risk_reasons=risk_reasons,
        unrealized_class=unrealized_class,
        price_position=price_position,
        environment_class=environment_class,
        relative_strength_class=relative_strength_class,
    )

    return {
        "symbol": symbol,
        "guidance": guidance_action["guidance"],
        "position_status": guidance_action["position_status"],
        "risk_level": risk_level,
        "risk_score": risk_score,
        "actionability": guidance_action["actionability"],
        "guidance_reason": guidance_reason,
        "time_horizon": time_horizon,
        "exit_strategy": exit_strategy,
        "inputs": {
            "unrealized_class": unrealized_class,
            "price_position": price_position,
            "environment_class": environment_class,
            "relative_strength_class": relative_strength_class,
            "market_state": market_state,
            "relative_strength": relative_strength,
        },
    }