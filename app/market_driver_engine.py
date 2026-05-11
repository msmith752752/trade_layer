from datetime import datetime


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


SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AMD": "Technology",
    "AVGO": "Technology", "CSCO": "Technology", "ORCL": "Technology", "CRM": "Technology",
    "ADBE": "Technology", "INTC": "Technology", "PLTR": "Technology",
    "META": "Communication Services", "GOOGL": "Communication Services", "NFLX": "Communication Services",
    "DIS": "Communication Services",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary", "UBER": "Consumer Discretionary",
    "PYPL": "Financials", "JPM": "Financials", "GS": "Financials",
    "XOM": "Energy", "CVX": "Energy",
    "BA": "Industrials", "QXO": "Industrials",
    "KRMN": "Speculative / Small Cap", "SOFI": "Speculative / High Beta", "ULTY": "Options Income / High Yield",
    "SGOV": "Cash / Treasury", "BIL": "Cash / Treasury", "SHV": "Cash / Treasury", "BOXX": "Cash / Treasury",
}

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Financials": "XLF",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Healthcare": "XLV",
    "Speculative / Small Cap": "IWM",
    "Speculative / High Beta": "ARKK",
    "Options Income / High Yield": "SPY",
    "Cash / Treasury": "SGOV",
}


def classify_symbol(symbol: str) -> str:
    return SECTOR_MAP.get(str(symbol or "").upper().strip(), "Unclassified")


def extract_change(snapshot: dict) -> float:
    return safe_float(
        snapshot.get("daily_change_percent")
        or snapshot.get("change_percent")
        or snapshot.get("percent_change")
        or snapshot.get("day_change_percent"),
        0.0,
    )


def driver_status(change: float, positive_label: str, negative_label: str, neutral_label: str = "Neutral") -> str:
    if change >= 0.75:
        return positive_label
    if change <= -0.75:
        return negative_label
    return neutral_label


def build_market_driver_cards(driver_snapshots: dict) -> list:
    vix = driver_snapshots.get("^VIX", {})
    tnx = driver_snapshots.get("^TNX", {})
    spy = driver_snapshots.get("SPY", {})
    qqq = driver_snapshots.get("QQQ", {})
    iwm = driver_snapshots.get("IWM", {})
    oil = driver_snapshots.get("USO", {})

    vix_price = safe_float(vix.get("price"), None)
    vix_change = extract_change(vix)
    tnx_change = extract_change(tnx)
    spy_change = extract_change(spy)
    qqq_change = extract_change(qqq)
    iwm_change = extract_change(iwm)
    oil_change = extract_change(oil)

    if vix_price is None:
        volatility_signal = "Unavailable"
        volatility_impact = "VIX data is unavailable, so volatility impact is neutral by default."
        volatility_bias = "NEUTRAL"
    elif vix_price >= 24 or vix_change >= 5:
        volatility_signal = "Risk Pressure"
        volatility_impact = "Elevated or rising volatility usually pressures speculative positions and argues for smaller size."
        volatility_bias = "DEFENSIVE"
    elif vix_price <= 17 and vix_change <= 2:
        volatility_signal = "Volatility Supportive"
        volatility_impact = "Low or stable volatility generally supports selective risk-taking, but can create complacency."
        volatility_bias = "SUPPORTIVE"
    else:
        volatility_signal = "Normal Volatility"
        volatility_impact = "Volatility is not sending a major stress signal. Position quality should drive decisions."
        volatility_bias = "NEUTRAL"

    yield_signal = driver_status(tnx_change, "Rates Rising", "Rates Falling")
    if yield_signal == "Rates Rising":
        yield_impact = "Higher yields can pressure long-duration growth, high-yield equity income, and speculative risk."
        yield_bias = "CAUTION"
    elif yield_signal == "Rates Falling":
        yield_impact = "Falling yields can support growth assets and rate-sensitive equities."
        yield_bias = "SUPPORTIVE"
    else:
        yield_impact = "Rates are not producing a strong directional pressure signal."
        yield_bias = "NEUTRAL"

    risk_appetite_change = (spy_change + qqq_change + iwm_change) / 3 if any([spy_change, qqq_change, iwm_change]) else 0
    risk_signal = driver_status(risk_appetite_change, "Risk Appetite Improving", "Risk Appetite Weakening", "Mixed Risk Appetite")
    if risk_signal == "Risk Appetite Improving":
        risk_impact = "Major index proxies are supporting selective long exposure and stronger setups."
        risk_bias = "SUPPORTIVE"
    elif risk_signal == "Risk Appetite Weakening":
        risk_impact = "Index weakness argues for capital protection before adding exposure."
        risk_bias = "DEFENSIVE"
    else:
        risk_impact = "Market tone is mixed; position-level discipline matters more than broad aggression."
        risk_bias = "SELECTIVE"

    oil_signal = driver_status(oil_change, "Energy Tailwind", "Energy Headwind", "Energy Neutral")
    oil_impact = "Oil movement mainly matters for energy exposure and inflation/rates sensitivity."

    return [
        {
            "driver": "Volatility",
            "symbol": "^VIX",
            "value": vix.get("price"),
            "change_percent": round(vix_change, 2),
            "signal": volatility_signal,
            "bias": volatility_bias,
            "impact": volatility_impact,
        },
        {
            "driver": "10Y Yield",
            "symbol": "^TNX",
            "value": tnx.get("price"),
            "change_percent": round(tnx_change, 2),
            "signal": yield_signal,
            "bias": yield_bias,
            "impact": yield_impact,
        },
        {
            "driver": "Risk Appetite",
            "symbol": "SPY / QQQ / IWM",
            "value": None,
            "change_percent": round(risk_appetite_change, 2),
            "signal": risk_signal,
            "bias": risk_bias,
            "impact": risk_impact,
        },
        {
            "driver": "Oil / Inflation Proxy",
            "symbol": "USO",
            "value": oil.get("price"),
            "change_percent": round(oil_change, 2),
            "signal": oil_signal,
            "bias": "SECTOR",
            "impact": oil_impact,
        },
    ]


