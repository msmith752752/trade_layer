def recommend_options_strategy(
    market_state: str,
    options_pressure: str | None = None,
    overextended: bool = False,
):
    """
    Maps TradeLayer market state + options pressure into an appropriate
    options trade structure.

    This is not financial advice. It is a strategy-fit engine that explains
    which structure best matches the detected environment.
    """

    recommended_strategy = "no_trade"
    strategy_family = "risk_control"
    strategy_bias = "neutral"
    strategy_reason = []
    strategy_notes = []

    if overextended or market_state == "overextended_chase":
        recommended_strategy = "avoid_chasing_or_wait_for_pullback"
        strategy_family = "risk_control"
        strategy_bias = "neutral"
        strategy_reason = [
            "Price is overextended relative to normal scanner rules.",
            "Chasing after a large move creates poor reward/risk.",
            "Better setup may appear after consolidation or pullback.",
        ]
        strategy_notes = [
            "Avoid opening aggressive directional trades into exhaustion.",
            "Consider waiting for a reset near support or moving averages.",
        ]

    elif market_state == "trend_continuation":
        recommended_strategy = "bull_call_vertical_spread"
        strategy_family = "directional_defined_risk"
        strategy_bias = "bullish"
        strategy_reason = [
            "Bullish trend structure is intact.",
            "Momentum supports directional continuation.",
            "A vertical spread expresses bullish direction with defined risk.",
        ]
        strategy_notes = [
            "Useful when direction is favored but outright long calls may be expensive.",
            "Risk is capped compared with buying stock or naked options.",
        ]

    elif market_state == "breakout_expansion":
        recommended_strategy = "debit_vertical_spread"
        strategy_family = "directional_expansion"
        strategy_bias = "bullish"
        strategy_reason = [
            "Price action suggests expansion or breakout behavior.",
            "A debit spread can participate in directional movement while limiting risk.",
            "This structure is cleaner than selling premium during expansion.",
        ]
        strategy_notes = [
            "Avoid short-premium neutral structures during strong expansion.",
            "Best when breakout has room before major resistance.",
        ]

    elif market_state == "volatility_compression":
        recommended_strategy = "iron_butterfly_or_iron_condor"
        strategy_family = "neutral_premium"
        strategy_bias = "neutral"
        strategy_reason = [
            "Price action appears compressed with limited directional movement.",
            "Neutral premium structures can fit range-bound conditions.",
            "Iron butterfly is tighter; iron condor gives the trade more room.",
        ]
        strategy_notes = [
            "Iron butterfly fits tighter, more stable ranges.",
            "Iron condor fits wider neutral ranges.",
            "Avoid if breakout risk or event risk is elevated.",
        ]

    elif market_state == "unstable_high_risk":
        recommended_strategy = "no_trade_or_small_defined_risk_spread"
        strategy_family = "risk_control"
        strategy_bias = "defensive"
        strategy_reason = [
            "Trend structure is weak or unstable.",
            "Poor environment for confident directional trades.",
            "Risk should be reduced until conditions improve.",
        ]
        strategy_notes = [
            "Avoid large premium-selling positions in unstable conditions.",
            "If trading, use small defined-risk structures only.",
        ]

    else:
        recommended_strategy = "watchlist_wait_for_clearer_setup"
        strategy_family = "watchlist"
        strategy_bias = "neutral"
        strategy_reason = [
            "Market state is not strong enough for a high-confidence structure.",
            "Waiting may provide a better entry or clearer volatility signal.",
        ]
        strategy_notes = [
            "Monitor for trend confirmation, compression breakout, or volatility reset.",
        ]

    if options_pressure == "strong_bullish" and strategy_bias == "bullish":
        strategy_reason.append("Options positioning supports the bullish structure.")

    elif options_pressure == "bearish" and strategy_bias == "bullish":
        strategy_reason.append("Options positioning conflicts with the bullish setup, reducing conviction.")

    return {
        "recommended_strategy": recommended_strategy,
        "strategy_family": strategy_family,
        "strategy_bias": strategy_bias,
        "strategy_reason": strategy_reason,
        "strategy_notes": strategy_notes,
    }