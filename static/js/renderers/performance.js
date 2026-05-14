// TradeLayer Performance Renderer
// Displays the TradeLayer Performance Analytics Engine output.

function renderPerformanceScorecardShell() {
    return `
        <div id="performanceScorecardPanel" class="card performance-scorecard-card">
            <div class="section-title">TradeLayer Performance Scorecard</div>
            <div class="section-subtitle">
                Measuring realized trade-log performance and forward-test signal journal behavior.
            </div>
            <div class="empty-state">Fetching /performance...</div>
        </div>
    `;
}

async function loadPerformanceScorecardPanel() {
    const panel = document.getElementById("performanceScorecardPanel");

    if (!panel) {
        return;
    }

    try {
        const data = await fetchJson(`${API_BASE}/performance`);
        panel.outerHTML = renderPerformanceScorecardPanel(data);
    } catch (error) {
        console.error("Performance scorecard unavailable:", error);

        panel.innerHTML = `
            <div class="section-title">TradeLayer Performance Scorecard</div>
            <div class="section-subtitle">
                Performance analytics unavailable. Confirm /performance is running.
            </div>
            <div class="empty-state">Unable to load TradeLayer performance data.</div>
        `;
    }
}

function renderPerformanceScorecardPanel(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card performance-scorecard-card">
                <div class="section-title">TradeLayer Performance Scorecard</div>
                <div class="empty-state">Performance engine did not return a valid response.</div>
            </div>
        `;
    }

    const trade = data.trade_log_performance || {};
    const signal = data.signal_journal_performance || {};
    const signalSummary = signal.summary || {};
    const bestTrade = trade.best_trade || {};
    const worstTrade = trade.worst_trade || {};

    return `
        <div class="card performance-scorecard-card">
            <div class="performance-scorecard-hero">
                <div class="performance-status-panel">
                    <div class="daily-mode-label">Performance Engine</div>
                    <div class="performance-status-value ${getPerformanceConfidenceClass(data.confidence_label)}">
                        ${safe(data.confidence_label)}
                    </div>
                    <div class="small">${safe(data.confidence_note)}</div>

                    <div class="badge-row">
                        <div class="badge blue-bg">${safe(data.engine)}</div>
                        <div class="badge">Closed Trades: ${safe(trade.closed_trades)}</div>
                        <div class="badge">Signals: ${safe(signal.total_signals)}</div>
                    </div>
                </div>

                <div class="performance-metric-grid">
                    <div class="metric">
                        <div class="label">Trade Log Win Rate</div>
                        <div class="value ${getPerformanceRateClass(trade.win_rate)}">${formatPercent(trade.win_rate)}</div>
                        <div class="small">Wins: ${safe(trade.wins)} · Losses: ${safe(trade.losses)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Realized P/L</div>
                        <div class="value ${getPnlClass(trade.total_realized_pl)}">${formatCurrencyOrDash(trade.total_realized_pl)}</div>
                        <div class="small">Avg trade: ${formatCurrencyOrDash(trade.average_trade_pl ?? trade.avg_pl)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Signal Win Rate</div>
                        <div class="value ${getPerformanceRateClass(signalSummary.win_rate)}">${formatPercent(signalSummary.win_rate)}</div>
                        <div class="small">Resolved: ${safe(signalSummary.resolved)} / ${safe(signalSummary.total)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Signal Avg Return</div>
                        <div class="value ${getPnlClass(signalSummary.average_current_return_percent)}">${formatPercent(signalSummary.average_current_return_percent)}</div>
                        <div class="small">Open positive: ${safe(signalSummary.open_positive)} · Open negative: ${safe(signalSummary.open_negative)}</div>
                    </div>
                </div>
            </div>

            <div class="performance-detail-grid">
                <div class="performance-detail-card">
                    <div class="section-title">Trade Log Quality</div>
                    <div class="metric-grid two">
                        <div class="mini-metric">
                            <div class="label">Average Winner</div>
                            <div class="value green">${formatCurrencyOrDash(trade.average_winner)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Average Loser</div>
                            <div class="value red">${formatCurrencyOrDash(trade.average_loser)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Expectancy</div>
                            <div class="value ${getPnlClass(trade.expectancy)}">${formatCurrencyOrDash(trade.expectancy)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Profit Factor</div>
                            <div class="value blue">${formatNumberOrDash(trade.profit_factor)}</div>
                        </div>
                    </div>

                    <div class="empty-state">
                        <strong>Best trade:</strong> ${formatTradeSummary(bestTrade)}
                        <br>
                        <strong>Worst trade:</strong> ${formatTradeSummary(worstTrade)}
                    </div>
                </div>

                <div class="performance-detail-card">
                    <div class="section-title">Signal Journal Quality</div>
                    <div class="metric-grid two">
                        <div class="mini-metric">
                            <div class="label">Best Strategy</div>
                            <div class="value blue" style="font-size:16px;">${formatExpressionLabel(signal.best_strategy)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Best Score Bucket</div>
                            <div class="value blue">${safe(signal.best_score_bucket)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Signal Losses</div>
                            <div class="value red">${safe(signalSummary.losses)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Open Positive</div>
                            <div class="value green">${safe(signalSummary.open_positive)}</div>
                        </div>
                    </div>

                    <div class="empty-state">
                        This panel measures TradeLayer itself. Early results should be treated as feedback for improving score rules, stops, and setup filters — not statistical proof.
                    </div>
                </div>
            </div>
        </div>
    `;
}

function formatTradeSummary(trade) {
    if (!trade || !trade.symbol) {
        return "—";
    }

    return `${safe(trade.symbol)} · ${safe(trade.account)} · ${formatCurrencyOrDash(trade.realized_pl)}`;
}

function getPerformanceConfidenceClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("usable")) return "green";
    if (text.includes("developing")) return "blue";
    if (text.includes("early")) return "yellow";

    return "blue";
}

function getPerformanceRateClass(value) {
    const number = Number(value);

    if (Number.isNaN(number)) {
        return "blue";
    }

    if (number >= 60) return "green";
    if (number >= 40) return "yellow";

    return "red";
}

function formatNumberOrDash(value) {
    if (value === null || value === undefined || value === "") return "—";

    const number = Number(value);
    if (Number.isNaN(number)) return "—";

    return number.toFixed(2);
}
