"""
TradeLayer Position Sizing Intelligence Engine

Purpose:
Add conservative probability-aware sizing guidance without turning TradeLayer
into an aggressive Kelly-sizing system.

Core principles:
- Never use full Kelly directly.
- Reduce sizing when sample size is small.
- Reduce sizing when volatility or environment risk is elevated.
- Preserve the existing risk engine exposure caps.
- Treat probability estimates as decision-support inputs, not certainty.
"""


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = (
                value.replace("$", "")
                .replace(",", "")
                .replace("(", "-")
                .replace(")", "")
                .replace("%", "")
                .strip()
            )

        return float(value)

    except (TypeError, ValueError):
        return default


def clamp(value, low, high):
    return max(low, min(high, value))


def infer_confidence_probability(
    trade_score=None,
    signal_win_rate=None,
    sample_size=0,
    market_environment=None,
):
    """
    Estimates a conservative win probability.

    This is intentionally cautious. When sample size is small, TradeLayer
    pulls probability toward 50% instead of over-trusting early results.
    """

    score = safe_float(trade_score, 50)
    win_rate = safe_float(signal_win_rate, 50)
    sample_size = int(safe_float(sample_size, 0))

    if score > 100:
        score_probability = clamp(0.50 + ((score - 100) / 300), 0.45, 0.68)
    else:
        score_probability = clamp(score / 100, 0.45, 0.62)

    observed_probability = clamp(win_rate / 100, 0.35, 0.70)

    if sample_size < 10:
        sample_weight = 0.15
    elif sample_size < 30:
        sample_weight = 0.35
    else:
        sample_weight = 0.55

    blended = (observed_probability * sample_weight) + (score_probability * (1 - sample_weight))

    environment_text = str(market_environment or "").lower()

    if any(term in environment_text for term in ["hostile", "risk-off", "unstable", "defensive", "avoid"]):
        blended -= 0.05
    elif any(term in environment_text for term in ["mixed", "neutral", "selective", "compression"]):
        blended -= 0.02
    elif any(term in environment_text for term in ["supportive", "risk-on", "trend", "bullish"]):
        blended += 0.01

    return round(clamp(blended, 0.35, 0.70), 4)


def classify_sample_confidence(sample_size):
    sample_size = int(safe_float(sample_size, 0))

    if sample_size < 10:
        return {
            "label": "EARLY SAMPLE",
            "multiplier": 0.50,
            "note": "Signal sample is small, so TradeLayer reduces probability-based sizing.",
        }

    if sample_size < 30:
        return {
            "label": "DEVELOPING SAMPLE",
            "multiplier": 0.70,
            "note": "Signal sample is developing. Sizing remains below full model output.",
        }

    return {
        "label": "USABLE SAMPLE",
        "multiplier": 0.85,
        "note": "Signal sample is more useful, but TradeLayer still avoids full Kelly sizing.",
    }


def classify_volatility_adjustment(volatility_state=None):
    text = str(volatility_state or "").lower()

    if any(term in text for term in ["stress", "high", "elevated", "unstable"]):
        return {
            "label": "ELEVATED",
            "multiplier": 0.50,
            "note": "Volatility is elevated, so suggested risk is reduced.",
        }

    if any(term in text for term in ["compression", "low"]):
        return {
            "label": "COMPRESSION",
            "multiplier": 0.80,
            "note": "Low volatility can hide expansion risk, so sizing remains controlled.",
        }

    if any(term in text for term in ["normal", "stable"]):
        return {
            "label": "NORMAL",
            "multiplier": 1.00,
            "note": "Volatility appears normal. No extra volatility reduction applied.",
        }

    return {
        "label": "UNKNOWN",
        "multiplier": 0.75,
        "note": "Volatility state is unclear, so TradeLayer applies a conservative reduction.",
    }


def classify_environment_adjustment(environment=None):
    text = str(environment or "").lower()

    if any(term in text for term in ["hostile", "risk-off", "panic", "unstable", "breakdown", "avoid"]):
        return {
            "label": "DEFENSIVE",
            "multiplier": 0.50,
            "note": "Environment is defensive or unstable, so risk is reduced materially.",
        }

    if any(term in text for term in ["overextended", "chase", "extended"]):
        return {
            "label": "EXTENDED",
            "multiplier": 0.65,
            "note": "Setup appears extended, so TradeLayer reduces chase risk.",
        }

    if any(term in text for term in ["mixed", "neutral", "selective", "range"]):
        return {
            "label": "SELECTIVE",
            "multiplier": 0.80,
            "note": "Environment is selective, so sizing remains below the base risk level.",
        }

    if any(term in text for term in ["supportive", "risk-on", "constructive", "trend", "bullish"]):
        return {
            "label": "SUPPORTIVE",
            "multiplier": 1.00,
            "note": "Environment is supportive. No environment reduction applied.",
        }

    return {
        "label": "UNKNOWN",
        "multiplier": 0.85,
        "note": "Environment is unclear, so TradeLayer applies a modest reduction.",
    }


