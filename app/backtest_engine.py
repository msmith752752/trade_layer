"""
TradeLayer Backtest Engine

Replays the TradeLayer scanner logic against historical price data
for a given symbol list and date range.

For each trading day in the range:
- Pulls OHLCV data as if we were at that date
- Runs the same scoring logic as the live scanner
- Simulates entry at next-day open, tracks outcome vs target/stop
- Returns a full trade-by-trade log and summary stats

This is NOT live trading. No orders are placed. Suggestions only.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Optional


# ─────────────────────────────────────────────
# Default universe — same as your live scanner
# ─────────────────────────────────────────────
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "AMD", "ORCL", "CRM",
    "CSCO", "INTC", "PLTR", "COIN", "MSTR",
    "SPY", "QQQ", "ARKK", "SOFI", "HOOD",
]


def _safe_float(val, default=None):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _score_day(hist_slice: pd.DataFrame) -> Optional[dict]:
    """
    Runs TradeLayer's core scoring logic against a historical slice.
    Returns a scored signal dict or None if data is insufficient.
    hist_slice: DataFrame with columns Open, High, Low, Close, Volume
                indexed by date, covering up to the 'signal date'
    """
    if hist_slice is None or len(hist_slice) < 50:
        return None

    try:
        latest = hist_slice.iloc[-1]
        previous = hist_slice.iloc[-2]

        current_price = float(latest["Close"])
        current_volume = float(latest["Volume"])
        prev_close = float(previous["Close"])

        last_20 = hist_slice.tail(20)
        last_50 = hist_slice.tail(50)

        avg_price_20 = float(last_20["Close"].mean())
        avg_price_50 = float(last_50["Close"].mean())
        avg_volume_20 = float(last_20["Volume"].mean())

        daily_change_pct = ((current_price - prev_close) / prev_close) * 100

        # ── Trend structure ──────────────────────────
        above_20 = current_price > avg_price_20
        above_50 = current_price > avg_price_50
        bullish_structure = avg_price_20 > avg_price_50

        technical_score = 0
        tech_reasons = []

        if above_20:
            technical_score += 20
            tech_reasons.append("above_20ma")
        if above_50:
            technical_score += 20
            tech_reasons.append("above_50ma")
        if bullish_structure:
            technical_score += 20
            tech_reasons.append("bullish_structure")
        if daily_change_pct > 0:
            technical_score += 15
            tech_reasons.append("positive_momentum")
        if daily_change_pct > 1:
            technical_score += 10
            tech_reasons.append("strong_momentum")

        # ── Volume confirmation ───────────────────────
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
        volume_spike = volume_ratio >= 1.5

        if volume_spike:
            technical_score += 10
            tech_reasons.append("volume_spike")

        # ── Liquidity ────────────────────────────────
        if avg_volume_20 >= 1_000_000:
            technical_score += 5
            tech_reasons.append("liquid")

        # ── Overextension check ───────────────────────
        overextended = daily_change_pct > 8

        # ── Action label ──────────────────────────────
        if overextended:
            action_label = "WATCH FOR PULLBACK"
        elif technical_score >= 70 and above_20 and above_50:
            action_label = "ACTIONABLE TODAY"
        elif technical_score >= 50:
            action_label = "WAIT FOR CONFIRMATION"
        else:
            action_label = "NO TRADE"

        # ── Entry / Stop / Target ─────────────────────
        atr_approx = float(hist_slice.tail(14).apply(
            lambda r: r["High"] - r["Low"], axis=1
        ).mean())

        entry = round(current_price, 2)
        stop = round(current_price - (atr_approx * 1.5), 2)
        target = round(current_price + (atr_approx * 3.0), 2)

        rr = round((target - entry) / (entry - stop), 2) if (entry - stop) > 0 else None

        return {
            "technical_score": round(technical_score, 2),
            "action_label": action_label,
            "entry": entry,
            "stop": stop,
            "target": target,
            "reward_risk_ratio": rr,
            "daily_change_pct": round(daily_change_pct, 2),
            "volume_spike": volume_spike,
            "volume_ratio": round(volume_ratio, 2),
            "above_20ma": above_20,
            "above_50ma": above_50,
            "bullish_structure": bullish_structure,
            "overextended": overextended,
            "tech_reasons": tech_reasons,
        }

    except Exception as e:
        print(f"SCORE ERROR: {e}")
        return None


def _simulate_outcome(
    full_hist: pd.DataFrame,
    signal_date: date,
    entry: float,
    target: float,
    stop: float,
    max_hold_days: int = 10,
) -> dict:
    """
    Simulates trade outcome starting from the day after the signal.
    Entry assumed at next-day open price.
    Checks each subsequent day's high/low for target or stop hit.
    """
    # Get rows after signal date
    future = full_hist[full_hist.index.date > signal_date]

    if future.empty:
        return {
            "outcome_label": "NO DATA",
            "actual_entry": None,
            "exit_price": None,
            "return_pct": None,
            "days_held": None,
            "target_hit": False,
            "stop_hit": False,
            "exit_date": None,
            "return_1d_pct": None,
            "return_5d_pct": None,
            "return_10d_pct": None,
        }

    # Actual entry = next day open
    actual_entry = float(future.iloc[0]["Open"])

    # Recalculate target/stop relative to actual entry
    # (keep same R/R structure but anchor to real fill)
    entry_diff = actual_entry - entry
    adj_target = round(target + entry_diff, 2)
    adj_stop = round(stop + entry_diff, 2)

    target_hit_date = None
    stop_hit_date = None
    exit_price = None
    exit_date = None

    window = future.head(max_hold_days)

    # Helper for index returns
    def close_at(idx):
        if idx < len(future):
            return float(future.iloc[idx]["Close"])
        return None

    return_1d = _pct(close_at(0), actual_entry)
    return_5d = _pct(close_at(4), actual_entry)
    return_10d = _pct(close_at(9), actual_entry)

    for _, row in window.iterrows():
        row_date = _.date().isoformat() if hasattr(_, 'date') else str(_)[:10]
        high = float(row["High"])
        low = float(row["Low"])

        target_hit_today = high >= adj_target
        stop_hit_today = low <= adj_stop

        if target_hit_today and stop_hit_today:
            # Ambiguous — can't know which came first intraday
            if target_hit_date is None and stop_hit_date is None:
                target_hit_date = row_date
                stop_hit_date = row_date
            break
        elif target_hit_today and target_hit_date is None:
            target_hit_date = row_date
        elif stop_hit_today and stop_hit_date is None:
            stop_hit_date = row_date

        if target_hit_date or stop_hit_date:
            break

    # Determine outcome
    if target_hit_date and stop_hit_date:
        if target_hit_date < stop_hit_date:
            outcome_label = "TARGET HIT"
            exit_price = adj_target
            exit_date = target_hit_date
        elif stop_hit_date < target_hit_date:
            outcome_label = "STOP HIT"
            exit_price = adj_stop
            exit_date = stop_hit_date
        else:
            outcome_label = "AMBIGUOUS"
            exit_price = float(window.iloc[-1]["Close"])
            exit_date = target_hit_date
    elif target_hit_date:
        outcome_label = "TARGET HIT"
        exit_price = adj_target
        exit_date = target_hit_date
    elif stop_hit_date:
        outcome_label = "STOP HIT"
        exit_price = adj_stop
        exit_date = stop_hit_date
    else:
        # Held to end of window
        outcome_label = "EXPIRED"
        exit_price = float(window.iloc[-1]["Close"])
        exit_date = window.index[-1].date().isoformat()

    days_held = len(window)
    return_pct = _pct(exit_price, actual_entry)

    return {
        "outcome_label": outcome_label,
        "actual_entry": round(actual_entry, 2),
        "exit_price": round(exit_price, 2),
        "return_pct": return_pct,
        "days_held": days_held,
        "target_hit": bool(target_hit_date),
        "stop_hit": bool(stop_hit_date),
        "exit_date": exit_date,
        "return_1d_pct": return_1d,
        "return_5d_pct": return_5d,
        "return_10d_pct": return_10d,
        "adj_target": adj_target,
        "adj_stop": adj_stop,
    }


def _pct(price, entry):
    if price is None or entry in [None, 0]:
        return None
    return round(((price - entry) / entry) * 100, 2)


def _fetch_full_history(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """Fetch enough history to score every day in the range."""
    # Need 50 extra days before start for MA calculation
    fetch_start = start - timedelta(days=90)

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            start=fetch_start.isoformat(),
            end=(end + timedelta(days=15)).isoformat(),
            interval="1d",
            auto_adjust=False,
        )

        if hist is None or hist.empty or len(hist) < 50:
            return None

        return hist

    except Exception as e:
        print(f"FETCH ERROR {symbol}: {e}")
        return None


def _get_trading_days(hist: pd.DataFrame, start: date, end: date) -> list:
    """Return list of dates within range that appear in the history."""
    return [
        idx.date()
        for idx in hist.index
        if start <= idx.date() <= end
    ]


def run_backtest(
    symbols: list,
    start_date: str,
    end_date: str,
    min_score: int = 70,
    max_hold_days: int = 10,
    actionable_only: bool = True,
) -> dict:
    """
    Main entry point for the backtest engine.

    symbols: list of ticker symbols
    start_date: "YYYY-MM-DD"
    end_date: "YYYY-MM-DD"
    min_score: minimum technical score to log a signal (default 70)
    max_hold_days: how many days to hold before closing at market
    actionable_only: if True, only log ACTIONABLE TODAY signals
    """

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    if end > date.today():
        end = date.today() - timedelta(days=1)

    all_trades = []
    skipped_symbols = []

    for symbol in symbols:
        print(f"BACKTESTING: {symbol}")

        full_hist = _fetch_full_history(symbol, start, end)

        if full_hist is None:
            skipped_symbols.append(symbol)
            continue

        trading_days = _get_trading_days(full_hist, start, end)

        for signal_date in trading_days:
            # Slice history up to and including signal_date (as if we're AT that date)
            hist_slice = full_hist[full_hist.index.date <= signal_date]

            if len(hist_slice) < 52:
                continue

            scored = _score_day(hist_slice)

            if scored is None:
                continue

            if scored["technical_score"] < min_score:
                continue

            if actionable_only and scored["action_label"] != "ACTIONABLE TODAY":
                continue

            # Simulate what would have happened
            outcome = _simulate_outcome(
                full_hist=full_hist,
                signal_date=signal_date,
                entry=scored["entry"],
                target=scored["target"],
                stop=scored["stop"],
                max_hold_days=max_hold_days,
            )

            all_trades.append({
                "symbol": symbol,
                "signal_date": signal_date.isoformat(),
                "score": scored["technical_score"],
                "action_label": scored["action_label"],
                "signal_entry": scored["entry"],
                "signal_target": scored["target"],
                "signal_stop": scored["stop"],
                "reward_risk_ratio": scored["reward_risk_ratio"],
                "daily_change_pct": scored["daily_change_pct"],
                "volume_spike": scored["volume_spike"],
                "tech_reasons": scored["tech_reasons"],
                **outcome,
            })

    # ── Summary stats ─────────────────────────────
    total = len(all_trades)
    target_hits = sum(1 for t in all_trades if t["outcome_label"] == "TARGET HIT")
    stop_hits = sum(1 for t in all_trades if t["outcome_label"] == "STOP HIT")
    ambiguous = sum(1 for t in all_trades if t["outcome_label"] == "AMBIGUOUS")
    expired = sum(1 for t in all_trades if t["outcome_label"] == "EXPIRED")

    returns = [t["return_pct"] for t in all_trades if t["return_pct"] is not None]
    avg_return = round(sum(returns) / len(returns), 2) if returns else None

    winner_returns = [r for r in returns if r > 0]
    loser_returns = [r for r in returns if r < 0]

    avg_winner = round(sum(winner_returns) / len(winner_returns), 2) if winner_returns else None
    avg_loser = round(sum(loser_returns) / len(loser_returns), 2) if loser_returns else None

    resolved = target_hits + stop_hits
    target_hit_rate = round((target_hits / resolved) * 100, 2) if resolved > 0 else None

    profitable = sum(1 for r in returns if r > 0)
    win_rate = round((profitable / len(returns)) * 100, 2) if returns else None

    # Sort by date then symbol
    all_trades.sort(key=lambda t: (t["signal_date"], t["symbol"]))

    return {
        "status": "ok",
        "generated_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "parameters": {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "min_score": min_score,
            "max_hold_days": max_hold_days,
            "actionable_only": actionable_only,
        },
        "summary": {
            "total_signals": total,
            "target_hits": target_hits,
            "stop_hits": stop_hits,
            "ambiguous": ambiguous,
            "expired": expired,
            "target_hit_rate_pct": target_hit_rate,
            "win_rate_pct": win_rate,
            "avg_return_pct": avg_return,
            "avg_winner_pct": avg_winner,
            "avg_loser_pct": avg_loser,
            "total_symbols_scanned": len(symbols),
            "skipped_symbols": skipped_symbols,
        },
        "trades": all_trades,
        "disclaimer": (
            "Backtest results are simulated using historical data. "
            "Past performance does not guarantee future results. "
            "No trades are placed automatically. All trading decisions remain with the operator."
        ),
    }
