// TradeLayer Dashboard Controller
// Main dashboard orchestration only. Feature-specific renderers live in static/js/renderers/.

function renderDashboard(scanData, tradeLogData, portfolioData, portfolioAnalysisData, performanceData, dailyActionData, capitalAllocationData, marketDriverData, marketStatusData, tradeRecommendationData) {
    const top = scanData?.top_trade || null;
    const topTradeSection = top ? renderTopTradeAndRiskSection(top) : renderNoTradeWorkstationSection(scanData, tradeRecommendationData);

    document.getElementById("dashboard").innerHTML = `
        <div class="workspace-command-zone">
            ${renderMarketStatusStrip(marketStatusData)}
            ${renderPreMarketCommandShell()}
        </div>

        <div class="workspace-tabs-shell">
            <div class="workspace-tabs-header">
                <button class="workspace-tab-button active" data-workspace-tab="opportunities">Opportunities</button>
                <button class="workspace-tab-button" data-workspace-tab="portfolio">Portfolio</button>
                <button class="workspace-tab-button" data-workspace-tab="performance">Performance</button>
                <button class="workspace-tab-button" data-workspace-tab="market-drivers">Market Drivers</button>
            </div>

            <div class="workspace-tab-panel active" data-workspace-panel="opportunities">
                ${renderTradeRecommendationCard(tradeRecommendationData)}

                ${topTradeSection}

                ${top ? renderOptionsIntelligenceShell() : ""}

                <div class="card top-opportunities">
                    <div class="section-title">Top Opportunities</div>
                    <div class="section-subtitle">
                        Highest-ranked setups after trend, momentum, liquidity, options pressure, regime, and RS vs SPY filters.
                    </div>

                    <div class="opportunity-grid">
                        ${renderOpportunityCards(scanData?.trade_opportunities || [])}
                    </div>
                </div>

                <div class="bottom-grid">
                    <div class="card">
                        <div class="section-title">Watchlist</div>
                        <div class="section-subtitle">
                            Names with potential, but not yet strong enough for top-trade status.
                        </div>

                        <div class="list">
                            ${renderRows(scanData?.watchlist || [])}
                        </div>
                    </div>

                    <div class="card">
                        <div class="section-title">Avoid / Weak Environment</div>
                        <div class="section-subtitle">
                            Strong names can still be poor trades if the environment is unstable or overextended.
                        </div>

                        <div class="list">
                            ${renderRows(scanData?.avoid || [])}
                        </div>
                    </div>
                </div>
            </div>

            <div class="workspace-tab-panel" data-workspace-panel="portfolio">
                ${renderDailyActionPlan(dailyActionData)}

                ${renderCapitalAllocationGuidance(capitalAllocationData)}

                ${renderPortfolioAnalysis(portfolioAnalysisData)}

                <div class="positions-grid">
                    <div class="card">
                        <div class="section-title">Open Positions</div>
                        <div class="section-subtitle">
                            Live unrealized P/L calculated from current market price, share count, and cost basis.
                        </div>
                        ${renderOpenPositions(tradeLogData, portfolioData, portfolioAnalysisData)}
                    </div>

                    <div class="card">
                        <div class="section-title">Closed Trades</div>
                        <div class="section-subtitle">
                            Completed trades and realized P/L summary.
                        </div>
                        ${renderClosedTrades(tradeLogData, performanceData)}
                    </div>
                </div>
            </div>

            <div class="workspace-tab-panel" data-workspace-panel="performance">
                ${renderPerformanceScorecardShell()}
                ${renderSignalJournalShell()}
            </div>

            <div class="workspace-tab-panel" data-workspace-panel="market-drivers">
                ${renderMarketDriverImpact(marketDriverData)}
            </div>
        </div>
    `;

    initializeWorkspaceTabs();
    loadPreMarketCommandCenter();
    loadOptionsIntelligencePanel();
    loadSignalJournalPanel();
    loadPerformanceScorecardPanel();
}





