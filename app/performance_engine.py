from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


SIGNAL_JOURNAL_PATH = Path("data") / "signal_journal.json"


def safe_float(value: Any, default: float = 0.0) -> float:
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


def safe_date(value: Any) -> Optional[datetime]:
    if not value:
        return None

    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    except Exception:
        return None


def get_trade_cost_basis(trade: Dict[str, Any]) -> float:
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


def get_trade_exit_price(trade: Dict[str, Any]) -> float:
    if trade.get("exit_price") is not None:
        return safe_float(trade.get("exit_price"))

    if trade.get("sale_price") is not None:
        return safe_float(trade.get("sale_price"))

    if trade.get("sell_price") is not None:
        return safe_float(trade.get("sell_price"))

    if trade.get("price") is not None:
        return safe_float(trade.get("price"))

    return 0.0


def is_option_spread(trade: Dict[str, Any]) -> bool:
    """Returns True if this trade is an option spread."""
    asset_type = str(trade.get("asset_type", "")).lower()
    action = str(trade.get("action", "")).lower()
    return (
        "spread" in asset_type
        or action in ["buy_to_open", "sell_to_close", "buy_to_close"]
        or trade.get("long_strike") is not None
    )


def calculate_spread_pl(trade: Dict[str, Any]) -> float:
    """P/L for option spread: (exit_premium - debit_paid) * 100"""
    if trade.get("realized_pl") is not None:
        return safe_float(trade.get("realized_pl"))
    debit_paid = safe_float(trade.get("price", trade.get("cost_basis", 0)))
    exit_premium = safe_float(trade.get("exit_price", trade.get("exit_premium", 0)))
    if exit_premium == 0:
        return 0.0
    return round((exit_premium - debit_paid) * 100, 2)


def calculate_realized_pl(trade: Dict[str, Any]) -> float:
    if trade.get("realized_pl") is not None:
        return safe_float(trade.get("realized_pl"))

    if is_option_spread(trade):
        return calculate_spread_pl(trade)

    shares = safe_float(trade.get("shares", trade.get("qty", 0)))
    cost_basis = get_trade_cost_basis(trade)
    exit_price = get_trade_exit_price(trade)

    if shares == 0:
        return 0.0

    return (exit_price - cost_basis) * abs(shares)


def classify_trade_result(pl: float) -> str:
    if pl > 0:
        return "WIN"

    if pl < 0:
        return "LOSS"

    return "FLAT"


