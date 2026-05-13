function renderMarketStatusStrip(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="market-status-strip">
                <div class="market-strip-top">
                    <div>
                        <div class="market-strip-title">Market Status</div>
                        <div class="market-strip-subtitle">Market status strip unavailable. Confirm /market-status-strip is running.</div>
                    </div>
                </div>
            </div>
        `;
    }

    const items = data.items || [];
    const label = data.display_mode === "futures" ? "Futures Overnight / Pre-Market" : "Live Index Pulse";

    return `
        <div class="market-status-strip">
            <div class="market-strip-top">
                <div>
                    <div class="market-strip-title">${safe(label)}</div>
                    <div class="market-strip-subtitle">${safe(data.summary)}</div>
                </div>
                <div class="badge ${data.market_session === "OPEN" ? "green-bg" : "blue-bg"}">${safe(data.market_session)}</div>
            </div>

            <div class="market-strip-grid">
                ${items.map(renderMarketStripItem).join("")}
            </div>
        </div>
    `;
}

function renderMarketStripItem(item) {
    const change = Number(item.change_percent || 0);
    const changeClass = change > 0 ? "green" : change < 0 ? "red" : "yellow";
    const directionLabel = change > 0 ? "Up today" : change < 0 ? "Down today" : "Flat / no move reported";

    return `
        <div class="market-strip-item">
            <div class="market-strip-symbol">${safe(item.label || item.symbol)}</div>
            <div class="market-strip-price">${formatMarketValue(item.price)}</div>
            <div class="market-strip-change ${changeClass}">${formatSignedPercent(item.change_percent)}</div>
            <div class="small">${safe(item.symbol)} · ${directionLabel}</div>
        </div>
    `;
}

function formatMarketValue(value) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (Number.isNaN(number)) return safe(value);
    return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatSignedPercent(value) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (Number.isNaN(number)) return safe(value);
    const sign = number > 0 ? "+" : "";
    return `${sign}${number.toFixed(2)}%`;
}

function renderMarketDriverImpact(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card market-driver-card">
                <div class="section-title">Market Drivers & Position Impact</div>
                <div class="section-subtitle">
                    Market driver data unavailable. Confirm /market-driver-impact is running.
                </div>
            </div>
        `;
    }

    const drivers = data.market_drivers || [];
    const positionImpacts = data.position_driver_impacts || [];
    const recommendationImpacts = data.recommendation_driver_impacts || [];
    const directives = data.driver_directives || [];

    return `
        <div class="card market-driver-card">
            <div class="section-title">Market Drivers & Position Impact</div>
            <div class="section-subtitle">
                Financial data that can move the market, mapped directly to current positions and recommendations.
            </div>

            <div class="market-driver-hero">
                <div class="driver-status-panel">
                    <div class="daily-mode-label">Driver Summary</div>
                    <div class="allocation-status-value blue">MARKET CONTEXT</div>
                    <div class="small">${safe(data.driver_summary)}</div>
                </div>

                <div>
                    <div class="section-title">Driver Directives</div>
                    <div class="allocation-directive-grid">
                        ${directives.length ? directives.map(item => `<div class="allocation-directive">${safe(item)}</div>`).join("") : `<div class="empty-state">No driver directives available.</div>`}
                    </div>
                </div>
            </div>

            <div class="driver-grid">
                ${drivers.map(renderMarketDriverCard).join("")}
            </div>

            <div class="impact-block">
                <div class="section-title">Current Position Driver Impact</div>
                <div class="section-subtitle">
                    Shows whether today’s volatility, rates, index tone, oil, and sector proxies are creating tailwinds or headwinds for your holdings.
                </div>
                <div class="driver-impact-grid">
                    ${positionImpacts.length ? positionImpacts.slice(0, 6).map(renderPositionDriverImpactCard).join("") : `<div class="empty-state">No current position impact data available.</div>`}
                </div>
            </div>

            <div class="impact-block" style="margin-top:18px;">
                <div class="section-title">Recommendation Driver Confirmation</div>
                <div class="section-subtitle">
                    Checks whether top scanner ideas are supported or conflicted by market-moving drivers.
                </div>
                <div class="driver-impact-grid">
                    ${recommendationImpacts.length ? recommendationImpacts.slice(0, 6).map(renderRecommendationDriverImpactCard).join("") : `<div class="empty-state">No recommendation impact data available.</div>`}
                </div>
            </div>
        </div>
    `;
}

