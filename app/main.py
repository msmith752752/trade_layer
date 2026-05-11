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
        or data.get("change_percent")
        or data.get("percent_change")
        or data.get("day_change_percent")
    )

    return {
        "symbol": symbol,
        "status": "ok",
        "price": round(safe_float(price), 2) if price is not None else None,
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
    trades = read_trade_log()

    total_trades = len(trades)
    open_trades = 0
    closed_trades = 0
    wins = 0
    losses = 0
    total_pl = 0

    for t in trades:
        if t.get("status") == "open":
            open_trades += 1
            continue

        if t.get("status") == "closed":
            closed_trades += 1
            closed_trade = enrich_closed_trade(t)
            pl = closed_trade.get("realized_pl", 0)
            total_pl += pl

            if pl > 0:
                wins += 1

            elif pl < 0:
                losses += 1

    avg_pl = total_pl / closed_trades if closed_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "open_trades": open_trades,
        "closed_trades": closed_trades,
        "wins": wins,
        "losses": losses,
        "total_pl": round(total_pl, 2),
        "total_realized_pl": round(total_pl, 2),
        "avg_pl": round(avg_pl, 2),
    }


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