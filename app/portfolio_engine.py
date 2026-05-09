"""
TradeLayer Portfolio Intelligence Engine

Purpose:
Analyze account-level portfolio structure, not just individual positions.

Core philosophy:
- Portfolio construction matters more than isolated trades
- Risk control requires account context
- Defensive reserves, concentration, income exposure, and speculative exposure
  should all be visible
- Defensive concentration is not the same as speculative/equity concentration
- Portfolio stability matters because consistency and survivability are core
  TradeLayer priorities
- Account-level guidance should convert analysis into clear action:
  HOLD, ADD SELECTIVELY, REDUCE RISK, RAISE CASH, REBALANCE, or AVOID ADDING RISK
"""


DEFENSIVE_SYMBOLS = {
    "SGOV", "BIL", "SHV", "SHY", "BND", "AGG", "TLT", "IEF"
}

INCOME_SYMBOLS = {
    "JEPI", "JEPQ", "SCHD", "IDV", "MAIN", "VICI", "T", "VZ", "PFE", "BMY", "XOM", "ADC"
}

SPECULATIVE_SYMBOLS = {
    "BTCI", "PLTR", "QXO", "FIGR", "KRMN", "SOFI", "TSLA", "VKTX", "ULTY"
}


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


def normalize_symbol(position: dict):
    return str(position.get("symbol", "")).upper().strip()


def get_position_value(position: dict):
    for key in ["market_value", "mkt_val", "value", "position_value"]:
        if position.get(key) is not None:
            return safe_float(position.get(key))

    qty = safe_float(position.get("shares") or position.get("qty"))
    price = safe_float(position.get("current_price") or position.get("price"))

    return qty * price


def get_position_unrealized_pl(position: dict):
    for key in ["unrealized_pl", "p_l", "pl", "unrealized"]:
        if position.get(key) is not None:
            return safe_float(position.get(key))

    value = get_position_value(position)

    total_basis = None

    for key in ["total_basis", "cost_basis_total", "Cost Basis"]:
        if position.get(key) is not None:
            total_basis = safe_float(position.get(key))
            break

    if total_basis is None:
        shares = abs(safe_float(position.get("shares") or position.get("qty")))
        cost_basis = safe_float(position.get("cost_basis") or position.get("price"))
        total_basis = shares * cost_basis

    if total_basis is None:
        return 0.0

    return value - total_basis


def get_asset_type(position: dict):
    return str(position.get("asset_type", position.get("Asset Type", ""))).strip()


def is_cash_position(position: dict):
    symbol = normalize_symbol(position)
    asset_type = get_asset_type(position).lower()
    description = str(position.get("description", "")).lower()

    return (
        "cash" in symbol.lower()
        or "cash" in asset_type
        or "money market" in asset_type
        or "cash" in description
    )


def is_option_position(position: dict):
    asset_type = get_asset_type(position).lower()
    symbol = normalize_symbol(position)
    description = str(position.get("description", "")).lower()

    return (
        "option" in asset_type
        or "call " in description
        or "put " in description
        or " c" in symbol.lower()
        or " p" in symbol.lower()
    )


def is_fixed_income_position(position: dict):
    asset_type = get_asset_type(position).lower()
    description = str(position.get("description", "")).lower()

    return (
        "fixed income" in asset_type
        or "bond" in asset_type
        or "treasury" in asset_type
        or "treasury" in description
        or "cd" in description
    )


def classify_position_bucket(position: dict):
    symbol = normalize_symbol(position)
    asset_type = get_asset_type(position).lower()

    if is_cash_position(position):
        return "cash"

    if is_fixed_income_position(position):
        return "defensive"

    if symbol in DEFENSIVE_SYMBOLS:
        return "defensive"

    if is_option_position(position):
        return "options"

    if symbol in SPECULATIVE_SYMBOLS:
        return "speculative"

    if symbol in INCOME_SYMBOLS:
        return "income"

    if "etf" in asset_type:
        return "fund"

    return "equity"


def is_defensive_bucket(bucket: str):
    return bucket in ["cash", "defensive"]


