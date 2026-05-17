// TradeLayer Morning Brief Renderer
// The default view — answers three questions every trading day:
// 1. Is today a trading day?
// 2. What are the 1-3 best setups right now?
// 3. What do I watch for to confirm or invalidate each setup?

// IRA account constants — must match options_contract_selector.py
const IRA_CASH = 1208.00;
const IRA_MAX_RISK = 120.00;
const IRA_MAX_TRADES = 4;

function loadMorningBriefPanel(scanData, tradeRecommendationData) {
    const panel = document.getElementById("morningBriefPanel");
    if (!panel) return;

    panel.innerHTML = renderMorningBriefPanel(scanData, tradeRecommendationData);
}

function renderMorningBriefPanel(scanData, tradeRecommendationData) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const dateStr = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

    const top = scanData?.top_trade || null;
    const opportunities = scanData?.trade_opportunities || [];
    const market = tradeRecommendationData?.market_context || {};
    const option = tradeRecommendationData?.options_recommendation || {};

    // ── Step 1: Is today a trading day? ─────────────────────────────────────
    const goDecision = getGoDecision(scanData, tradeRecommendationData);

    // ── Step 2: Best 1-3 setups ──────────────────────────────────────────────
    const topSetups = opportunities.slice(0, 3);

    return `
        <div class="card morning-brief-card">

            <div class="morning-brief-header">
                <div>
                    <div class="morning-brief-date">${safe(dateStr)}</div>
                    <div class="morning-brief-title">Morning Brief</div>
                    <div class="small">Last updated ${safe(timeStr)} · IRA ...823 · $${IRA_CASH.toFixed(2)} cash · Max risk $${IRA_MAX_RISK}/trade</div>
                </div>
                <div class="morning-brief-go ${goDecision.cssClass}">
                    ${safe(goDecision.label)}
                </div>
            </div>

            <div class="morning-brief-go-reason">
                ${safe(goDecision.reason)}
            </div>

            ${topSetups.length ? `
                <div class="section-title" style="margin-top:20px;">Today's Best Setups</div>
                <div class="section-subtitle">Sized for IRA ...823. Max risk $${IRA_MAX_RISK} per trade. Place manually in Schwab.</div>

                <div class="morning-setup-grid">
                    ${topSetups.map((setup, i) => renderMorningSetupCard(setup, i + 1)).join("")}
                </div>
            ` : `
                <div class="why-box" style="margin-top:20px;">
                    <div class="section-title">No Setups Today</div>
                    <div class="empty-state">
                        No setups met the minimum criteria today. The scanner requires trend, momentum, volume, and a supportive market environment. Stay in cash and check back tomorrow.
                    </div>
                </div>
            `}

            <div class="morning-brief-footer">
                <div class="small">Market Regime: <strong>${safe(market.market_regime || "—")}</strong></div>
                <div class="small">Risk Appetite: <strong>${safe(market.risk_appetite || "—")}</strong></div>
                <div class="small">Scanned: <strong>${safe(scanData?.scanned || 0)} symbols</strong></div>
                <div class="small">This is decision support only. All trades placed manually by operator.</div>
            </div>
        </div>
    `;
}

