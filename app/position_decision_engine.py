"""
TradeLayer Position Decision Engine

Purpose:
Translate market environment, portfolio posture, risk pressure, and existing open
positions into capital-allocation guidance.

This engine answers the practical portfolio question:
"Should I add, hold, reduce, exit, or watch this position today?"

It is intentionally conservative. It is not financial advice or a prediction
engine. It is a rules-based decision-support layer designed to improve process,
reduce impulsive trading, and keep capital allocation aligned with current risk.
"""

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


def safe_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def safe_upper(value, default=""):
    return safe_text(value, default).upper()


def normalize_positions(portfolio_data):
    if not portfolio_data:
        return []

    positions = portfolio_data.get("open_positions") or portfolio_data.get("positions") or []
    return positions if isinstance(positions, list) else []


def normalize_accounts(portfolio_analysis_data):
    if not portfolio_analysis_data:
        return []

    accounts = portfolio_analysis_data.get("portfolio_analyses") or []
    return accounts if isinstance(accounts, list) else []


def get_account_lookup(portfolio_analysis_data):
    lookup = {}

    for account in normalize_accounts(portfolio_analysis_data):
        account_name = safe_text(account.get("account"), "Uncategorized")
        lookup[account_name] = account

    return lookup


def get_position_account(position):
    return safe_text(
        position.get("account")
        or position.get("account_type")
        or position.get("Account")
        or "Uncategorized"
    )


def get_position_symbol(position):
    return safe_upper(position.get("symbol") or position.get("Symbol") or "UNKNOWN")


def get_portfolio_mode(position, account=None):
    mode = safe_text(position.get("portfolio_mode") or position.get("mode"), "")

    if not mode and account:
        mode = safe_text(account.get("portfolio_mode"), "")

    if mode.lower() == "paper":
        return "paper"

    return "real"


def classify_market_bias(briefing, daily_action_data):
    market_regime = safe_upper((briefing or {}).get("market_regime"))
    risk_appetite = safe_upper((briefing or {}).get("risk_appetite"))
    risk_score = safe_float((briefing or {}).get("risk_score"), 50)
    volatility_state = safe_upper(((briefing or {}).get("volatility") or {}).get("volatility_state"))
    breadth_state = safe_upper(((briefing or {}).get("breadth") or {}).get("breadth_state"))
    daily_mode = safe_upper(((daily_action_data or {}).get("daily_mode") or {}).get("daily_mode"))

    if "PRESERVATION" in daily_mode or "RISK-OFF" in market_regime or risk_appetite == "LOW" or volatility_state == "STRESS":
        return {
            "market_bias": "DEFENSIVE",
            "risk_score": risk_score,
            "reason": "Market or daily mode is defensive, so existing exposure should be managed before adding risk.",
        }

    if "DEFENSIVE" in daily_mode or volatility_state == "ELEVATED" or breadth_state == "WEAK" or risk_score < 45:
        return {
            "market_bias": "CAUTIOUS",
            "risk_score": risk_score,
            "reason": "Market signals are not clean enough for broad adding; capital deployment should be selective.",
        }

    if "SELECTIVE" in daily_mode or breadth_state == "MIXED" or risk_appetite in ["NEUTRAL", "CAUTIOUS"]:
        return {
            "market_bias": "SELECTIVE",
            "risk_score": risk_score,
            "reason": "The environment supports selectivity, but not indiscriminate adding.",
        }

    return {
        "market_bias": "SUPPORTIVE",
        "risk_score": risk_score,
        "reason": "The environment is supportive enough to consider high-quality add opportunities.",
    }


