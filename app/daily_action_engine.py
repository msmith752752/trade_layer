"""
TradeLayer Daily Action Engine

Purpose:
Convert market regime, portfolio posture, open-position guidance, and scanner output
into one practical daily operating plan.

This engine is intentionally conservative. It is not a prediction engine and it does
not guarantee results. Its job is to reduce impulsive decisions, protect capital,
and make the dashboard answer: "What should I do today, and how am I doing?"
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


def safe_upper(value, default=""):
    if value is None:
        return default
    return str(value).upper().strip()


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


def classify_market_pressure(briefing):
    if not briefing:
        return {
            "market_pressure": "UNKNOWN",
            "market_pressure_score": 50,
            "reason": "Market briefing unavailable.",
        }

    risk_score = safe_float(briefing.get("risk_score"), 50)
    risk_appetite = safe_upper(briefing.get("risk_appetite"))
    market_regime = safe_upper(briefing.get("market_regime"))
    volatility_state = safe_upper((briefing.get("volatility") or {}).get("volatility_state"))
    breadth_state = safe_upper((briefing.get("breadth") or {}).get("breadth_state"))

    if "RISK-OFF" in market_regime or risk_appetite == "LOW" or volatility_state == "STRESS":
        return {
            "market_pressure": "HIGH",
            "market_pressure_score": min(100, max(70, 100 - risk_score)),
            "reason": "Market regime is defensive or volatility stress is elevated.",
        }

    if volatility_state == "ELEVATED" or breadth_state == "WEAK" or risk_score < 45:
        return {
            "market_pressure": "ELEVATED",
            "market_pressure_score": min(85, max(55, 100 - risk_score)),
            "reason": "Market internals or volatility require controlled risk-taking.",
        }

    if breadth_state == "MIXED" or risk_appetite in ["NEUTRAL", "CAUTIOUS"]:
        return {
            "market_pressure": "MIXED",
            "market_pressure_score": 50,
            "reason": "Market signals are mixed, so selectivity matters more than aggression.",
        }

    return {
        "market_pressure": "SUPPORTIVE",
        "market_pressure_score": max(0, 100 - risk_score),
        "reason": "Market regime is supportive enough for selective opportunities.",
    }


def summarize_portfolio_posture(portfolio_data, portfolio_analysis_data):
    positions = normalize_positions(portfolio_data)
    accounts = normalize_accounts(portfolio_analysis_data)

    open_pl = safe_float((portfolio_data or {}).get("open_pl"), 0)
    open_pl_percent = safe_float((portfolio_data or {}).get("open_pl_percent"), 0)
    market_value = safe_float((portfolio_data or {}).get("market_value"), 0)

    account_count = len(accounts)
    open_count = len(positions)

    average_health = 70
    average_stability = 70
    high_risk_accounts = []
    defensive_accounts = []
    simulation_accounts = []

    if accounts:
        average_health = sum(safe_float(a.get("portfolio_health_score"), 70) for a in accounts) / len(accounts)
        average_stability = sum(safe_float(a.get("portfolio_stability_score"), 70) for a in accounts) / len(accounts)

        for account in accounts:
            health_label = safe_upper(account.get("portfolio_health_label"))
            stability_label = safe_upper(account.get("portfolio_stability_label"))
            account_name = account.get("account", "Account")
            mode = str(account.get("portfolio_mode", "real")).lower()
            defensive_percent = safe_float((account.get("bucket_percents") or {}).get("defensive"), 0)
            cash_percent = safe_float((account.get("bucket_percents") or {}).get("cash"), 0)

            if "RISK" in health_label or "UNSTABLE" in stability_label:
                high_risk_accounts.append(account_name)

            if defensive_percent + cash_percent >= 50:
                defensive_accounts.append(account_name)

            if mode == "paper":
                simulation_accounts.append(account_name)

    if average_stability >= 80 and average_health >= 75:
        posture = "STABLE"
    elif average_stability >= 65 and average_health >= 60:
        posture = "BALANCED"
    elif average_stability >= 50 and average_health >= 50:
        posture = "MIXED"
    else:
        posture = "FRAGILE"

    if open_pl_percent <= -4:
        pnl_state = "UNDER PRESSURE"
    elif open_pl_percent >= 4:
        pnl_state = "WORKING"
    elif open_pl > 0:
        pnl_state = "SLIGHTLY POSITIVE"
    elif open_pl < 0:
        pnl_state = "SLIGHTLY NEGATIVE"
    else:
        pnl_state = "FLAT"

    return {
        "portfolio_posture": posture,
        "pnl_state": pnl_state,
        "account_count": account_count,
        "open_position_count": open_count,
        "market_value": round(market_value, 2),
        "open_pl": round(open_pl, 2),
        "open_pl_percent": round(open_pl_percent, 2),
        "average_health_score": round(average_health, 2),
        "average_stability_score": round(average_stability, 2),
        "high_risk_accounts": high_risk_accounts,
        "defensive_accounts": defensive_accounts,
        "simulation_accounts": simulation_accounts,
    }


def score_daily_mode(market_pressure, portfolio_posture):
    pressure = market_pressure.get("market_pressure")
    posture = portfolio_posture.get("portfolio_posture")
    open_pl_percent = safe_float(portfolio_posture.get("open_pl_percent"), 0)
    stability = safe_float(portfolio_posture.get("average_stability_score"), 70)

    score = 50

    if pressure == "SUPPORTIVE":
        score += 22
    elif pressure == "MIXED":
        score += 4
    elif pressure == "ELEVATED":
        score -= 15
    elif pressure == "HIGH":
        score -= 32

    if posture == "STABLE":
        score += 14
    elif posture == "BALANCED":
        score += 5
    elif posture == "MIXED":
        score -= 8
    elif posture == "FRAGILE":
        score -= 20

    if open_pl_percent >= 5:
        score += 4
    elif open_pl_percent <= -5:
        score -= 12

    if stability < 50:
        score -= 10

    score = max(0, min(100, round(score, 2)))

    if score >= 78:
        mode = "AGGRESSIVE SELECTIVE"
        label = "Risk allowed, but only in high-quality setups"
    elif score >= 58:
        mode = "SELECTIVE"
        label = "Trade selectively and manage open positions first"
    elif score >= 38:
        mode = "DEFENSIVE"
        label = "Maintenance first; new trades need strong confirmation"
    else:
        mode = "CAPITAL PRESERVATION"
        label = "Protect capital and avoid new risk unless conditions improve"

    return {
        "daily_mode": mode,
        "daily_mode_score": score,
        "daily_mode_label": label,
    }


def build_new_trade_permission(daily_mode, briefing, scan_data):
    top_trade = (scan_data or {}).get("top_trade") if scan_data else None
    mode = daily_mode.get("daily_mode")

    if mode == "AGGRESSIVE SELECTIVE":
        permission = "ALLOWED"
        max_new_trades = 2
        sizing = "Normal size only if the setup is not extended; otherwise reduce size."
    elif mode == "SELECTIVE":
        permission = "SELECTIVE ONLY"
        max_new_trades = 1
        sizing = "Starter size preferred. Do not add multiple correlated positions."
    elif mode == "DEFENSIVE":
        permission = "RESTRICTED"
        max_new_trades = 0
        sizing = "Maintenance first. Only consider a very small defined-risk trade."
    else:
        permission = "AVOID NEW RISK"
        max_new_trades = 0
        sizing = "No new directional trades. Preserve capital and review existing positions."

    top_trade_actionable = bool(top_trade and top_trade.get("actionable"))

    if top_trade and not top_trade_actionable and permission in ["ALLOWED", "SELECTIVE ONLY"]:
        permission_note = "Scanner has ideas, but the top trade is not cleanly actionable. Wait for better confirmation."
    elif top_trade and top_trade_actionable:
        permission_note = f"Top scanner candidate is {top_trade.get('symbol')}, but still confirm entry quality before acting."
    else:
        permission_note = "No clean scanner candidate is available right now."

    return {
        "permission": permission,
        "max_new_trades_today": max_new_trades,
        "sizing_guidance": sizing,
        "permission_note": permission_note,
        "top_trade_symbol": top_trade.get("symbol") if top_trade else None,
        "top_trade_action_label": top_trade.get("action_label") if top_trade else None,
    }


def classify_position_priority(position, daily_mode):
    guidance = safe_upper(position.get("guidance"))
    status = safe_upper(position.get("position_status"))
    risk_level = safe_upper(position.get("risk_level"))
    pl_percent = safe_float(position.get("unrealized_pl_percent"), 0)
    pl = safe_float(position.get("unrealized_pl"), 0)
    mode = daily_mode.get("daily_mode")

    priority_score = 40

    if "EXIT" in guidance or "REDUCE" in guidance:
        priority_score += 40
    elif "TIGHTEN" in guidance or "PROTECT" in guidance:
        priority_score += 28
    elif "AVOID" in guidance:
        priority_score += 18

    if risk_level == "HIGH":
        priority_score += 22
    elif risk_level == "ELEVATED":
        priority_score += 12

    if pl_percent <= -6:
        priority_score += 18
    elif pl_percent >= 8:
        priority_score += 10

    if mode in ["DEFENSIVE", "CAPITAL PRESERVATION"] and pl < 0:
        priority_score += 10

    priority_score = max(0, min(100, round(priority_score, 2)))

    if priority_score >= 82:
        priority = "URGENT REVIEW"
    elif priority_score >= 65:
        priority = "MANAGE TODAY"
    elif priority_score >= 48:
        priority = "MONITOR"
    else:
        priority = "NO ACTION"

    if "EXIT" in guidance or "REDUCE" in guidance:
        action = "Review exit/reduction plan"
    elif "TIGHTEN" in guidance:
        action = "Tighten risk controls"
    elif "PROTECT" in guidance:
        action = "Protect profits"
    elif "AVOID" in guidance:
        action = "Do not add"
    elif pl_percent >= 5:
        action = "Hold winner with discipline"
    elif pl_percent < 0:
        action = "Monitor weakness"
    else:
        action = "Hold / monitor"

    reason_parts = []

    if position.get("guidance_reason"):
        reason_parts.append(str(position.get("guidance_reason")))
    elif guidance:
        reason_parts.append(f"Existing position engine says {guidance}.")

    if mode in ["DEFENSIVE", "CAPITAL PRESERVATION"]:
        reason_parts.append("Daily mode is defensive, so existing-position maintenance comes before new trades.")

    if pl_percent <= -4:
        reason_parts.append("Position is below cost basis enough to require discipline.")
    elif pl_percent >= 5:
        reason_parts.append("Position has a gain that should be protected, not ignored.")

    if not reason_parts:
        reason_parts.append("No major risk trigger detected from current guidance inputs.")

    return {
        "symbol": position.get("symbol"),
        "account": position.get("account") or position.get("account_type") or "Uncategorized",
        "portfolio_mode": position.get("portfolio_mode", "real"),
        "shares": position.get("shares"),
        "current_price": position.get("current_price"),
        "market_value": position.get("market_value"),
        "unrealized_pl": position.get("unrealized_pl"),
        "unrealized_pl_percent": position.get("unrealized_pl_percent"),
        "existing_guidance": position.get("guidance"),
        "position_status": position.get("position_status"),
        "risk_level": position.get("risk_level"),
        "priority": priority,
        "priority_score": priority_score,
        "recommended_action": action,
        "action_reason": " ".join(reason_parts),
    }


def build_position_action_plan(portfolio_data, daily_mode):
    positions = normalize_positions(portfolio_data)
    action_items = [classify_position_priority(position, daily_mode) for position in positions]

    action_items.sort(key=lambda item: item.get("priority_score", 0), reverse=True)

    urgent = [item for item in action_items if item.get("priority") == "URGENT REVIEW"]
    manage_today = [item for item in action_items if item.get("priority") == "MANAGE TODAY"]
    monitor = [item for item in action_items if item.get("priority") == "MONITOR"]
    no_action = [item for item in action_items if item.get("priority") == "NO ACTION"]

    if urgent:
        headline = f"Review {len(urgent)} position(s) before considering new trades."
    elif manage_today:
        headline = f"Manage {len(manage_today)} position(s) today; keep new risk selective."
    elif monitor:
        headline = "Portfolio is mostly stable; monitor active positions."
    else:
        headline = "No major maintenance trigger detected."

    return {
        "headline": headline,
        "urgent_review": urgent,
        "manage_today": manage_today,
        "monitor": monitor,
        "no_action": no_action,
        "top_actions": action_items[:6],
        "action_counts": {
            "urgent_review": len(urgent),
            "manage_today": len(manage_today),
            "monitor": len(monitor),
            "no_action": len(no_action),
        },
    }


def build_account_action_plan(portfolio_analysis_data, daily_mode):
    accounts = normalize_accounts(portfolio_analysis_data)
    mode = daily_mode.get("daily_mode")
    account_actions = []

    for account in accounts:
        health = safe_float(account.get("portfolio_health_score"), 70)
        stability = safe_float(account.get("portfolio_stability_score"), 70)
        recommendation = account.get("recommendation") or account.get("recommendation_label") or "HOLD"
        account_name = account.get("account", "Account")
        bucket_percents = account.get("bucket_percents") or {}
        speculative = safe_float(bucket_percents.get("speculative"), 0)
        defensive = safe_float(bucket_percents.get("defensive"), 0) + safe_float(bucket_percents.get("cash"), 0)

        if mode in ["DEFENSIVE", "CAPITAL PRESERVATION"] and speculative >= 10:
            action = "Avoid adding speculative risk"
            reason = "Daily mode is defensive and this account already has speculative exposure."
        elif stability < 55:
            action = "Improve stability before adding risk"
            reason = "Portfolio stability score is below the preferred range."
        elif health < 55:
            action = "Reduce weak links / concentration"
            reason = "Portfolio health score is mixed or elevated risk."
        elif defensive >= 50 and mode in ["AGGRESSIVE SELECTIVE", "SELECTIVE"]:
            action = "Selective deployment allowed"
            reason = "Defensive reserves are healthy and the daily mode allows selective risk."
        else:
            action = recommendation
            reason = "Account-level recommendation remains the primary guide."

        account_actions.append({
            "account": account_name,
            "portfolio_mode": account.get("portfolio_mode", "real"),
            "health_score": round(health, 2),
            "stability_score": round(stability, 2),
            "recommendation": recommendation,
            "daily_account_action": action,
            "action_reason": reason,
        })

    account_actions.sort(key=lambda item: (item.get("stability_score", 0), item.get("health_score", 0)))
    return account_actions


def build_daily_directives(daily_mode, trade_permission, position_plan, portfolio_posture, briefing):
    directives = []
    mode = daily_mode.get("daily_mode")

    if position_plan.get("urgent_review"):
        directives.append("Handle urgent position reviews before opening any new trades.")

    if mode == "CAPITAL PRESERVATION":
        directives.append("Do not force trades today; protect cash and reduce avoidable risk.")
    elif mode == "DEFENSIVE":
        directives.append("Maintenance first. New trades should be rare, smaller, and clearly defined-risk.")
    elif mode == "SELECTIVE":
        directives.append("One clean trade is better than several average trades.")
    else:
        directives.append("Risk is allowed, but only in high-quality, non-extended setups.")

    if safe_float(portfolio_posture.get("open_pl_percent"), 0) >= 4:
        directives.append("Open P/L is positive; avoid giving back gains through unnecessary new risk.")
    elif safe_float(portfolio_posture.get("open_pl_percent"), 0) <= -4:
        directives.append("Open P/L is under pressure; stabilize existing positions before adding exposure.")

    avoid_today = (briefing or {}).get("avoid_today") or []
    if avoid_today:
        directives.append(f"Avoid today: {avoid_today[0]}")

    directives.append(trade_permission.get("sizing_guidance"))

    return [item for item in directives if item]


def build_daily_action_plan(
    briefing=None,
    portfolio_data=None,
    portfolio_analysis_data=None,
    scan_data=None,
):
    market_pressure = classify_market_pressure(briefing)
    portfolio_posture = summarize_portfolio_posture(portfolio_data, portfolio_analysis_data)
    daily_mode = score_daily_mode(market_pressure, portfolio_posture)
    trade_permission = build_new_trade_permission(daily_mode, briefing, scan_data)
    position_plan = build_position_action_plan(portfolio_data, daily_mode)
    account_plan = build_account_action_plan(portfolio_analysis_data, daily_mode)
    directives = build_daily_directives(
        daily_mode=daily_mode,
        trade_permission=trade_permission,
        position_plan=position_plan,
        portfolio_posture=portfolio_posture,
        briefing=briefing,
    )

    briefing_summary = (briefing or {}).get("briefing_summary") or "Market briefing unavailable."

    summary = (
        f"TradeLayer mode is {daily_mode.get('daily_mode')}. "
        f"New trade permission: {trade_permission.get('permission')}. "
        f"{position_plan.get('headline')} "
        f"{briefing_summary}"
    )

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "daily_mode": daily_mode,
        "market_pressure": market_pressure,
        "portfolio_posture": portfolio_posture,
        "new_trade_permission": trade_permission,
        "position_action_plan": position_plan,
        "account_action_plan": account_plan,
        "daily_directives": directives,
        "disclaimer": "Decision-support only. Confirm prices, news, liquidity, and personal risk limits before placing trades.",
    }
