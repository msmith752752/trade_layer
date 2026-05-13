import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf


SIGNAL_JOURNAL_PATH = Path("data") / "signal_journal.json"


def _now_et():
    return datetime.now(ZoneInfo("America/New_York"))


def _today_et_string():
    return _now_et().date().isoformat()


def _safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default

        if isinstance(value, str):
            value = (
                value.replace("$", "")
                .replace(",", "")
                .replace("%", "")
                .replace("(", "-")
                .replace(")", "")
                .strip()
            )

        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_round(value, digits=2):
    number = _safe_float(value, None)

    if number is None:
        return None

    return round(number, digits)


def _read_journal():
    if not SIGNAL_JOURNAL_PATH.exists():
        return []

    try:
        with open(SIGNAL_JOURNAL_PATH, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception as e:
        print("ERROR READING SIGNAL JOURNAL:", e)
        return []


def _write_journal(entries):
    SIGNAL_JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SIGNAL_JOURNAL_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def _extract_market_context(briefing):
    briefing = briefing or {}

    return {
        "market_regime": briefing.get("market_regime"),
        "risk_appetite": briefing.get("risk_appetite"),
        "risk_score": briefing.get("risk_score"),
        "recommended_posture": briefing.get("recommended_posture"),
    }


def _build_signal_entry(signal, briefing):
    if not signal:
        return None

    symbol = str(signal.get("symbol", "")).upper().strip()

    if not symbol:
        return None

    entry = _safe_float(signal.get("entry"), None)
    target = _safe_float(signal.get("target"), None)
    stop = _safe_float(signal.get("stop_loss"), None)

    if entry is None:
        return None

    captured_at = _now_et().isoformat()
    captured_date = _today_et_string()
    market_context = _extract_market_context(briefing)

    return {
        "id": f"{captured_date}_{symbol}",
        "captured_date": captured_date,
        "captured_at": captured_at,
        "symbol": symbol,
        "entry": _safe_round(entry),
        "target": _safe_round(target),
        "stop": _safe_round(stop),
        "trade_score": _safe_round(signal.get("score"), 2),
        "action_label": signal.get("action_label"),
        "signal_type": signal.get("signal_type"),
        "market_state": signal.get("market_state"),
        "recommended_strategy": signal.get("recommended_strategy"),
        "strategy_family": signal.get("strategy_family"),
        "options_pressure": signal.get("options_pressure"),
        "options_score": _safe_round(signal.get("options_score"), 2),
        "relative_strength_vs_spy": _safe_round(signal.get("relative_strength_vs_spy"), 2),
        "expected_hold": signal.get("expected_hold"),
        "trade_timeframe": signal.get("trade_timeframe"),
        "market_context": market_context,
        "status": "open",
        "outcome": {
            "outcome_label": "OPEN",
            "current_price": None,
            "current_return_percent": None,
            "days_elapsed": 0,
            "target_hit": False,
            "stop_hit": False,
            "target_hit_date": None,
            "stop_hit_date": None,
            "max_favorable_percent": None,
            "max_adverse_percent": None,
            "return_1d_percent": None,
            "return_5d_percent": None,
            "return_10d_percent": None,
        },
    }


def capture_daily_top_signal(scan_data, briefing=None):
    scan_data = scan_data or {}
    top_signal = scan_data.get("top_trade")

    entry = _build_signal_entry(top_signal, briefing)

    if not entry:
        return {
            "captured": False,
            "reason": "No top trade available to capture.",
            "entry": None,
        }

    entries = _read_journal()

    existing_index = None

    for index, item in enumerate(entries):
        if item.get("id") == entry["id"]:
            existing_index = index
            break

    if existing_index is None:
        entries.append(entry)
        _write_journal(entries)

        return {
            "captured": True,
            "created": True,
            "reason": f"Captured today's top TradeLayer signal for {entry['symbol']}.",
            "entry": entry,
        }

    existing = entries[existing_index]

    preserved_outcome = existing.get("outcome")
    preserved_status = existing.get("status")

    updated = {
        **existing,
        **entry,
        "captured_at": existing.get("captured_at") or entry["captured_at"],
        "last_seen_at": entry["captured_at"],
        "status": preserved_status or entry["status"],
        "outcome": preserved_outcome or entry["outcome"],
    }

    entries[existing_index] = updated
    _write_journal(entries)

    return {
        "captured": True,
        "created": False,
        "reason": f"Today's {entry['symbol']} signal was already in the journal; refreshed metadata.",
        "entry": updated,
    }


def _get_history(symbol, captured_date):
    try:
        start_date = datetime.fromisoformat(captured_date).date()
        end_date = _now_et().date() + timedelta(days=1)

        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval="1d",
            auto_adjust=False,
        )

        if hist is None or hist.empty:
            return None

        return hist

    except Exception as e:
        print(f"ERROR FETCHING JOURNAL HISTORY FOR {symbol}:", e)
        return None