def classify_account_pressure(account):
    if not account:
        return {
            "account_pressure": "UNKNOWN",
            "pressure_score": 50,
            "reason": "Account analysis unavailable.",
        }

    health_score = safe_float(account.get("portfolio_health_score"), 70)
    stability_score = safe_float(account.get("portfolio_stability_score"), 70)
    concentration_label = safe_upper(account.get("concentration_label"))
    bucket_percents = account.get("bucket_percents") or {}
    speculative_percent = safe_float(bucket_percents.get("speculative"), 0)
    defensive_percent = safe_float(bucket_percents.get("defensive"), 0)
    cash_percent = safe_float(bucket_percents.get("cash"), 0)

    pressure_score = 100 - ((health_score + stability_score) / 2)

    if "VERY HIGH" in concentration_label or speculative_percent >= 25 or stability_score < 45:
        return {
            "account_pressure": "HIGH",
            "pressure_score": round(max(pressure_score, 75), 2),
            "reason": "Account risk is elevated because concentration, stability, or speculative exposure needs attention.",
        }

    if "HIGH" in concentration_label or speculative_percent >= 15 or stability_score < 60 or health_score < 60:
        return {
            "account_pressure": "ELEVATED",
            "pressure_score": round(max(pressure_score, 58), 2),
            "reason": "Account has enough risk pressure to favor cautious adds and tighter maintenance.",
        }

    if defensive_percent + cash_percent >= 50 and stability_score >= 65:
        return {
            "account_pressure": "DEFENSIVE CAPACITY",
            "pressure_score": round(max(15, pressure_score), 2),
            "reason": "Account has meaningful defensive reserves, so selective deployment may be possible when setups are strong.",
        }

    return {
        "account_pressure": "NORMAL",
        "pressure_score": round(max(20, pressure_score), 2),
        "reason": "Account structure is stable enough for normal risk review.",
    }


def classify_position_pressure(position, account_pressure, market_bias):
    pnl = safe_float(position.get("unrealized_pl"), 0)
    pnl_percent = safe_float(position.get("unrealized_pl_percent"), 0)
    risk_level = safe_upper(position.get("risk_level"))
    guidance = safe_upper(position.get("guidance") or position.get("position_status"))
    actionability = safe_upper(position.get("actionability"))
    market_value = safe_float(position.get("market_value"), 0)
    total_basis = safe_float(position.get("total_basis"), 0)

    pressure = 0
    reasons = []

    if pnl_percent <= -8:
        pressure += 35
        reasons.append("Position drawdown is large enough to require active review.")
    elif pnl_percent <= -4:
        pressure += 22
        reasons.append("Position is under moderate P/L pressure.")
    elif pnl_percent >= 8:
        pressure -= 10
        reasons.append("Position has a meaningful unrealized gain.")
    elif pnl > 0:
        pressure -= 4
        reasons.append("Position is working modestly.")

    if "HIGH" in risk_level or "ELEVATED" in risk_level:
        pressure += 18
        reasons.append("Existing guidance marks risk as elevated.")

    if "EXIT" in guidance or "REDUCE" in guidance or "STOP" in guidance:
        pressure += 24
        reasons.append("Existing guidance already points to exit, reduction, or stop review.")
    elif "HOLD" in guidance:
        pressure -= 6
        reasons.append("Existing guidance supports holding rather than forcing action.")

    if "NOT" in actionability or "AVOID" in actionability:
        pressure += 10
        reasons.append("Actionability is weak, so adding capital is not favored.")

    if account_pressure in ["HIGH", "ELEVATED"]:
        pressure += 10
        reasons.append("Account-level risk pressure argues against adding without confirmation.")

    if market_bias in ["DEFENSIVE", "CAUTIOUS"]:
        pressure += 12
        reasons.append("Market posture is cautious, so position maintenance outranks new capital deployment.")
    elif market_bias == "SUPPORTIVE":
        pressure -= 5
        reasons.append("Market posture is supportive enough to avoid unnecessary defensive action.")

    if market_value <= 0 and total_basis <= 0:
        pressure -= 15
        reasons.append("Position appears cash-like or non-standard; reduce/exit logic may not apply.")

    pressure = max(0, min(100, round(pressure, 2)))

    return {
        "position_pressure_score": pressure,
        "pressure_reasons": reasons[:5],
    }


