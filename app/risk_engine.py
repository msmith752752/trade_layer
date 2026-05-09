# app/risk_engine.py

"""
TradeLayer Risk Engine

Purpose:
Calculate position sizing through a risk-control and consistency lens.

This engine starts with classic fixed-fraction risk sizing, then adds
risk-adjusted controls for exposure, volatility, and environment quality.

Core principle:
Do not size positions only by upside potential.
Size positions by how much damage the trade can cause if wrong.
"""


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_account_exposure(position_exposure_percent: float):
    if position_exposure_percent >= 80:
        return "VERY HIGH"
    if position_exposure_percent >= 50:
        return "HIGH"
    if position_exposure_percent >= 25:
        return "MODERATE"
    return "LOW"


def classify_risk_percent(risk_percent: float):
    if risk_percent > 5:
        return "AGGRESSIVE"
    if risk_percent > 2:
        return "ELEVATED"
    if risk_percent >= 1:
        return "STANDARD"
    return "CONSERVATIVE"


def classify_environment_risk(environment: str | None):
    if not environment:
        return {
            "label": "UNKNOWN",
            "risk_multiplier": 1.0,
            "note": "No environment adjustment applied.",
        }

    normalized = str(environment).lower()

    if any(term in normalized for term in ["hostile", "panic", "risk-off", "unstable", "breakdown"]):
        return {
            "label": "HOSTILE",
            "risk_multiplier": 0.50,
            "note": "Hostile environment detected. Suggested position size reduced by 50%.",
        }

    if any(term in normalized for term in ["extended", "chase", "overextended"]):
        return {
            "label": "EXTENDED",
            "risk_multiplier": 0.70,
            "note": "Extended environment detected. Suggested position size reduced by 30%.",
        }

    if any(term in normalized for term in ["mixed", "neutral", "range", "compression"]):
        return {
            "label": "NEUTRAL",
            "risk_multiplier": 0.85,
            "note": "Neutral/mixed environment detected. Suggested position size modestly reduced.",
        }

    if any(term in normalized for term in ["supportive", "trend", "risk-on", "constructive", "bullish"]):
        return {
            "label": "SUPPORTIVE",
            "risk_multiplier": 1.0,
            "note": "Supportive environment detected. No reduction applied.",
        }

    return {
        "label": "UNKNOWN",
        "risk_multiplier": 1.0,
        "note": "Environment not recognized. No environment adjustment applied.",
    }


