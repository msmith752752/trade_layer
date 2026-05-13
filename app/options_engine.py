import math
from statistics import mean
from typing import Any, Dict, List, Optional

import yfinance as yf


MIN_VOLUME_FOR_LIQUID = 25
MIN_OPEN_INTEREST_FOR_LIQUID = 100
MAX_ACCEPTABLE_SPREAD_PERCENT = 18.0
MAX_ACCEPTABLE_IV = 1.50
IDEAL_IV_LOW = 0.20
IDEAL_IV_HIGH = 0.85
NEAR_THE_MONEY_RANGE = 0.12


def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None:
            return default

        if isinstance(value, float) and math.isnan(value):
            return default

        if isinstance(value, str):
            value = (
                value.replace("$", "")
                .replace(",", "")
                .replace("%", "")
                .strip()
            )

        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    number = _safe_float(value, None)
    if number is None:
        return default
    return int(number)


def _round_or_none(value: Any, digits: int = 2):
    number = _safe_float(value, None)
    if number is None:
        return None
    return round(number, digits)


def _classify_spread_quality(spread_percent: Optional[float]) -> str:
    if spread_percent is None:
        return "unknown"
    if spread_percent <= 5:
        return "excellent"
    if spread_percent <= 10:
        return "good"
    if spread_percent <= 18:
        return "acceptable"
    if spread_percent <= 30:
        return "wide"
    return "poor"


def _classify_liquidity_score(volume: int, open_interest: int, spread_percent: Optional[float]) -> int:
    score = 0

    if volume >= 1000:
        score += 35
    elif volume >= 250:
        score += 28
    elif volume >= 100:
        score += 22
    elif volume >= 25:
        score += 14
    elif volume > 0:
        score += 6

    if open_interest >= 5000:
        score += 35
    elif open_interest >= 1000:
        score += 28
    elif open_interest >= 500:
        score += 22
    elif open_interest >= 100:
        score += 14
    elif open_interest > 0:
        score += 6

    if spread_percent is None:
        score += 5
    elif spread_percent <= 5:
        score += 30
    elif spread_percent <= 10:
        score += 24
    elif spread_percent <= 18:
        score += 16
    elif spread_percent <= 30:
        score += 6

    return int(max(0, min(100, score)))