def decide_position_action(position, account, market_context):
    symbol = get_position_symbol(position)
    account_name = get_position_account(position)
    portfolio_mode = get_portfolio_mode(position, account)

    market_bias = market_context.get("market_bias", "SELECTIVE")
    account_pressure_data = classify_account_pressure(account)
    account_pressure = account_pressure_data.get("account_pressure")
    position_pressure = classify_position_pressure(position, account_pressure, market_bias)

    pnl = safe_float(position.get("unrealized_pl"), 0)
    pnl_percent = safe_float(position.get("unrealized_pl_percent"), 0)
    market_value = safe_float(position.get("market_value"), 0)
    shares = safe_float(position.get("shares") or position.get("qty"), 0)
    risk_level = safe_text(position.get("risk_level"), "Unknown")
    current_guidance = safe_text(position.get("guidance") or position.get("position_status"), "Monitor")
    pressure_score = position_pressure.get("position_pressure_score", 0)

    decision = "HOLD"
    action_label = "Hold / monitor"
    priority = "NORMAL"
    add_permission = "NO ADD"
    reduce_permission = "NO REDUCE NEEDED"
    suggested_action = "Hold the position and monitor existing guidance."
    decision_reason = "Position does not require urgent capital-allocation changes right now."
    add_rule = "Only add if the setup improves and the daily mode allows new risk."
    reduce_rule = "No reduction required unless risk level worsens or the position breaks your stop logic."

    if market_value <= 0 and shares == 0:
        decision = "IGNORE / CASH-LIKE"
        action_label = "No action"
        priority = "LOW"
        add_permission = "N/A"
        reduce_permission = "N/A"
        suggested_action = "No trade action required for this item."
        decision_reason = "This appears to be cash-like or non-position data."
        add_rule = "Not applicable."
        reduce_rule = "Not applicable."

    elif pressure_score >= 72 or pnl_percent <= -10:
        decision = "REDUCE / EXIT WATCH"
        action_label = "Protect capital"
        priority = "HIGH"
        add_permission = "DO NOT ADD"
        reduce_permission = "REDUCE OR EXIT WATCH"
        suggested_action = "Do not add. Review stop, position size, and whether this still deserves capital."
        decision_reason = "Position pressure is high due to drawdown, risk, account pressure, or weak market posture."
        add_rule = "Do not add until the position recovers, risk score improves, and market posture is supportive."
        reduce_rule = "Consider reducing if the position remains below your risk tolerance or violates stop logic."

    elif pressure_score >= 50 or pnl_percent <= -4 or market_bias in ["DEFENSIVE", "CAUTIOUS"]:
        decision = "HOLD / DO NOT ADD"
        action_label = "Maintenance first"
        priority = "ELEVATED"
        add_permission = "DO NOT ADD"
        reduce_permission = "REDUCE IF WEAKENS"
        suggested_action = "Hold only if the position remains within your risk plan. Avoid adding today."
        decision_reason = "Risk conditions are not strong enough to justify adding capital."
        add_rule = "Wait for stronger market posture and position-level confirmation before adding."
        reduce_rule = "Reduce if P/L pressure deepens, risk rating worsens, or the position loses support."

    elif pnl_percent >= 8 and market_bias in ["SELECTIVE", "SUPPORTIVE"] and account_pressure not in ["HIGH"]:
        decision = "HOLD / TRAIL WINNER"
        action_label = "Let winner work"
        priority = "NORMAL"
        add_permission = "ADD ONLY ON PULLBACK"
        reduce_permission = "TRIM OPTIONAL"
        suggested_action = "Hold the winner. Consider trailing risk rather than adding into strength."
        decision_reason = "The position is working, but adding should require a better entry or pullback."
        add_rule = "Add only on a controlled pullback or fresh confirmation with acceptable risk/reward."
        reduce_rule = "Trim only if the position becomes oversized, hits target, or market posture weakens."

    elif pnl_percent >= 0 and market_bias == "SUPPORTIVE" and account_pressure in ["NORMAL", "DEFENSIVE CAPACITY"]:
        decision = "HOLD / ADD SELECTIVELY"
        action_label = "Eligible for selective add"
        priority = "NORMAL"
        add_permission = "SELECTIVE ADD"
        reduce_permission = "NO REDUCE NEEDED"
        suggested_action = "Position may deserve more capital only if the setup still ranks well and risk/reward is clean."
        decision_reason = "Market posture, account pressure, and current P/L are constructive enough for selective adding."
        add_rule = "Add only with a defined stop, acceptable position size, and confirmation from scanner/market state."
        reduce_rule = "No reduction needed unless market posture deteriorates or the position becomes too concentrated."

    elif pnl_percent >= 0 and market_bias in ["SELECTIVE", "SUPPORTIVE"]:
        decision = "HOLD"
        action_label = "Hold steady"
        priority = "NORMAL"
        add_permission = "WAIT"
        reduce_permission = "NO REDUCE NEEDED"
        suggested_action = "Hold. Do not force additional capital until account and setup quality are stronger."
        decision_reason = "The position is acceptable, but the add case is not strong enough yet."
        add_rule = "Add only if account pressure improves and the setup becomes clearly actionable."
        reduce_rule = "No reduction needed unless risk level worsens."

    confidence = 50
    confidence += 15 if decision in ["REDUCE / EXIT WATCH", "HOLD / DO NOT ADD"] and pressure_score >= 50 else 0
    confidence += 12 if decision in ["HOLD / ADD SELECTIVELY", "HOLD / TRAIL WINNER"] and pnl_percent >= 0 else 0
    confidence += 8 if market_bias in ["DEFENSIVE", "SUPPORTIVE"] else 0
    confidence += 5 if account_pressure in ["HIGH", "NORMAL", "DEFENSIVE CAPACITY"] else 0
    confidence = max(35, min(92, round(confidence, 2)))

    return {
        "symbol": symbol,
        "account": account_name,
        "portfolio_mode": portfolio_mode,
        "decision": decision,
        "action_label": action_label,
        "priority": priority,
        "confidence": confidence,
        "add_permission": add_permission,
        "reduce_permission": reduce_permission,
        "suggested_action": suggested_action,
        "decision_reason": decision_reason,
        "add_rule": add_rule,
        "reduce_rule": reduce_rule,
        "current_guidance": current_guidance,
        "risk_level": risk_level,
        "shares": round(shares, 4),
        "market_value": round(market_value, 2),
        "unrealized_pl": round(pnl, 2),
        "unrealized_pl_percent": round(pnl_percent, 2),
        "position_pressure_score": pressure_score,
        "pressure_reasons": position_pressure.get("pressure_reasons", []),
        "account_pressure": account_pressure,
        "account_pressure_reason": account_pressure_data.get("reason"),
        "market_bias": market_bias,
    }


