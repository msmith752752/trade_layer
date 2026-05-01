from fastapi import FastAPI
from app.market_data import get_market_data
from app.trade_engine import generate_trade_signal

app = FastAPI()


@app.get("/")
def root():
    return {"message": "TradeLayer API is running"}


@app.get("/trade-signal")
def get_trade_signal(symbol: str):

    data = get_market_data(symbol)

    if not data or "error" in data:
        return {"error": f"Could not fetch data for {symbol}"}

    signal = generate_trade_signal(symbol, data)

    return signal


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

        if signal["signal_type"] in ["strong_long", "long"]:
            trade_opportunities.append(signal)

        elif signal["signal_type"] == "watchlist":
            watchlist.append(signal)

        else:
            avoid.append(signal)

    # Sort by score (highest first)
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