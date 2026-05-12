from datetime import datetime, date


def calculate_covered_call_position(
    symbol: str,
    shares: int,
    stock_cost_basis: float,
    call_strike: float,
    call_premium: float,
    expiration: str,
    current_stock_price: float | None = None,
    current_call_price: float | None = None,
    account: str = "Uncategorized",
) -> dict:
    """
    Evaluates a covered call position.

    This engine is for position intelligence only.
    It does not place trades.
    """

    contracts = shares // 100
    premium_collected = round(call_premium * 100 * contracts, 2)
    stock_cost_total = round(stock_cost_basis * shares, 2)

    adjusted_basis_per_share = round(stock_cost_basis - call_premium, 2)
    adjusted_basis_total = round(adjusted_basis_per_share * shares, 2)

    max_stock_gain_per_share = round(call_strike - stock_cost_basis, 2)
    max_profit_if_assigned = round((max_stock_gain_per_share + call_premium) * shares, 2)

    downside_buffer_percent = round((call_premium / stock_cost_basis) * 100, 2) if stock_cost_basis else 0

    current_unrealized_stock_pl = None
    current_total_position_pl_estimate = None
    distance_to_strike_percent = None

    if current_stock_price is not None:
        current_unrealized_stock_pl = round((current_stock_price - stock_cost_basis) * shares, 2)
        distance_to_strike_percent = round(((call_strike - current_stock_price) / current_stock_price) * 100, 2)

        if current_call_price is not None:
            current_call_buyback_cost = current_call_price * 100 * contracts
            current_total_position_pl_estimate = round(
                current_unrealized_stock_pl + premium_collected - current_call_buyback_cost,
                2,
            )
        else:
            current_total_position_pl_estimate = round(
                current_unrealized_stock_pl + premium_collected,
                2,
            )

    status = "MONITOR"

    if current_stock_price is not None:
        if current_stock_price >= call_strike:
            status = "ASSIGNMENT WATCH"
        elif distance_to_strike_percent is not None and distance_to_strike_percent <= 3:
            status = "ROLL / ASSIGNMENT WATCH"
        elif current_stock_price < adjusted_basis_per_share:
            status = "DOWNSIDE WATCH"
        else:
            status = "HOLD"

    management_note = build_covered_call_management_note(
        status=status,
        symbol=symbol,
        call_strike=call_strike,
        adjusted_basis_per_share=adjusted_basis_per_share,
        expiration=expiration,
    )

    return {
        "status": "ok",
        "strategy": "covered_call",
        "symbol": symbol.upper(),
        "account": account,
        "shares": shares,
        "contracts": contracts,
        "stock_cost_basis": round(stock_cost_basis, 2),
        "stock_cost_total": stock_cost_total,
        "call_strike": round(call_strike, 2),
        "call_premium": round(call_premium, 2),
        "premium_collected": premium_collected,
        "expiration": expiration,
        "adjusted_basis_per_share": adjusted_basis_per_share,
        "adjusted_basis_total": adjusted_basis_total,
        "max_profit_if_assigned": max_profit_if_assigned,
        "downside_buffer_percent": downside_buffer_percent,
        "current_stock_price": current_stock_price,
        "current_call_price": current_call_price,
        "current_unrealized_stock_pl": current_unrealized_stock_pl,
        "current_total_position_pl_estimate": current_total_position_pl_estimate,
        "distance_to_strike_percent": distance_to_strike_percent,
        "position_status": status,
        "management_note": management_note,
        "generated_at": datetime.now().isoformat(),
    }


def build_covered_call_management_note(
    status: str,
    symbol: str,
    call_strike: float,
    adjusted_basis_per_share: float,
    expiration: str,
) -> str:
    if status == "ASSIGNMENT WATCH":
        return (
            f"{symbol.upper()} is at or above the covered call strike. "
            f"Assignment risk is elevated. Review whether assignment is acceptable or whether rolling makes sense."
        )

    if status == "ROLL / ASSIGNMENT WATCH":
        return (
            f"{symbol.upper()} is approaching the {call_strike} strike. "
            f"Monitor remaining premium, time to expiration, and whether upside momentum justifies rolling."
        )

    if status == "DOWNSIDE WATCH":
        return (
            f"{symbol.upper()} is below the adjusted basis of {adjusted_basis_per_share}. "
            f"The call premium helped reduce risk, but downside pressure should be monitored."
        )

    if status == "HOLD":
        return (
            f"{symbol.upper()} covered call is behaving normally. "
            f"Premium has reduced basis and the position can be monitored into {expiration}."
        )

    return (
        f"{symbol.upper()} covered call position is active. "
        f"Monitor price versus strike, premium decay, and expiration timing."
    )


def get_sample_pltr_covered_call() -> dict:
    """
    Sample PLTR setup from manual trade entry.

    Long 100 PLTR shares
    Approx average stock basis: 135.45
    Short 1 call
    Strike: 142
    Expiration: 2026-06-12
    Premium collected: 5.10
    """

    return calculate_covered_call_position(
        symbol="PLTR",
        shares=100,
        stock_cost_basis=135.45,
        call_strike=142.00,
        call_premium=5.10,
        expiration="2026-06-12",
        current_stock_price=135.61,
        current_call_price=5.10,
        account="Schwab Brokerage",
    )