from datetime import datetime


def build_bull_call_vertical_spread(
    symbol: str,
    current_price: float,
    account_size: float,
    expiration: str = "2026-05-24",
) -> dict:
    """
    Simple starter contract selector for a bull call vertical spread.

    This is intentionally lightweight and modular.
    Real options-chain pricing will later come from Schwab API.
    """

    # Basic strike selection logic
    long_call_strike = round(current_price)
    short_call_strike = long_call_strike + 5

    # Placeholder premium estimates
    estimated_long_call_cost = 3.20
    estimated_short_call_credit = 1.85

    estimated_debit = round(
        estimated_long_call_cost - estimated_short_call_credit,
        2
    )

    max_risk = round(estimated_debit * 100, 2)

    spread_width = short_call_strike - long_call_strike

    max_reward = round((spread_width * 100) - max_risk, 2)

    reward_risk_ratio = round(
        max_reward / max_risk,
        2
    ) if max_risk > 0 else 0

    affordable = max_risk <= (account_size * 0.25)

    affordability_label = (
        "AFFORDABLE"
        if affordable
        else "TOO LARGE FOR ACCOUNT"
    )

    recommendation_strength = "MODERATE"

    if reward_risk_ratio >= 2:
        recommendation_strength = "STRONG"

    return {
        "status": "ok",
        "strategy": "bull_call_vertical_spread",
        "symbol": symbol.upper(),
        "generated_at": datetime.now().isoformat(),

        "expiration": expiration,

        "buy_call": {
            "strike": long_call_strike,
            "estimated_price": estimated_long_call_cost,
        },

        "sell_call": {
            "strike": short_call_strike,
            "estimated_price": estimated_short_call_credit,
        },

        "estimated_debit": estimated_debit,
        "max_risk": max_risk,
        "max_reward": max_reward,
        "reward_risk_ratio": reward_risk_ratio,

        "account_size": account_size,
        "affordability_label": affordability_label,

        "recommendation_strength": recommendation_strength,

        "trade_summary": (
            f"Buy the {long_call_strike} call and sell the "
            f"{short_call_strike} call for an estimated "
            f"debit of ${estimated_debit}."
        ),

        "risk_note": (
            "Defined-risk spread for small-account directional exposure."
        ),
    }


def get_sample_contract_selection() -> dict:
    """
    Sample contract selection for testing.
    """

    return build_bull_call_vertical_spread(
        symbol="CSCO",
        current_price=98.72,
        account_size=229.90,
    )