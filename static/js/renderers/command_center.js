// TradeLayer Command Center Renderer
// Extracted from dashboard.js to keep the main dashboard controller smaller.

function renderPreMarketCommandShell() {
    return `
        <div id="preMarketCommandPanel" class="card premarket-command-card">
            <div class="section-title">Pre-Market Command Center</div>
            <div class="section-subtitle">
                Converting futures, volatility, breadth, and market regime into one operating decision before the open.
            </div>
            <div class="empty-state">Fetching /pre-market-command-center...</div>
        </div>
    `;
}

async function loadPreMarketCommandCenter() {
    const panel = document.getElementById("preMarketCommandPanel");

    if (!panel) {
        return;
    }

    try {
        const data = await fetchJson(`${API_BASE}/pre-market-command-center`);
        panel.outerHTML = renderPreMarketCommandPanel(data);
    } catch (error) {
        console.error("Pre-market command center unavailable:", error);

        panel.innerHTML = `
            <div class="section-title">Pre-Market Command Center</div>
            <div class="section-subtitle">
                Command center unavailable. Confirm /pre-market-command-center is running.
            </div>
            <div class="empty-state">Unable to load pre-market command data.</div>
        `;
    }
}

function renderPreMarketCommandPanel(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card premarket-command-card">
                <div class="section-title">Pre-Market Command Center</div>
                <div class="empty-state">Pre-market command center did not return a valid response.</div>
            </div>
        `;
    }

    const permissionClass = getCommandPermissionClass(data.new_trade_permission);
    const biasClass = getCommandBiasClass(data.market_bias);
    const futuresClass = getCommandFuturesClass(data.futures_tone);
    const volatilityClass = getCommandVolatilityClass(data.volatility_state);
    const directives = data.directives || [];

    return `
        <div class="card premarket-command-card">
            <div class="premarket-command-hero">
                <div class="premarket-command-main">
                    <div class="daily-mode-label">Pre-Market Command</div>
                    <div class="premarket-command-action ${permissionClass}">${safe(data.new_trade_permission)}</div>
                    <div class="premarket-command-summary">${safe(data.summary)}</div>

                    <div class="badge-row">
                        <div class="badge ${biasClass}">Market Bias: ${safe(data.market_bias)}</div>
                        <div class="badge ${futuresClass}">Futures: ${safe(data.futures_tone)}</div>
                        <div class="badge ${volatilityClass}">Volatility: ${safe(data.volatility_state)}</div>
                        <div class="badge">Score: ${safe(data.command_score)} / 100</div>
                    </div>
                </div>

                <div class="premarket-command-metrics">
                    <div class="metric">
                        <div class="label">Today’s Action</div>
                        <div class="value blue" style="font-size:20px;">${safe(data.today_action)}</div>
                        <div class="small">${safe(data.command_label)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Futures Tone</div>
                        <div class="value ${getCommandTextClass(data.futures_tone)}">${safe(data.futures_tone)}</div>
                        <div class="small">Avg: ${formatSignedPercent(data.average_futures_change_percent)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Market Regime</div>
                        <div class="value ${getCommandTextClass(data.market_bias)}" style="font-size:18px;">${safe(data.market_regime)}</div>
                        <div class="small">Risk appetite: ${safe(data.risk_appetite)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Volatility</div>
                        <div class="value ${getCommandVolatilityTextClass(data.volatility_state)}" style="font-size:18px;">${safe(data.volatility_state)}</div>
                        <div class="small">${safe(data.volatility_label)}</div>
                    </div>
                </div>
            </div>

            <div class="premarket-directive-grid">
                ${directives.length ? directives.map(item => `<div class="premarket-directive">${safe(item)}</div>`).join("") : `<div class="empty-state">No command directives returned.</div>`}
            </div>
        </div>
    `;
}

function getCommandPermissionClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("allowed")) return "green";
    if (text.includes("selective")) return "yellow";
    if (text.includes("avoid")) return "red";
    return "blue";
}

function getCommandBiasClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("supportive")) return "green-bg";
    if (text.includes("mixed")) return "yellow-bg";
    if (text.includes("defensive")) return "red-bg";
    return "blue-bg";
}

function getCommandFuturesClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("bullish") || text.includes("positive")) return "green-bg";
    if (text.includes("bearish") || text.includes("negative")) return "red-bg";
    return "yellow-bg";
}

function getCommandVolatilityClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("stress") || text.includes("elevated")) return "red-bg";
    if (text.includes("normal")) return "green-bg";
    if (text.includes("compression")) return "blue-bg";
    return "yellow-bg";
}

function getCommandTextClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("supportive") || text.includes("bullish") || text.includes("positive")) return "green";
    if (text.includes("defensive") || text.includes("bearish") || text.includes("negative") || text.includes("avoid")) return "red";
    if (text.includes("mixed") || text.includes("selective") || text.includes("flat")) return "yellow";
    return "blue";
}

function getCommandVolatilityTextClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("stress") || text.includes("elevated")) return "red";
    if (text.includes("normal")) return "green";
    if (text.includes("compression")) return "blue";
    return "yellow";
}