def summarize_capital_allocation(decisions, market_context, portfolio_data):
    total_value = safe_float((portfolio_data or {}).get("market_value"), 0)
    open_pl = safe_float((portfolio_data or {}).get("open_pl"), 0)
    open_pl_percent = safe_float((portfolio_data or {}).get("open_pl_percent"), 0)

    add_count = len([d for d in decisions if "ADD" in d.get("add_permission", "") and "DO NOT" not in d.get("add_permission", "")])
    reduce_count = len([d for d in decisions if d.get("decision") in ["REDUCE / EXIT WATCH", "HOLD / DO NOT ADD"]])
    high_priority_count = len([d for d in decisions if d.get("priority") == "HIGH"])

    market_bias = market_context.get("market_bias")

    if high_priority_count > 0:
        deployment_status = "MAINTENANCE FIRST"
        headline = "Address high-priority position risk before committing new capital."
    elif market_bias in ["DEFENSIVE", "CAUTIOUS"]:
        deployment_status = "RESTRICTED"
        headline = "New capital should stay restricted until the market posture improves."
    elif add_count > 0 and reduce_count == 0:
        deployment_status = "SELECTIVE DEPLOYMENT"
        headline = "Some positions may qualify for selective adds, but only with defined risk."
    else:
        deployment_status = "HOLD / MONITOR"
        headline = "Current portfolio does not require major capital movement today."

    return {
        "deployment_status": deployment_status,
        "headline": headline,
        "market_bias": market_bias,
        "total_position_value": round(total_value, 2),
        "open_pl": round(open_pl, 2),
        "open_pl_percent": round(open_pl_percent, 2),
        "add_candidates": add_count,
        "reduce_or_protect_count": reduce_count,
        "high_priority_count": high_priority_count,
        "summary": (
            f"Capital allocation status is {deployment_status.lower()}. "
            f"Market bias is {market_bias.lower() if market_bias else 'unknown'}, "
            f"open P/L is {round(open_pl_percent, 2)}%, and {high_priority_count} position(s) require high-priority review."
        ),
    }