def _percent_return(price, entry):
    price = _safe_float(price, None)
    entry = _safe_float(entry, None)

    if price is None or entry in [None, 0]:
        return None

    return round(((price - entry) / entry) * 100, 2)


def _close_return_at_index(hist, entry, index):
    if hist is None or hist.empty:
        return None

    if len(hist) <= index:
        return None

    close_price = float(hist.iloc[index]["Close"])
    return _percent_return(close_price, entry)


def _evaluate_outcome(entry):
    symbol = entry.get("symbol")
    captured_date = entry.get("captured_date")
    entry_price = _safe_float(entry.get("entry"), None)
    target = _safe_float(entry.get("target"), None)
    stop = _safe_float(entry.get("stop"), None)

    if not symbol or not captured_date or entry_price is None:
        return entry

    hist = _get_history(symbol, captured_date)

    if hist is None or hist.empty:
        return entry

    latest = hist.iloc[-1]
    current_price = float(latest["Close"])

    target_hit_date = None
    stop_hit_date = None
    ambiguous_hit_date = None

    for index, row in hist.iterrows():
        row_date = index.date().isoformat()

        high = _safe_float(row.get("High"), None)
        low = _safe_float(row.get("Low"), None)

        target_hit_today = target is not None and high is not None and high >= target
        stop_hit_today = stop is not None and low is not None and low <= stop

        if target_hit_today and stop_hit_today and not ambiguous_hit_date:
            ambiguous_hit_date = row_date

        if target_hit_today and not target_hit_date:
            target_hit_date = row_date

        if stop_hit_today and not stop_hit_date:
            stop_hit_date = row_date

    highs = hist["High"].dropna()
    lows = hist["Low"].dropna()

    max_favorable_percent = None
    max_adverse_percent = None

    if not highs.empty:
        max_favorable_percent = _percent_return(float(highs.max()), entry_price)

    if not lows.empty:
        max_adverse_percent = _percent_return(float(lows.min()), entry_price)

    current_return_percent = _percent_return(current_price, entry_price)
    days_elapsed = max(0, len(hist) - 1)

    if target_hit_date and stop_hit_date:
        if target_hit_date < stop_hit_date:
            outcome_label = "TARGET HIT"
            status = "closed"
        elif stop_hit_date < target_hit_date:
            outcome_label = "STOP HIT"
            status = "closed"
        else:
            outcome_label = "AMBIGUOUS"
            status = "review"
    elif target_hit_date:
        outcome_label = "TARGET HIT"
        status = "closed"
    elif stop_hit_date:
        outcome_label = "STOP HIT"
        status = "closed"
    elif current_return_percent is not None and current_return_percent > 0:
        outcome_label = "OPEN / POSITIVE"
        status = "open"
    elif current_return_percent is not None and current_return_percent < 0:
        outcome_label = "OPEN / NEGATIVE"
        status = "open"
    else:
        outcome_label = "OPEN"
        status = "open"

    entry["status"] = status
    entry["outcome"] = {
        "outcome_label": outcome_label,
        "current_price": round(current_price, 2),
        "current_return_percent": current_return_percent,
        "days_elapsed": days_elapsed,
        "target_hit": bool(target_hit_date),
        "stop_hit": bool(stop_hit_date),
        "target_hit_date": target_hit_date,
        "stop_hit_date": stop_hit_date,
        "ambiguous_hit_date": ambiguous_hit_date,
        "max_favorable_percent": max_favorable_percent,
        "max_adverse_percent": max_adverse_percent,
        "return_1d_percent": _close_return_at_index(hist, entry_price, 1),
        "return_5d_percent": _close_return_at_index(hist, entry_price, 5),
        "return_10d_percent": _close_return_at_index(hist, entry_price, 10),
        "last_evaluated_at": _now_et().isoformat(),
    }

    return entry


def update_signal_outcomes():
    entries = _read_journal()
    updated_entries = []

    for entry in entries:
        try:
            updated_entries.append(_evaluate_outcome(entry))
        except Exception as e:
            print(f"ERROR EVALUATING SIGNAL JOURNAL ENTRY {entry.get('id')}:", e)
            updated_entries.append(entry)

    _write_journal(updated_entries)

    return updated_entries


def _entry_in_window(entry, days):
    captured_date = entry.get("captured_date")

    if not captured_date:
        return False

    try:
        captured = datetime.fromisoformat(captured_date).date()
        cutoff = _now_et().date() - timedelta(days=days)
        return captured >= cutoff

    except Exception:
        return False