function renderMorningSetupCard(setup, rank) {
    const symbol = setup.symbol || "—";
    const entry = setup.entry || 0;
    const target = setup.target || 0;
    const stop = setup.stop_loss || 0;
    const score = setup.score || 0;
    const strategy = setup.recommended_strategy || "—";
    const optionsPressure = setup.options_pressure || "—";
    const marketState = setup.market_state || "—";
    const actionReason = setup.action_reason || setup.reason || "—";
    const rr = stop > 0 ? ((target - entry) / (entry - stop)).toFixed(1) : "—";

    // IRA sizing
    const iraFit = getIraFit(entry, stop);

    // Watch for
    const watchFor = getWatchFor(setup);

    return `
        <div class="morning-setup-card">
            <div class="morning-setup-top">
                <div>
                    <div class="morning-setup-rank">#${rank}</div>
                    <div class="morning-setup-symbol">${safe(symbol)}</div>
                    <div class="small">${safe(marketState.replace(/_/g, " "))} · Score: ${safe(score)}</div>
                </div>
                <div class="badge green-bg">SETUP READY</div>
            </div>

            <div class="morning-setup-levels">
                <div class="mini-metric">
                    <div class="label">Entry</div>
                    <div class="value">${formatCurrency(entry)}</div>
                </div>
                <div class="mini-metric">
                    <div class="label">Target</div>
                    <div class="value green">${formatCurrency(target)}</div>
                </div>
                <div class="mini-metric">
                    <div class="label">Stop</div>
                    <div class="value red">${formatCurrency(stop)}</div>
                </div>
                <div class="mini-metric">
                    <div class="label">R/R</div>
                    <div class="value">${safe(rr)}:1</div>
                </div>
            </div>

            <div class="morning-setup-ira">
                <div class="section-title" style="font-size:12px;">IRA Sizing</div>
                <div class="morning-ira-grid">
                    <div class="mini-metric">
                        <div class="label">Structure</div>
                        <div class="value blue" style="font-size:13px;">${formatExpressionLabel(strategy)}</div>
                    </div>
                    <div class="mini-metric">
                        <div class="label">Est. Cost</div>
                        <div class="value">${formatCurrency(iraFit.estimatedCost)}</div>
                    </div>
                    <div class="mini-metric">
                        <div class="label">Max Risk</div>
                        <div class="value ${iraFit.withinLimit ? "green" : "red"}">${formatCurrency(iraFit.maxRisk)}</div>
                    </div>
                    <div class="mini-metric">
                        <div class="label">Fits IRA?</div>
                        <div class="value ${iraFit.withinLimit ? "green" : "red"}">${iraFit.withinLimit ? "YES" : "TOO LARGE"}</div>
                    </div>
                </div>
                <div class="small" style="margin-top:6px;">${safe(iraFit.note)}</div>
            </div>

            <div class="morning-setup-why">
                <div class="label">Why this setup</div>
                <div class="small">${safe(actionReason)}</div>
                <div class="badge-row" style="margin-top:6px;">
                    <div class="badge">${safe(optionsPressure.replace(/_/g, " "))}</div>
                    <div class="badge">${formatExpressionLabel(strategy)}</div>
                </div>
            </div>

            <div class="morning-setup-watch">
                <div class="label">Watch for</div>
                <div class="small">${safe(watchFor)}</div>
            </div>
        </div>
    `;
}

// ─── Decision Logic ───────────────────────────────────────────────────────────

function getMarketSessionInfo() {
    const now = new Date();
    const day = now.getDay(); // 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
    const etHour = now.toLocaleString("en-US", { timeZone: "America/New_York", hour: "numeric", hour12: false });
    const hour = parseInt(etHour);

    if (day === 0) {
        // Sunday — futures open at 6pm ET
        if (hour >= 18) {
            return { session: "FUTURES_OPEN", label: "Futures Open", note: "Equity futures are open. Market opens Monday 9:30am ET." };
        }
        return { session: "WEEKEND", label: "Market Closed", note: "Market is closed. Futures open tonight at 6:00pm ET. Next session: Monday 9:30am ET." };
    }
    if (day === 6) {
        return { session: "WEEKEND", label: "Market Closed", note: "Market is closed for the weekend. Futures open Sunday at 6:00pm ET." };
    }
    if (day >= 1 && day <= 5) {
        if (hour >= 9 && hour < 16) {
            return { session: "MARKET_OPEN", label: "Market Open", note: "Regular trading session is active." };
        }
        if (hour >= 4 && hour < 9) {
            return { session: "PRE_MARKET", label: "Pre-Market", note: "Pre-market session active (4am-9:30am ET). Use limit orders." };
        }
        if (hour >= 16 && hour < 20) {
            return { session: "AFTER_HOURS", label: "After Hours", note: "After-hours session active (4pm-8pm ET). Lower liquidity." };
        }
        if (hour >= 18 || hour < 4) {
            return { session: "FUTURES_OPEN", label: "Futures Open", note: "Equity futures are trading overnight." };
        }
    }
    return { session: "CLOSED", label: "Market Closed", note: "Market is closed." };
}

