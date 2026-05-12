function renderTradeRecommendationCard(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card trade-recommendation-card">
                <div class="section-title">Trade Recommendation</div>
                <div class="empty-state">
                    Trade recommendation unavailable. Confirm /trade-recommendations is running.
                </div>
            </div>
        `;
    }

    const top = data.top_trade || {};
    const option = data.options_recommendation || {};
    const risk = option.risk_profile || {};
    const market = data.market_context || {};
    const expression = option.preferred_expression || "NO_TRADE";
    const expressionLabel = formatExpressionLabel(expression);
    const expressionClass = getExpressionClass(expression);
    const confidenceClass = getConfidenceClass(option.confidence);
    const warnings = option.warnings || [];

    return `
        <div class="card trade-recommendation-card">
            <div class="section-title">Trade Recommendation</div>
            <div class="section-subtitle">
                Daily decision layer for the Individual 556 small-account test. Focus: consistency, defined risk, and capital preservation.
            </div>

            <div class="trade-recommendation-hero">
                <div class="recommendation-command-panel">
                    <div class="recommendation-label">Today’s Primary Candidate</div>
                    <div class="recommendation-symbol-row">
                        <div>
                            <div class="recommendation-symbol">${safe(top.symbol || option.symbol)}</div>
                            <div class="small">${safe(top.market_state)} · ${safe(top.expected_hold)}</div>
                        </div>
                        <div class="badge ${confidenceClass}">${safe(option.confidence)} Confidence</div>
                    </div>

                    <div class="recommendation-label">Preferred Expression</div>
                    <div class="recommendation-expression ${expressionClass}">${safe(expressionLabel)}</div>

                    <div class="recommendation-summary-box">
                        ${safe(data.summary)}
                    </div>
                </div>

                <div>
                    <div class="recommendation-detail-grid">
                        <div class="metric">
                            <div class="label">Account Value</div>
                            <div class="value">${formatCurrency(data.account_value || risk.account_value)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Preferred Risk</div>
                            <div class="value yellow">${formatCurrency(risk.preferred_risk_per_trade)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Max Risk</div>
                            <div class="value red">${formatCurrency(risk.max_risk_per_trade)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Conviction</div>
                            <div class="value ${confidenceClass.replace("-bg", "")}">${safe(option.conviction_score)}</div>
                        </div>
                    </div>

                    <div class="recommendation-detail-grid">
                        <div class="metric">
                            <div class="label">Entry</div>
                            <div class="value">${formatCurrency(top.entry)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Target</div>
                            <div class="value green">${formatCurrency(top.target)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Stop</div>
                            <div class="value red">${formatCurrency(top.stop_loss)}</div>
                        </div>

                        <div class="metric">
                            <div class="label">Market Regime</div>
                            <div class="value blue" style="font-size:17px;">${safe(market.market_regime)}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="recommendation-reason-grid">
                <div class="recommendation-reason-panel">
                    <div class="section-title">Why This Structure</div>
                    <div class="small">${safe(option.reason)}</div>
                    <div class="badge-row">
                        <div class="badge blue-bg">Scanner: ${safe(option.scanner_recommended_strategy)}</div>
                        <div class="badge">Options Pressure: ${safe(option.options_pressure)}</div>
                        <div class="badge ${getMarketBiasClass(market.risk_appetite)}">Risk Appetite: ${safe(market.risk_appetite)}</div>
                    </div>
                </div>

                <div class="recommendation-warning-panel">
                    <div class="section-title">Risk Control</div>
                    <div class="small">${safe(data.risk_note || risk.philosophy)}</div>
                    ${warnings.length ? `<div style="margin-top:10px;">${warnings.map(item => `<div class="small">• ${safe(item)}</div>`).join("")}</div>` : `<div class="small" style="margin-top:10px;">No active warnings returned by the options engine.</div>`}
                </div>
            </div>
        </div>
    `;
}

function formatExpressionLabel(value) {
    const text = String(value || "").toUpperCase();
    const labels = {
        "BULL_CALL_VERTICAL_SPREAD": "Bull Call Vertical Spread",
        "BEAR_PUT_VERTICAL_SPREAD": "Bear Put Vertical Spread",
        "LONG_CALL": "Long Call",
        "LONG_PUT": "Long Put",
        "SHARES": "Shares",
        "NO_TRADE": "No Trade"
    };

    return labels[text] || text.replaceAll("_", " ");
}

function getExpressionClass(value) {
    const text = String(value || "").toUpperCase();
    if (text.includes("BULL") || text.includes("CALL") || text === "SHARES") return "green";
    if (text.includes("BEAR") || text.includes("PUT")) return "red";
    if (text.includes("NO_TRADE")) return "yellow";
    return "blue";
}

function getConfidenceClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("high")) return "green-bg";
    if (text.includes("moderate") || text.includes("medium")) return "blue-bg";
    if (text.includes("low")) return "yellow-bg";
    return "blue-bg";
}