function renderTopTradeAndRiskSection(top) {
    const rsClass = getRsClass(top.relative_strength_vs_spy);
    const environmentClass = getEnvironmentClass(top.market_state);

    return `
        <div class="main-grid">
            <div class="card">
                <div class="top-trade-label">Recommended Daily Trade</div>
                <div class="symbol">${safe(top.symbol)}</div>
                <div class="subtitle">${safe(top.market_state)}</div>

                <div class="badge-row">
                    <div class="badge ${environmentClass}">${safe(top.action_label)}</div>
                    <div class="badge">${safe(top.recommended_strategy)}</div>
                    <div class="badge">Options: ${safe(top.options_pressure)}</div>
                </div>

                <div class="metric-grid">
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
                        <div class="label">Trade Score</div>
                        <div class="value">${safe(top.score)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Relative Strength vs SPY</div>
                        <div class="value ${rsClass}">${formatPercent(top.relative_strength_vs_spy)}</div>
                    </div>

                    <div class="metric">
                        <div class="label">Expected Hold</div>
                        <div class="value">${safe(top.expected_hold)}</div>
                    </div>
                </div>

                <div class="why-box">
                    <div class="section-title">Why This Strategy</div>
                    ${renderReasonList(top.strategy_reason)}
                </div>
            </div>

            <div class="card">
                <div class="section-title">Risk Management</div>
                <div class="section-subtitle">
                    Environment-aware sizing using account value, max risk, entry, stop, market state, and exposure caps.
                </div>

                <div class="risk-field">
                    <label for="accountValue">Account Value ($)</label>
                    <input id="accountValue" class="risk-input" type="number" value="25000">
                </div>

                <div class="risk-field">
                    <label for="riskPercent">Max Risk Per Trade (%)</label>
                    <input id="riskPercent" class="risk-input" type="number" value="2">
                </div>

                <button
                    class="risk-button"
                    onclick="calculateRisk(${Number(top.entry)}, ${Number(top.stop_loss)}, '${safe(top.symbol)}', ${Number(top.target)}, ${Number(top.score)})"
                >
                    Calculate Position Size
                </button>

                <div id="riskResults"></div>
            </div>
        </div>
    `;
}




