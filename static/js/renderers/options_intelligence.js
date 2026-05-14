// TradeLayer Options Intelligence Renderer
// Extracted from dashboard.js to keep options structure analysis UI modular.

function renderOptionsIntelligenceShell() {
    return `
        <div class="card daily-action-card">
            <div id="optionsIntelligencePanel">
                <div class="why-box">
                    <div class="section-title">Options Intelligence</div>
                    <div class="section-subtitle">
                        Loading account-aware options structure analysis.
                    </div>
                    <div class="empty-state">Fetching /options-intelligence...</div>
                </div>
            </div>
        </div>
    `;
}

function renderNoTradeWorkstationSection(scanData, tradeRecommendationData) {
    const watchlist = scanData?.watchlist || [];
    const avoid = scanData?.avoid || [];
    const market = tradeRecommendationData?.market_context || {};
    const topWatch = watchlist.slice(0, 4);

    return `
        <div class="card daily-action-card">
            <div class="section-title">No Actionable Trade Today</div>
            <div class="section-subtitle">
                TradeLayer did not find a setup strong enough for new capital deployment. The workstation remains active for market context, watchlist review, and position management.
            </div>

            <div class="action-plan-grid">
                <div class="metric">
                    <div class="label">Preferred Action</div>
                    <div class="value yellow">Stay in Cash</div>
                    <div class="small">Preserve capital until confirmation improves.</div>
                </div>

                <div class="metric">
                    <div class="label">Market Regime</div>
                    <div class="value blue" style="font-size:17px;">${safe(market.market_regime)}</div>
                    <div class="small">Risk appetite: ${safe(market.risk_appetite)}</div>
                </div>

                <div class="metric">
                    <div class="label">Watchlist Candidates</div>
                    <div class="value">${safe(watchlist.length)}</div>
                    <div class="small">Close, but not actionable yet.</div>
                </div>

                <div class="metric">
                    <div class="label">Avoid / Weak</div>
                    <div class="value red">${safe(avoid.length)}</div>
                    <div class="small">Failed confirmation or risk filters.</div>
                </div>
            </div>

            <div id="optionsIntelligencePanel">
                <div class="why-box">
                    <div class="section-title">Options Intelligence</div>
                    <div class="section-subtitle">
                        Loading account-aware options structure analysis.
                    </div>
                    <div class="empty-state">Fetching /options-intelligence...</div>
                </div>
            </div>

            <div class="why-box">
                <div class="section-title">Closest Watchlist Setups</div>
                <div class="opportunity-grid">
                    ${topWatch.length ? renderOpportunityCards(topWatch) : `<div class="empty-state">No watchlist candidates returned.</div>`}
                </div>
            </div>
        </div>
    `;
}

async function loadOptionsIntelligencePanel() {
    const panel = document.getElementById("optionsIntelligencePanel");

    if (!panel) {
        return;
    }

    try {
        const data = await fetchJson(`${API_BASE}/options-intelligence`);
        panel.innerHTML = renderOptionsIntelligencePanel(data);
    } catch (error) {
        console.error("Options intelligence unavailable:", error);

        panel.innerHTML = `
            <div class="why-box">
                <div class="section-title">Options Intelligence</div>
                <div class="section-subtitle">
                    Account-aware options structure analysis.
                </div>
                <div class="empty-state">
                    Options intelligence unavailable. Confirm /options-intelligence is running.
                </div>
            </div>
        `;
    }
}

