function renderDashboard(scanData, tradeLogData, portfolioData, portfolioAnalysisData, performanceData, dailyActionData, capitalAllocationData, marketDriverData, marketStatusData, tradeRecommendationData) {
    const top = scanData?.top_trade || null;
    const topTradeSection = top ? renderTopTradeAndRiskSection(top) : renderNoTradeWorkstationSection(scanData, tradeRecommendationData);

    document.getElementById("dashboard").innerHTML = `
        ${renderMarketStatusStrip(marketStatusData)}

        ${renderPreMarketCommandShell()}

        ${renderTradeRecommendationCard(tradeRecommendationData)}

        ${topTradeSection}

        ${top ? renderOptionsIntelligenceShell() : ""}

        ${renderSignalJournalShell()}

        ${renderMarketDriverImpact(marketDriverData)}

        ${renderDailyActionPlan(dailyActionData)}

        ${renderCapitalAllocationGuidance(capitalAllocationData)}

        <div class="card top-opportunities">
            <div class="section-title">Top Opportunities</div>
            <div class="section-subtitle">
                Highest-ranked setups after trend, momentum, liquidity, options pressure, regime, and RS vs SPY filters.
            </div>

            <div class="opportunity-grid">
                ${renderOpportunityCards(scanData?.trade_opportunities || [])}
            </div>
        </div>

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
    `;

    loadPreMarketCommandCenter();
    loadOptionsIntelligencePanel();
    loadSignalJournalPanel();
}


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
                    onclick="calculateRisk(${Number(top.entry)}, ${Number(top.stop_loss)}, '${safe(top.symbol)}')"
                >
                    Calculate Position Size
                </button>

                <div id="riskResults"></div>
            </div>
        </div>
    `;
}


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

async function calculateRisk(entry, stop, symbol = "") {
    try {
        const accountValue = document.getElementById("accountValue").value;
        const riskPercent = document.getElementById("riskPercent").value;

        const symbolParam = symbol ? `&symbol=${encodeURIComponent(symbol)}` : "";

        const data = await fetchJson(
            `${API_BASE}/risk-plan?account_value=${accountValue}&risk_percent=${riskPercent}&entry_price=${entry}&stop_price=${stop}${symbolParam}`
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

