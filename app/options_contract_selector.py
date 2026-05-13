from datetime import datetime


INDIVIDUAL_556_VALUE = 237.00
ROTH_VALUE = 859.00


def classify_affordability(max_risk: float, account_size: float) -> dict:
    """
    Classifies whether an options structure fits the account size.

    Conservative small-account rules:
    - Affordable: <= 10% of account
    - Stretched: <= 20% of account
    - Too Large: > 20% of account
    """

    if account_size <= 0:
        return {
            "affordability_label": "UNKNOWN",
            "risk_percent_of_account": None,
            "account_fit": "Account size unavailable.",
        }

    risk_percent = round((max_risk / account_size) * 100, 2)

    if risk_percent <= 10:
        label = "AFFORDABLE"
        fit = "Fits conservative small-account risk limits."
    elif risk_percent <= 20:
        label = "STRETCHED"
        fit = "Possible, but risk is high for this account size."
    else:
        label = "TOO LARGE"
        fit = "Not suitable for this account size under survivability rules."

    return {
        "affordability_label": label,
        "risk_percent_of_account": risk_percent,
        "account_fit": fit,
    }


def build_long_call(
    symbol: str,
    current_price: float,
    account_size: float,
    expiration: str = "2026-05-24",
) -> dict:
    strike = round(current_price)

    estimated_premium = 3.20
    max_risk = round(estimated_premium * 100, 2)

    affordability = classify_affordability(max_risk, account_size)

    return {
        "status": "ok",
        "strategy": "long_call",
        "symbol": symbol.upper(),
        "generated_at": datetime.now().isoformat(),
        "expiration": expiration,
        "buy_call": {
            "strike": strike,
            "estimated_price": estimated_premium,
        },
        "estimated_debit": estimated_premium,
        "max_risk": max_risk,
        "max_reward": "unlimited_theoretical",
        "reward_risk_ratio": None,
        "account_size": account_size,
        **affordability,
        "recommendation_strength": (
            "REJECT"
            if affordability["affordability_label"] == "TOO LARGE"
            else "MODERATE"
        ),
        "trade_summary": (
            f"Buy the {strike} call for an estimated premium of "
            f"${estimated_premium}."
        ),
        "risk_note": "Long calls are defined-risk but can decay quickly if timing is wrong.",
    }


def build_long_put(
    symbol: str,
    current_price: float,
    account_size: float,
    expiration: str = "2026-05-24",
) -> dict:
    strike = round(current_price)

    estimated_premium = 3.10
    max_risk = round(estimated_premium * 100, 2)

    affordability = classify_affordability(max_risk, account_size)

    return {
        "status": "ok",
        "strategy": "long_put",
        "symbol": symbol.upper(),
        "generated_at": datetime.now().isoformat(),
        "expiration": expiration,
        "buy_put": {
            "strike": strike,
            "estimated_price": estimated_premium,
        },
        "estimated_debit": estimated_premium,
        "max_risk": max_risk,
        "max_reward": "large_but_limited_by_stock_to_zero",
        "reward_risk_ratio": None,
        "account_size": account_size,
        **affordability,
        "recommendation_strength": (
            "REJECT"
            if affordability["affordability_label"] == "TOO LARGE"
            else "MODERATE"
        ),
        "trade_summary": (
            f"Buy the {strike} put for an estimated premium of "
            f"${estimated_premium}."
        ),
        "risk_note": "Long puts are defined-risk bearish exposure but require timely downside movement.",
    }


def build_bull_call_vertical_spread(
    symbol: str,
    current_price: float,
    account_size: float,
    expiration: str = "2026-05-24",
) -> dict:
    long_call_strike = round(current_price)
    short_call_strike = long_call_strike + 5

    estimated_long_call_cost = 3.20
    estimated_short_call_credit = 1.85

    estimated_debit = round(estimated_long_call_cost - estimated_short_call_credit, 2)
    max_risk = round(estimated_debit * 100, 2)

    spread_width = short_call_strike - long_call_strike
    max_reward = round((spread_width * 100) - max_risk, 2)

    reward_risk_ratio = round(max_reward / max_risk, 2) if max_risk > 0 else 0

    affordability = classify_affordability(max_risk, account_size)

    recommendation_strength = "MODERATE"

    if affordability["affordability_label"] == "TOO LARGE":
        recommendation_strength = "REJECT"
    elif reward_risk_ratio >= 2:
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
        **affordability,
        "recommendation_strength": recommendation_strength,
        "trade_summary": (
            f"Buy the {long_call_strike} call and sell the "
            f"{short_call_strike} call for an estimated debit of "
            f"${estimated_debit}."
        ),
        "risk_note": "Defined-risk bullish spread for small-account directional exposure.",
    }


