from datetime import datetime


SMALL_ACCOUNT_VALUE = 229.90


def get_small_account_risk_profile(account_value: float = SMALL_ACCOUNT_VALUE) -> dict:
    max_risk_per_trade = round(account_value * 0.10, 2)
    preferred_risk_per_trade = round(account_value * 0.05, 2)

    return {
        "account_value": account_value,
        "risk_mode": "small_account_consistency",
        "preferred_risk_per_trade": preferred_risk_per_trade,
        "max_risk_per_trade": max_risk_per_trade,
        "philosophy": "Preserve capital, avoid large losses, prioritize repeatable small wins.",
    }


def normalize_strategy(strategy: str | None) -> str | None:
    if not strategy:
        return None

    value = strategy.lower().strip()

    strategy_map = {
        "bull_call_vertical_spread": "BULL_CALL_VERTICAL_SPREAD",
        "bull_call_spread": "BULL_CALL_VERTICAL_SPREAD",
        "bear_put_vertical_spread": "BEAR_PUT_VERTICAL_SPREAD",
        "bear_put_spread": "BEAR_PUT_VERTICAL_SPREAD",
        "long_call": "LONG_CALL",
        "long_put": "LONG_PUT",
        "shares": "SHARES",
        "stock": "SHARES",
    }

    return strategy_map.get(value)


def choose_trade_expression(
    symbol: str,
    directional_bias: str,
    conviction_score: int,
    market_environment: str = "neutral",
    volatility_environment: str = "stable",
    capital_efficiency_needed: bool = True,
    account_value: float = SMALL_ACCOUNT_VALUE,
    scanner_recommended_strategy: str | None = None,
    strategy_family: str | None = None,
    options_pressure: str | None = None,
    overextended: bool = False,
) -> dict:
    risk_profile = get_small_account_risk_profile(account_value)

    bias = directional_bias.lower().strip()
    market = market_environment.lower().strip()
    volatility = volatility_environment.lower().strip()
    normalized_scanner_strategy = normalize_strategy(scanner_recommended_strategy)

    reasons = []
    warnings = []

    if conviction_score < 60:
        return {
            "symbol": symbol.upper(),
            "recommendation": "AVOID",
            "preferred_expression": "NO_TRADE",
            "confidence": "Low",
            "reason": "Conviction score is below the minimum threshold for a quality setup.",
            "risk_profile": risk_profile,
            "warnings": ["No trade is recommended when setup quality is weak."],
            "timestamp": datetime.now().isoformat(),
        }

    if overextended:
        return {
            "symbol": symbol.upper(),
            "recommendation": "AVOID_CHASING",
            "preferred_expression": "NO_TRADE",
            "confidence": "Low",
            "reason": "The setup is directionally interesting but overextended. Avoid chasing and wait for a better entry.",
            "risk_profile": risk_profile,
            "warnings": ["Overextension risk is active."],
            "timestamp": datetime.now().isoformat(),
        }

    if volatility in ["unstable", "elevated", "expanding"]:
        warnings.append("Volatility is elevated or unstable, so outright long options may carry higher premium and timing risk.")

    if market in ["risk_off", "defensive", "weak"]:
        reasons.append("Market environment is defensive; size should remain small.")

    if normalized_scanner_strategy in ["BULL_CALL_VERTICAL_SPREAD", "BEAR_PUT_VERTICAL_SPREAD"]:
        preferred_expression = normalized_scanner_strategy
        recommendation = f"{normalized_scanner_strategy}_CANDIDATE"
        reasons.append("Existing scanner strategy recommends a defined-risk vertical spread.")
        reasons.append("Options strategy engine is respecting the scanner's defined-risk structure.")
        reasons.append("This fits the small-account goal of limiting maximum loss while maintaining directional exposure.")

    elif bias in ["bullish", "long", "up"]:
        if capital_efficiency_needed and conviction_score >= 70 and volatility in ["stable", "neutral", "normal"]:
            preferred_expression = "LONG_CALL"
            recommendation = "BUY_CALL_CANDIDATE"
            reasons.append("Bullish directional setup with capital efficiency needed for small account.")
            reasons.append("Long call provides defined risk and lower capital requirement than shares.")
        elif capital_efficiency_needed and volatility in ["elevated", "expanding", "unstable"]:
            preferred_expression = "BULL_CALL_VERTICAL_SPREAD"
            recommendation = "BULL_CALL_VERTICAL_SPREAD_CANDIDATE"
            reasons.append("Bullish setup, but volatility risk makes a defined-risk spread preferable to a naked long call.")
        else:
            preferred_expression = "SHARES"
            recommendation = "BUY_SHARES_CANDIDATE"
            reasons.append("Bullish setup, but shares may be cleaner than options due to volatility or conviction level.")

    elif bias in ["bearish", "short", "down"]:
        if conviction_score >= 75 and volatility in ["stable", "neutral", "normal"]:
            preferred_expression = "LONG_PUT"
            recommendation = "BUY_PUT_CANDIDATE"
            reasons.append("Bearish directional setup with defined-risk downside exposure.")
        elif conviction_score >= 70:
            preferred_expression = "BEAR_PUT_VERTICAL_SPREAD"
            recommendation = "BEAR_PUT_VERTICAL_SPREAD_CANDIDATE"
            reasons.append("Bearish setup, but spread structure may better control premium risk.")
        else:
            preferred_expression = "NO_TRADE"
            recommendation = "AVOID"
            reasons.append("Bearish bias exists, but conviction is not strong enough for a put trade.")

    else:
        preferred_expression = "NO_TRADE"
        recommendation = "AVOID"
        reasons.append("Directional bias is unclear.")

    if account_value <= 500 and preferred_expression in ["LONG_CALL", "LONG_PUT"]:
        warnings.append("Small account warning: verify option premium does not exceed preferred or maximum risk limits.")

    if options_pressure:
        reasons.append(f"Options pressure context: {options_pressure}.")

    confidence = "High" if conviction_score >= 80 else "Moderate" if conviction_score >= 65 else "Low"

    return {
        "symbol": symbol.upper(),
        "recommendation": recommendation,
        "preferred_expression": preferred_expression,
        "directional_bias": directional_bias,
        "conviction_score": conviction_score,
        "confidence": confidence,
        "market_environment": market_environment,
        "volatility_environment": volatility_environment,
        "scanner_recommended_strategy": scanner_recommended_strategy,
        "strategy_family": strategy_family,
        "options_pressure": options_pressure,
        "risk_profile": risk_profile,
        "reason": " ".join(reasons),
        "warnings": warnings,
        "timestamp": datetime.now().isoformat(),
    }


def get_sample_options_recommendation() -> dict:
    return choose_trade_expression(
        symbol="AVGO",
        directional_bias="bullish",
        conviction_score=95,
        market_environment="supportive",
        volatility_environment="stable",
        capital_efficiency_needed=True,
        account_value=SMALL_ACCOUNT_VALUE,
        scanner_recommended_strategy="bull_call_vertical_spread",
        strategy_family="directional_defined_risk",
        options_pressure="strong_bullish",
        overextended=False,
    )