def classify_raw_concentration(max_position_percent):
    if max_position_percent >= 50:
        return "VERY HIGH"
    if max_position_percent >= 35:
        return "HIGH"
    if max_position_percent >= 20:
        return "ELEVATED"
    if max_position_percent >= 10:
        return "MODERATE"

    return "LOW"


def classify_concentration(max_position_percent, largest_position_bucket):
    raw_label = classify_raw_concentration(max_position_percent)

    if is_defensive_bucket(largest_position_bucket):
        if max_position_percent >= 70:
            return "DEFENSIVE CONCENTRATION"
        if max_position_percent >= 50:
            return "HIGH DEFENSIVE RESERVE"
        if max_position_percent >= 35:
            return "ELEVATED DEFENSIVE RESERVE"

    return raw_label


def classify_defensive_profile(defensive_percent, cash_percent):
    combined = defensive_percent + cash_percent

    if combined >= 70:
        return "VERY DEFENSIVE"
    if combined >= 50:
        return "DEFENSIVE"
    if combined >= 25:
        return "BALANCED"
    if combined >= 10:
        return "GROWTH TILT"

    return "AGGRESSIVE"


def classify_speculative_profile(speculative_percent):
    if speculative_percent >= 25:
        return "HIGH"
    if speculative_percent >= 15:
        return "ELEVATED"
    if speculative_percent >= 5:
        return "MODERATE"

    return "LOW"


def calculate_portfolio_health_score(
    concentration_label,
    largest_position_bucket,
    defensive_percent,
    cash_percent,
    speculative_percent,
    options_percent,
):
    score = 100

    if concentration_label == "VERY HIGH":
        score -= 35
    elif concentration_label == "HIGH":
        score -= 25
    elif concentration_label == "ELEVATED":
        score -= 15
    elif concentration_label == "MODERATE":
        score -= 7
    elif concentration_label == "DEFENSIVE CONCENTRATION":
        score -= 5
    elif concentration_label == "HIGH DEFENSIVE RESERVE":
        score += 2
    elif concentration_label == "ELEVATED DEFENSIVE RESERVE":
        score += 3

    if defensive_percent + cash_percent >= 50:
        score += 10
    elif defensive_percent + cash_percent < 10:
        score -= 15

    if speculative_percent >= 25:
        score -= 25
    elif speculative_percent >= 15:
        score -= 15
    elif speculative_percent >= 5:
        score -= 7

    if options_percent >= 20:
        score -= 15
    elif options_percent >= 10:
        score -= 8

    return max(0, min(100, score))


def classify_portfolio_health(score):
    if score >= 85:
        return "STRONG"
    if score >= 70:
        return "STABLE"
    if score >= 55:
        return "MIXED"
    if score >= 40:
        return "ELEVATED RISK"

    return "HIGH RISK"


