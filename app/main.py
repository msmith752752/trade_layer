print("LOADING THIS FILE:", __file__)

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market_data import get_market_data, get_current_price
from app.trade_engine import generate_trade_signal

from app.risk_engine import (
    calculate_risk_plan,
    get_risk_percent_levels,
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


def read_trade_log() -> list:
    if not TRADE_LOG_PATH.exists():
        return []

    with open(TRADE_LOG_PATH, "r") as f:
        return json.load(f)


def write_trade_log(trades: list) -> None:
    with open(TRADE_LOG_PATH, "w") as f:
        json.dump(trades, f, indent=2)


def get_trade_cost_basis(trade: dict) -> float:
    """
    Returns per-share cost basis.
    Supports price, entry, cost_basis, or total_basis / shares.
    """
    shares = float(trade.get("shares", 0) or 0)

    if trade.get("cost_basis") is not None:
        return float(trade.get("cost_basis"))

    if trade.get("entry") is not None:
        return float(trade.get("entry"))

    if trade.get("price") is not None:
        return float(trade.get("price"))

    if trade.get("total_basis") is not None and shares > 0:
        return float(trade.get("total_basis")) / shares

    return 0.0


def get_trade_total_basis(trade: dict) -> float:
    shares = float(trade.get("shares", 0) or 0)

    if trade.get("total_basis") is not None:
        return float(trade.get("total_basis"))

    return get_trade_cost_basis(trade) * shares


def get_trade_exit_price(trade: dict) -> float:
    if trade.get("exit_price") is not None:
        return float(trade.get("exit_price"))

    if trade.get("sale_price") is not None:
        return float(trade.get("sale_price"))

    if trade.get("sell_price") is not None:
        return float(trade.get("sell_price"))

    if trade.get("price") is not None:
        return float(trade.get("price"))

    return 0.0


def get_position_guidance(unrealized_pl: float | None, unrealized_pl_percent: float | None) -> str:
    if unrealized_pl is None:
        return "hold_position / price unavailable"

    if unrealized_pl_percent is not None:
        if unrealized_pl_percent >= 5:
            return "monitor target / consider trimming"
        if unrealized_pl_percent <= -5:
            return "review stop / avoid adding"

    if unrealized_pl > 0:
        return "hold_position / monitor target"

    if unrealized_pl < 0:
        return "review stop / avoid adding"

    return "hold_position / monitor setup"


def enrich_open_position(trade: dict) -> dict:
    symbol = str(trade.get("symbol", "")).upper().strip()
    shares = float(trade.get("shares", 0) or 0)
    cost_basis = get_trade_cost_basis(trade)
    total_basis = get_trade_total_basis(trade)

    current_price = get_current_price(symbol)

    if current_price is None or shares <= 0:
        market_value = None
        unrealized_pl = None
        unrealized_pl_percent = None
    else:
        market_value = current_price * shares
        unrealized_pl = market_value - total_basis
        unrealized_pl_percent = (unrealized_pl / total_basis) * 100 if total_basis else None

    return {
        **trade,
        "symbol": symbol,
        "shares": shares,
        "cost_basis": round(cost_basis, 4),
        "total_basis": round(total_basis, 2),
        "current_price": round(current_price, 2) if current_price is not None else None,
        "market_value": round(market_value, 2) if market_value is not None else None,
        "unrealized_pl": round(unrealized_pl, 2) if unrealized_pl is not None else None,
        "unrealized_pl_percent": round(unrealized_pl_percent, 2) if unrealized_pl_percent is not None else None,
        "guidance": get_position_guidance(unrealized_pl, unrealized_pl_percent),
    }


def enrich_closed_trade(trade: dict) -> dict:
    shares = float(trade.get("shares", 0) or 0)
    cost_basis = get_trade_cost_basis(trade)
    exit_price = get_trade_exit_price(trade)

    realized_pl = trade.get("realized_pl")

    if realized_pl is None and shares > 0:
        realized_pl = (exit_price - cost_basis) * shares

    return {
        **trade,
        "cost_basis": round(cost_basis, 4),
        "exit_price": round(exit_price, 2),
        "realized_pl": round(float(realized_pl or 0), 2),
    }


def enrich_signal(signal: dict) -> dict:
    """
    Adds clearer score breakdown and explanation fields without changing
    the core trade recommendation logic.
    """

    final_score = signal.get("score", 0)
    technical_score = signal.get("technical_score", final_score)
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
        reasons.append("Stock may be extended after a large move, so chasing risk is elevated.")
    else:
        reasons.append("Move does not appear severely overextended based on current scanner rules.")

    if options_score and options_score > 0:
        reasons.append("Options positioning supports the setup.")

    if signal.get("trade_timeframe"):
        reasons.append(f"Suggested timeframe: {signal.get('trade_timeframe')}.")

    if signal.get("expected_hold"):
        reasons.append(f"Expected hold: {signal.get('expected_hold')}.")

    # ACTIONABILITY LAYER

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

    signal["score_breakdown"] = {
        "technical_score": technical_score,
        "options_score": options_score,
        "risk_score": risk_score,
        "final_score": final_score,
    }

    signal["trade_summary"] = {
        "headline": f"{signal.get('symbol', 'Unknown')} is currently ranked as a {signal.get('signal_type', 'unknown')} setup.",
        "why_this_trade": reasons,
        "exit_rule": signal.get("exit_rule", "Use target, stop loss, or scanner downgrade as exit guidance."),
    }

    return signal


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

    trade_opportunities, watchlist, avoid, failed_symbols = [], [], [], []

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
        "scanned": len(symbols)
    }


@app.post("/log-trade")
def log_trade(trade: dict):

    trade["timestamp"] = datetime.now().isoformat()

    trades = read_trade_log()
    trades.append(trade)

    write_trade_log(trades)

    return {"status": "trade logged", "trade": trade}


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
        "avg_pl": round(avg_pl, 2)
    }


@app.get("/portfolio")
def get_portfolio():

    trades = read_trade_log()

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


@app.get("/risk-levels")
def risk_levels(account_value: float):

    return get_risk_percent_levels(account_value)


@app.get("/risk-plan")
def risk_plan(
    account_value: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
):

    return calculate_risk_plan(
        account_value=account_value,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_price=stop_price,
    )