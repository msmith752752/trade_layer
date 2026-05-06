📈 TradeLayer

AI-assisted directional trade scanner using trend structure, momentum, liquidity, and options positioning.

TradeLayer is a FastAPI-powered trading intelligence engine that scans a curated universe of stocks and ranks directional trade opportunities using technical structure and options market data.

The system is designed to move beyond basic stock screening by classifying:

actionable setups
overextended momentum
developing watchlist candidates
weak/no-trade conditions
🚀 Features
📊 Trade Scanner

Scans a universe of equities and ranks:

Long setups
Watchlist setups
Avoid / No-trade setups
🧠 AI-Assisted Trade Logic

TradeLayer evaluates:

Trend structure
Momentum
Liquidity
Volume confirmation
Options positioning
Overextension risk
📈 Technical Analysis Engine

Current technical model includes:

20-day moving average
50-day moving average
Bullish trend structure validation
Momentum filters
Volume spike confirmation
Liquidity requirements
🧩 Options Positioning Engine

TradeLayer includes a dedicated options analysis layer using live options chain data.

Evaluates:

Put/call volume ratio
Call vs put open interest
Bullish/bearish options pressure
Largest call OI strike
Largest put OI strike
Options pressure scoring overlay
⚠️ Overextension Detection

TradeLayer detects extended momentum conditions and adjusts guidance accordingly.

Example:

Large upside moves may trigger:
WATCH FOR PULLBACK
same_day_only
elevated risk labeling

This helps reduce emotional chasing behavior.

🏷 Scanner Classification System

TradeLayer classifies setups into:

Label	Meaning
ACTIONABLE TODAY	Valid setup meeting scanner criteria
WATCH FOR PULLBACK	Bullish but extended
WAIT FOR CONFIRMATION	Close setup lacking confirmation
NO TRADE	Weak structure or failed criteria
📋 Trade Guidance Output

Each trade includes:

Entry price
Stop loss
Profit target
Risk/reward ratio
Trade timeframe
Expected hold duration
Exit guidance
Technical score
Options score
Risk score
Final ranking score
🧠 Example Scanner Output
{
  "symbol": "ORCL",
  "action_label": "ACTIONABLE TODAY",
  "technical_score": 95,
  "options_score": 20,
  "final_score": 115,
  "trade_timeframe": "swing_trade",
  "expected_hold": "2 to 5 trading days"
}
🏗 Architecture
Backend
FastAPI
Python
Market Data
Yahoo Finance (yfinance)
Components
trade_engine.py
options_engine.py
market_data.py
📡 API Endpoints
Scanner
/trade-scan

Returns:

top trade
trade opportunities
watchlist
avoid list
score breakdowns
action labels
Single Trade Signal
/trade-signal?symbol=AAPL
Portfolio Tracking
/portfolio
Performance Tracking
/performance
Trade Logging
/log-trade
▶️ Running Locally
Start FastAPI Backend
python -m uvicorn app.main:app --reload

Backend:

http://127.0.0.1:8000
Open Scanner
http://127.0.0.1:8000/trade-scan
🔮 Planned Improvements
Relative strength vs SPY
RSI filtering
ATR volatility sizing
ETF universe support
Dashboard UI upgrades
Options resistance logic
Support/resistance awareness
Improved timeframe modeling
Risk-adjusted ranking
Institutional-style dashboard presentation
⚠️ Disclaimer

TradeLayer is for educational and informational purposes only.

This project does not provide financial advice, investment recommendations, or guarantees of performance.

Trading involves substantial risk and may result in loss of capital.