def _summarize_window(entries, days):
    window_entries = [entry for entry in entries if _entry_in_window(entry, days)]

    total = len(window_entries)

    if total == 0:
        return {
            "days": days,
            "total_signals": 0,
            "closed_signals": 0,
            "open_signals": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "ambiguous": 0,
            "positive_open": 0,
            "negative_open": 0,
            "target_hit_rate": 0,
            "stop_hit_rate": 0,
            "average_current_return_percent": 0,
            "average_5d_return_percent": None,
            "best_symbol": None,
            "worst_symbol": None,
        }

    target_hits = 0
    stop_hits = 0
    ambiguous = 0
    positive_open = 0
    negative_open = 0
    open_signals = 0

    current_returns = []
    return_5d_values = []

    best_entry = None
    worst_entry = None

    for entry in window_entries:
        outcome = entry.get("outcome", {}) or {}
        label = str(outcome.get("outcome_label", "")).upper()

        current_return = _safe_float(outcome.get("current_return_percent"), None)
        return_5d = _safe_float(outcome.get("return_5d_percent"), None)

        if "TARGET HIT" in label:
            target_hits += 1
        elif "STOP HIT" in label:
            stop_hits += 1
        elif "AMBIGUOUS" in label:
            ambiguous += 1
        else:
            open_signals += 1

            if current_return is not None and current_return > 0:
                positive_open += 1

            if current_return is not None and current_return < 0:
                negative_open += 1

        if current_return is not None:
            current_returns.append(current_return)

            if best_entry is None or current_return > _safe_float(best_entry.get("outcome", {}).get("current_return_percent"), -9999):
                best_entry = entry

            if worst_entry is None or current_return < _safe_float(worst_entry.get("outcome", {}).get("current_return_percent"), 9999):
                worst_entry = entry

        if return_5d is not None:
            return_5d_values.append(return_5d)

    closed_signals = target_hits + stop_hits + ambiguous
    resolved_for_hit_rate = target_hits + stop_hits

    target_hit_rate = (
        round((target_hits / resolved_for_hit_rate) * 100, 2)
        if resolved_for_hit_rate
        else 0
    )

    stop_hit_rate = (
        round((stop_hits / resolved_for_hit_rate) * 100, 2)
        if resolved_for_hit_rate
        else 0
    )

    avg_current = (
        round(sum(current_returns) / len(current_returns), 2)
        if current_returns
        else 0
    )

    avg_5d = (
        round(sum(return_5d_values) / len(return_5d_values), 2)
        if return_5d_values
        else None
    )

    return {
        "days": days,
        "total_signals": total,
        "closed_signals": closed_signals,
        "open_signals": open_signals,
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "ambiguous": ambiguous,
        "positive_open": positive_open,
        "negative_open": negative_open,
        "target_hit_rate": target_hit_rate,
        "stop_hit_rate": stop_hit_rate,
        "average_current_return_percent": avg_current,
        "average_5d_return_percent": avg_5d,
        "best_symbol": best_entry.get("symbol") if best_entry else None,
        "worst_symbol": worst_entry.get("symbol") if worst_entry else None,
    }


def _summarize_score_buckets(entries):
    buckets = {
        "high_score_180_plus": [],
        "medium_score_120_to_179": [],
        "lower_score_below_120": [],
    }

    for entry in entries:
        score = _safe_float(entry.get("trade_score"), 0)

        if score >= 180:
            buckets["high_score_180_plus"].append(entry)
        elif score >= 120:
            buckets["medium_score_120_to_179"].append(entry)
        else:
            buckets["lower_score_below_120"].append(entry)

    result = {}

    for name, bucket_entries in buckets.items():
        current_returns = [
            _safe_float(item.get("outcome", {}).get("current_return_percent"), None)
            for item in bucket_entries
        ]

        current_returns = [item for item in current_returns if item is not None]

        result[name] = {
            "signals": len(bucket_entries),
            "average_current_return_percent": (
                round(sum(current_returns) / len(current_returns), 2)
                if current_returns
                else None
            ),
        }

    return result


def build_signal_journal_report(scan_data=None, briefing=None, auto_capture=True):
    capture_result = None

    if auto_capture:
        capture_result = capture_daily_top_signal(scan_data or {}, briefing)

    entries = update_signal_outcomes()

    entries.sort(
        key=lambda item: item.get("captured_at") or item.get("captured_date") or "",
        reverse=True,
    )

    recent_entries = entries[:12]

    windows = {
        "seven_day": _summarize_window(entries, 7),
        "thirty_day": _summarize_window(entries, 30),
        "six_month": _summarize_window(entries, 182),
        "one_year": _summarize_window(entries, 365),
    }

    score_buckets = _summarize_score_buckets(entries)

    return {
        "status": "ok",
        "journal_path": str(SIGNAL_JOURNAL_PATH),
        "generated_at": _now_et().isoformat(),
        "capture_result": capture_result,
        "total_entries": len(entries),
        "windows": windows,
        "score_buckets": score_buckets,
        "recent_entries": recent_entries,
        "summary": (
            "Signal Journal V1 records TradeLayer's daily top recommendation and tracks what happened afterward. "
            "This is forward testing, not proof of a finalized trading system."
        ),
    }
