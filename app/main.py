print("LOADING THIS FILE:", __file__)

import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market_data import get_market_data, get_current_price
from app.trade_engine import generate_trade_signal
from app.market_state_engine import classify_market_state

from app.risk_engine import (
    calculate_risk_plan,
    get_risk_percent_levels,
)

from app.position_guidance_engine import (
    get_position_guidance,
)

from app.portfolio_engine import (
    analyze_portfolio,
)

from app.daily_action_engine import (
    build_daily_action_plan,
)

from app.position_decision_engine import (
    build_capital_allocation_guidance,
)

from app.market_driver_engine import (
    build_market_driver_impact,
)

from app.options_strategy_engine import (
    SMALL_ACCOUNT_VALUE,
    choose_trade_expression,
)

from app.covered_call_position_engine import (
    calculate_covered_call_position,
    get_sample_pltr_covered_call,
)

from app.options_contract_selector import (
    build_options_contract_candidates,
)

from app.options_engine import (
    get_options_quality,
)

from app.signal_journal_engine import (
    build_signal_journal_report,
)

from app.performance_engine import (
    build_performance_report,
)

from app.ai_interpretation_engine import (
    build_ai_interpretation,
)

from app.backtest_engine import (
    run_backtest,
    DEFAULT_SYMBOLS,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRADE_LOG_PATH = Path("trade_log.json")
PORTFOLIO_SNAPSHOT_PATH = Path("portfolio_snapshot.json")
LEGACY_PAPER_PORTFOLIO_PATH = Path("paper_portfolio.json")


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


def read_trade_log() -> list:
    if not TRADE_LOG_PATH.exists():
        return []

    with open(TRADE_LOG_PATH, "r") as f:
        return json.load(f)


def write_trade_log(trades: list) -> None:
    with open(TRADE_LOG_PATH, "w") as f:
        json.dump(trades, f, indent=2)


def read_portfolio_snapshot() -> list:
    snapshot_path = PORTFOLIO_SNAPSHOT_PATH

    if not snapshot_path.exists() and LEGACY_PAPER_PORTFOLIO_PATH.exists():
        snapshot_path = LEGACY_PAPER_PORTFOLIO_PATH

    if not snapshot_path.exists():
        return []

    try:
        with open(snapshot_path, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("positions", [])

        return []

    except Exception as e:
        print("ERROR LOADING PORTFOLIO SNAPSHOT:", e)
        return []


def get_trade_cost_basis(trade: dict) -> float:
    shares = safe_float(trade.get("shares", trade.get("qty", 0)))

    if trade.get("cost_basis") is not None:
        return safe_float(trade.get("cost_basis"))

    if trade.get("cost_per_share") is not None:
        return safe_float(trade.get("cost_per_share"))

    if trade.get("Cost/Share") is not None:
        return safe_float(trade.get("Cost/Share"))

    if trade.get("entry") is not None:
        return safe_float(trade.get("entry"))

    if trade.get("price") is not None:
        return safe_float(trade.get("price"))

    if trade.get("total_basis") is not None and shares != 0:
        return safe_float(trade.get("total_basis")) / abs(shares)

    return 0.0


def get_trade_total_basis(trade: dict) -> float:
    shares = safe_float(trade.get("shares", trade.get("qty", 0)))

    if trade.get("total_basis") is not None:
        return safe_float(trade.get("total_basis"))

    if trade.get("cost_basis_total") is not None:
        return safe_float(trade.get("cost_basis_total"))

    if trade.get("Cost Basis") is not None:
        return safe_float(trade.get("Cost Basis"))

    return get_trade_cost_basis(trade) * abs(shares)


def get_trade_exit_price(trade: dict) -> float:
    if trade.get("exit_price") is not None:
        return safe_float(trade.get("exit_price"))

    if trade.get("sale_price") is not None:
        return safe_float(trade.get("sale_price"))

    if trade.get("sell_price") is not None:
        return safe_float(trade.get("sell_price"))

    if trade.get("price") is not None:
        return safe_float(trade.get("price"))

    return 0.0


def get_manual_market_value(trade: dict):
    for key in ["market_value", "mkt_val", "value", "position_value", "Mkt Val (Market Value)"]:
        if trade.get(key) is not None:
            return safe_float(trade.get(key))

    return None


def is_cash_or_snapshot_position(trade: dict) -> bool:
    symbol = str(trade.get("symbol", "")).upper()
    asset_type = str(trade.get("asset_type", trade.get("Asset Type", ""))).lower()
    description = str(trade.get("description", "")).lower()

    return (
        "cash" in symbol.lower()
        or "cash" in asset_type
        or "money market" in asset_type
        or "cash" in description
        or "fixed income" in asset_type
    )


def enrich_open_position(trade: dict) -> dict:
    symbol = str(trade.get("symbol", "")).upper().strip()
    shares = safe_float(trade.get("shares", trade.get("qty", 0)))

    cost_basis = get_trade_cost_basis(trade)
    total_basis = get_trade_total_basis(trade)

    manual_market_value = get_manual_market_value(trade)

    current_price = trade.get("current_price")

    if current_price is None:
        current_price = trade.get("price")

    if current_price is None and not is_cash_or_snapshot_position(trade):
        current_price = get_current_price(symbol)

    current_price = safe_float(current_price, None)

    if manual_market_value is not None:
        market_value = manual_market_value

    elif current_price is not None and shares != 0:
        market_value = current_price * shares

    else:
        market_value = None

    if market_value is None:
        unrealized_pl = None
        unrealized_pl_percent = None

    else:
        unrealized_pl = market_value - total_basis

        unrealized_pl_percent = (
            (unrealized_pl / total_basis) * 100
            if total_basis
            else None
        )

    market_state = "supportive_trend"
    relative_strength = 1.5

    guidance_price = current_price

    if guidance_price is None and shares != 0 and market_value is not None:
        guidance_price = market_value / abs(shares)

    guidance_data = get_position_guidance(
        symbol=symbol,
        entry_price=cost_basis,
        current_price=guidance_price,
        unrealized_pl=unrealized_pl,
        unrealized_pl_percent=unrealized_pl_percent,
        market_state=market_state,
        relative_strength=relative_strength,
    )

    return {
        **trade,
        "symbol": symbol,
        "shares": shares,
        "cost_basis": round(cost_basis, 4),
        "total_basis": round(total_basis, 2),
        "current_price": round(guidance_price, 2) if guidance_price is not None else None,
        "market_value": round(market_value, 2) if market_value is not None else None,
        "unrealized_pl": round(unrealized_pl, 2) if unrealized_pl is not None else None,
        "unrealized_pl_percent": round(unrealized_pl_percent, 2) if unrealized_pl_percent is not None else None,
        "guidance": guidance_data["guidance"],
        "position_status": guidance_data["position_status"],
        "risk_level": guidance_data["risk_level"],
        "risk_score": guidance_data["risk_score"],
        "actionability": guidance_data["actionability"],
        "guidance_reason": guidance_data["guidance_reason"],
        "time_horizon": guidance_data["time_horizon"],
        "exit_strategy": guidance_data["exit_strategy"],
        "guidance_inputs": guidance_data["inputs"],
    }


def enrich_closed_trade(trade: dict) -> dict:
    shares = safe_float(trade.get("shares", trade.get("qty", 0)))
    cost_basis = get_trade_cost_basis(trade)
    exit_price = get_trade_exit_price(trade)

    realized_pl = trade.get("realized_pl")

    if realized_pl is None and shares != 0:
        realized_pl = (exit_price - cost_basis) * abs(shares)

    return {
        **trade,
        "cost_basis": round(cost_basis, 4),
        "exit_price": round(exit_price, 2),
        "realized_pl": round(safe_float(realized_pl), 2),
    }


def enrich_signal(signal: dict) -> dict:
    final_score = signal.get("score", 0)
    options_score = signal.get("options_score", 0)

    risk_score = signal.get("risk_score")

    if risk_score is None:
        if signal.get("overextended"):
            risk_score = "High"
        elif final_score >= 8:
            risk_score = "Moderate"
        else:
            risk_score = "Elevated"

    reasons = []

    if signal.get("signal_type") in ["strong_long", "long"]:
        reasons.append("Bullish directional setup passed the scanner filters.")

    if signal.get("overextended"):
        reasons.append(
            "Stock may be extended after a large move, so chasing risk is elevated."
        )
    else:
        reasons.append(
            "Move does not appear severely overextended based on current scanner rules."
        )

    if options_score and options_score > 0:
        reasons.append("Options positioning supports the setup.")

    if signal.get("trade_timeframe"):
        reasons.append(f"Suggested timeframe: {signal.get('trade_timeframe')}.")

    if signal.get("expected_hold"):
        reasons.append(f"Expected hold: {signal.get('expected_hold')}.")

    if signal.get("signal_type") in ["strong_long", "long"] and not signal.get("overextended"):
        actionable = True
        action_label = "ACTIONABLE TODAY"
        action_reason = "Meets trade criteria and is not flagged as overextended."

    elif signal.get("signal_type") in ["strong_long", "long"] and signal.get("overextended"):
        actionable = False
        action_label = "WATCH FOR PULLBACK"
        action_reason = "Trade setup is bullish, but price is extended. Avoid chasing."

    elif signal.get("signal_type") == "watchlist":
        actionable = False
        action_label = "WAIT FOR CONFIRMATION"
        action_reason = "Setup is close, but scanner wants more confirmation before entry."

    else:
        actionable = False
        action_label = "NO TRADE"
        action_reason = "Does not meet minimum trade criteria."

    signal["actionable"] = actionable
    signal["action_label"] = action_label
    signal["action_reason"] = action_reason

    return signal


MARKET_BRIEFING_SYMBOLS = ["SPY", "QQQ", "IWM", "^VIX"]
MARKET_DRIVER_SYMBOLS = [
    "SPY", "QQQ", "IWM", "^VIX", "^TNX",
    "USO", "XLK", "XLC", "XLY", "XLF", "XLE", "XLI", "XLV", "ARKK", "SGOV"
]

MARKET_OPEN_STRIP_SYMBOLS = [
    {"symbol": "SPY", "label": "S&P 500"},
    {"symbol": "QQQ", "label": "Nasdaq 100"},
    {"symbol": "DIA", "label": "Dow"},
    {"symbol": "IWM", "label": "Russell 2000"},
    {"symbol": "^VIX", "label": "VIX"},
    {"symbol": "^TNX", "label": "10Y Yield"},
]

MARKET_CLOSED_STRIP_SYMBOLS = [
    {"symbol": "ES=F", "label": "S&P Futures"},
    {"symbol": "NQ=F", "label": "Nasdaq Futures"},
    {"symbol": "YM=F", "label": "Dow Futures"},
    {"symbol": "RTY=F", "label": "Russell Futures"},
    {"symbol": "^VIX", "label": "VIX"},
    {"symbol": "^TNX", "label": "10Y Yield"},
]


def get_index_snapshot(symbol: str) -> dict:
    data = get_market_data(symbol)

    if not data or "error" in data:
        return {
            "symbol": symbol,
            "status": "unavailable",
            "price": None,
            "daily_change_percent": None,
            "market_state": None,
            "environment_score": None,
            "state_reason": f"Could not fetch market data for {symbol}.",
        }

    market_state = classify_market_state(data)

    price = (
        data.get("price")
        or data.get("current_price")
        or data.get("last_price")
        or data.get("close")
    )

    daily_change_percent = (
        data.get("daily_change_percent")
        or data.get("daily_change_pct")
        or data.get("change_percent")
        or data.get("percent_change")
        or data.get("day_change_percent")
    )

    daily_change = (
        data.get("daily_change")
        or data.get("change")
        or data.get("day_change")
    )

    return {
        "symbol": symbol,
        "status": "ok",
        "price": round(safe_float(price), 2) if price is not None else None,
        "daily_change": round(safe_float(daily_change), 2) if daily_change is not None else None,
        "daily_change_percent": round(safe_float(daily_change_percent), 2) if daily_change_percent is not None else None,
        "market_state": market_state.get("market_state"),
        "environment_score": market_state.get("environment_score"),
        "state_reason": market_state.get("state_reason"),
        "raw_market_context": market_state,
    }



def is_regular_market_open_now() -> bool:
    now_et = datetime.now(ZoneInfo("America/New_York"))

    if now_et.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)
    return market_open <= now_et.time() <= market_close


def build_market_status_strip() -> dict:
    market_is_open = is_regular_market_open_now()
    symbols = MARKET_OPEN_STRIP_SYMBOLS if market_is_open else MARKET_CLOSED_STRIP_SYMBOLS
    display_mode = "indexes" if market_is_open else "futures"
    session = "OPEN" if market_is_open else "CLOSED"

    items = []

    for config in symbols:
        symbol = config["symbol"]
        snapshot = get_index_snapshot(symbol)
        items.append({
            "symbol": symbol,
            "label": config["label"],
            "status": snapshot.get("status"),
            "price": snapshot.get("price"),
            "daily_change": snapshot.get("daily_change"),
            "change_percent": snapshot.get("daily_change_percent"),
            "market_state": snapshot.get("market_state"),
            "environment_score": snapshot.get("environment_score"),
        })

    summary = (
        "Regular market is open. Showing live index ETFs and key risk gauges."
        if market_is_open
        else "Regular market is closed. Showing futures and overnight/pre-market risk gauges where available."
    )

    return {
        "status": "ok",
        "market_session": session,
        "display_mode": display_mode,
        "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "summary": summary,
        "items": items,
    }


def _average_available(values: list, default: float = 0.0) -> float:
    clean_values = []

    for value in values:
        parsed = safe_float(value, None)
        if parsed is not None:
            clean_values.append(parsed)

    if not clean_values:
        return default

    return sum(clean_values) / len(clean_values)


def build_pre_market_command_center() -> dict:
    """
    Builds a concise pre-market operating command center.

    Purpose:
    TradeLayer already has market status, volatility, trade recommendations,
    options intelligence, and portfolio guidance. This function converts that
    context into one decision layer: whether to add risk, wait, or only manage
    existing positions.
    """

    market_status = build_market_status_strip()
    market_items = market_status.get("items", [])

    try:
        briefing = build_daily_market_briefing()
    except Exception as e:
        print("ERROR BUILDING PRE-MARKET BRIEFING:", e)
        briefing = {}

    futures_items = [
        item for item in market_items
        if str(item.get("symbol", "")).upper() in ["ES=F", "NQ=F", "YM=F", "RTY=F"]
    ]

    equity_index_items = [
        item for item in market_items
        if str(item.get("symbol", "")).upper() in ["SPY", "QQQ", "DIA", "IWM"]
    ]

    risk_items = futures_items if futures_items else equity_index_items
    average_change_percent = _average_available(
        [item.get("change_percent") for item in risk_items],
        default=0.0,
    )

    positive_count = len([
        item for item in risk_items
        if safe_float(item.get("change_percent"), 0) > 0.05
    ])
    negative_count = len([
        item for item in risk_items
        if safe_float(item.get("change_percent"), 0) < -0.05
    ])

    if average_change_percent >= 0.35 and positive_count >= max(1, len(risk_items) // 2):
        futures_tone = "BULLISH"
        futures_tone_label = "Futures are supportive"
        futures_score = 75
    elif average_change_percent <= -0.35 and negative_count >= max(1, len(risk_items) // 2):
        futures_tone = "BEARISH"
        futures_tone_label = "Futures are weak"
        futures_score = 25
    elif average_change_percent > 0.05:
        futures_tone = "MILDLY POSITIVE"
        futures_tone_label = "Futures are slightly positive"
        futures_score = 60
    elif average_change_percent < -0.05:
        futures_tone = "MILDLY NEGATIVE"
        futures_tone_label = "Futures are slightly negative"
        futures_score = 40
    else:
        futures_tone = "FLAT"
        futures_tone_label = "Futures are flat"
        futures_score = 50

    volatility = briefing.get("volatility", {}) or {}
    breadth = briefing.get("breadth", {}) or {}
    market_regime = briefing.get("market_regime", "UNKNOWN")
    risk_appetite = briefing.get("risk_appetite", "UNKNOWN")
    risk_score = safe_float(briefing.get("risk_score"), 50)
    volatility_state = volatility.get("volatility_state", "UNKNOWN")
    volatility_label = volatility.get("volatility_label", "Volatility unavailable")
    breadth_state = breadth.get("breadth_state", "UNKNOWN")

    command_score = 50
    command_score += (futures_score - 50) * 0.35
    command_score += (risk_score - 50) * 0.45
    command_score += (safe_float(volatility.get("volatility_score"), 50) - 50) * 0.20
    command_score = max(0, min(100, round(command_score, 2)))

    if volatility_state in ["STRESS", "ELEVATED"] and futures_tone in ["BEARISH", "MILDLY NEGATIVE"]:
        market_bias = "DEFENSIVE"
        new_trade_permission = "AVOID"
        today_action = "MANAGE POSITIONS ONLY"
        command_label = "Protect capital"
    elif command_score >= 68 and futures_tone in ["BULLISH", "MILDLY POSITIVE"] and risk_appetite in ["SUPPORTIVE", "NEUTRAL"]:
        market_bias = "SUPPORTIVE"
        new_trade_permission = "ALLOWED"
        today_action = "TRADE SELECTIVELY"
        command_label = "Risk-on but still selective"
    elif command_score <= 38 or risk_appetite in ["LOW", "CAUTIOUS"]:
        market_bias = "DEFENSIVE"
        new_trade_permission = "AVOID"
        today_action = "WATCH / MANAGE ONLY"
        command_label = "Low-conviction environment"
    else:
        market_bias = "MIXED"
        new_trade_permission = "SELECTIVE"
        today_action = "WAIT FOR CONFIRMATION"
        command_label = "Selective confirmation required"

    summary = (
        f"Pre-market command is {new_trade_permission.lower()}. "
        f"{futures_tone_label}, while the broader market regime is {market_regime.lower()} "
        f"with {volatility_label.lower()}. "
        f"Primary action: {today_action.lower()}."
    )

    directives = []

    if new_trade_permission == "ALLOWED":
        directives.extend([
            "New trades are permitted only if the setup also passes options quality and risk sizing checks.",
            "Favor defined-risk structures or small share size until the cash session confirms the pre-market tone.",
            "Avoid chasing gaps above the planned entry zone.",
        ])
    elif new_trade_permission == "SELECTIVE":
        directives.extend([
            "Do not force a new trade at the open; wait for confirmation after the first volatility window.",
            "Use TradeLayer top ideas as a watchlist, not automatic entries.",
            "Prioritize position management and only add risk if market drivers improve.",
        ])
    else:
        directives.extend([
            "Avoid new directional risk until volatility and futures improve.",
            "Focus on stop discipline, trimming weak positions, and protecting capital.",
            "Defined-risk or covered-call maintenance may be considered only if position-level logic supports it.",
        ])

    return {
        "status": "ok",
        "generated_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "market_session": market_status.get("market_session"),
        "display_mode": market_status.get("display_mode"),
        "command_score": command_score,
        "command_label": command_label,
        "market_bias": market_bias,
        "futures_tone": futures_tone,
        "futures_tone_label": futures_tone_label,
        "average_futures_change_percent": round(average_change_percent, 2),
        "volatility_state": volatility_state,
        "volatility_label": volatility_label,
        "breadth_state": breadth_state,
        "risk_appetite": risk_appetite,
        "market_regime": market_regime,
        "new_trade_permission": new_trade_permission,
        "today_action": today_action,
        "summary": summary,
        "directives": directives,
        "market_items": market_items,
    }

def classify_volatility_state(vix_snapshot: dict) -> dict:
    vix_price = safe_float(vix_snapshot.get("price"), None)

    if vix_price is None or vix_snapshot.get("status") != "ok":
        return {
            "volatility_state": "UNKNOWN",
            "volatility_label": "Volatility unavailable",
            "volatility_score": 50,
            "volatility_reason": "VIX data is unavailable, so volatility posture is neutral by default.",
        }

    if vix_price >= 30:
        return {
            "volatility_state": "STRESS",
            "volatility_label": "High volatility / stress",
            "volatility_score": 20,
            "volatility_reason": "VIX is elevated, suggesting unstable risk conditions and wider expected moves.",
        }

    if vix_price >= 22:
        return {
            "volatility_state": "ELEVATED",
            "volatility_label": "Elevated volatility",
            "volatility_score": 40,
            "volatility_reason": "VIX is above normal levels, so position sizing and chasing risk should be controlled.",
        }

    if vix_price >= 16:
        return {
            "volatility_state": "NORMAL",
            "volatility_label": "Normal volatility",
            "volatility_score": 65,
            "volatility_reason": "VIX is in a normal range, which supports selective trade activity.",
        }

    return {
        "volatility_state": "COMPRESSION",
        "volatility_label": "Low volatility / compression",
        "volatility_score": 75,
        "volatility_reason": "VIX is low, suggesting calmer conditions but potential complacency risk.",
    }


def classify_breadth_proxy(index_snapshots: dict) -> dict:
    risk_indices = [
        index_snapshots.get("SPY", {}),
        index_snapshots.get("QQQ", {}),
        index_snapshots.get("IWM", {}),
    ]

    ok_indices = [item for item in risk_indices if item.get("status") == "ok"]

    if not ok_indices:
        return {
            "breadth_state": "UNKNOWN",
            "breadth_label": "Breadth unavailable",
            "breadth_score": 50,
            "breadth_reason": "Index breadth proxy is unavailable.",
        }

    supportive_count = 0
    weak_count = 0
    total_score = 0

    for item in ok_indices:
        state = str(item.get("market_state", "")).lower()
        score = safe_float(item.get("environment_score"), 50)
        total_score += score

        if (
            "supportive" in state
            or "trend" in state
            or "breakout" in state
            or score >= 65
        ):
            supportive_count += 1

        if (
            "unstable" in state
            or "weak" in state
            or "avoid" in state
            or score <= 40
        ):
            weak_count += 1

    average_score = total_score / len(ok_indices)

    if supportive_count >= 2 and average_score >= 60:
        return {
            "breadth_state": "SUPPORTIVE",
            "breadth_label": "Supportive breadth proxy",
            "breadth_score": round(average_score, 2),
            "breadth_reason": "Major index proxies are broadly supportive, suggesting risk appetite is present.",
        }

    if weak_count >= 2 or average_score <= 40:
        return {
            "breadth_state": "WEAK",
            "breadth_label": "Weak breadth proxy",
            "breadth_score": round(average_score, 2),
            "breadth_reason": "Multiple index proxies are weak or unstable, suggesting caution.",
        }

    return {
        "breadth_state": "MIXED",
        "breadth_label": "Mixed breadth proxy",
        "breadth_score": round(average_score, 2),
        "breadth_reason": "Index proxies are mixed, so selective positioning is preferred over broad aggression.",
    }


def build_daily_market_briefing(scan_data: dict = None) -> dict:
    index_snapshots = {
        symbol: get_index_snapshot(symbol)
        for symbol in MARKET_BRIEFING_SYMBOLS
    }

    vix_snapshot = index_snapshots.get("^VIX", {})
    volatility = classify_volatility_state(vix_snapshot)
    breadth = classify_breadth_proxy(index_snapshots)

    spy_state = str(index_snapshots.get("SPY", {}).get("market_state", "")).lower()
    qqq_state = str(index_snapshots.get("QQQ", {}).get("market_state", "")).lower()
    iwm_state = str(index_snapshots.get("IWM", {}).get("market_state", "")).lower()

    risk_score = 50
    risk_score += (breadth.get("breadth_score", 50) - 50) * 0.6
    risk_score += (volatility.get("volatility_score", 50) - 50) * 0.4
    risk_score = max(0, min(100, round(risk_score, 2)))

    if volatility.get("volatility_state") in ["STRESS", "ELEVATED"] and breadth.get("breadth_state") == "WEAK":
        market_regime = "RISK-OFF / DEFENSIVE"
        risk_appetite = "LOW"
        recommended_posture = "Protect capital, avoid aggressive new risk, and prioritize defensive or defined-risk structures."
        best_structures = [
            "Cash / treasury exposure",
            "Defined-risk bearish or neutral spreads",
            "Small-size covered calls on existing positions",
        ]
        avoid_today = [
            "Aggressive momentum chasing",
            "Oversized directional trades",
            "Low-quality speculative names",
        ]

    elif breadth.get("breadth_state") == "SUPPORTIVE" and volatility.get("volatility_state") in ["NORMAL", "COMPRESSION"]:
        market_regime = "RISK-ON / SELECTIVE TREND"
        risk_appetite = "SUPPORTIVE"
        recommended_posture = "Selective long exposure is reasonable, but entries should still respect overextension and position sizing."
        best_structures = [
            "Long stock in high-quality setups",
            "Bull call spreads",
            "Cash-secured puts on names you want to own",
            "Covered calls on existing positions",
        ]
        avoid_today = [
            "Chasing extended moves",
            "Adding to weak positions without confirmation",
            "Ignoring stop levels",
        ]

    elif breadth.get("breadth_state") == "MIXED":
        market_regime = "MIXED / SELECTIVE"
        risk_appetite = "NEUTRAL"
        recommended_posture = "Favor selective trades only. Let account stability and position quality determine whether to add risk."
        best_structures = [
            "Covered calls",
            "Defined-risk vertical spreads",
            "Small starter positions",
            "Cash-secured puts only on high-quality names",
        ]
        avoid_today = [
            "Broad market assumptions",
            "Overconcentration in one theme",
            "Adding to speculative positions just because they are down",
        ]

    else:
        market_regime = "CAUTIOUS / LOW CONVICTION"
        risk_appetite = "CAUTIOUS"
        recommended_posture = "Wait for cleaner confirmation before adding meaningful risk."
        best_structures = [
            "Cash",
            "Treasury ETFs",
            "Small defined-risk trades only",
            "Covered calls against existing holdings",
        ]
        avoid_today = [
            "Low-conviction trades",
            "Overnight risk without a plan",
            "High-beta speculation",
        ]

    top_trade = scan_data.get("top_trade") if scan_data else None

    briefing_summary = (
        f"Today’s environment is classified as {market_regime}. "
        f"Risk appetite is {risk_appetite.lower()}, with {breadth.get('breadth_label', 'mixed breadth').lower()} "
        f"and {volatility.get('volatility_label', 'unclear volatility').lower()}. "
        f"{recommended_posture}"
    )

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "market_regime": market_regime,
        "risk_appetite": risk_appetite,
        "risk_score": risk_score,
        "recommended_posture": recommended_posture,
        "best_structures_today": best_structures,
        "avoid_today": avoid_today,
        "briefing_summary": briefing_summary,
        "volatility": volatility,
        "breadth": breadth,
        "index_snapshots": index_snapshots,
        "technical_context": {
            "spy_market_state": index_snapshots.get("SPY", {}).get("market_state"),
            "qqq_market_state": index_snapshots.get("QQQ", {}).get("market_state"),
            "iwm_market_state": index_snapshots.get("IWM", {}).get("market_state"),
            "spy_context": spy_state,
            "qqq_context": qqq_state,
            "iwm_context": iwm_state,
        },
        "top_trade_context": {
            "symbol": top_trade.get("symbol") if top_trade else None,
            "score": top_trade.get("score") if top_trade else None,
            "action_label": top_trade.get("action_label") if top_trade else None,
            "recommended_strategy": top_trade.get("recommended_strategy") if top_trade else None,
        },
    }


def normalize_conviction_score(raw_score) -> int:
    """
    Converts TradeLayer scanner scores into a 0-100 conviction score.
    Supports both older small-scale scores and future 0-100 scores.
    """

    score = safe_float(raw_score, 0)

    if score <= 10:
        score = score * 10

    return int(max(0, min(100, round(score))))


def infer_directional_bias(signal: dict) -> str:
    """
    Infers directional bias from the existing equity scanner output.
    Current scanner is mainly long-equity oriented, so bearish outputs remain conservative.
    """

    signal_type = str(signal.get("signal_type", "")).lower()
    action_label = str(signal.get("action_label", "")).lower()

    if signal_type in ["strong_long", "long"]:
        return "bullish"

    if "short" in signal_type or "bear" in signal_type or "put" in action_label:
        return "bearish"

    return "unclear"


def map_market_environment_for_options(briefing: dict) -> str:
    """
    Converts the broader market briefing into the simpler labels expected by
    the options strategy engine.
    """

    if not briefing:
        return "neutral"

    risk_appetite = str(briefing.get("risk_appetite", "")).upper()
    market_regime = str(briefing.get("market_regime", "")).upper()

    if "LOW" in risk_appetite or "RISK-OFF" in market_regime or "DEFENSIVE" in market_regime:
        return "defensive"

    if "SUPPORTIVE" in risk_appetite or "RISK-ON" in market_regime:
        return "supportive"

    if "CAUTIOUS" in risk_appetite:
        return "weak"

    return "neutral"


def map_volatility_environment_for_options(briefing: dict) -> str:
    """
    Converts VIX/volatility classifications into the labels expected by
    the options strategy engine.
    """

    if not briefing:
        return "stable"

    volatility = briefing.get("volatility", {}) or {}
    volatility_state = str(volatility.get("volatility_state", "")).upper()

    if volatility_state in ["STRESS", "ELEVATED"]:
        return "elevated"

    if volatility_state in ["NORMAL", "COMPRESSION"]:
        return "stable"

    return "neutral"



@app.get("/pre-market-command-center")
def pre_market_command_center():
    return build_pre_market_command_center()


@app.get("/")
def root():
    return {"message": "TradeLayer API is running"}


@app.get("/trade-signal")
def get_trade_signal(symbol: str):
    data = get_market_data(symbol)

    if not data or "error" in data:
        return {"error": f"Could not fetch data for {symbol}"}

    signal = generate_trade_signal(symbol, data)

    return enrich_signal(signal)


@app.get("/trade-scan")
def trade_scan():
    symbols = [
        "AAPL", "NVDA", "TSLA", "AMD", "MSFT",
        "META", "AMZN", "GOOGL", "NFLX", "AVGO",
        "PLTR", "SOFI", "INTC", "CSCO", "ADBE",
        "CRM", "ORCL", "PYPL", "UBER", "DIS",
        "BA", "JPM", "GS", "XOM", "CVX"
    ]

    trade_opportunities = []
    watchlist = []
    avoid = []
    failed_symbols = []

    for symbol in symbols:
        data = get_market_data(symbol)

        if not data or "error" in data:
            failed_symbols.append(symbol)
            continue

        signal = generate_trade_signal(symbol, data)
        signal = enrich_signal(signal)

        if signal["signal_type"] in ["strong_long", "long"]:
            trade_opportunities.append(signal)

        elif signal["signal_type"] == "watchlist":
            watchlist.append(signal)

        else:
            avoid.append(signal)

    trade_opportunities.sort(key=lambda x: x["score"], reverse=True)
    watchlist.sort(key=lambda x: x["score"], reverse=True)
    avoid.sort(key=lambda x: x["score"], reverse=True)

    return {
        "top_trade": trade_opportunities[0] if trade_opportunities else None,
        "trade_opportunities": trade_opportunities,
        "watchlist": watchlist,
        "avoid": avoid,
        "failed_symbols": failed_symbols,
        "scanned": len(symbols),
    }


@app.get("/trade-recommendations")
def trade_recommendations(account_value: float = SMALL_ACCOUNT_VALUE):
    """
    Builds a TradeLayer recommendation package that connects:
    - scanner output
    - market environment
    - volatility posture
    - small-account risk rules
    - options-vs-shares expression logic

    This endpoint recommends ideas only. It does not place trades.
    """

    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING TRADE RECOMMENDATION SCAN DATA:", e)
        scan_data = {
            "top_trade": None,
            "trade_opportunities": [],
            "watchlist": [],
            "avoid": [],
            "failed_symbols": [],
        }

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING TRADE RECOMMENDATION MARKET BRIEFING:", e)
        briefing_data = None

    top_trade = scan_data.get("top_trade") if scan_data else None

    if not top_trade:
        return {
            "status": "ok",
            "recommendation_type": "NO_TRADE",
            "summary": "No high-quality trade candidate was found by the scanner.",
            "account_value": round(account_value, 2),
            "preferred_action": "Stay patient and preserve capital.",
            "options_recommendation": choose_trade_expression(
                symbol="CASH",
                directional_bias="unclear",
                conviction_score=0,
                market_environment=map_market_environment_for_options(briefing_data),
                volatility_environment=map_volatility_environment_for_options(briefing_data),
                capital_efficiency_needed=True,
                account_value=account_value,
            ),
            "market_context": {
                "market_regime": briefing_data.get("market_regime") if briefing_data else None,
                "risk_appetite": briefing_data.get("risk_appetite") if briefing_data else None,
                "risk_score": briefing_data.get("risk_score") if briefing_data else None,
            },
            "scan_context": scan_data,
            "timestamp": datetime.now().isoformat(),
        }

    symbol = top_trade.get("symbol", "UNKNOWN")
    directional_bias = infer_directional_bias(top_trade)
    conviction_score = normalize_conviction_score(top_trade.get("score", 0))
    market_environment = map_market_environment_for_options(briefing_data)
    volatility_environment = map_volatility_environment_for_options(briefing_data)

    options_recommendation = choose_trade_expression(
        symbol=symbol,
        directional_bias=directional_bias,
        conviction_score=conviction_score,
        market_environment=market_environment,
        volatility_environment=volatility_environment,
        capital_efficiency_needed=True,
        account_value=account_value,
        scanner_recommended_strategy=top_trade.get("recommended_strategy") or top_trade.get("strategy"),
        strategy_family=top_trade.get("strategy_family"),
        options_pressure=top_trade.get("options_pressure"),
        overextended=top_trade.get("overextended", False),
    )

    summary = (
        f"TradeLayer's top candidate is {symbol}. "
        f"The current preferred expression is {options_recommendation.get('preferred_expression')}. "
        f"This is a recommendation only and should be manually reviewed before any trade is placed."
    )

    return {
        "status": "ok",
        "recommendation_type": "TRADE_CANDIDATE",
        "summary": summary,
        "account_value": round(account_value, 2),
        "top_trade": top_trade,
        "options_recommendation": options_recommendation,
        "market_context": {
            "market_regime": briefing_data.get("market_regime") if briefing_data else None,
            "risk_appetite": briefing_data.get("risk_appetite") if briefing_data else None,
            "risk_score": briefing_data.get("risk_score") if briefing_data else None,
            "market_environment_used": market_environment,
            "volatility_environment_used": volatility_environment,
        },
        "risk_note": "Small-account mode is active. Recommendations should favor defined risk, small size, and capital preservation.",
        "timestamp": datetime.now().isoformat(),
    }



@app.get("/options-intelligence")
def options_intelligence(
    symbol: Optional[str] = None,
    current_price: Optional[float] = None,
    directional_bias: Optional[str] = None,
):
    """
    Returns account-aware options contract candidates for TradeLayer.

    This endpoint does not place trades. It evaluates possible options
    structures against small-account survivability rules.
    Schwab live option-chain data can replace placeholder pricing later.
    """

    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING OPTIONS INTELLIGENCE SCAN DATA:", e)
        scan_data = {
            "top_trade": None,
            "trade_opportunities": [],
            "watchlist": [],
            "avoid": [],
            "failed_symbols": [],
        }

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING OPTIONS INTELLIGENCE MARKET BRIEFING:", e)
        briefing_data = None

    top_trade = scan_data.get("top_trade") if scan_data else None

    if top_trade:
        selected_symbol = symbol or top_trade.get("symbol", "CSCO")
        selected_price = current_price or safe_float(top_trade.get("entry"), 98.72)
        selected_bias = directional_bias or infer_directional_bias(top_trade)
        setup_source = "top_trade"
        setup_context = top_trade
    else:
        watchlist = scan_data.get("watchlist", []) if scan_data else []
        fallback = watchlist[0] if watchlist else None

        selected_symbol = symbol or (fallback.get("symbol") if fallback else "CSCO")
        selected_price = current_price or safe_float(fallback.get("entry") if fallback else 98.72, 98.72)
        selected_bias = directional_bias or (infer_directional_bias(fallback) if fallback else "bullish")
        setup_source = "watchlist_fallback" if fallback else "manual_default"
        setup_context = fallback

    individual_556 = build_options_contract_candidates(
        symbol=selected_symbol,
        current_price=selected_price,
        account_size=237.00,
        directional_bias=selected_bias,
    )

    roth_account = build_options_contract_candidates(
        symbol=selected_symbol,
        current_price=selected_price,
        account_size=859.00,
        directional_bias=selected_bias,
    )

    try:
        options_quality = get_options_quality(
            symbol=selected_symbol,
            current_price=selected_price,
            directional_bias=selected_bias,
        )
    except Exception as e:
        print("ERROR BUILDING OPTIONS QUALITY DATA:", e)
        options_quality = {
            "has_options_quality_data": False,
            "options_confidence": 0,
            "quality_label": "Unavailable",
            "actionability": "Unavailable",
            "summary": "Options quality data unavailable.",
            "avoid_reasons": ["Options quality data unavailable."],
            "structure_bias": {
                "preferred_structure": "NO TRADE",
                "structure_quality": "Unavailable",
                "reason": "Options quality data unavailable.",
            },
        }

    return {
        "status": "ok",
        "symbol": selected_symbol,
        "current_price": round(selected_price, 2),
        "directional_bias": selected_bias,
        "setup_source": setup_source,
        "setup_context": setup_context,
        "market_context": {
            "market_regime": briefing_data.get("market_regime") if briefing_data else None,
            "risk_appetite": briefing_data.get("risk_appetite") if briefing_data else None,
            "risk_score": briefing_data.get("risk_score") if briefing_data else None,
            "recommended_posture": briefing_data.get("recommended_posture") if briefing_data else None,
        },
        "options_quality": options_quality,
        "structure_quality": options_quality.get("structure_bias", {}),
        "execution_quality": {
            "options_confidence": options_quality.get("options_confidence"),
            "quality_label": options_quality.get("quality_label"),
            "actionability": options_quality.get("actionability"),
            "summary": options_quality.get("summary"),
            "avoid_reasons": options_quality.get("avoid_reasons", []),
        },
        "accounts": {
            "individual_556": individual_556,
            "roth_account": roth_account,
        },
        "risk_note": (
            "Options intelligence is account-aware. A bullish or bearish setup "
            "can still be rejected if max risk is too large for the account."
        ),
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/covered-call-position")
def covered_call_position(
    symbol: str = "PLTR",
    shares: int = 100,
    stock_cost_basis: float = 135.45,
    call_strike: float = 142.00,
    call_premium: float = 5.10,
    expiration: str = "2026-06-12",
    current_stock_price: Optional[float] = None,
    current_call_price: Optional[float] = None,
    account: str = "Schwab Brokerage",
):
    """
    Evaluates a covered call position such as the current PLTR setup.

    This endpoint is for position intelligence only.
    It does not place trades.
    """

    if current_stock_price is None:
        try:
            current_stock_price = get_current_price(symbol.upper())
        except Exception as e:
            print(f"ERROR FETCHING CURRENT PRICE FOR COVERED CALL {symbol}:", e)
            current_stock_price = None

    return calculate_covered_call_position(
        symbol=symbol,
        shares=shares,
        stock_cost_basis=stock_cost_basis,
        call_strike=call_strike,
        call_premium=call_premium,
        expiration=expiration,
        current_stock_price=current_stock_price,
        current_call_price=current_call_price,
        account=account,
    )


@app.get("/sample-pltr-covered-call")
def sample_pltr_covered_call():
    """
    Returns the current manual PLTR covered call test case.
    Useful for validating the covered call position engine.
    """

    return get_sample_pltr_covered_call()


@app.post("/log-trade")
def log_trade(trade: dict):
    trade["timestamp"] = datetime.now().isoformat()

    trades = read_trade_log()
    trades.append(trade)
    write_trade_log(trades)

    return {
        "status": "trade logged",
        "trade": trade,
    }


@app.get("/trade-log")
def get_trade_log():
    trades = read_trade_log()
    updated = False

    for t in trades:
        if t.get("status") == "closed":
            continue

        if not t.get("stop_loss"):
            continue

        current_price = get_current_price(t["symbol"])

        if current_price is None:
            continue

        if current_price <= t["stop_loss"]:
            t["status"] = "closed"
            t["exit_price"] = current_price
            updated = True

    if updated:
        write_trade_log(trades)

    return trades


@app.get("/portfolio")
def get_portfolio():
    trades = read_trade_log()
    snapshot_positions = read_portfolio_snapshot()

    open_positions = []
    closed_positions = []

    total_open_basis = 0
    total_market_value = 0
    total_unrealized_pl = 0

    for t in trades:
        if t.get("status") == "open":
            enriched = enrich_open_position(t)
            open_positions.append(enriched)

            total_open_basis += enriched.get("total_basis") or 0
            total_market_value += enriched.get("market_value") or 0
            total_unrealized_pl += enriched.get("unrealized_pl") or 0

        elif t.get("status") == "closed":
            closed_positions.append(enrich_closed_trade(t))

    for position in snapshot_positions:
        enriched = enrich_open_position(position)
        open_positions.append(enriched)

        total_open_basis += enriched.get("total_basis") or 0
        total_market_value += enriched.get("market_value") or 0
        total_unrealized_pl += enriched.get("unrealized_pl") or 0

    total_unrealized_pl_percent = (
        (total_unrealized_pl / total_open_basis) * 100
        if total_open_basis
        else 0
    )

    return {
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "open_count": len(open_positions),
        "closed_count": len(closed_positions),
        "open_basis": round(total_open_basis, 2),
        "market_value": round(total_market_value, 2),
        "open_pl": round(total_unrealized_pl, 2),
        "open_pl_percent": round(total_unrealized_pl_percent, 2),
    }


@app.get("/performance")
def get_performance():
    """
    Returns realized trade performance plus TradeLayer signal-journal analytics.

    The heavy calculation logic lives in app/performance_engine.py so main.py
    remains focused on API routing.
    """

    trades = read_trade_log()
    return build_performance_report(trades=trades)


@app.get("/signal-journal")
def signal_journal():
    """
    Captures the current top TradeLayer signal and evaluates previous journal entries.

    This is a forward-test journal, not a finalized backtest engine.
    It records what TradeLayer recommended and later checks how those signals performed.
    """

    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING SIGNAL JOURNAL SCAN DATA:", e)
        scan_data = None

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING SIGNAL JOURNAL MARKET BRIEFING:", e)
        briefing_data = None

    return build_signal_journal_report(
        scan_data=scan_data,
        briefing=briefing_data,
        auto_capture=True,
    )


@app.get("/risk-levels")
def risk_levels(account_value: float):
    return get_risk_percent_levels(account_value)


@app.get("/risk-plan")
def risk_plan(
    account_value: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
    symbol: Optional[str] = None,
    environment: Optional[str] = None,
    volatility_buffer_percent: float = 0.0,
    max_exposure_percent: float = 50.0,
    target_price: Optional[float] = None,
    trade_score: Optional[float] = None,
    signal_win_rate: Optional[float] = None,
    signal_sample_size: int = 0,
    volatility_state: Optional[str] = None,
):
    market_context = None
    risk_environment = environment

    if symbol:
        ticker = symbol.upper().strip()
        data = get_market_data(ticker)

        if data and "error" not in data:
            market_context = classify_market_state(data)
            risk_environment = market_context.get("market_state")

        else:
            market_context = {
                "market_state": None,
                "environment_score": None,
                "state_reason": f"Could not fetch market state for {ticker}.",
            }

    plan = calculate_risk_plan(
        account_value=account_value,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_price=stop_price,
        environment=risk_environment,
        volatility_buffer_percent=volatility_buffer_percent,
        max_exposure_percent=max_exposure_percent,
        target_price=target_price,
        trade_score=trade_score,
        signal_win_rate=signal_win_rate,
        signal_sample_size=signal_sample_size,
        volatility_state=volatility_state,
    )

    if plan.get("status") == "ok":
        plan["symbol"] = symbol.upper().strip() if symbol else None
        plan["market_context"] = market_context
        plan["risk_environment_used"] = risk_environment

    return plan


@app.get("/daily-briefing")
def daily_briefing():
    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING DAILY BRIEFING SCAN CONTEXT:", e)
        scan_data = None

    return build_daily_market_briefing(scan_data=scan_data)


@app.get("/daily-action-plan")
def daily_action_plan():
    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING DAILY ACTION SCAN CONTEXT:", e)
        scan_data = None

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING DAILY ACTION MARKET BRIEFING:", e)
        briefing_data = None

    try:
        portfolio_data = get_portfolio()
    except Exception as e:
        print("ERROR BUILDING DAILY ACTION PORTFOLIO DATA:", e)
        portfolio_data = None

    try:
        portfolio_analysis_data = portfolio_analysis()
    except Exception as e:
        print("ERROR BUILDING DAILY ACTION PORTFOLIO ANALYSIS:", e)
        portfolio_analysis_data = None

    return build_daily_action_plan(
        briefing=briefing_data,
        portfolio_data=portfolio_data,
        portfolio_analysis_data=portfolio_analysis_data,
        scan_data=scan_data,
    )



@app.get("/market-status-strip")
def market_status_strip():
    return build_market_status_strip()

@app.get("/market-driver-impact")
def market_driver_impact():
    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING MARKET DRIVER SCAN CONTEXT:", e)
        scan_data = None

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING MARKET DRIVER BRIEFING CONTEXT:", e)
        briefing_data = None

    try:
        portfolio_data = get_portfolio()
    except Exception as e:
        print("ERROR BUILDING MARKET DRIVER PORTFOLIO CONTEXT:", e)
        portfolio_data = None

    driver_snapshots = {}

    for symbol in MARKET_DRIVER_SYMBOLS:
        try:
            driver_snapshots[symbol] = get_index_snapshot(symbol)
        except Exception as e:
            print(f"ERROR FETCHING MARKET DRIVER {symbol}:", e)
            driver_snapshots[symbol] = {
                "symbol": symbol,
                "status": "unavailable",
                "price": None,
                "daily_change_percent": None,
                "market_state": None,
                "environment_score": None,
                "state_reason": f"Could not fetch market-driver data for {symbol}.",
            }

    return build_market_driver_impact(
        briefing=briefing_data,
        portfolio_data=portfolio_data,
        scan_data=scan_data,
        driver_snapshots=driver_snapshots,
    )


@app.get("/capital-allocation-guidance")
def capital_allocation_guidance():
    try:
        scan_data = trade_scan()
    except Exception as e:
        print("ERROR BUILDING CAPITAL ALLOCATION SCAN CONTEXT:", e)
        scan_data = None

    try:
        briefing_data = build_daily_market_briefing(scan_data=scan_data)
    except Exception as e:
        print("ERROR BUILDING CAPITAL ALLOCATION MARKET BRIEFING:", e)
        briefing_data = None

    try:
        portfolio_data = get_portfolio()
    except Exception as e:
        print("ERROR BUILDING CAPITAL ALLOCATION PORTFOLIO DATA:", e)
        portfolio_data = None

    try:
        portfolio_analysis_data = portfolio_analysis()
    except Exception as e:
        print("ERROR BUILDING CAPITAL ALLOCATION PORTFOLIO ANALYSIS:", e)
        portfolio_analysis_data = None

    try:
        daily_action_data = build_daily_action_plan(
            briefing=briefing_data,
            portfolio_data=portfolio_data,
            portfolio_analysis_data=portfolio_analysis_data,
            scan_data=scan_data,
        )
    except Exception as e:
        print("ERROR BUILDING CAPITAL ALLOCATION DAILY ACTION CONTEXT:", e)
        daily_action_data = None

    return build_capital_allocation_guidance(
        briefing=briefing_data,
        portfolio_data=portfolio_data,
        portfolio_analysis_data=portfolio_analysis_data,
        daily_action_data=daily_action_data,
    )


@app.get("/portfolio-analysis")
def portfolio_analysis():
    trades = read_trade_log()
    snapshot_positions = read_portfolio_snapshot()

    grouped_accounts = {}

    for trade in trades:
        if trade.get("status") != "open":
            continue

        account = (
            trade.get("account")
            or trade.get("account_type")
            or "Uncategorized"
        )

        if account not in grouped_accounts:
            grouped_accounts[account] = []

        enriched = enrich_open_position(trade)
        grouped_accounts[account].append(enriched)

    for position in snapshot_positions:
        account = (
            position.get("account")
            or "Portfolio Snapshot"
        )

        if account not in grouped_accounts:
            grouped_accounts[account] = []

        enriched = enrich_open_position(position)
        grouped_accounts[account].append(enriched)

    analyses = []

    for account_name, positions in grouped_accounts.items():
        analysis = analyze_portfolio(
            account_name=account_name,
            positions=positions,
        )

        analyses.append(analysis)

    analyses.sort(key=lambda x: x.get("total_value", 0), reverse=True)

    total_value = sum(x.get("total_value", 0) for x in analyses)

    return {
        "status": "ok",
        "accounts_analyzed": len(analyses),
        "combined_portfolio_value": round(total_value, 2),
        "portfolio_analyses": analyses,
    }

@app.get("/ai-briefing")
def ai_briefing():
    """
    Returns a plain-English AI interpretation of TradeLayer's current state.

    The AI explains structured engine output. It does not place trades or
    override risk controls.
    """

    try:
        scan_data = trade_scan()
    except Exception as e:
        print("AI BRIEFING: trade_scan unavailable:", e)
        scan_data = {}

    try:
        command_center = pre_market_command_center()
    except Exception as e:
        print("AI BRIEFING: command center unavailable:", e)
        command_center = {}

    try:
        recommendation = trade_recommendations()
    except Exception as e:
        print("AI BRIEFING: trade recommendations unavailable:", e)
        recommendation = {}

    try:
        performance = get_performance()
    except Exception as e:
        print("AI BRIEFING: performance unavailable:", e)
        performance = {}

    try:
        journal = signal_journal()
    except Exception as e:
        print("AI BRIEFING: signal journal unavailable:", e)
        journal = {}

    try:
        allocation = capital_allocation_guidance()
    except Exception as e:
        print("AI BRIEFING: allocation unavailable:", e)
        allocation = {}

    context = {
        "top_trade": scan_data.get("top_trade") if isinstance(scan_data, dict) else {},
        "trade_opportunities": (scan_data.get("trade_opportunities", [])[:3] if isinstance(scan_data, dict) else []),
        "command_center": command_center,
        "trade_recommendation": recommendation,
        "performance": performance,
        "signal_journal": journal,
        "capital_allocation": allocation,
    }

    return build_ai_interpretation(context)


@app.get("/backtest")
def backtest(
    symbols: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    min_score: int = 70,
    max_hold_days: int = 10,
    actionable_only: bool = True,
):
    """
    Run a historical backtest of TradeLayer's scanner logic.

    Parameters:
    - symbols: comma-separated list e.g. "AAPL,NVDA,MSFT" (defaults to full universe)
    - start: start date "YYYY-MM-DD" (defaults to 90 days ago)
    - end: end date "YYYY-MM-DD" (defaults to yesterday)
    - min_score: minimum technical score to include a signal (default 70)
    - max_hold_days: days to hold before closing at market price (default 10)
    - actionable_only: only include ACTIONABLE TODAY signals (default true)

    Example: /backtest?symbols=AAPL,NVDA&start=2025-01-01&end=2025-03-31
    """
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).date()

    # Default date range: last 90 days
    default_end = (today - timedelta(days=1)).isoformat()
    default_start = (today - timedelta(days=90)).isoformat()

    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else DEFAULT_SYMBOLS
    )

    start_date = start or default_start
    end_date = end or default_end

    return run_backtest(
        symbols=symbol_list,
        start_date=start_date,
        end_date=end_date,
        min_score=min_score,
        max_hold_days=max_hold_days,
        actionable_only=actionable_only,
    )