def calculate_kelly_fraction(probability, payoff_ratio):
    """
    Kelly formula:
    f* = (b*p - q) / b

    p = win probability
    q = losing probability
    b = payoff ratio

    This function returns full Kelly mathematically, but the final engine
    uses only fractional Kelly and caps it aggressively.
    """

    p = clamp(safe_float(probability, 0.50), 0.01, 0.99)
    b = safe_float(payoff_ratio, 1.0)

    if b <= 0:
        return 0.0

    q = 1 - p
    full_kelly = ((b * p) - q) / b

    return round(max(0.0, full_kelly), 4)


def build_position_sizing_intelligence(
    account_value,
    base_risk_percent,
    entry_price,
    stop_price,
    target_price=None,
    trade_score=None,
    signal_win_rate=None,
    signal_sample_size=0,
    market_environment=None,
    volatility_state=None,
    max_risk_percent=None,
):
    """
    Returns conservative sizing guidance to be layered on top of the existing
    fixed-fraction risk plan.
    """

    account_value = safe_float(account_value)
    base_risk_percent = safe_float(base_risk_percent)
    entry_price = safe_float(entry_price)
    stop_price = safe_float(stop_price)
    target_price = safe_float(target_price, None)
    max_risk_percent = safe_float(max_risk_percent, base_risk_percent)

    risk_per_share = max(0.0, entry_price - stop_price)

    if target_price and target_price > entry_price and risk_per_share > 0:
        reward_per_share = target_price - entry_price
        payoff_ratio = reward_per_share / risk_per_share
    else:
        payoff_ratio = 1.5

    probability = infer_confidence_probability(
        trade_score=trade_score,
        signal_win_rate=signal_win_rate,
        sample_size=signal_sample_size,
        market_environment=market_environment,
    )

    full_kelly = calculate_kelly_fraction(probability, payoff_ratio)
    fractional_kelly = full_kelly * 0.25

    sample_adjustment = classify_sample_confidence(signal_sample_size)
    volatility_adjustment = classify_volatility_adjustment(volatility_state)
    environment_adjustment = classify_environment_adjustment(market_environment)

    adjusted_risk_percent = base_risk_percent
    adjusted_risk_percent *= sample_adjustment["multiplier"]
    adjusted_risk_percent *= volatility_adjustment["multiplier"]
    adjusted_risk_percent *= environment_adjustment["multiplier"]

    kelly_risk_percent = fractional_kelly * 100

    final_risk_percent = min(
        base_risk_percent,
        max_risk_percent,
        adjusted_risk_percent,
        kelly_risk_percent if kelly_risk_percent > 0 else adjusted_risk_percent,
    )

    final_risk_percent = clamp(final_risk_percent, 0.0, max_risk_percent)

    final_risk_dollars = account_value * (final_risk_percent / 100)

    warnings = []

    if full_kelly <= 0:
        warnings.append("Kelly estimate is zero or negative. TradeLayer would not increase risk based on probability math.")

    if signal_sample_size < 10:
        warnings.append("Signal sample is small. Probability-based sizing is heavily reduced.")

    if final_risk_percent < base_risk_percent:
        warnings.append("Final risk is below the requested base risk because TradeLayer applied conservative sizing filters.")

    return {
        "status": "ok",
        "engine": "TradeLayer Position Sizing Intelligence V1",
        "base_risk_percent": round(base_risk_percent, 2),
        "max_risk_percent": round(max_risk_percent, 2),
        "estimated_win_probability": round(probability * 100, 2),
        "payoff_ratio": round(payoff_ratio, 2),
        "full_kelly_fraction": round(full_kelly, 4),
        "full_kelly_percent": round(full_kelly * 100, 2),
        "fractional_kelly_fraction": round(fractional_kelly, 4),
        "fractional_kelly_percent": round(fractional_kelly * 100, 2),
        "sample_confidence": sample_adjustment,
        "volatility_filter": volatility_adjustment,
        "environment_filter": environment_adjustment,
        "kelly_risk_percent": round(kelly_risk_percent, 2),
        "adjusted_risk_percent": round(adjusted_risk_percent, 2),
        "final_risk_percent": round(final_risk_percent, 2),
        "final_risk_dollars": round(final_risk_dollars, 2),
        "warnings": warnings,
        "summary": (
            f"TradeLayer reduced the requested {round(base_risk_percent, 2)}% risk "
            f"to {round(final_risk_percent, 2)}% using conservative fractional Kelly, "
            f"sample-size, volatility, and environment filters."
        ),
    }
