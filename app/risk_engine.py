# app/risk_engine.py

def calculate_risk_plan(
    account_value: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
):
    """
    Calculates position sizing based on account value, risk percentage,
    entry price, and stop price.
    """

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

    risk_per_share = entry_price - stop_price

    if risk_per_share <= 0:
        return {
            "status": "error",
            "message": "Stop price must be below entry price for a long trade.",
        }

    allowed_risk_dollars = account_value * (risk_percent / 100)
    suggested_shares = int(allowed_risk_dollars // risk_per_share)
    position_value = suggested_shares * entry_price
    estimated_max_loss = suggested_shares * risk_per_share
    position_exposure_percent = (
        (position_value / account_value) * 100 if account_value > 0 else 0
    )

    return {
        "status": "ok",
        "account_value": round(account_value, 2),
        "risk_percent": round(risk_percent, 2),
        "allowed_risk_dollars": round(allowed_risk_dollars, 2),
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "risk_per_share": round(risk_per_share, 2),
        "suggested_shares": suggested_shares,
        "position_value": round(position_value, 2),
        "estimated_max_loss": round(estimated_max_loss, 2),
        "position_exposure_percent": round(position_exposure_percent, 2),
    }


def get_risk_percent_levels(account_value: float):
    """
    Returns 1% through 5% risk levels for the account.
    """

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