def load_signal_journal(path: Path = SIGNAL_JOURNAL_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    try:
        with open(path, "r") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            entries = data.get("entries", [])
            return entries if isinstance(entries, list) else []

        return []

    except Exception as e:
        print("ERROR LOADING SIGNAL JOURNAL FOR PERFORMANCE ENGINE:", e)
        return []


def analyze_closed_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    closed = [trade for trade in trades if trade.get("status") == "closed"]
    open_trades = [trade for trade in trades if trade.get("status") == "open"]

    # Separate open spreads for unrealized P/L tracking
    open_spreads = [t for t in open_trades if is_option_spread(t)]

    enriched_closed = []

    for trade in closed:
        realized_pl = calculate_realized_pl(trade)
        result = classify_trade_result(realized_pl)
        spread = is_option_spread(trade)

        enriched_closed.append({
            **trade,
            "realized_pl": round(realized_pl, 2),
            "result": result,
            "symbol": str(trade.get("symbol", "UNKNOWN")).upper(),
            "account": trade.get("account") or trade.get("account_type") or "Uncategorized",
            "trade_type": "option_spread" if spread else "equity",
            "max_profit": safe_float(trade.get("max_profit")) if spread else None,
            "max_loss": safe_float(trade.get("max_loss")) if spread else None,
            "expiry": trade.get("expiry"),
        })

    # Enrich open spreads with current status
    enriched_open_spreads = []
    for trade in open_spreads:
        debit_paid = safe_float(trade.get("price", trade.get("cost_basis", 0)))
        max_loss = safe_float(trade.get("max_loss", debit_paid * 100))
        max_profit = safe_float(trade.get("max_profit", 0))
        enriched_open_spreads.append({
            **trade,
            "trade_type": "option_spread",
            "debit_paid": debit_paid,
            "max_loss": max_loss,
            "max_profit": max_profit,
            "symbol": str(trade.get("symbol", "UNKNOWN")).upper(),
            "account": trade.get("account") or trade.get("account_type") or "Uncategorized",
        })

    wins = [trade for trade in enriched_closed if trade["result"] == "WIN"]
    losses = [trade for trade in enriched_closed if trade["result"] == "LOSS"]

    total_realized_pl = sum(trade["realized_pl"] for trade in enriched_closed)
    average_trade_pl = total_realized_pl / len(enriched_closed) if enriched_closed else 0.0
    average_winner = sum(trade["realized_pl"] for trade in wins) / len(wins) if wins else 0.0
    average_loser = sum(trade["realized_pl"] for trade in losses) / len(losses) if losses else 0.0

    gross_profit = sum(trade["realized_pl"] for trade in wins)
    gross_loss = abs(sum(trade["realized_pl"] for trade in losses))
    profit_factor = gross_profit / gross_loss if gross_loss else None

    win_rate = (len(wins) / len(enriched_closed)) * 100 if enriched_closed else 0.0
    loss_rate = (len(losses) / len(enriched_closed)) * 100 if enriched_closed else 0.0

    expectancy = (
        ((win_rate / 100) * average_winner)
        + ((loss_rate / 100) * average_loser)
        if enriched_closed
        else 0.0
    )

    best_trade = max(enriched_closed, key=lambda x: x["realized_pl"], default=None)
    worst_trade = min(enriched_closed, key=lambda x: x["realized_pl"], default=None)

    return {
        "total_trades": len(trades),
        "open_trades": len(open_trades),
        "open_spreads": enriched_open_spreads,
        "closed_trades": len(enriched_closed),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len([trade for trade in enriched_closed if trade["result"] == "FLAT"]),
        "win_rate": round(win_rate, 2),
        "loss_rate": round(loss_rate, 2),
        "total_pl": round(total_realized_pl, 2),
        "total_realized_pl": round(total_realized_pl, 2),
        "avg_pl": round(average_trade_pl, 2),
        "average_trade_pl": round(average_trade_pl, 2),
        "average_winner": round(average_winner, 2),
        "average_loser": round(average_loser, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "expectancy": round(expectancy, 2),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "recent_closed_trades": enriched_closed[-10:],
    }


def classify_signal_outcome(entry: Dict[str, Any]) -> Dict[str, Any]:
    outcome = entry.get("outcome", {}) or {}
    label = str(outcome.get("outcome_label", "")).upper()

    current_return = safe_float(outcome.get("current_return_percent"), 0.0)
    max_favorable = safe_float(outcome.get("max_favorable_percent"), 0.0)
    max_adverse = safe_float(outcome.get("max_adverse_percent"), 0.0)

    if "TARGET" in label:
        result = "WIN"
    elif "STOP" in label:
        result = "LOSS"
    elif current_return > 0:
        result = "OPEN_POSITIVE"
    elif current_return < 0:
        result = "OPEN_NEGATIVE"
    else:
        result = "OPEN_FLAT"

    return {
        "result": result,
        "outcome_label": outcome.get("outcome_label"),
        "current_return_percent": round(current_return, 2),
        "max_favorable_percent": round(max_favorable, 2),
        "max_adverse_percent": round(max_adverse, 2),
        "days_elapsed": outcome.get("days_elapsed"),
    }


def bucket_score(score: Any) -> str:
    value = safe_float(score, 0)

    if value >= 200:
        return "200+"

    if value >= 150:
        return "150-199"

    if value >= 100:
        return "100-149"

    return "below_100"


def summarize_group(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "open_positive": 0,
            "open_negative": 0,
            "win_rate": 0.0,
            "average_current_return_percent": 0.0,
        }

    wins = [entry for entry in entries if entry["classified_outcome"]["result"] == "WIN"]
    losses = [entry for entry in entries if entry["classified_outcome"]["result"] == "LOSS"]
    open_positive = [entry for entry in entries if entry["classified_outcome"]["result"] == "OPEN_POSITIVE"]
    open_negative = [entry for entry in entries if entry["classified_outcome"]["result"] == "OPEN_NEGATIVE"]

    returns = [
        entry["classified_outcome"]["current_return_percent"]
        for entry in entries
        if entry["classified_outcome"]["current_return_percent"] is not None
    ]

    resolved = len(wins) + len(losses)
    win_rate = (len(wins) / resolved) * 100 if resolved else 0.0
    avg_return = sum(returns) / len(returns) if returns else 0.0

    return {
        "total": len(entries),
        "resolved": resolved,
        "wins": len(wins),
        "losses": len(losses),
        "open_positive": len(open_positive),
        "open_negative": len(open_negative),
        "win_rate": round(win_rate, 2),
        "average_current_return_percent": round(avg_return, 2),
    }


def analyze_signal_journal(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    enriched = []

    for entry in entries:
        classified = classify_signal_outcome(entry)

        enriched.append({
            **entry,
            "classified_outcome": classified,
            "score_bucket": bucket_score(entry.get("trade_score")),
            "strategy": entry.get("recommended_strategy") or entry.get("strategy") or "Unknown",
            "market_regime": entry.get("market_regime") or entry.get("market_state") or "Unknown",
        })

    summary = summarize_group(enriched)

    by_strategy = {}
    by_score_bucket = {}
    by_market_regime = {}

    for entry in enriched:
        by_strategy.setdefault(entry["strategy"], []).append(entry)
        by_score_bucket.setdefault(entry["score_bucket"], []).append(entry)
        by_market_regime.setdefault(entry["market_regime"], []).append(entry)

    strategy_performance = {
        key: summarize_group(value)
        for key, value in sorted(by_strategy.items())
    }

    score_bucket_performance = {
        key: summarize_group(value)
        for key, value in sorted(by_score_bucket.items())
    }

    market_regime_performance = {
        key: summarize_group(value)
        for key, value in sorted(by_market_regime.items())
    }

    best_strategy = None

    if strategy_performance:
        best_strategy = max(
            strategy_performance.items(),
            key=lambda item: (item[1].get("win_rate", 0), item[1].get("average_current_return_percent", 0)),
        )[0]

    best_score_bucket = None

    if score_bucket_performance:
        best_score_bucket = max(
            score_bucket_performance.items(),
            key=lambda item: (item[1].get("win_rate", 0), item[1].get("average_current_return_percent", 0)),
        )[0]

    return {
        "total_signals": len(enriched),
        "summary": summary,
        "best_strategy": best_strategy,
        "best_score_bucket": best_score_bucket,
        "strategy_performance": strategy_performance,
        "score_bucket_performance": score_bucket_performance,
        "market_regime_performance": market_regime_performance,
        "recent_signals": enriched[-10:],
    }


def build_performance_report(
    trades: List[Dict[str, Any]],
    signal_journal_entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Builds the TradeLayer performance report.

    This combines:
    - realized trade-log performance
    - forward-test signal journal performance

    It does not claim statistical significance. It is a measurement layer
    used to help TradeLayer learn which signals, structures, and score
    buckets are working over time.
    """

    if signal_journal_entries is None:
        signal_journal_entries = load_signal_journal()

    trade_performance = analyze_closed_trades(trades)
    signal_performance = analyze_signal_journal(signal_journal_entries)

    if signal_performance["total_signals"] < 10:
        confidence_label = "Early Sample"
        confidence_note = "Signal sample is still small. Use this as directional feedback, not statistical proof."
    elif signal_performance["total_signals"] < 30:
        confidence_label = "Developing Sample"
        confidence_note = "Signal sample is growing, but more observations are needed before relying on performance conclusions."
    else:
        confidence_label = "Usable Sample"
        confidence_note = "Signal sample is large enough to begin comparing strategy and score-bucket behavior."

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "engine": "TradeLayer Performance Analytics Engine V1",
        "confidence_label": confidence_label,
        "confidence_note": confidence_note,
        "trade_log_performance": trade_performance,
        "signal_journal_performance": signal_performance,

        # Backward-compatible fields used by the existing dashboard.
        "total_trades": trade_performance["total_trades"],
        "open_trades": trade_performance["open_trades"],
        "closed_trades": trade_performance["closed_trades"],
        "wins": trade_performance["wins"],
        "losses": trade_performance["losses"],
        "total_pl": trade_performance["total_pl"],
        "total_realized_pl": trade_performance["total_realized_pl"],
        "avg_pl": trade_performance["avg_pl"],
    }