def calculate_risk_plan(
    account_value: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
    environment: str | None = None,
    volatility_buffer_percent: float = 0.0,
    max_exposure_percent: float = 50.0,
):
    """
    Calculates risk-adjusted position sizing.

    Inputs:
    - account_value: total account size
    - risk_percent: max account risk per trade
    - entry_price: expected entry
    - stop_price: planned stop
    - environment: optional market/trade environment descriptor
    - volatility_buffer_percent: optional extra buffer added to risk per share
    - max_exposure_percent: cap on position value as % of account

    Example:
    Account = 856.42
    Risk = 2%
    Entry = 95.63
    Stop = 93.72
    Allowed risk = 17.13
    Risk/share = 1.91
    Suggested shares = 8
    """

    account_value = safe_float(account_value)
    risk_percent = safe_float(risk_percent)
    entry_price = safe_float(entry_price)
    stop_price = safe_float(stop_price)
    volatility_buffer_percent = safe_float(volatility_buffer_percent)
    max_exposure_percent = safe_float(max_exposure_percent, 50.0)

    if account_value <= 0:
        return {
            "status": "error",
            "message": "Account value must be greater than zero.",
        }

    if risk_percent <= 0:
        return {
            "status": "error",
            "message": "Risk percent must be greater than zero.",
        }

    if entry_price <= 0 or stop_price <= 0:
        return {
            "status": "error",
            "message": "Entry and stop prices must be greater than zero.",
        }

    if max_exposure_percent <= 0:
        return {
            "status": "error",
            "message": "Max exposure percent must be greater than zero.",
        }

    base_risk_per_share = entry_price - stop_price

    if base_risk_per_share <= 0:
        return {
            "status": "error",
            "message": "Stop price must be below entry price for a long trade.",
        }

    allowed_risk_dollars = account_value * (risk_percent / 100)

    volatility_buffer_dollars = base_risk_per_share * (
        volatility_buffer_percent / 100
    )

    adjusted_risk_per_share = base_risk_per_share + volatility_buffer_dollars

    environment_result = classify_environment_risk(environment)

    base_suggested_shares = int(
        allowed_risk_dollars // adjusted_risk_per_share
    )

    environment_adjusted_shares = int(
        base_suggested_shares * environment_result["risk_multiplier"]
    )

    max_position_value = account_value * (max_exposure_percent / 100)

    max_shares_by_exposure = int(max_position_value // entry_price)

    suggested_shares = min(
        environment_adjusted_shares,
        max_shares_by_exposure
    )

    suggested_shares = max(0, suggested_shares)

    position_value = suggested_shares * entry_price

    estimated_max_loss = suggested_shares * adjusted_risk_per_share

    position_exposure_percent = (
        (position_value / account_value) * 100
        if account_value > 0
        else 0
    )

    base_position_value = base_suggested_shares * entry_price

    base_position_exposure_percent = (
        (base_position_value / account_value) * 100
        if account_value > 0
        else 0
    )

    risk_percent_classification = classify_risk_percent(risk_percent)

    exposure_classification = classify_account_exposure(
        position_exposure_percent
    )

    warnings = []

    if risk_percent > 2:
        warnings.append(
            "Risk per trade is above 2%. This may reduce consistency if losses cluster."
        )

    if position_exposure_percent > 50:
        warnings.append(
            "Position exposure is above 50% of account value. Concentration risk is high."
        )

    if base_position_exposure_percent > max_exposure_percent:
        warnings.append(
            "Base share size exceeded the max exposure cap, so TradeLayer reduced suggested shares."
        )

    if volatility_buffer_percent > 0:
        warnings.append(
            "Volatility buffer applied. Position size reduced to account for slippage or wider price movement."
        )

    if environment_result["risk_multiplier"] < 1:
        warnings.append(environment_result["note"])

    if suggested_shares == 0:
        warnings.append(
            "Suggested share size is zero because the defined risk or exposure cap is too restrictive for this setup."
        )

    return {
        "status": "ok",

        "account_value": round(account_value, 2),
        "risk_percent": round(risk_percent, 2),
        "risk_percent_classification": risk_percent_classification,

        "allowed_risk_dollars": round(allowed_risk_dollars, 2),

        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),

        "base_risk_per_share": round(base_risk_per_share, 2),
        "volatility_buffer_percent": round(volatility_buffer_percent, 2),
        "volatility_buffer_dollars": round(volatility_buffer_dollars, 2),
        "risk_per_share": round(adjusted_risk_per_share, 2),

        "base_suggested_shares": base_suggested_shares,
        "environment_adjusted_shares": environment_adjusted_shares,
        "suggested_shares": suggested_shares,

        "max_exposure_percent": round(max_exposure_percent, 2),
        "max_position_value": round(max_position_value, 2),
        "max_shares_by_exposure": max_shares_by_exposure,

        "position_value": round(position_value, 2),
        "estimated_max_loss": round(estimated_max_loss, 2),
        "position_exposure_percent": round(position_exposure_percent, 2),
        "exposure_classification": exposure_classification,

        "environment": environment,
        "environment_label": environment_result["label"],
        "environment_risk_multiplier": environment_result["risk_multiplier"],
        "environment_note": environment_result["note"],

        "warnings": warnings,

        "risk_summary": (
            f"This plan risks approximately ${round(estimated_max_loss, 2)} "
            f"if the stop is hit, using {suggested_shares} shares. "
            f"Position exposure would be {round(position_exposure_percent, 2)}% "
            f"of the account."
        ),
    }


def get_risk_percent_levels(account_value: float):
    """
    Returns 1% through 5% risk levels for the account.
    """

    account_value = safe_float(account_value)

    if account_value <= 0:
        return {
            "status": "error",
            "message": "Account value must be greater than zero.",
        }

    levels = {}

    for percent in range(1, 6):
        levels[f"{percent}%"] = round(account_value * (percent / 100), 2)

    return {
        "status": "ok",
        "account_value": round(account_value, 2),
        "risk_levels": levels,
    }