def build_sector_context(driver_snapshots: dict) -> dict:
    sector_context = {}
    for sector, etf in SECTOR_ETF_MAP.items():
        snapshot = driver_snapshots.get(etf, {})
        sector_context[sector] = {
            "sector": sector,
            "etf": etf,
            "price": snapshot.get("price"),
            "daily_change_percent": round(extract_change(snapshot), 2),
            "state": snapshot.get("market_state"),
            "environment_score": snapshot.get("environment_score"),
        }
    return sector_context


def score_position_driver_impact(position: dict, driver_snapshots: dict, sector_context: dict, briefing: dict) -> dict:
    symbol = str(position.get("symbol", "")).upper().strip()
    sector = classify_symbol(symbol)
    sector_data = sector_context.get(sector, {})

    pnl_pct = safe_float(position.get("unrealized_pl_percent"), 0.0)
    risk_score = safe_float(position.get("risk_score"), 50.0)
    sector_change = safe_float(sector_data.get("daily_change_percent"), 0.0)
    vix_price = safe_float(driver_snapshots.get("^VIX", {}).get("price"), 18.0)
    tnx_change = extract_change(driver_snapshots.get("^TNX", {}))
    iwm_change = extract_change(driver_snapshots.get("IWM", {}))

    pressure = 0
    tailwind = 0
    reasons = []

    if pnl_pct <= -8:
        pressure += 25
        reasons.append("Position is already under loss pressure.")
    elif pnl_pct >= 5:
        tailwind += 12
        reasons.append("Position is profitable, giving more flexibility.")

    if risk_score >= 70:
        pressure += 18
        reasons.append("Existing position guidance marks risk as elevated.")

    if sector_change <= -1:
        pressure += 16
        reasons.append(f"Sector/ETF proxy is weak today ({sector_data.get('etf')}: {sector_change:.2f}%).")
    elif sector_change >= 1:
        tailwind += 14
        reasons.append(f"Sector/ETF proxy is supportive today ({sector_data.get('etf')}: {sector_change:.2f}%).")

    if vix_price >= 24 and sector in ["Speculative / Small Cap", "Speculative / High Beta", "Technology", "Consumer Discretionary"]:
        pressure += 14
        reasons.append("Elevated VIX increases pressure on higher-beta exposure.")

    if tnx_change >= 0.75 and sector in ["Technology", "Speculative / High Beta", "Options Income / High Yield"]:
        pressure += 10
        reasons.append("Rising yields can pressure this type of exposure.")
    elif tnx_change <= -0.75 and sector in ["Technology", "Consumer Discretionary"]:
        tailwind += 8
        reasons.append("Falling yields can support this type of exposure.")

    if iwm_change <= -1 and sector in ["Speculative / Small Cap", "Speculative / High Beta"]:
        pressure += 14
        reasons.append("Small-cap/high-beta tape is weak, which matters for this position.")

    net_score = max(0, min(100, 50 + tailwind - pressure))

    if pressure >= 45:
        impact = "HEADWIND"
        action = "Do not add; review reduce/exit rules."
    elif pressure >= 25:
        impact = "CAUTION"
        action = "Hold only if risk controls remain intact; avoid adding today."
    elif tailwind >= 20 and pnl_pct >= -3:
        impact = "TAILWIND"
        action = "Eligible to hold; adding only makes sense if capital allocation rules permit it."
    else:
        impact = "MIXED"
        action = "Hold/monitor; let position decision engine drive action."

    if not reasons:
        reasons.append("No major driver conflict detected from current market-driver data.")

    return {
        "symbol": symbol,
        "account": position.get("account") or position.get("account_type") or "Uncategorized",
        "sector": sector,
        "sector_proxy": sector_data.get("etf"),
        "market_value": position.get("market_value"),
        "open_pl": position.get("unrealized_pl"),
        "open_pl_percent": position.get("unrealized_pl_percent"),
        "driver_impact": impact,
        "driver_score": round(net_score, 2),
        "driver_action": action,
        "driver_reasons": reasons[:4],
    }