def calculate_portfolio_stability(
    defensive_percent,
    cash_percent,
    speculative_percent,
    options_percent,
    concentration_label,
    health_score,
):
    """
    Portfolio survivability / consistency scoring.

    Health = structure and allocation quality.
    Stability = ability to withstand volatility, drawdowns, and bad trade sequences.
    """

    stability_score = 50

    stability_drivers = []
    instability_drivers = []

    defensive_total = defensive_percent + cash_percent

    if defensive_total >= 70:
        stability_score += 30
        stability_drivers.append(
            "Large defensive reserve improves drawdown resilience."
        )
    elif defensive_total >= 50:
        stability_score += 20
        stability_drivers.append(
            "Healthy defensive allocation supports portfolio stability."
        )
    elif defensive_total >= 25:
        stability_score += 10
        stability_drivers.append(
            "Moderate defensive reserve supports risk control."
        )
    elif defensive_total < 10:
        stability_score -= 20
        instability_drivers.append(
            "Very limited defensive reserve increases portfolio fragility."
        )

    if speculative_percent >= 25:
        stability_score -= 25
        instability_drivers.append(
            "High speculative exposure increases volatility risk."
        )
    elif speculative_percent >= 15:
        stability_score -= 15
        instability_drivers.append(
            "Elevated speculative exposure may reduce consistency."
        )
    elif speculative_percent <= 5:
        stability_score += 5
        stability_drivers.append(
            "Limited speculative exposure supports consistency."
        )

    if options_percent >= 20:
        stability_score -= 20
        instability_drivers.append(
            "Large options exposure increases complexity and volatility."
        )
    elif options_percent >= 10:
        stability_score -= 10
        instability_drivers.append(
            "Moderate options exposure requires active risk management."
        )

    if concentration_label == "VERY HIGH":
        stability_score -= 25
        instability_drivers.append(
            "Very high single-position risk-asset concentration reduces survivability."
        )
    elif concentration_label == "HIGH":
        stability_score -= 15
        instability_drivers.append(
            "High concentration risk may increase drawdown severity."
        )
    elif concentration_label == "ELEVATED":
        stability_score -= 8
        instability_drivers.append(
            "Elevated concentration risk should be monitored."
        )
    elif concentration_label == "DEFENSIVE CONCENTRATION":
        stability_score += 5
        stability_drivers.append(
            "Defensive reserve concentration supports capital preservation."
        )
    elif concentration_label in ["HIGH DEFENSIVE RESERVE", "ELEVATED DEFENSIVE RESERVE"]:
        stability_score += 4
        stability_drivers.append(
            "Defensive reserve supports portfolio survivability."
        )

    if health_score >= 85:
        stability_score += 10
        stability_drivers.append(
            "Strong portfolio health score supports consistency."
        )
    elif health_score < 40:
        stability_score -= 15
        instability_drivers.append(
            "Low portfolio health score reduces stability."
        )

    stability_score = max(0, min(100, stability_score))

    if stability_score >= 85:
        stability_label = "HIGHLY STABLE"
    elif stability_score >= 70:
        stability_label = "STABLE"
    elif stability_score >= 55:
        stability_label = "MODERATELY STABLE"
    elif stability_score >= 40:
        stability_label = "UNSTABLE"
    else:
        stability_label = "HIGHLY UNSTABLE"

    if not stability_drivers:
        stability_drivers.append(
            "No major portfolio stability strengths detected."
        )

    if not instability_drivers:
        instability_drivers.append(
            "No major portfolio instability drivers detected."
        )

    return {
        "stability_score": stability_score,
        "stability_label": stability_label,
        "stability_drivers": stability_drivers,
        "instability_drivers": instability_drivers,
    }


def get_account_mode(positions: list):
    modes = [
        str(position.get("portfolio_mode", "")).lower().strip()
        for position in positions
        if position.get("portfolio_mode")
    ]

    if "paper" in modes:
        return "paper"

    if "real" in modes:
        return "real"

    return "real"


def calculate_position_guidance_mix(positions: list):
    guidance_counts = {
        "hold": 0,
        "tighten_risk": 0,
        "avoid_adding": 0,
        "review": 0,
    }

    losing_positions = []
    winning_positions = []

    for position in positions:
        guidance = str(position.get("guidance", "")).lower()
        symbol = normalize_symbol(position)
        unrealized_pl = safe_float(position.get("unrealized_pl"), None)

        if unrealized_pl is None:
            unrealized_pl = get_position_unrealized_pl(position)

        if "avoid" in guidance:
            guidance_counts["avoid_adding"] += 1
        elif "tighten" in guidance or "risk" in guidance:
            guidance_counts["tighten_risk"] += 1
        elif "review" in guidance:
            guidance_counts["review"] += 1
        else:
            guidance_counts["hold"] += 1

        if unrealized_pl < 0:
            losing_positions.append({
                "symbol": symbol,
                "unrealized_pl": round(unrealized_pl, 2),
            })
        elif unrealized_pl > 0:
            winning_positions.append({
                "symbol": symbol,
                "unrealized_pl": round(unrealized_pl, 2),
            })

    losing_positions.sort(key=lambda x: x["unrealized_pl"])
    winning_positions.sort(key=lambda x: x["unrealized_pl"], reverse=True)

    return {
        "guidance_counts": guidance_counts,
        "losing_positions": losing_positions[:5],
        "winning_positions": winning_positions[:5],
    }