function renderOptionsIntelligencePanel(data) {
    if (!data || data.status !== "ok") {
        return `
            <div class="why-box">
                <div class="section-title">Options Intelligence</div>
                <div class="section-subtitle">
                    Account-aware options structure analysis.
                </div>
                <div class="empty-state">
                    Options intelligence did not return a valid response.
                </div>
            </div>
        `;
    }

    const individual = data.accounts?.individual_556 || {};
    const roth = data.accounts?.roth_account || {};
    const individualBest = individual.best_candidate || null;
    const rothBest = roth.best_candidate || null;

    return `
        <div class="why-box">
            <div class="section-title">Options Intelligence</div>
            <div class="section-subtitle">
                Structure-aware options analysis filtered through account survivability and defined-risk rules.
            </div>

            <div class="action-plan-grid">
                <div class="metric">
                    <div class="label">Setup</div>
                    <div class="value blue">${safe(data.symbol)}</div>
                    <div class="small">${safe(data.directional_bias)} · ${safe(data.setup_source)}</div>
                </div>

                <div class="metric">
                    <div class="label">Market Context</div>
                    <div class="value blue" style="font-size:17px;">${safe(data.market_context?.market_regime)}</div>
                    <div class="small">Risk appetite: ${safe(data.market_context?.risk_appetite)}</div>
                </div>

                <div class="metric">
                    <div class="label">Individual 556</div>
                    <div class="value ${individualBest ? "yellow" : "red"}">${individualBest ? safe(individualBest.affordability_label) : "NO FIT"}</div>
                    <div class="small">${individualBest ? safe(individualBest.strategy) : "No acceptable structure"}</div>
                </div>

                <div class="metric">
                    <div class="label">Roth 705</div>
                    <div class="value ${rothBest ? "yellow" : "red"}">${rothBest ? safe(rothBest.affordability_label) : "NO FIT"}</div>
                    <div class="small">${rothBest ? safe(rothBest.strategy) : "No acceptable structure"}</div>
                </div>
            </div>

            ${renderOptionsQualitySection(data.options_quality, data.execution_quality, data.structure_quality)}

            <div class="position-action-grid" style="margin-top:16px;">
                ${renderOptionsAccountCard("Individual 556", individual)}
                ${renderOptionsAccountCard("Roth 705", roth)}
            </div>

            <div class="small" style="margin-top:14px;">
                ${safe(data.risk_note)}
            </div>
        </div>
    `;
}

function renderOptionsQualitySection(optionsQuality, executionQuality, structureQuality) {
    const quality = optionsQuality || {};
    const execution = executionQuality || {};
    const structure = structureQuality || quality.structure_bias || {};
    const metrics = quality.quality_metrics || {};
    const calls = quality.calls || {};
    const puts = quality.puts || {};
    const avoidReasons = execution.avoid_reasons || quality.avoid_reasons || [];

    const confidence = execution.options_confidence ?? quality.options_confidence;
    const confidenceClass = getOptionsConfidenceClass(confidence);
    const actionabilityClass = getOptionsActionabilityClass(execution.actionability || quality.actionability);

    return `
        <div class="why-box" style="margin-top:16px;">
            <div class="section-title">Execution Quality Layer</div>
            <div class="section-subtitle">
                IV, liquidity, bid/ask spread, open interest, and near-the-money contract quality. Source: ${safe(quality.data_source || "yfinance_fallback")}.
            </div>

            <div class="action-plan-grid">
                <div class="metric">
                    <div class="label">Options Confidence</div>
                    <div class="value ${confidenceClass}">${safe(confidence)} / 100</div>
                    <div class="small">${safe(execution.quality_label || quality.quality_label)}</div>
                </div>

                <div class="metric">
                    <div class="label">Actionability</div>
                    <div class="value ${actionabilityClass}">${safe(execution.actionability || quality.actionability)}</div>
                    <div class="small">${safe(metrics.tradable_contracts)} tradable / ${safe(metrics.contracts_reviewed)} reviewed</div>
                </div>

                <div class="metric">
                    <div class="label">Preferred Structure</div>
                    <div class="value blue" style="font-size:17px;">${safe(structure.preferred_structure)}</div>
                    <div class="small">Quality: ${safe(structure.structure_quality)}</div>
                </div>

                <div class="metric">
                    <div class="label">Expiration Used</div>
                    <div class="value">${safe(quality.expiration_used)}</div>
                    <div class="small">Avg liquidity: ${safe(metrics.average_liquidity_score)}</div>
                </div>
            </div>

            <div class="position-action-grid" style="margin-top:14px;">
                ${renderOptionsSideQualityCard("Calls", calls)}
                ${renderOptionsSideQualityCard("Puts", puts)}
            </div>

            <div class="empty-state" style="margin-top:14px;">
                ${safe(execution.summary || quality.summary)}
                <br><br>
                <strong>Structure logic:</strong> ${safe(structure.reason)}
                ${avoidReasons.length ? `<br><br><strong>Avoid reasons:</strong><br>${avoidReasons.map(item => `• ${safe(item)}`).join("<br>")}` : ""}
            </div>
        </div>
    `;
}