def score_recommendation_driver_impact(recommendation: dict, driver_snapshots: dict, sector_context: dict) -> dict:
    symbol = str(recommendation.get("symbol", "")).upper().strip()
    sector = classify_symbol(symbol)
    sector_data = sector_context.get(sector, {})
    sector_change = safe_float(sector_data.get("daily_change_percent"), 0.0)
    vix_price = safe_float(driver_snapshots.get("^VIX", {}).get("price"), 18.0)
    tnx_change = extract_change(driver_snapshots.get("^TNX", {}))

    score = safe_float(recommendation.get("score"), 0.0)
    reasons = []
    quality = 50

    if score >= 180:
        quality += 18
        reasons.append("Scanner score is strong.")

    if sector_change >= 1:
        quality += 14
        reasons.append(f"Sector proxy is supportive today ({sector_data.get('etf')}: {sector_change:.2f}%).")
    elif sector_change <= -1:
        quality -= 18
        reasons.append(f"Sector proxy is weak today ({sector_data.get('etf')}: {sector_change:.2f}%).")

    if vix_price >= 24 and sector in ["Technology", "Consumer Discretionary", "Speculative / High Beta", "Speculative / Small Cap"]:
        quality -= 14
        reasons.append("Elevated volatility reduces quality for high-beta new entries.")

    if tnx_change >= 0.75 and sector in ["Technology", "Speculative / High Beta", "Options Income / High Yield"]:
        quality -= 8
        reasons.append("Rising yields are a potential headwind for this setup type.")

    quality = max(0, min(100, quality))

    if quality >= 75:
        decision = "DRIVER CONFIRMED"
        action = "Setup has market-driver support; still apply capital allocation limits."
    elif quality >= 55:
        decision = "SELECTIVE"
        action = "Setup is viable, but do not chase. Prefer clean entry/risk."
    else:
        decision = "DRIVER CONFLICT"
        action = "Market drivers do not strongly support adding this today."

    if not reasons:
        reasons.append("No major driver confirmation or conflict detected.")

    return {
        "symbol": symbol,
        "sector": sector,
        "sector_proxy": sector_data.get("etf"),
        "scanner_score": recommendation.get("score"),
        "recommended_strategy": recommendation.get("recommended_strategy"),
        "driver_decision": decision,
        "driver_quality_score": round(quality, 2),
        "driver_action": action,
        "driver_reasons": reasons[:4],
    }


def build_market_driver_impact(briefing=None, portfolio_data=None, scan_data=None, driver_snapshots=None):
    briefing = briefing or {}
    portfolio_data = portfolio_data or {}
    scan_data = scan_data or {}
    driver_snapshots = driver_snapshots or {}

    sector_context = build_sector_context(driver_snapshots)
    driver_cards = build_market_driver_cards(driver_snapshots)

    open_positions = portfolio_data.get("open_positions") or []
    position_impacts = []
    for position in open_positions:
        symbol = str(position.get("symbol", "")).upper().strip()
        if not symbol or classify_symbol(symbol) == "Cash / Treasury":
            continue
        position_impacts.append(score_position_driver_impact(position, driver_snapshots, sector_context, briefing))

    impact_priority = {"HEADWIND": 4, "CAUTION": 3, "MIXED": 2, "TAILWIND": 1}
    position_impacts.sort(key=lambda x: (impact_priority.get(x.get("driver_impact"), 0), x.get("driver_score", 50)), reverse=True)

    recommendations = scan_data.get("trade_opportunities") or []
    recommendation_impacts = [
        score_recommendation_driver_impact(item, driver_snapshots, sector_context)
        for item in recommendations[:8]
    ]
    recommendation_impacts.sort(key=lambda x: x.get("driver_quality_score", 0), reverse=True)

    headwinds = [item for item in position_impacts if item.get("driver_impact") in ["HEADWIND", "CAUTION"]]
    confirmed = [item for item in recommendation_impacts if item.get("driver_decision") == "DRIVER CONFIRMED"]

    directives = []
    if headwinds:
        directives.append("Review driver headwinds on current positions before deploying new capital.")
    if confirmed:
        directives.append("Only consider new trades where scanner quality and market-driver confirmation both align.")
    if not confirmed:
        directives.append("No recommendation has strong market-driver confirmation; stay selective.")

    vix_price = safe_float(driver_snapshots.get("^VIX", {}).get("price"), None)
    if vix_price is not None and vix_price >= 24:
        directives.append("Volatility is elevated; reduce size and avoid averaging down into weak positions.")

    summary = (
        f"Market-driver layer mapped {len(position_impacts)} current position(s) and "
        f"{len(recommendation_impacts)} recommendation(s) against volatility, rates, index tone, oil, and sector proxies."
    )

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "driver_summary": summary,
        "driver_directives": directives,
        "market_drivers": driver_cards,
        "sector_context": sector_context,
        "position_driver_impacts": position_impacts[:12],
        "recommendation_driver_impacts": recommendation_impacts[:8],
    }