function renderCapitalAllocationGuidance(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card capital-allocation-card">
                <div class="section-title">Capital Allocation Guidance</div>
                <div class="empty-state">
                    Capital allocation guidance unavailable. Confirm /capital-allocation-guidance is running.
                </div>
            </div>
        `;
    }

    const summary = data.allocation_summary || {};
    const context = data.market_context || {};
    const directives = data.directives || [];
    const decisions = data.top_position_decisions || data.position_decisions || [];
    const accounts = data.account_summaries || [];
    const statusClass = getAllocationStatusClass(summary.deployment_status);
    const marketBiasClass = getMarketBiasClass(context.market_bias);

    return `
        <div class="card capital-allocation-card">
            <div class="section-title">Capital Allocation Guidance</div>
            <div class="section-subtitle">
                Converts market regime, account pressure, open P/L, and position guidance into add / hold / reduce / exit decisions.
            </div>

            <div class="capital-allocation-hero">
                <div class="allocation-status-panel">
                    <div class="daily-mode-label">Capital Deployment Status</div>
                    <div class="allocation-status-value ${statusClass}">${safe(summary.deployment_status)}</div>
                    <div class="small">${safe(summary.headline)}</div>

                    <div class="badge-row">
                        <div class="badge ${marketBiasClass}">Market Bias: ${safe(context.market_bias)}</div>
                        <div class="badge">Add Candidates: ${safe(summary.add_candidates)}</div>
                        <div class="badge ${summary.high_priority_count > 0 ? "red-bg" : "green-bg"}">High Priority: ${safe(summary.high_priority_count)}</div>
                    </div>

                    <div class="empty-state">
                        ${safe(summary.summary)}
                    </div>
                </div>

                <div>
                    <div class="section-title">Allocation Directives</div>
                    <div class="allocation-directive-grid">
                        ${directives.length ? directives.map(item => `<div class="allocation-directive">${safe(item)}</div>`).join("") : `<div class="empty-state">No allocation directives available.</div>`}
                    </div>
                </div>
            </div>

            <div class="capital-decision-grid">
                <div class="metric">
                    <div class="label">Total Position Value</div>
                    <div class="value">${formatCurrencyOrDash(summary.total_position_value)}</div>
                </div>

                <div class="metric">
                    <div class="label">Open P/L</div>
                    <div class="value ${getPnlClass(summary.open_pl)}">${formatCurrencyOrDash(summary.open_pl)}</div>
                    <div class="small">${formatPercent(summary.open_pl_percent)}</div>
                </div>

                <div class="metric">
                    <div class="label">Reduce / Protect</div>
                    <div class="value ${summary.reduce_or_protect_count > 0 ? "yellow" : "green"}">${safe(summary.reduce_or_protect_count)}</div>
                    <div class="small">Positions needing caution</div>
                </div>

                <div class="metric">
                    <div class="label">Market Bias</div>
                    <div class="value ${getMarketBiasTextClass(context.market_bias)}">${safe(context.market_bias)}</div>
                    <div class="small">${safe(context.reason)}</div>
                </div>
            </div>

            <div class="why-box">
                <div class="section-title">Position Decisions</div>
                <div class="section-subtitle">
                    Ranked by urgency, pressure, and capital-allocation relevance.
                </div>
                ${renderPositionDecisionCards(decisions)}
            </div>

            ${accounts.length ? `
                <div class="why-box">
                    <div class="section-title">Account Allocation Summary</div>
                    <div class="account-allocation-grid">
                        ${accounts.map(renderAccountAllocationCard).join("")}
                    </div>
                </div>
            ` : ""}

            <div class="small" style="margin-top:14px;">
                ${safe(data.disclaimer)}
            </div>
        </div>
    `;
}

function renderPositionDecisionCards(items) {
    if (!items.length) {
        return `<div class="empty-state">No open position decisions available yet.</div>`;
    }

    return `
        <div class="position-decision-grid">
            ${items.map(item => `
                <div class="position-decision-card">
                    <div class="position-decision-top">
                        <div>
                            <div class="decision-symbol">${safe(item.symbol)}</div>
                            <div class="small">${safe(item.account)}</div>
                        </div>
                        <div class="badge ${getPriorityClass(item.priority)}">${safe(item.priority)}</div>
                    </div>

                    <div class="decision-main ${getDecisionTextClass(item.decision)}">${safe(item.decision)}</div>

                    <div class="metric-grid two" style="margin-bottom:10px;">
                        <div class="mini-metric">
                            <div class="label">Open P/L</div>
                            <div class="value ${getPnlClass(item.unrealized_pl)}">${formatCurrencyOrDash(item.unrealized_pl)}</div>
                            <div class="small">${formatPercent(item.unrealized_pl_percent)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Pressure</div>
                            <div class="value ${getPressureScoreClass(item.position_pressure_score)}">${safe(item.position_pressure_score)}</div>
                            <div class="small">Confidence: ${safe(item.confidence)}</div>
                        </div>
                    </div>

                    <div class="badge-row" style="margin-top:6px; margin-bottom:8px;">
                        <div class="badge ${getAddPermissionClass(item.add_permission)}">${safe(item.add_permission)}</div>
                        <div class="badge ${getReducePermissionClass(item.reduce_permission)}">${safe(item.reduce_permission)}</div>
                    </div>

                    <div class="small">Current guidance: ${safe(item.current_guidance)} • Risk: ${safe(item.risk_level)}</div>
                    <div class="action-text">${safe(item.suggested_action)}</div>

                    <div class="decision-rules">
                        <div class="decision-rule"><strong>Add rule:</strong> ${safe(item.add_rule)}</div>
                        <div class="decision-rule"><strong>Reduce rule:</strong> ${safe(item.reduce_rule)}</div>
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}

function renderAccountAllocationCard(account) {
    return `
        <div class="account-allocation-card">
            <div class="account-name">${safe(account.account)}</div>
            <div class="small" style="margin-bottom:10px;">${safe(account.dominant_action)}</div>

            <div class="metric-grid two" style="margin-bottom:0;">
                <div class="mini-metric">
                    <div class="label">Value</div>
                    <div class="value">${formatCurrencyOrDash(account.total_market_value)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Open P/L</div>
                    <div class="value ${getPnlClass(account.open_pl)}">${formatCurrencyOrDash(account.open_pl)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Add Candidates</div>
                    <div class="value blue">${safe(account.add_candidates)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Protect</div>
                    <div class="value ${account.reduce_or_protect_count > 0 ? "yellow" : "green"}">${safe(account.reduce_or_protect_count)}</div>
                </div>
            </div>
        </div>
    `;
}

function renderDailyActionPlan(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="card daily-action-card">
                <div class="section-title">Daily Action Plan</div>
                <div class="empty-state">
                    Daily action plan unavailable. Confirm /daily-action-plan is running.
                </div>
            </div>
        `;
    }

    const mode = data.daily_mode || {};
    const posture = data.portfolio_posture || {};
    const permission = data.new_trade_permission || {};
    const pressure = data.market_pressure || {};
    const positionPlan = data.position_action_plan || {};
    const directives = data.daily_directives || [];
    const modeClass = getDailyModeClass(mode.daily_mode);
    const permissionClass = getPermissionClass(permission.permission);

    return `
        <div class="card daily-action-card">
            <div class="section-title">Daily Action Plan</div>
            <div class="section-subtitle">
                Market regime + portfolio posture + open-position maintenance converted into one operating plan.
            </div>

            <div class="daily-action-hero">
                <div class="daily-mode-panel">
                    <div class="daily-mode-label">Today’s Mode</div>
                    <div class="daily-mode-value ${modeClass}">${safe(mode.daily_mode)}</div>
                    <div class="small">${safe(mode.daily_mode_label)}</div>

                    <div class="badge-row">
                        <div class="badge ${permissionClass}">New Trades: ${safe(permission.permission)}</div>
                        <div class="badge">Max New Trades: ${safe(permission.max_new_trades_today)}</div>
                        <div class="badge">Mode Score: ${safe(mode.daily_mode_score)}</div>
                    </div>

                    <div class="empty-state">
                        ${safe(data.summary)}
                    </div>
                </div>

                <div>
                    <div class="section-title">What To Do Today</div>
                    <div class="directive-list">
                        ${directives.length ? directives.map(item => `<div class="directive-item">${safe(item)}</div>`).join("") : `<div class="empty-state">No daily directives available.</div>`}
                    </div>
                </div>
            </div>

            <div class="action-plan-grid">
                <div class="metric">
                    <div class="label">Market Pressure</div>
                    <div class="value ${getPressureClass(pressure.market_pressure)}">${safe(pressure.market_pressure)}</div>
                    <div class="small">${safe(pressure.reason)}</div>
                </div>

                <div class="metric">
                    <div class="label">Portfolio Posture</div>
                    <div class="value ${getPostureClass(posture.portfolio_posture)}">${safe(posture.portfolio_posture)}</div>
                    <div class="small">Open P/L: ${formatCurrency(posture.open_pl)} (${formatPercent(posture.open_pl_percent)})</div>
                </div>

                <div class="metric">
                    <div class="label">Maintenance</div>
                    <div class="value yellow">${safe(positionPlan.action_counts?.urgent_review || 0)} / ${safe(positionPlan.action_counts?.manage_today || 0)}</div>
                    <div class="small">Urgent review / manage today</div>
                </div>

                <div class="metric">
                    <div class="label">Sizing Guidance</div>
                    <div class="value blue">${safe(permission.permission)}</div>
                    <div class="small">${safe(permission.sizing_guidance)}</div>
                </div>
            </div>

            <div class="why-box">
                <div class="section-title">Position Maintenance Queue</div>
                <div class="section-subtitle">
                    Highest-priority open positions based on existing guidance, P/L pressure, and today’s mode.
                </div>
                ${renderPositionActionCards(positionPlan.top_actions || [])}
            </div>

            <div class="small" style="margin-top:14px;">
                ${safe(data.disclaimer)}
            </div>
        </div>
    `;
}

function renderPositionActionCards(items) {
    if (!items.length) {
        return `<div class="empty-state">No open positions require action review right now.</div>`;
    }

    return `
        <div class="position-action-grid">
            ${items.map(item => `
                <div class="position-action-card">
                    <div class="position-action-top">
                        <div>
                            <div class="action-symbol">${safe(item.symbol)}</div>
                            <div class="small">${safe(item.account)}</div>
                        </div>
                        <div class="badge ${getPriorityClass(item.priority)}">${safe(item.priority)}</div>
                    </div>

                    <div class="metric-grid two" style="margin-bottom:10px;">
                        <div class="mini-metric">
                            <div class="label">Open P/L</div>
                            <div class="value ${getPnlClass(item.unrealized_pl)}">${formatCurrencyOrDash(item.unrealized_pl)}</div>
                            <div class="small">${formatPercent(item.unrealized_pl_percent)}</div>
                        </div>

                        <div class="mini-metric">
                            <div class="label">Action</div>
                            <div class="value blue" style="font-size:16px;">${safe(item.recommended_action)}</div>
                        </div>
                    </div>

                    <div class="small">Existing guidance: ${safe(item.existing_guidance)} • Risk: ${safe(item.risk_level)}</div>
                    <div class="action-text">${safe(item.action_reason)}</div>
                </div>
            `).join("")}
        </div>
    `;
}

async function calculateRisk(entry, stop, symbol = "", target = null, tradeScore = null) {
    try {
        const accountValue = document.getElementById("accountValue").value;
        const riskPercent = document.getElementById("riskPercent").value;

        const symbolParam = symbol ? `&symbol=${encodeURIComponent(symbol)}` : "";
        const targetParam = target ? `&target_price=${encodeURIComponent(target)}` : "";
        const scoreParam = tradeScore ? `&trade_score=${encodeURIComponent(tradeScore)}` : "";

        const data = await fetchJson(
            `${API_BASE}/risk-plan?account_value=${accountValue}&risk_percent=${riskPercent}&entry_price=${entry}&stop_price=${stop}${symbolParam}${targetParam}${scoreParam}&signal_sample_size=3&volatility_state=normal`
        );

        document.getElementById("riskResults").innerHTML = `
            <div class="metric-grid two">
                <div class="metric">
                    <div class="label">Allowed Risk</div>
                    <div class="value red">${formatCurrency(data.allowed_risk_dollars)}</div>
                </div>

                <div class="metric">
                    <div class="label">Suggested Shares</div>
                    <div class="value">${safe(data.suggested_shares)}</div>
                </div>

                <div class="metric">
                    <div class="label">Estimated Max Loss</div>
                    <div class="value red">${formatCurrency(data.estimated_max_loss)}</div>
                </div>

                <div class="metric">
                    <div class="label">Risk / Share</div>
                    <div class="value">${formatCurrency(data.risk_per_share)}</div>
                </div>

                <div class="metric">
                    <div class="label">Account Exposure</div>
                    <div class="value yellow">${formatPercent(data.position_exposure_percent)}</div>
                </div>

                <div class="metric">
                    <div class="label">Environment</div>
                    <div class="value blue">${safe(data.environment_label)}</div>
                </div>
            </div>

            ${renderPositionSizingIntelligence(data.position_sizing_intelligence)}

            <div class="empty-state">
                ${safe(data.risk_summary)}
                ${data.warnings?.length ? `<br><br>${data.warnings.map(w => `• ${safe(w)}`).join("<br>")}` : ""}
            </div>
        `;
    } catch (error) {
        console.error(error);
        document.getElementById("riskResults").innerHTML = `
            <div class="empty-state">
                Risk calculator unavailable. Confirm the /risk-plan endpoint is running.
            </div>
        `;
    }
}

function renderPositionSizingIntelligence(data) {
    if (!data || data.status !== "ok") {
        return "";
    }

    const sample = data.sample_confidence || {};
    const volatility = data.volatility_filter || {};
    const environment = data.environment_filter || {};

    return `
        <div class="position-sizing-box">
            <div class="section-title">Position Sizing Intelligence</div>
            <div class="section-subtitle">
                Conservative fractional Kelly, sample-size, volatility, and environment filters.
            </div>

            <div class="metric-grid two">
                <div class="mini-metric">
                    <div class="label">Base Risk</div>
                    <div class="value">${formatPercent(data.base_risk_percent)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Final Risk</div>
                    <div class="value blue">${formatPercent(data.final_risk_percent)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Estimated Probability</div>
                    <div class="value">${formatPercent(data.estimated_win_probability)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Fractional Kelly</div>
                    <div class="value yellow">${formatPercent(data.fractional_kelly_percent)}</div>
                </div>
            </div>

            <div class="badge-row">
                <div class="badge blue-bg">${safe(sample.label)}</div>
                <div class="badge">${safe(volatility.label)} volatility</div>
                <div class="badge">${safe(environment.label)} environment</div>
            </div>

            <div class="empty-state">
                ${safe(data.summary)}
                ${data.warnings?.length ? `<br><br>${data.warnings.map(w => `• ${safe(w)}`).join("<br>")}` : ""}
            </div>
        </div>
    `;
}


function renderOpportunityCards(items) {
    if (!items || items.length === 0) {
        return `<div class="empty-state">No top opportunities returned.</div>`;
    }

    return items.slice(0, 4).map(item => {
        return `
            <div class="row">
                <div class="row-top">
                    <div class="row-symbol">${safe(item.symbol)}</div>
                    <div class="row-score">${safe(item.score)}</div>
                </div>

                <div class="small">${safe(item.market_state)}</div>
                <div class="small">${safe(item.recommended_strategy)}</div>

                <div class="small">
                    RS vs SPY:
                    <span class="${getRsClass(item.relative_strength_vs_spy)}">
                        ${formatPercent(item.relative_strength_vs_spy)}
                    </span>
                </div>

                <div class="small">
                    Entry: ${formatCurrency(item.entry)}
                    |
                    Target: ${formatCurrency(item.target)}
                </div>
            </div>
        `;
    }).join("");
}

function renderRows(items) {
    if (!items || items.length === 0) {
        return `<div class="empty-state">No names returned for this section.</div>`;
    }

    return items.slice(0, 6).map(item => {
        return `
            <div class="row">
                <div class="row-top">
                    <div class="row-symbol">${safe(item.symbol)}</div>
                    <div class="row-score">${safe(item.score)}</div>
                </div>

                <div class="small">${safe(item.market_state)}</div>
                <div class="small">${safe(item.recommended_strategy)}</div>

                <div class="small">
                    RS vs SPY:
                    <span class="${getRsClass(item.relative_strength_vs_spy)}">
                        ${formatPercent(item.relative_strength_vs_spy)}
                    </span>
                </div>
            </div>
        `;
    }).join("");
}


function safe(value) {
    if (value === null || value === undefined || value === "") return "—";

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderReasonList(reasons) {
    if (!reasons || reasons.length === 0) {
        return `<div class="small">No strategy explanation returned yet.</div>`;
    }

    return reasons.map(r => `<div class="small">• ${safe(r)}</div>`).join("");
}

function renderMiniList(items) {
    if (!items || items.length === 0) {
        return `<div class="small">—</div>`;
    }

    return items.slice(0, 3).map(item => `<div class="small">• ${safe(item)}</div>`).join("");
}

function getRsClass(value) {
    const number = Number(value);
    if (number >= 1) return "green";
    if (number <= -1) return "red";
    return "yellow";
}

function getPnlClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "";
    if (number > 0) return "green";
    if (number < 0) return "red";
    return "yellow";
}

function getEnvironmentClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("unstable") || text.includes("avoid") || text.includes("high_risk")) {
        return "red-bg";
    }

    if (text.includes("watch") || text.includes("neutral") || text.includes("mixed")) {
        return "yellow-bg";
    }

    return "green-bg";
}

function getHealthClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("strong") || text.includes("stable")) return "green-bg";
    if (text.includes("mixed") || text.includes("elevated")) return "yellow-bg";
    if (text.includes("high risk")) return "red-bg";

    return "";
}

function getStabilityClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("highly stable") || text === "stable") return "green-bg";
    if (text.includes("moderately")) return "yellow-bg";
    if (text.includes("unstable")) return "red-bg";

    return "";
}

function getConcentrationClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("defensive")) return "blue";
    if (text.includes("very high") || text.includes("high")) return "red-bg";
    if (text.includes("elevated") || text.includes("moderate")) return "yellow-bg";

    return "green-bg";
}

function getDailyModeClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("aggressive")) return "green";
    if (text.includes("selective")) return "blue";
    if (text.includes("defensive")) return "yellow";
    if (text.includes("preservation")) return "red";
    return "blue";
}

function getPermissionClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("allowed") && !text.includes("avoid")) return "green-bg";
    if (text.includes("selective")) return "blue-bg";
    if (text.includes("restricted")) return "yellow-bg";
    if (text.includes("avoid")) return "red-bg";
    return "";
}

function getPressureClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("supportive")) return "green";
    if (text.includes("mixed")) return "yellow";
    if (text.includes("elevated")) return "yellow";
    if (text.includes("high")) return "red";
    return "blue";
}

function getPostureClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("stable")) return "green";
    if (text.includes("balanced")) return "blue";
    if (text.includes("mixed")) return "yellow";
    if (text.includes("fragile")) return "red";
    return "blue";
}

function getPriorityClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("urgent")) return "red-bg";
    if (text.includes("manage")) return "yellow-bg";
    if (text.includes("monitor")) return "";
    return "green-bg";
}

function getAllocationStatusClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("selective deployment")) return "green";
    if (text.includes("hold")) return "blue";
    if (text.includes("restricted")) return "yellow";
    if (text.includes("maintenance")) return "red";
    return "blue";
}

function getMarketBiasClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("supportive")) return "green-bg";
    if (text.includes("selective")) return "blue-bg";
    if (text.includes("cautious")) return "yellow-bg";
    if (text.includes("defensive")) return "red-bg";
    return "";
}

function getMarketBiasTextClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("supportive")) return "green";
    if (text.includes("selective")) return "blue";
    if (text.includes("cautious")) return "yellow";
    if (text.includes("defensive")) return "red";
    return "blue";
}

function getDecisionTextClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("add")) return "green";
    if (text.includes("trail") || text === "hold") return "blue";
    if (text.includes("do not add")) return "yellow";
    if (text.includes("reduce") || text.includes("exit")) return "red";
    return "blue";
}

function getPressureScoreClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "blue";
    if (number >= 70) return "red";
    if (number >= 45) return "yellow";
    return "green";
}

function getAddPermissionClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("selective")) return "green-bg";
    if (text.includes("pullback") || text.includes("wait")) return "blue-bg";
    if (text.includes("do not")) return "red-bg";
    return "";
}

function getReducePermissionClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("reduce") || text.includes("exit")) return "red-bg";
    if (text.includes("weakens") || text.includes("trim")) return "yellow-bg";
    if (text.includes("no reduce")) return "green-bg";
    return "";
}


function formatExpressionLabel(value) {
    if (value === null || value === undefined || value === "") return "—";

    return String(value)
        .replaceAll("_", " ")
        .replace(/\b\w/g, letter => letter.toUpperCase());
}

function formatScoreOutOf100(value) {
    if (value === null || value === undefined || value === "") return "—";

    const number = Number(value);
    if (Number.isNaN(number)) return safe(value);

    return `${Math.round(number)} / 100`;
}

function getDriverQualityLabel(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "Confirmation unavailable";

    if (number >= 80) return "Strong driver confirmation";
    if (number >= 65) return "Moderate confirmation";
    if (number >= 50) return "Mixed confirmation";
    if (number >= 35) return "Weak confirmation";
    return "Driver conflict";
}

function getDriverQualityTextClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "blue";

    if (number >= 80) return "green";
    if (number >= 65) return "blue";
    if (number >= 50) return "yellow";
    return "red";
}

function formatCurrency(value) {
    if (value === null || value === undefined || value === "") return "$—";

    const number = Number(value);
    if (Number.isNaN(number)) return "$—";

    const absoluteValue = Math.abs(number).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });

    return number < 0 ? `-$${absoluteValue}` : `$${absoluteValue}`;
}