def generate_account_recommendation(
    account_name,
    portfolio_mode,
    health_score,
    stability_score,
    concentration_label,
    defensive_percent,
    cash_percent,
    speculative_percent,
    options_percent,
    largest_position,
    position_guidance_mix,
):
    defensive_total = defensive_percent + cash_percent
    recommendation = "HOLD"
    recommendation_label = "HOLD"
    recommendation_score = 70
    reasons = []

    account_lower = account_name.lower()

    if portfolio_mode == "paper":
        recommendation = "SIMULATION / TEST STRATEGIES"
        recommendation_label = "SIMULATION"
        recommendation_score = 75
        reasons.append(
            "This account is marked as paper capital, so recommendations should be used for testing strategy behavior rather than real-money action."
        )

        if defensive_total >= 50:
            reasons.append(
                "Large defensive reserve makes the paper account useful for testing selective risk deployment."
            )

        if speculative_percent >= 10:
            reasons.append(
                "Speculative exposure exists in the simulation account; useful for monitoring how higher-risk names affect stability."
            )

        return {
            "account_recommendation": recommendation,
            "account_recommendation_label": recommendation_label,
            "account_recommendation_score": recommendation_score,
            "account_recommendation_reason": reasons[0],
            "account_recommendation_reasons": reasons,
        }

    if stability_score < 40 or health_score < 45:
        recommendation = "REDUCE RISK"
        recommendation_label = "REDUCE RISK"
        recommendation_score = 35
        reasons.append(
            "Account stability or health is weak enough that adding risk is not favored."
        )

    elif concentration_label in ["VERY HIGH", "HIGH"] and largest_position:
        recommendation = "REBALANCE"
        recommendation_label = "REBALANCE"
        recommendation_score = 45
        reasons.append(
            f"{largest_position.get('symbol', 'Largest position')} represents a large share of the account, creating concentration risk."
        )

    elif speculative_percent >= 25:
        recommendation = "REDUCE SPECULATIVE EXPOSURE"
        recommendation_label = "REDUCE RISK"
        recommendation_score = 40
        reasons.append(
            "Speculative exposure is high enough to reduce account durability."
        )

    elif speculative_percent >= 15:
        recommendation = "AVOID ADDING RISK"
        recommendation_label = "AVOID ADDING"
        recommendation_score = 55
        reasons.append(
            "Speculative exposure is elevated, so new risk should be limited until quality improves."
        )

    elif options_percent >= 15:
        recommendation = "MONITOR OPTIONS RISK"
        recommendation_label = "MONITOR"
        recommendation_score = 60
        reasons.append(
            "Options exposure is meaningful, so assignment, decay, and volatility risk should be monitored."
        )

    elif defensive_total < 10:
        recommendation = "RAISE CASH / DEFENSIVE RESERVE"
        recommendation_label = "RAISE CASH"
        recommendation_score = 50
        reasons.append(
            "Defensive reserve is low, which can make the account more vulnerable during drawdowns."
        )

    elif stability_score >= 85 and health_score >= 85 and speculative_percent < 10:
        recommendation = "HOLD / ADD SELECTIVELY"
        recommendation_label = "ADD SELECTIVELY"
        recommendation_score = 85
        reasons.append(
            "Strong health, strong stability, and limited speculative exposure support selective additions only in high-quality setups."
        )

    elif stability_score >= 70 and health_score >= 70:
        recommendation = "HOLD"
        recommendation_label = "HOLD"
        recommendation_score = 75
        reasons.append(
            "Account structure is stable enough to maintain current positioning."
        )

    else:
        recommendation = "HOLD / MONITOR"
        recommendation_label = "MONITOR"
        recommendation_score = 65
        reasons.append(
            "Account is acceptable, but not strong enough for aggressive additions."
        )

    guidance_counts = position_guidance_mix.get("guidance_counts", {})
    avoid_count = guidance_counts.get("avoid_adding", 0)
    tighten_count = guidance_counts.get("tighten_risk", 0)

    if avoid_count + tighten_count >= 2:
        if recommendation in ["HOLD", "HOLD / ADD SELECTIVELY"]:
            recommendation = "HOLD / DO NOT ADD"
            recommendation_label = "AVOID ADDING"
            recommendation_score = min(recommendation_score, 58)

        reasons.append(
            "Multiple positions are flagged for tighter risk control or avoiding additional exposure."
        )

    losing_positions = position_guidance_mix.get("losing_positions", [])

    if losing_positions:
        worst = losing_positions[0]
        reasons.append(
            f"Worst current drag is {worst.get('symbol')} at approximately ${worst.get('unrealized_pl')} unrealized P/L."
        )

    if "hsa" in account_lower and speculative_percent >= 5:
        reasons.append(
            "Because this is an HSA, speculative exposure should be sized carefully relative to defensive reserves."
        )

    if defensive_total >= 50:
        reasons.append(
            "Defensive reserves support survivability and give the account flexibility."
        )

    return {
        "account_recommendation": recommendation,
        "account_recommendation_label": recommendation_label,
        "account_recommendation_score": recommendation_score,
        "account_recommendation_reason": reasons[0] if reasons else "No major action required.",
        "account_recommendation_reasons": reasons or ["No major action required."],
    }


