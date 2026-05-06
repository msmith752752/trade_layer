print("LOADING THIS FILE:", __file__)

import json
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.market_data import get_market_data
from app.trade_engine import generate_trade_signal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    with open("trade_log.json", "r") as f:
        trades = json.load(f)

    trades.append(trade)

    with open("trade_log.json", "w") as f:
        json.dump(trades, f, indent=2)

    return {"status": "trade logged", "trade": trade}


@app.get("/trade-log")
def get_trade_log():

    with open("trade_log.json", "r") as f:
        trades = json.load(f)

    updated = False

    for t in trades:

        if t.get("status") == "closed":
            continue

        if not t.get("stop_loss"):
            continue

        data = get_market_data(t["symbol"])
        if not data or "error" in data:
            continue

        current_price = data["price"]

        if current_price <= t["stop_loss"]:
            t["status"] = "closed"
            t["exit_price"] = current_price
            updated = True

    if updated:
        with open("trade_log.json", "w") as f:
            json.dump(trades, f, indent=2)

    return trades


@app.get("/performance")
def get_performance():

    with open("trade_log.json", "r") as f:
        trades = json.load(f)

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

            entry = t.get("entry")
            exit_price = t.get("exit_price")
            shares = t.get("shares", 0)

            if entry and exit_price:
                pl = (exit_price - entry) * shares
                total_pl += pl

                if pl > 0:
                    wins += 1
                else:
                    losses += 1

    avg_pl = total_pl / closed_trades if closed_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "open_trades": open_trades,
        "closed_trades": closed_trades,
        "wins": wins,
        "losses": losses,
        "total_pl": round(total_pl, 2),
        "avg_pl": round(avg_pl, 2)
    }


@app.get("/portfolio")
def get_portfolio():

    with open("trade_log.json", "r") as f:
        trades = json.load(f)

    open_pl = 0

    for t in trades:

        if t.get("status") != "open":
            continue

        data = get_market_data(t["symbol"])
        if not data or "error" in data:
            continue

        current = data["price"]
        entry = t["entry"]
        shares = t.get("shares", 0)

        open_pl += (current - entry) * shares

    return {
        "open_pl": round(open_pl, 2)
    }