function getGoDecision(scanData, tradeRecommendationData) {
    const opportunities = scanData?.trade_opportunities || [];
    const market = tradeRecommendationData?.market_context || {};
    const regime = String(market.market_regime || "").toLowerCase();
    const riskAppetite = String(market.risk_appetite || "").toLowerCase();
    const top = scanData?.top_trade || null;
    const session = getMarketSessionInfo();

    // Weekend — market closed
    if (session.session === "WEEKEND") {
        return {
            label: "CLOSED",
            cssClass: "wait",
            reason: session.note + (opportunities.length > 0 ? ` ${opportunities.length} setup(s) are queued and ready to review for Monday open.` : " Use this time to review setups and prepare your watchlist.")
        };
    }

    // Futures open (Sunday evening or overnight)
    if (session.session === "FUTURES_OPEN") {
        return {
            label: "FUTURES",
            cssClass: "selective",
            reason: session.note + " Monitor overnight price action but hold off on equity/options entries until regular session opens."
        };
    }

    if (!top && opportunities.length === 0) {
        return {
            label: "WAIT",
            cssClass: "wait",
            reason: "No setups met minimum criteria today. Scanner found no actionable signals. Stay in cash."
        };
    }

    if (regime.includes("defensive") || riskAppetite.includes("low")) {
        return {
            label: "WAIT",
            cssClass: "wait",
            reason: "Market environment is defensive. Good setups exist but macro conditions don't support new entries. Watch, don't act."
        };
    }

    if (regime.includes("cautious") || regime.includes("selective")) {
        return {
            label: "SELECTIVE",
            cssClass: "selective",
            reason: `Market is mixed/selective. ${opportunities.length} setup(s) available. Only take the highest conviction trade with defined risk. Size small.`
        };
    }

    return {
        label: "GO",
        cssClass: "go",
        reason: `${opportunities.length} setup(s) confirmed. Market environment is supportive. Execute with discipline — defined risk, IRA limits apply.`
    };
}

function getIraFit(entry, stop) {
    // Use a $3-wide bull call spread at ~$1.00 debit = $100 max risk
    // This fits comfortably within the $120 IRA limit
    // Actual premium must be confirmed in Schwab before placing
    const estimatedDebit = 1.00;
    const estimatedCost = Math.round(estimatedDebit * 100 * 100) / 100;
    const maxRisk = estimatedCost;
    const withinLimit = maxRisk <= IRA_MAX_RISK;

    return {
        estimatedCost,
        maxRisk,
        withinLimit,
        note: withinLimit
            ? `$3-wide spread at ~$1.00 debit fits IRA limit. Confirm actual premium in Schwab before placing.`
            : `Estimated cost exceeds IRA $${IRA_MAX_RISK} limit. Consider a narrower spread or skip.`
    };
}

function getWatchFor(setup) {
    const state = String(setup.market_state || "").toLowerCase();
    const symbol = setup.symbol || "price";
    const entry = setup.entry || 0;
    const stop = setup.stop_loss || 0;

    if (state.includes("trend_continuation")) {
        return `${symbol} holds above $${entry.toFixed(2)} on any opening dip with volume support. A close below $${stop.toFixed(2)} invalidates the setup.`;
    }
    if (state.includes("breakout")) {
        return `${symbol} pushes through with expanding volume in the first 30 minutes. Low-volume breakouts often fail — wait for confirmation.`;
    }
    if (state.includes("compression")) {
        return `${symbol} breaks out of the tight range with a volume spike. Direction is uncertain until the break happens.`;
    }
    return `${symbol} holds the entry level and shows positive momentum. Exit immediately if price closes below $${stop.toFixed(2)}.`;
}