function renderOptionsSideQualityCard(label, sideData) {
    const best = sideData?.best_contract || {};

    return `
        <div class="position-action-card">
            <div class="position-action-top">
                <div>
                    <div class="action-symbol">${safe(label)}</div>
                    <div class="small">Tradable: ${safe(sideData?.tradable_count)} / ${safe(sideData?.count)}</div>
                </div>
                <div class="badge ${getOptionsConfidenceBadgeClass(sideData?.average_liquidity_score)}">Liquidity ${safe(sideData?.average_liquidity_score)}</div>
            </div>

            <div class="metric-grid two" style="margin-bottom:10px;">
                <div class="mini-metric">
                    <div class="label">Best Strike</div>
                    <div class="value blue">${formatCurrencyOrDash(best.strike)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">IV</div>
                    <div class="value ${getIvClass(best.iv_regime)}">${formatPercent(best.implied_volatility_percent)}</div>
                    <div class="small">${safe(best.iv_regime)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Spread</div>
                    <div class="value ${getSpreadClass(best.spread_quality)}">${formatPercent(best.bid_ask_spread_percent)}</div>
                    <div class="small">${safe(best.spread_quality)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Volume / OI</div>
                    <div class="value">${safe(best.volume)} / ${safe(best.open_interest)}</div>
                    <div class="small">${safe(best.liquidity_label)}</div>
                </div>
            </div>

            <div class="small">
                Best contract: ${safe(best.contract_symbol)}
            </div>
        </div>
    `;
}

function renderOptionsAccountCard(accountLabel, accountData) {
    const best = accountData?.best_candidate || null;
    const candidates = accountData?.candidates || [];

    if (!best) {
        return `
            <div class="position-action-card">
                <div class="position-action-top">
                    <div>
                        <div class="action-symbol">${safe(accountLabel)}</div>
                        <div class="small">Account value: ${formatCurrency(accountData?.account_size)}</div>
                    </div>
                    <div class="badge red-bg">NO FIT</div>
                </div>

                <div class="empty-state">
                    No acceptable options structure passed survivability rules for this account size.
                </div>

                <div class="small" style="margin-top:10px;">
                    ${candidates.length ? "Rejected structures: " + candidates.map(item => `${safe(item.strategy)} (${safe(item.affordability_label)})`).join(", ") : "No candidates returned."}
                </div>
            </div>
        `;
    }

    return `
        <div class="position-action-card">
            <div class="position-action-top">
                <div>
                    <div class="action-symbol">${safe(accountLabel)}</div>
                    <div class="small">Account value: ${formatCurrency(accountData.account_size)}</div>
                </div>
                <div class="badge ${best.affordability_label === "AFFORDABLE" ? "green-bg" : "yellow-bg"}">${safe(best.affordability_label)}</div>
            </div>

            <div class="decision-main blue">${formatExpressionLabel(best.strategy)}</div>

            <div class="metric-grid two" style="margin-bottom:10px;">
                <div class="mini-metric">
                    <div class="label">Max Risk</div>
                    <div class="value red">${formatCurrency(best.max_risk)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Max Reward</div>
                    <div class="value green">${formatCurrency(best.max_reward)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">Risk %</div>
                    <div class="value yellow">${formatPercent(best.risk_percent_of_account)}</div>
                </div>

                <div class="mini-metric">
                    <div class="label">R/R</div>
                    <div class="value">${safe(best.reward_risk_ratio)}</div>
                </div>
            </div>

            <div class="action-text">${safe(best.trade_summary)}</div>
            <div class="small">${safe(best.account_fit)}</div>
        </div>
    `;
}