def _classify_liquidity_label(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 65:
        return "tradable"
    if score >= 45:
        return "thin"
    return "weak"


def _classify_iv_regime(iv: Optional[float]) -> str:
    if iv is None:
        return "unknown"
    if iv >= MAX_ACCEPTABLE_IV:
        return "excessive"
    if iv >= 0.90:
        return "elevated"
    if iv >= IDEAL_IV_LOW:
        return "normal"
    return "low"


def _quality_passes(liquidity_score: int, spread_percent: Optional[float], iv: Optional[float]) -> bool:
    if liquidity_score < 45:
        return False
    if spread_percent is not None and spread_percent > 30:
        return False
    if iv is not None and iv > MAX_ACCEPTABLE_IV:
        return False
    return True


def _build_contract_snapshot(row, option_type: str, current_price: float) -> Dict[str, Any]:
    strike = _safe_float(row.get("strike"), None)
    bid = _safe_float(row.get("bid"), None)
    ask = _safe_float(row.get("ask"), None)
    last_price = _safe_float(row.get("lastPrice"), None)
    volume = _safe_int(row.get("volume"), 0)
    open_interest = _safe_int(row.get("openInterest"), 0)
    implied_volatility = _safe_float(row.get("impliedVolatility"), None)

    midpoint = None
    spread = None
    spread_percent = None

    if bid is not None and ask is not None and ask > 0:
        midpoint = (bid + ask) / 2
        spread = ask - bid
        if midpoint > 0:
            spread_percent = (spread / midpoint) * 100

    moneyness_percent = None
    if strike is not None and current_price:
        moneyness_percent = ((strike - current_price) / current_price) * 100

    liquidity_score = _classify_liquidity_score(volume, open_interest, spread_percent)
    liquidity_label = _classify_liquidity_label(liquidity_score)
    spread_quality = _classify_spread_quality(spread_percent)
    iv_regime = _classify_iv_regime(implied_volatility)

    quality_pass = _quality_passes(liquidity_score, spread_percent, implied_volatility)

    return {
        "contract_symbol": row.get("contractSymbol"),
        "option_type": option_type,
        "strike": _round_or_none(strike, 2),
        "bid": _round_or_none(bid, 2),
        "ask": _round_or_none(ask, 2),
        "last_price": _round_or_none(last_price, 2),
        "midpoint": _round_or_none(midpoint, 2),
        "bid_ask_spread": _round_or_none(spread, 2),
        "bid_ask_spread_percent": _round_or_none(spread_percent, 2),
        "spread_quality": spread_quality,
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": _round_or_none(implied_volatility, 4),
        "implied_volatility_percent": _round_or_none(implied_volatility * 100 if implied_volatility is not None else None, 2),
        "iv_regime": iv_regime,
        "moneyness_percent": _round_or_none(moneyness_percent, 2),
        "liquidity_score": liquidity_score,
        "liquidity_label": liquidity_label,
        "quality_pass": quality_pass,
    }


def _filter_near_money(df, current_price: float):
    lower = current_price * (1 - NEAR_THE_MONEY_RANGE)
    upper = current_price * (1 + NEAR_THE_MONEY_RANGE)
    return df[(df["strike"] >= lower) & (df["strike"] <= upper)].copy()


def _summarize_contracts(contracts: List[Dict[str, Any]], option_type: str) -> Dict[str, Any]:
    if not contracts:
        return {
            "option_type": option_type,
            "count": 0,
            "tradable_count": 0,
            "average_liquidity_score": 0,
            "average_iv_percent": None,
            "best_contract": None,
        }

    tradable = [item for item in contracts if item.get("quality_pass")]
    iv_values = [item["implied_volatility_percent"] for item in contracts if item.get("implied_volatility_percent") is not None]

    sorted_contracts = sorted(
        contracts,
        key=lambda item: (
            item.get("quality_pass", False),
            item.get("liquidity_score", 0),
            item.get("open_interest", 0),
            item.get("volume", 0),
        ),
        reverse=True,
    )

    return {
        "option_type": option_type,
        "count": len(contracts),
        "tradable_count": len(tradable),
        "average_liquidity_score": round(mean([item.get("liquidity_score", 0) for item in contracts]), 2),
        "average_iv_percent": round(mean(iv_values), 2) if iv_values else None,
        "best_contract": sorted_contracts[0] if sorted_contracts else None,
    }


def _build_quality_summary(call_summary: Dict[str, Any], put_summary: Dict[str, Any]) -> Dict[str, Any]:
    call_score = call_summary.get("average_liquidity_score", 0) or 0
    put_score = put_summary.get("average_liquidity_score", 0) or 0
    average_score = round((call_score + put_score) / 2, 2)

    total_count = call_summary.get("count", 0) + put_summary.get("count", 0)
    tradable_count = call_summary.get("tradable_count", 0) + put_summary.get("tradable_count", 0)
    tradable_ratio = (tradable_count / total_count) if total_count else 0

    confidence = int(max(0, min(100, (average_score * 0.75) + (tradable_ratio * 25))))

    if confidence >= 80:
        label = "High Quality"
        actionability = "Tradable"
        summary = "Options chain quality is strong enough to support defined-risk strategy selection."
    elif confidence >= 65:
        label = "Acceptable Quality"
        actionability = "Selective"
        summary = "Options chain quality is acceptable, but contract selection still matters."
    elif confidence >= 45:
        label = "Thin / Mixed Quality"
        actionability = "Caution"
        summary = "Options chain quality is mixed. Avoid forcing trades unless the setup is unusually strong."
    else:
        label = "Poor Quality"
        actionability = "Avoid"
        summary = "Options chain quality is weak. TradeLayer should reject most option structures here."

    return {
        "options_confidence": confidence,
        "quality_label": label,
        "actionability": actionability,
        "tradable_contracts": tradable_count,
        "contracts_reviewed": total_count,
        "average_liquidity_score": average_score,
        "summary": summary,
    }


def _build_avoid_reasons(quality: Dict[str, Any], call_summary: Dict[str, Any], put_summary: Dict[str, Any]) -> List[str]:
    reasons = []

    if quality.get("options_confidence", 0) < 45:
        reasons.append("Overall options confidence is below TradeLayer's minimum quality threshold.")

    if quality.get("tradable_contracts", 0) == 0:
        reasons.append("No near-the-money contracts passed liquidity and spread filters.")

    for label, summary in [("calls", call_summary), ("puts", put_summary)]:
        best = summary.get("best_contract") or {}
        if best:
            if best.get("bid_ask_spread_percent") is not None and best.get("bid_ask_spread_percent") > MAX_ACCEPTABLE_SPREAD_PERCENT:
                reasons.append(f"Best {label} still have a wide bid/ask spread.")
            if best.get("iv_regime") == "excessive":
                reasons.append(f"Best {label} show excessive implied volatility.")
            if best.get("liquidity_label") in ["weak", "thin"]:
                reasons.append(f"Best {label} have weak or thin liquidity.")

    return reasons


def get_options_quality(symbol: str, current_price: float, directional_bias: str = "unclear") -> Dict[str, Any]:
    """
    TradeLayer Options Intelligence V2.

    Uses yfinance option-chain data for now, but returns a Schwab-ready quality
    structure: IV regime, liquidity score, spread quality, tradable counts,
    best near-the-money call/put, and avoid reasons.
    """

    try:
        selected_symbol = str(symbol).upper().strip()
        selected_price = _safe_float(current_price, None)

        if not selected_symbol or selected_price is None or selected_price <= 0:
            return _empty_quality_result(symbol, current_price, "Missing symbol or current price.")

        ticker = yf.Ticker(selected_symbol)
        expirations = ticker.options

        if not expirations:
            return _empty_quality_result(selected_symbol, selected_price, "No options expirations found.")

        nearest_expiration = expirations[0]
        chain = ticker.option_chain(nearest_expiration)

        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return _empty_quality_result(selected_symbol, selected_price, "Options chain was empty.")

        near_calls = _filter_near_money(calls, selected_price)
        near_puts = _filter_near_money(puts, selected_price)

        if near_calls.empty:
            near_calls = calls.sort_values("strike").tail(8)

        if near_puts.empty:
            near_puts = puts.sort_values("strike").head(8)

        call_contracts = [
            _build_contract_snapshot(row, "call", selected_price)
            for _, row in near_calls.iterrows()
        ]
        put_contracts = [
            _build_contract_snapshot(row, "put", selected_price)
            for _, row in near_puts.iterrows()
        ]

        call_summary = _summarize_contracts(call_contracts, "call")
        put_summary = _summarize_contracts(put_contracts, "put")
        quality = _build_quality_summary(call_summary, put_summary)
        avoid_reasons = _build_avoid_reasons(quality, call_summary, put_summary)

        structure_bias = _infer_structure_bias(
            directional_bias=directional_bias,
            quality=quality,
            call_summary=call_summary,
            put_summary=put_summary,
        )

        return {
            "has_options_quality_data": True,
            "data_source": "yfinance_fallback",
            "symbol": selected_symbol,
            "current_price": round(selected_price, 2),
            "expiration_used": nearest_expiration,
            "directional_bias": directional_bias,
            "options_confidence": quality.get("options_confidence"),
            "quality_label": quality.get("quality_label"),
            "actionability": quality.get("actionability"),
            "summary": quality.get("summary"),
            "structure_bias": structure_bias,
            "avoid_reasons": avoid_reasons,
            "quality_metrics": quality,
            "calls": call_summary,
            "puts": put_summary,
            "top_call_contracts": sorted(call_contracts, key=lambda item: item.get("liquidity_score", 0), reverse=True)[:5],
            "top_put_contracts": sorted(put_contracts, key=lambda item: item.get("liquidity_score", 0), reverse=True)[:5],
        }

    except Exception as e:
        return _empty_quality_result(symbol, current_price, f"Options quality data unavailable: {str(e)}")


def _infer_structure_bias(
    directional_bias: str,
    quality: Dict[str, Any],
    call_summary: Dict[str, Any],
    put_summary: Dict[str, Any],
) -> Dict[str, Any]:
    confidence = quality.get("options_confidence", 0)
    bias = str(directional_bias or "unclear").lower()

    if confidence < 45:
        return {
            "preferred_structure": "NO TRADE",
            "structure_quality": "Rejected",
            "reason": "Options quality is too weak for a clean structure recommendation.",
        }

    if "bull" in bias:
        best_call = call_summary.get("best_contract") or {}
        if confidence >= 65 and best_call.get("quality_pass"):
            return {
                "preferred_structure": "Bull Call Spread",
                "structure_quality": "Tradable" if confidence >= 65 else "Selective",
                "reason": "Bullish setup with acceptable call-side liquidity favors a defined-risk bullish spread.",
            }
        return {
            "preferred_structure": "Watchlist / Shares Preferred",
            "structure_quality": "Caution",
            "reason": "Bullish bias exists, but call-side quality is not strong enough for clean options execution.",
        }

    if "bear" in bias:
        best_put = put_summary.get("best_contract") or {}
        if confidence >= 65 and best_put.get("quality_pass"):
            return {
                "preferred_structure": "Bear Put Spread",
                "structure_quality": "Tradable" if confidence >= 65 else "Selective",
                "reason": "Bearish setup with acceptable put-side liquidity favors a defined-risk bearish spread.",
            }
        return {
            "preferred_structure": "Avoid / Wait",
            "structure_quality": "Caution",
            "reason": "Bearish bias exists, but put-side quality is not strong enough for clean options execution.",
        }

    return {
        "preferred_structure": "Wait for Direction",
        "structure_quality": "Neutral",
        "reason": "Directional bias is unclear, so options should not be forced.",
    }


def get_options_pressure(symbol: str, current_price: float):
    """
    Options-positioning analysis for TradeLayer V2.

    Purpose:
    Options data should CONFIRM price action, not overpower it.

    Phase 2 metrics:
    - total call volume
    - total put volume
    - put/call volume ratio
    - largest call open-interest strike
    - largest put open-interest strike
    - balanced options pressure score
    """

    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options

        if not expirations:
            return _empty_options_result("No options expirations found.")

        nearest_expiration = expirations[0]
        chain = ticker.option_chain(nearest_expiration)

        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return _empty_options_result("Options chain was empty.")

        total_call_volume = int(calls["volume"].fillna(0).sum())
        total_put_volume = int(puts["volume"].fillna(0).sum())

        total_call_oi = int(calls["openInterest"].fillna(0).sum())
        total_put_oi = int(puts["openInterest"].fillna(0).sum())

        if total_call_volume > 0:
            put_call_volume_ratio = round(total_put_volume / total_call_volume, 2)
        else:
            put_call_volume_ratio = None

        largest_call_row = calls.sort_values("openInterest", ascending=False).head(1)
        largest_put_row = puts.sort_values("openInterest", ascending=False).head(1)

        largest_call_oi_strike = (
            float(largest_call_row.iloc[0]["strike"])
            if not largest_call_row.empty
            else None
        )

        largest_put_oi_strike = (
            float(largest_put_row.iloc[0]["strike"])
            if not largest_put_row.empty
            else None
        )

        score = 0
        pressure = "neutral"
        summary = "Options positioning is neutral or mixed."

        if put_call_volume_ratio is not None:
            if put_call_volume_ratio < 0.5:
                score += 15
                pressure = "strong_bullish"
                summary = "Options flow is strongly bullish: call volume is far higher than put volume."

            elif put_call_volume_ratio < 0.7:
                score += 10
                pressure = "bullish"
                summary = "Options flow is bullish: call volume is meaningfully higher than put volume."

            elif put_call_volume_ratio > 1.5:
                score -= 15
                pressure = "strong_bearish"
                summary = "Options flow is strongly bearish: put volume is far higher than call volume."

            elif put_call_volume_ratio > 1.2:
                score -= 10
                pressure = "bearish"
                summary = "Options flow is bearish: put volume is meaningfully higher than call volume."

        if total_call_oi > total_put_oi * 1.5:
            score += 5
        elif total_put_oi > total_call_oi * 1.5:
            score -= 5

        quality_data = get_options_quality(symbol, current_price, directional_bias="unclear")

        return {
            "has_options_data": True,
            "expiration_used": nearest_expiration,
            "options_pressure": pressure,
            "options_pressure_score": score,
            "options_summary": summary,
            "put_call_volume_ratio": put_call_volume_ratio,
            "total_call_volume": total_call_volume,
            "total_put_volume": total_put_volume,
            "total_call_open_interest": total_call_oi,
            "total_put_open_interest": total_put_oi,
            "largest_call_oi_strike": largest_call_oi_strike,
            "largest_put_oi_strike": largest_put_oi_strike,
            "current_price": round(current_price, 2),
            "options_quality": quality_data,
        }

    except Exception as e:
        return _empty_options_result(f"Options data unavailable: {str(e)}")


def _empty_quality_result(symbol: str, current_price: Any, reason: str) -> Dict[str, Any]:
    return {
        "has_options_quality_data": False,
        "data_source": "yfinance_fallback",
        "symbol": str(symbol).upper() if symbol else None,
        "current_price": _round_or_none(current_price, 2),
        "expiration_used": None,
        "directional_bias": None,
        "options_confidence": 0,
        "quality_label": "Unavailable",
        "actionability": "Unavailable",
        "summary": reason,
        "structure_bias": {
            "preferred_structure": "NO TRADE",
            "structure_quality": "Unavailable",
            "reason": reason,
        },
        "avoid_reasons": [reason],
        "quality_metrics": {
            "options_confidence": 0,
            "quality_label": "Unavailable",
            "actionability": "Unavailable",
            "tradable_contracts": 0,
            "contracts_reviewed": 0,
            "average_liquidity_score": 0,
            "summary": reason,
        },
        "calls": _summarize_contracts([], "call"),
        "puts": _summarize_contracts([], "put"),
        "top_call_contracts": [],
        "top_put_contracts": [],
    }


def _empty_options_result(reason: str):
    return {
        "has_options_data": False,
        "expiration_used": None,
        "options_pressure": "unavailable",
        "options_pressure_score": 0,
        "options_summary": reason,
        "put_call_volume_ratio": None,
        "total_call_volume": 0,
        "total_put_volume": 0,
        "total_call_open_interest": 0,
        "total_put_open_interest": 0,
        "largest_call_oi_strike": None,
        "largest_put_oi_strike": None,
        "current_price": None,
        "options_quality": _empty_quality_result("", None, reason),
    }