def build_bear_put_vertical_spread(
    symbol: str,
    current_price: float,
    account_size: float,
    expiration: str = "2026-05-24",
) -> dict:
    long_put_strike = round(current_price)
    short_put_strike = long_put_strike - 5

    estimated_long_put_cost = 3.10
    estimated_short_put_credit = 1.75

    estimated_debit = round(estimated_long_put_cost - estimated_short_put_credit, 2)
    max_risk = round(estimated_debit * 100, 2)

    spread_width = long_put_strike - short_put_strike
    max_reward = round((spread_width * 100) - max_risk, 2)

    reward_risk_ratio = round(max_reward / max_risk, 2) if max_risk > 0 else 0

    affordability = classify_affordability(max_risk, account_size)

    recommendation_strength = "MODERATE"

    if affordability["affordability_label"] == "TOO LARGE":
        recommendation_strength = "REJECT"
    elif reward_risk_ratio >= 2:
        recommendation_strength = "STRONG"

    return {
        "status": "ok",
        "strategy": "bear_put_vertical_spread",
        "symbol": symbol.upper(),
        "generated_at": datetime.now().isoformat(),
        "expiration": expiration,
        "buy_put": {
            "strike": long_put_strike,
            "estimated_price": estimated_long_put_cost,
        },
        "sell_put": {
            "strike": short_put_strike,
            "estimated_price": estimated_short_put_credit,
        },
        "estimated_debit": estimated_debit,
        "max_risk": max_risk,
        "max_reward": max_reward,
        "reward_risk_ratio": reward_risk_ratio,
        "account_size": account_size,
        **affordability,
        "recommendation_strength": recommendation_strength,
        "trade_summary": (
            f"Buy the {long_put_strike} put and sell the "
            f"{short_put_strike} put for an estimated debit of "
            f"${estimated_debit}."
        ),
        "risk_note": "Defined-risk bearish spread for small-account downside exposure.",
    }


def build_options_contract_candidates(
    symbol: str,
    current_price: float,
    account_size: float,
    directional_bias: str = "bullish",
    expiration: str = "2026-05-24",
) -> dict:
    bias = directional_bias.lower().strip()

    if bias in ["bullish", "long", "up"]:
        candidates = [
            build_long_call(symbol, current_price, account_size, expiration),
            build_bull_call_vertical_spread(symbol, current_price, account_size, expiration),
        ]

    elif bias in ["bearish", "short", "down"]:
        candidates = [
            build_long_put(symbol, current_price, account_size, expiration),
            build_bear_put_vertical_spread(symbol, current_price, account_size, expiration),
        ]

    else:
        candidates = []

    valid_candidates = [
        candidate for candidate in candidates
        if candidate.get("recommendation_strength") != "REJECT"
    ]

    if valid_candidates:
        best = sorted(
            valid_candidates,
            key=lambda item: (
                item.get("affordability_label") == "AFFORDABLE",
                item.get("reward_risk_ratio") or 0,
            ),
            reverse=True,
        )[0]
    else:
        best = None

    return {
        "status": "ok",
        "symbol": symbol.upper(),
        "directional_bias": directional_bias,
        "current_price": current_price,
        "account_size": account_size,
        "expiration": expiration,
        "candidate_count": len(candidates),
        "valid_candidate_count": len(valid_candidates),
        "best_candidate": best,
        "candidates": candidates,
        "generated_at": datetime.now().isoformat(),
    }


def get_sample_contract_selection() -> dict:
    return build_options_contract_candidates(
        symbol="CSCO",
        current_price=98.72,
        account_size=INDIVIDUAL_556_VALUE,
        directional_bias="bullish",
    )


def get_sample_contract_selection_roth() -> dict:
    return build_options_contract_candidates(
        symbol="CSCO",
        current_price=98.72,
        account_size=ROTH_VALUE,
        directional_bias="bullish",
    )