def build_account_summaries(decisions):
    grouped = {}

    for decision in decisions:
        account = decision.get("account", "Uncategorized")

        if account not in grouped:
            grouped[account] = {
                "account": account,
                "position_count": 0,
                "add_candidates": 0,
                "reduce_or_protect_count": 0,
                "high_priority_count": 0,
                "total_market_value": 0,
                "open_pl": 0,
                "dominant_action": "HOLD / MONITOR",
            }

        item = grouped[account]
        item["position_count"] += 1
        item["total_market_value"] += safe_float(decision.get("market_value"), 0)
        item["open_pl"] += safe_float(decision.get("unrealized_pl"), 0)

        if "ADD" in decision.get("add_permission", "") and "DO NOT" not in decision.get("add_permission", ""):
            item["add_candidates"] += 1

        if decision.get("decision") in ["REDUCE / EXIT WATCH", "HOLD / DO NOT ADD"]:
            item["reduce_or_protect_count"] += 1

        if decision.get("priority") == "HIGH":
            item["high_priority_count"] += 1

    summaries = []

    for item in grouped.values():
        if item["high_priority_count"] > 0:
            item["dominant_action"] = "PROTECT CAPITAL"
        elif item["reduce_or_protect_count"] > item["add_candidates"]:
            item["dominant_action"] = "MAINTAIN / DO NOT ADD"
        elif item["add_candidates"] > 0:
            item["dominant_action"] = "SELECTIVE ADD POSSIBLE"
        else:
            item["dominant_action"] = "HOLD / MONITOR"

        item["total_market_value"] = round(item["total_market_value"], 2)
        item["open_pl"] = round(item["open_pl"], 2)
        summaries.append(item)

    summaries.sort(key=lambda x: (x["high_priority_count"], x["reduce_or_protect_count"], x["total_market_value"]), reverse=True)
    return summaries


def build_capital_allocation_guidance(
    briefing=None,
    portfolio_data=None,
    portfolio_analysis_data=None,
    daily_action_data=None,
):
    positions = normalize_positions(portfolio_data)
    account_lookup = get_account_lookup(portfolio_analysis_data)
    market_context = classify_market_bias(briefing, daily_action_data)

    decisions = []

    for position in positions:
        account_name = get_position_account(position)
        account = account_lookup.get(account_name)
        decisions.append(decide_position_action(position, account, market_context))

    decision_rank = {
        "HIGH": 4,
        "ELEVATED": 3,
        "NORMAL": 2,
        "LOW": 1,
    }

    decisions.sort(
        key=lambda item: (
            decision_rank.get(item.get("priority"), 0),
            safe_float(item.get("position_pressure_score"), 0),
            abs(safe_float(item.get("market_value"), 0)),
        ),
        reverse=True,
    )

    allocation_summary = summarize_capital_allocation(decisions, market_context, portfolio_data)
    account_summaries = build_account_summaries(decisions)

    directives = []

    if allocation_summary["high_priority_count"] > 0:
        directives.append("Resolve high-priority position risk before adding new trades.")

    if allocation_summary["deployment_status"] == "SELECTIVE DEPLOYMENT":
        directives.append("Only add to positions where trend, risk/reward, and account pressure all support the add.")

    if allocation_summary["reduce_or_protect_count"] > 0:
        directives.append("Protect or reduce weak positions before increasing exposure elsewhere.")

    if market_context.get("market_bias") in ["DEFENSIVE", "CAUTIOUS"]:
        directives.append("Keep new buying limited until market bias improves.")

    if not directives:
        directives.append("Maintain current positions and wait for clearer add/reduce triggers.")

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "allocation_summary": allocation_summary,
        "market_context": market_context,
        "account_summaries": account_summaries,
        "position_decisions": decisions,
        "top_position_decisions": decisions[:8],
        "directives": directives,
        "disclaimer": "TradeLayer is a decision-support tool, not financial advice. Use your own judgment and risk controls before placing trades.",
    }