function renderMarketDriverCard(item) {
    const biasClass = getDriverBiasClass(item.bias);
    return `
        <div class="driver-card-mini">
            <div class="driver-name">${safe(item.driver)} · ${safe(item.symbol)}</div>
            <div class="driver-signal ${biasClass}">${safe(item.signal)}</div>
            <div class="small">Value: ${item.value === null || item.value === undefined ? "—" : safe(item.value)}</div>
            <div class="small">Change: ${formatPercent(item.change_percent)}</div>
            <div class="small" style="margin-top:8px;">${safe(item.impact)}</div>
        </div>
    `;
}

function renderPositionDriverImpactCard(item) {
    const impactClass = getDriverImpactClass(item.driver_impact);
    const reasons = item.driver_reasons || [];
    return `
        <div class="driver-impact-card">
            <div class="driver-impact-top">
                <div>
                    <div class="driver-symbol">${safe(item.symbol)}</div>
                    <div class="small">${safe(item.account)} · ${safe(item.sector)}</div>
                </div>
                <div class="badge ${impactClass}">${safe(item.driver_impact)}</div>
            </div>
            <div class="metric-grid" style="grid-template-columns: repeat(2, 1fr);">
                <div class="metric">
                    <div class="label">Open P/L</div>
                    <div class="value ${Number(item.open_pl || 0) >= 0 ? "green" : "red"}">${formatCurrency(item.open_pl)}</div>
                    <div class="small">${formatPercent(item.open_pl_percent)}</div>
                </div>
                <div class="metric">
                    <div class="label">Driver Score</div>
                    <div class="value ${impactClass}">${safe(item.driver_score)}</div>
                    <div class="small">${safe(item.sector_proxy)}</div>
                </div>
            </div>
            <div class="action-text"><strong>${safe(item.driver_action)}</strong></div>
            <div class="driver-reason-list">
                ${reasons.map(reason => `<div>• ${safe(reason)}</div>`).join("")}
            </div>
        </div>
    `;
}

function renderRecommendationDriverImpactCard(item) {
    const impactClass = getRecommendationDriverClass(item.driver_decision);
    const reasons = item.driver_reasons || [];
    return `
        <div class="driver-impact-card">
            <div class="driver-impact-top">
                <div>
                    <div class="driver-symbol">${safe(item.symbol)}</div>
                    <div class="small">${safe(item.sector)} · ${safe(item.sector_proxy)}</div>
                </div>
                <div class="badge ${impactClass}">${safe(item.driver_decision)}</div>
            </div>
            <div class="metric-grid" style="grid-template-columns: repeat(2, 1fr);">
                <div class="metric">
                    <div class="label">Scanner Score</div>
                    <div class="value">${safe(item.scanner_score)}</div>
                </div>
                <div class="metric">
                    <div class="label">Market Driver Confirmation</div>
                    <div class="value ${getDriverQualityTextClass(item.driver_quality_score)}">${formatScoreOutOf100(item.driver_quality_score)}</div>
                    <div class="small">${getDriverQualityLabel(item.driver_quality_score)}</div>
                </div>
            </div>
            <div class="action-text"><strong>${safe(item.driver_action)}</strong></div>
            <div class="driver-reason-list">
                ${reasons.map(reason => `<div>• ${safe(reason)}</div>`).join("")}
            </div>
        </div>
    `;
}

function getDriverBiasClass(bias) {
    const value = String(bias || "").toUpperCase();
    if (["SUPPORTIVE", "SECTOR"].includes(value)) return "green";
    if (["DEFENSIVE", "CAUTION"].includes(value)) return "red";
    if (["SELECTIVE", "NEUTRAL"].includes(value)) return "blue";
    return "yellow";
}

function getDriverImpactClass(impact) {
    const value = String(impact || "").toUpperCase();
    if (value === "TAILWIND") return "green";
    if (value === "HEADWIND") return "red";
    if (value === "CAUTION") return "yellow";
    return "blue";
}

function getRecommendationDriverClass(decision) {
    const value = String(decision || "").toUpperCase();
    if (value === "DRIVER CONFIRMED") return "green";
    if (value === "DRIVER CONFLICT") return "red";
    return "blue";
}


function formatSignedValue(value) {
    if (value === null || value === undefined || value === "") return "—";

    const number = Number(value);

    if (Number.isNaN(number)) return safe(value);

    const sign = number > 0 ? "+" : "";

    return `${sign}${number.toFixed(2)}`;
}