def analyze_portfolio(account_name: str, positions: list):
    if not positions:
        return {
            "account": account_name,
            "status": "empty",
            "message": "No positions available for portfolio analysis.",
        }

    enriched_positions = []
    total_value = 0.0

    for position in positions:
        value = get_position_value(position)
        bucket = classify_position_bucket(position)

        enriched_positions.append({
            **position,
            "portfolio_bucket": bucket,
            "portfolio_value": round(value, 2),
        })

        total_value += value

    bucket_totals = {
        "cash": 0.0,
        "defensive": 0.0,
        "income": 0.0,
        "speculative": 0.0,
        "options": 0.0,
        "fund": 0.0,
        "equity": 0.0,
    }

    largest_position = None
    largest_position_value = 0.0

    for position in enriched_positions:
        value = position["portfolio_value"]
        bucket = position["portfolio_bucket"]

        bucket_totals[bucket] = bucket_totals.get(bucket, 0.0) + value

        if value > largest_position_value:
            largest_position = position
            largest_position_value = value

    def pct(value):
        return round((value / total_value) * 100, 2) if total_value else 0.0

    bucket_percents = {
        bucket: pct(value)
        for bucket, value in bucket_totals.items()
    }

    largest_position_percent = pct(largest_position_value)

    largest_position_bucket = (
        largest_position.get("portfolio_bucket")
        if largest_position
        else None
    )

    raw_concentration_label = classify_raw_concentration(largest_position_percent)

    concentration_label = classify_concentration(
        max_position_percent=largest_position_percent,
        largest_position_bucket=largest_position_bucket,
    )

    defensive_profile = classify_defensive_profile(
        defensive_percent=bucket_percents.get("defensive", 0),
        cash_percent=bucket_percents.get("cash", 0),
    )

    speculative_profile = classify_speculative_profile(
        bucket_percents.get("speculative", 0)
    )

    health_score = calculate_portfolio_health_score(
        concentration_label=concentration_label,
        largest_position_bucket=largest_position_bucket,
        defensive_percent=bucket_percents.get("defensive", 0),
        cash_percent=bucket_percents.get("cash", 0),
        speculative_percent=bucket_percents.get("speculative", 0),
        options_percent=bucket_percents.get("options", 0),
    )

    health_label = classify_portfolio_health(health_score)

    stability = calculate_portfolio_stability(
        defensive_percent=bucket_percents.get("defensive", 0),
        cash_percent=bucket_percents.get("cash", 0),
        speculative_percent=bucket_percents.get("speculative", 0),
        options_percent=bucket_percents.get("options", 0),
        concentration_label=concentration_label,
        health_score=health_score,
    )

    position_guidance_mix = calculate_position_guidance_mix(enriched_positions)
    portfolio_mode = get_account_mode(enriched_positions)

    recommendation = generate_account_recommendation(
        account_name=account_name,
        portfolio_mode=portfolio_mode,
        health_score=health_score,
        stability_score=stability["stability_score"],
        concentration_label=concentration_label,
        defensive_percent=bucket_percents.get("defensive", 0),
        cash_percent=bucket_percents.get("cash", 0),
        speculative_percent=bucket_percents.get("speculative", 0),
        options_percent=bucket_percents.get("options", 0),
        largest_position=largest_position,
        position_guidance_mix=position_guidance_mix,
    )

    warnings = []

    if concentration_label in ["VERY HIGH", "HIGH"]:
        warnings.append(
            f"Largest risk-asset concentration is {concentration_label}. "
            f"{largest_position.get('symbol', 'Unknown')} represents "
            f"{largest_position_percent}% of the account."
        )

    elif concentration_label in [
        "DEFENSIVE CONCENTRATION",
        "HIGH DEFENSIVE RESERVE",
        "ELEVATED DEFENSIVE RESERVE",
    ]:
        warnings.append(
            f"Largest position is defensive: {largest_position.get('symbol', 'Unknown')} "
            f"represents {largest_position_percent}% of the account. "
            f"This is a defensive reserve concentration, not the same as concentrated equity risk."
        )

    elif concentration_label == "ELEVATED":
        warnings.append(
            f"Largest position concentration is elevated. "
            f"{largest_position.get('symbol', 'Unknown')} represents "
            f"{largest_position_percent}% of the account."
        )

    if bucket_percents.get("cash", 0) + bucket_percents.get("defensive", 0) < 10:
        warnings.append(
            "Defensive reserve is low. Account may be more vulnerable to drawdowns."
        )

    if speculative_profile in ["HIGH", "ELEVATED"]:
        warnings.append(
            f"Speculative exposure is {speculative_profile}. Monitor drawdown risk."
        )

    if bucket_percents.get("options", 0) >= 10:
        warnings.append(
            "Options exposure is meaningful. Monitor assignment, decay, and volatility risk."
        )

    if not warnings:
        warnings.append(
            "No major account-level portfolio warnings detected."
        )

    return {
        "account": account_name,
        "portfolio_mode": portfolio_mode,
        "status": "ok",
        "total_value": round(total_value, 2),
        "portfolio_health_score": health_score,
        "portfolio_health_label": health_label,
        "portfolio_stability_score": stability["stability_score"],
        "portfolio_stability_label": stability["stability_label"],
        "stability_drivers": stability["stability_drivers"],
        "instability_drivers": stability["instability_drivers"],
        "defensive_profile": defensive_profile,
        "speculative_profile": speculative_profile,
        "concentration_label": concentration_label,
        "raw_concentration_label": raw_concentration_label,
        "account_recommendation": recommendation["account_recommendation"],
        "account_recommendation_label": recommendation["account_recommendation_label"],
        "account_recommendation_score": recommendation["account_recommendation_score"],
        "account_recommendation_reason": recommendation["account_recommendation_reason"],
        "account_recommendation_reasons": recommendation["account_recommendation_reasons"],
        "position_guidance_mix": position_guidance_mix,
        "largest_position": {
            "symbol": largest_position.get("symbol") if largest_position else None,
            "value": round(largest_position_value, 2),
            "percent": largest_position_percent,
            "bucket": largest_position_bucket,
        },
        "bucket_totals": {
            bucket: round(value, 2)
            for bucket, value in bucket_totals.items()
        },
        "bucket_percents": bucket_percents,
        "warnings": warnings,
        "positions": enriched_positions,
        "summary": (
            f"{account_name} is classified as {health_label} with "
            f"{stability['stability_label']} stability, a "
            f"{defensive_profile} allocation profile, and "
            f"{concentration_label} concentration profile. "
            f"Recommendation: {recommendation['account_recommendation']}."
        ),
    }
