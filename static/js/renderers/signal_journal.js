// TradeLayer Signal Journal Renderer
// Extracted from dashboard.js to keep signal tracking UI modular.

function renderSignalJournalShell() {
    return `
        <div id="signalJournalPanel" class="card signal-journal-card">
            <div class="section-title">Signal Journal</div>
            <div class="section-subtitle">
                Capturing today’s top TradeLayer signal and evaluating prior recommendations.
            </div>
            <div class="empty-state">Fetching /signal-journal...</div>
        </div>
    `;
}

async function loadSignalJournalPanel() {
    const panel = document.getElementById("signalJournalPanel");

    if (!panel) {
        return;
    }

    try {
        const data = await fetchJson(`${API_BASE}/signal-journal`);
        panel.outerHTML = renderSignalJournalPanel(data);
    } catch (error) {
        console.error("Signal journal unavailable:", error);

        panel.innerHTML = `
            <div class="section-title">Signal Journal</div>
            <div class="section-subtitle">
                Forward-test tracking for TradeLayer recommendations.
            </div>
            <div class="empty-state">
                Signal journal unavailable. Confirm /signal-journal is running.
            </div>
        `;
    }
}

function renderSignalJournalPanel(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card signal-journal-card">
                <div class="section-title">Signal Journal</div>
                <div class="empty-state">Signal journal did not return a valid response.</div>
            </div>
        `;
    }

    const windows = data.windows || {};
    const recent = data.recent_entries || [];
    const capture = data.capture_result || {};

    return `
        <div class="card signal-journal-card">
            <div class="section-title">Signal Journal / Forward Test</div>
            <div class="section-subtitle">
                Records TradeLayer’s daily top recommendation, then checks target, stop, and forward returns. This is forward testing, not a finalized historical backtest.
            </div>

            <div class="signal-journal-hero">
                <div class="signal-journal-command">
                    <div class="daily-mode-label">Today’s Capture</div>
                    <div class="allocation-status-value blue">${safe(capture.entry?.symbol || "NO SIGNAL")}</div>
                    <div class="small">${safe(capture.reason)}</div>

                    <div class="badge-row">
                        <div class="badge ${capture.created ? "green-bg" : "blue-bg"}">${capture.created ? "NEW ENTRY" : "RECORDED"}</div>
                        <div class="badge">Total Signals: ${safe(data.total_entries)}</div>
                        <div class="badge">Path: ${safe(data.journal_path)}</div>
                    </div>
                </div>

                <div class="signal-window-grid">
                    ${renderSignalWindowCard("7 Days", windows.seven_day)}
                    ${renderSignalWindowCard("30 Days", windows.thirty_day)}
                    ${renderSignalWindowCard("6 Months", windows.six_month)}
                    ${renderSignalWindowCard("1 Year", windows.one_year)}
                </div>
            </div>

            <div class="why-box">
                <div class="section-title">Recent Signal Outcomes</div>
                <div class="section-subtitle">
                    Latest captured recommendations and their current measured outcomes.
                </div>
                ${renderRecentSignalRows(recent)}
            </div>

            <div class="small" style="margin-top:14px;">
                ${safe(data.summary)}
            </div>
        </div>
    `;
}

function renderSignalWindowCard(label, item) {
    item = item || {};

    return `
        <div class="metric">
            <div class="label">${safe(label)}</div>
            <div class="value ${getSignalReturnClass(item.average_current_return_percent)}">${formatPercent(item.average_current_return_percent)}</div>
            <div class="small">Signals: ${safe(item.total_signals)} · Open: ${safe(item.open_signals)}</div>
            <div class="small">Targets: ${safe(item.target_hits)} · Stops: ${safe(item.stop_hits)}</div>
        </div>
    `;
}

function renderRecentSignalRows(items) {
    if (!items || items.length === 0) {
        return `<div class="empty-state">No signals captured yet. Today’s top trade will be captured when this endpoint runs.</div>`;
    }

    return `
        <div class="signal-row-grid">
            ${items.slice(0, 8).map(item => {
                const outcome = item.outcome || {};
                const outcomeClass = getOutcomeClass(outcome.outcome_label);
                const returnClass = getSignalReturnClass(outcome.current_return_percent);

                return `
                    <div class="signal-row-card">
                        <div class="position-action-top">
                            <div>
                                <div class="action-symbol">${safe(item.symbol)}</div>
                                <div class="small">${safe(item.captured_date)} · ${safe(item.recommended_strategy)}</div>
                            </div>
                            <div class="badge ${outcomeClass}">${safe(outcome.outcome_label)}</div>
                        </div>

                        <div class="metric-grid two" style="margin-bottom:10px;">
                            <div class="mini-metric">
                                <div class="label">Entry</div>
                                <div class="value">${formatCurrency(item.entry)}</div>
                            </div>

                            <div class="mini-metric">
                                <div class="label">Current Return</div>
                                <div class="value ${returnClass}">${formatPercent(outcome.current_return_percent)}</div>
                            </div>

                            <div class="mini-metric">
                                <div class="label">Target / Stop</div>
                                <div class="value" style="font-size:16px;">${formatCurrency(item.target)} / ${formatCurrency(item.stop)}</div>
                            </div>

                            <div class="mini-metric">
                                <div class="label">Score</div>
                                <div class="value blue">${safe(item.trade_score)}</div>
                            </div>
                        </div>

                        <div class="small">
                            Max favorable: ${formatPercent(outcome.max_favorable_percent)} · Max adverse: ${formatPercent(outcome.max_adverse_percent)} · Days: ${safe(outcome.days_elapsed)}
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function getSignalReturnClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "blue";
    if (number > 0) return "green";
    if (number < 0) return "red";
    return "yellow";
}

function getOutcomeClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("target")) return "green-bg";
    if (text.includes("stop")) return "red-bg";
    if (text.includes("ambiguous")) return "yellow-bg";
    if (text.includes("positive")) return "green-bg";
    if (text.includes("negative")) return "red-bg";

    return "blue-bg";
}