function formatCurrencyOrDash(value) {
    if (value === null || value === undefined || value === "") return "$—";
    return formatCurrency(value);
}

function getOptionsConfidenceClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "yellow";
    if (number >= 75) return "green";
    if (number >= 55) return "yellow";
    return "red";
}

function getOptionsConfidenceBadgeClass(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return "yellow-bg";
    if (number >= 70) return "green-bg";
    if (number >= 45) return "yellow-bg";
    return "red-bg";
}

function getOptionsActionabilityClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("tradable")) return "green";
    if (text.includes("selective") || text.includes("caution")) return "yellow";
    if (text.includes("avoid")) return "red";
    return "blue";
}

function getIvClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("excessive")) return "red";
    if (text.includes("elevated")) return "yellow";
    if (text.includes("normal")) return "green";
    return "blue";
}

function getSpreadClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("excellent") || text.includes("good")) return "green";
    if (text.includes("acceptable")) return "yellow";
    if (text.includes("wide") || text.includes("poor")) return "red";
    return "blue";
}

function formatPercent(value) {
    if (value === null || value === undefined || value === "") return "—";

    const number = Number(value);
    if (Number.isNaN(number)) return "—";
    return `${number.toFixed(2)}%`;
}

function formatShares(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return safe(value);
    return Number.isInteger(number) ? String(number) : number.toFixed(4);
}

function updateRefreshStatus() {
    const now = new Date();

    document.getElementById("refreshStatus").textContent =
        `Last refreshed ${now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
}

loadDashboard();
