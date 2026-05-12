function renderPortfolioAnalysis(data) {
    const accounts = data?.portfolio_analyses || [];

    if (!accounts.length) {
        return `
            <div class="card portfolio-section">
                <div class="section-title">Portfolio Intelligence</div>
                <div class="empty-state">
                    Portfolio analysis unavailable. Confirm /portfolio-analysis is running.
                </div>
            </div>
        `;
    }

    return `
        <div class="card portfolio-section">
            <div class="section-title">Portfolio Intelligence</div>
            <div class="section-subtitle">
                Account-level health, stability, concentration, defensive reserves, and speculative exposure.
            </div>

            <div class="portfolio-grid">
                ${accounts.map(renderAccountCard).join("")}
            </div>
        </div>
    `;
}

function renderAccountCard(account) {
    const healthClass = getHealthClass(account.portfolio_health_label);
    const stabilityClass = getStabilityClass(account.portfolio_stability_label);
    const concentrationClass = getConcentrationClass(account.concentration_label);


    return `
        <div class="portfolio-card">
            <div class="portfolio-card-top">
                <div>
                    <div class="account-name">${safe(account.account)}</div>
                    <div class="small">${formatCurrency(account.total_value)} total value</div>
                </div>

                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    <div class="badge ${stabilityClass}">
                        ${safe(account.portfolio_stability_label)}
                    </div>
                </div>
            </div>

            <div class="badge-row">
                <div class="badge ${healthClass}">
                    Health: ${safe(account.portfolio_health_label)}
                </div>

                <div class="badge ${concentrationClass}">
                    ${safe(account.concentration_label)}
                </div>
            </div>

            <div class="portfolio-score-row">
                <div class="mini-metric">
                    <div class="label">Health Score</div>

                    <div class="value ${healthClass.replace("-bg", "")}">
                        ${safe(account.portfolio_health_score)}
                    </div>
                </div>

                <div class="mini-metric">
                    <div class="label">Stability Score</div>

                    <div class="value ${stabilityClass.replace("-bg", "")}">
                        ${safe(account.portfolio_stability_score)}
                    </div>
                </div>
            </div>

            <div class="metric-grid three">
                <div class="metric">
                    <div class="label">Defensive</div>
                    <div class="value blue">
                        ${formatPercent(account.bucket_percents?.defensive)}
                    </div>
                </div>

                <div class="metric">
                    <div class="label">Speculative</div>
                    <div class="value yellow">
                        ${formatPercent(account.bucket_percents?.speculative)}
                    </div>
                </div>

                <div class="metric">
                    <div class="label">Largest</div>

                    <div class="value">
                        ${safe(account.largest_position?.symbol)}
                    </div>

                    <div class="small">
                        ${formatPercent(account.largest_position?.percent)}
                    </div>
                </div>
            </div>

            <div class="driver-box">
                <strong class="green">Stability Drivers</strong>
                ${renderMiniList(account.stability_drivers)}
            </div>

            <div class="driver-box">
                <strong class="red">Instability Drivers</strong>
                ${renderMiniList(account.instability_drivers)}
            </div>

            <div class="driver-box">
                <strong class="yellow">Warnings</strong>
                ${renderMiniList(account.warnings)}
            </div>
        </div>
    `;
}

function renderOpenPositions(tradeLogData, portfolioData, portfolioAnalysisData) {
    const portfolioPositions = normalizeArray(portfolioData?.open_positions || portfolioData?.positions);
    const loggedTrades = normalizeTradeLog(tradeLogData);

    const openItems = portfolioPositions.length > 0
        ? portfolioPositions
        : loggedTrades.filter(t => isOpenTrade(t));

    if (openItems.length === 0) {
        return `<div class="empty-state">No open positions found yet.</div>`;
    }

    const openPL = portfolioData?.open_pl;
    const openPLPercent = portfolioData?.open_pl_percent;
    const marketValue = portfolioData?.market_value;
    const openBasis = portfolioData?.open_basis;

    const analysisByAccount = buildAnalysisByAccount(portfolioAnalysisData);
    const grouped = groupPositionsByAccount(openItems);

    return `
        <div class="metric-grid three">
            <div class="metric">
                <div class="label">Open P/L</div>
                <div class="value ${getPnlClass(openPL)}">${formatCurrencyOrDash(openPL)}</div>
            </div>

            <div class="metric">
                <div class="label">Open P/L %</div>
                <div class="value ${getPnlClass(openPLPercent)}">${formatPercent(openPLPercent)}</div>
            </div>

            <div class="metric">
                <div class="label">Market Value</div>
                <div class="value">${formatCurrencyOrDash(marketValue)}</div>
            </div>
        </div>

        <div class="small" style="margin-bottom: 12px;">
            Cost basis tracked: ${formatCurrencyOrDash(openBasis)}
        </div>

        <div class="list">
            ${Object.entries(grouped).map(([accountName, items]) => {
                const analysis = analysisByAccount[accountName] || null;
                return renderAccountPositionGroup(accountName, items, analysis);
            }).join("")}
        </div>
    `;
}

function renderAccountPositionGroup(accountName, items, analysis) {
    const stats = calculateAccountPositionStats(items);
    const recommendationLabel = analysis?.account_recommendation_label;
    const recommendation = analysis?.account_recommendation;
    const recommendationReason = analysis?.account_recommendation_reason;

    return `
        <div class="account-position-group">
            <div class="account-position-header">
                <div>
                    <div class="account-position-title-row">
                        <div class="account-position-title">${safe(accountName)}</div>
                        ${recommendationLabel ? `<div class="badge ${getRecommendationClass(recommendationLabel)}">${safe(recommendationLabel)}</div>` : ""}
                    </div>

                    <div class="account-position-summary">
                        ${items.length} open position${items.length === 1 ? "" : "s"}
                        ${analysis?.portfolio_stability_label ? ` • ${safe(analysis.portfolio_stability_label)} stability` : ""}
                        ${analysis?.concentration_label ? ` • ${safe(analysis.concentration_label)}` : ""}
                    </div>
                </div>

                <div class="account-position-metrics">
                    <div class="account-position-metric">
                        <div class="label">Value</div>
                        <div class="value">${formatCurrencyOrDash(stats.marketValue)}</div>
                    </div>

                    <div class="account-position-metric">
                        <div class="label">Open P/L</div>
                        <div class="value ${getPnlClass(stats.openPL)}">${formatCurrencyOrDash(stats.openPL)}</div>
                    </div>

                    <div class="account-position-metric">
                        <div class="label">Open P/L %</div>
                        <div class="value ${getPnlClass(stats.openPLPercent)}">${formatPercent(stats.openPLPercent)}</div>
                    </div>
                </div>
            </div>

            ${recommendation ? `
                <div class="recommendation-box">
                    <strong>Account Recommendation</strong>
                    <div class="small">
                        <span class="${getRecommendationTextClass(recommendationLabel)}">${safe(recommendation)}</span>
                        ${recommendationReason ? ` — ${safe(recommendationReason)}` : ""}
                    </div>
                </div>
            ` : ""}

            <div class="table-wrap">
                <table class="table grouped">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Qty</th>
                            <th>Cost</th>
                            <th>Current</th>
                            <th>Value</th>
                            <th>P/L</th>
                            <th>P/L %</th>
                            <th>Guidance</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map(item => {
                            const pnl = getFirstValue(item, ["unrealized_pl", "unrealized_p_l", "p_l", "pl", "unrealized"]);
                            const pnlPercent = getFirstValue(item, ["unrealized_pl_percent", "p_l_percent", "pl_percent"]);

                            return `
                                <tr>
                                    <td><strong>${safe(item.symbol)}</strong></td>
                                    <td>${formatShares(getFirstValue(item, ["shares", "quantity", "qty"], "—"))}</td>
                                    <td>${formatCurrency(getFirstValue(item, ["cost_basis", "entry", "price", "buy_price"]))}</td>
                                    <td>${formatCurrencyOrDash(getFirstValue(item, ["current_price", "current", "last_price"]))}</td>
                                    <td>${formatCurrencyOrDash(getFirstValue(item, ["market_value", "position_value", "value"]))}</td>
                                    <td class="${getPnlClass(pnl)}">${formatCurrencyOrDash(pnl)}</td>
                                    <td class="${getPnlClass(pnlPercent)}">${formatPercent(pnlPercent)}</td>
                                    <td>${safe(getPositionGuidance(item, pnl))}</td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function buildAnalysisByAccount(portfolioAnalysisData) {
    const accounts = portfolioAnalysisData?.portfolio_analyses || [];
    const map = {};

    accounts.forEach(account => {
        if (account.account) {
            map[account.account] = account;
        }
    });

    return map;
}

function groupPositionsByAccount(items) {
    const grouped = {};

    items.forEach(item => {
        const accountName = getFirstValue(item, ["account", "account_type"], "Uncategorized");

        if (!grouped[accountName]) {
            grouped[accountName] = [];
        }

        grouped[accountName].push(item);
    });

    return Object.fromEntries(
        Object.entries(grouped).sort(([accountA], [accountB]) => {
            const orderA = getAccountSortRank(accountA);
            const orderB = getAccountSortRank(accountB);

            if (orderA !== orderB) {
                return orderA - orderB;
            }

            return accountA.localeCompare(accountB);
        })
    );
}

function getAccountSortRank(accountName) {
    const text = String(accountName || "").toLowerCase();

    if (text.includes("ira 823")) return 1;
    if (text.includes("roth")) return 2;
    if (text.includes("individual")) return 3;
    if (text.includes("hsa")) return 4;
    if (text.includes("paper")) return 5;

    return 9;
}

function calculateAccountPositionStats(items) {
    let marketValue = 0;
    let openPL = 0;
    let basis = 0;

    items.forEach(item => {
        const value = Number(getFirstValue(item, ["market_value", "position_value", "value"], 0));
        const pnl = Number(getFirstValue(item, ["unrealized_pl", "unrealized_p_l", "p_l", "pl", "unrealized"], 0));
        const totalBasis = Number(getFirstValue(item, ["total_basis", "cost_basis_total"], null));
        const shares = Math.abs(Number(getFirstValue(item, ["shares", "quantity", "qty"], 0)));
        const cost = Number(getFirstValue(item, ["cost_basis", "entry", "price", "buy_price"], 0));

        if (!Number.isNaN(value)) {
            marketValue += value;
        }

        if (!Number.isNaN(pnl)) {
            openPL += pnl;
        }

        if (totalBasis !== null && !Number.isNaN(totalBasis)) {
            basis += Math.abs(totalBasis);
        } else if (!Number.isNaN(shares) && !Number.isNaN(cost)) {
            basis += shares * cost;
        }
    });

    const openPLPercent = basis ? (openPL / basis) * 100 : 0;

    return {
        marketValue,
        openPL,
        openPLPercent,
        basis,
    };
}

function getAccountModeFromPositions(items, analysis) {
    if (analysis?.portfolio_mode) {
        return analysis.portfolio_mode;
    }

    for (const item of items) {
        if (item.portfolio_mode) {
            return item.portfolio_mode;
        }
    }

    return "real";
}

function renderModeBadge(mode) {
    return "";
}

function getRecommendationClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("reduce") || text.includes("avoid") || text.includes("raise")) {
        return "red-bg";
    }

    if (text.includes("monitor") || text.includes("rebalance")) {
        return "yellow-bg";
    }

    return "green-bg";
}

function getRecommendationTextClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("reduce") || text.includes("avoid") || text.includes("raise")) {
        return "red";
    }

    if (text.includes("monitor") || text.includes("rebalance")) {
        return "yellow";
    }

    return "green";
}

function renderClosedTrades(tradeLogData, performanceData) {
    const loggedTrades = normalizeTradeLog(tradeLogData);
    const closedItems = loggedTrades.filter(t => isClosedTrade(t));

    let totalRealized = getFirstValue(
        performanceData || {},
        ["total_realized_pl", "realized_pl", "total_pl", "total_p_l"],
        null
    );

    const calculatedRealized = closedItems.reduce((sum, trade) => {
        const pnl = Number(getFirstValue(trade, ["realized_pl", "realized_p_l", "p_l", "pl"], 0));
        return Number.isNaN(pnl) ? sum : sum + pnl;
    }, 0);

    if (totalRealized === null || Number(totalRealized) === 0) {
        totalRealized = calculatedRealized;
    }

    if (closedItems.length === 0 && totalRealized === null) {
        return `<div class="empty-state">No closed trades found yet.</div>`;
    }

    return `
        <div class="metric-grid two">
            <div class="metric">
                <div class="label">Realized P/L</div>
                <div class="value ${getPnlClass(totalRealized)}">${formatCurrencyOrDash(totalRealized)}</div>
            </div>

            <div class="metric">
                <div class="label">Closed Trades</div>
                <div class="value">${closedItems.length}</div>
            </div>
        </div>

        ${closedItems.length > 0 ? `
            <div class="table-wrap">
                <table class="table compact">
                    <thead>
                        <tr>
                            <th>Account</th>
                            <th>Symbol</th>
                            <th>Exit</th>
                            <th>Realized P/L</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${closedItems.map(item => {
                            const pnl = getFirstValue(item, ["realized_pl", "realized_p_l", "p_l", "pl"]);
                            return `
                                <tr>
                                    <td>${safe(getFirstValue(item, ["account", "account_type"], "—"))}</td>
                                    <td><strong>${safe(item.symbol)}</strong></td>
                                    <td>${formatCurrency(getFirstValue(item, ["sale_price", "sell_price", "exit_price", "exit", "price"]))}</td>
                                    <td class="${getPnlClass(pnl)}">${formatCurrencyOrDash(pnl)}</td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        ` : ""}
    `;
}

function normalizeTradeLog(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.trades)) return data.trades;
    if (Array.isArray(data.trade_log)) return data.trade_log;

    if (Array.isArray(data.open_trades) || Array.isArray(data.closed_trades)) {
        return [
            ...(data.open_trades || []),
            ...(data.closed_trades || [])
        ];
    }

    return [];
}

function normalizeArray(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    return [];
}

function isOpenTrade(trade) {
    const status = String(getFirstValue(trade, ["status", "trade_status"], "")).toLowerCase();
    const action = String(getFirstValue(trade, ["action"], "")).toLowerCase();

    if (status.includes("open")) return true;
    if (status.includes("closed")) return false;
    if (action.includes("buy") && !action.includes("sell")) return true;

    return false;
}

function isClosedTrade(trade) {
    const status = String(getFirstValue(trade, ["status", "trade_status"], "")).toLowerCase();
    const action = String(getFirstValue(trade, ["action"], "")).toLowerCase();
    const realized = getFirstValue(trade, ["realized_pl", "realized_p_l", "p_l", "pl"], null);

    if (status.includes("closed")) return true;
    if (action.includes("sell")) return true;
    if (realized !== null && realized !== undefined) return true;

    return false;
}

function getPositionGuidance(item, pnl) {
    const guidance = getFirstValue(item, ["guidance", "position_guidance", "recommendation"]);

    if (guidance) return guidance;

    const pnlNumber = Number(pnl);

    if (!Number.isNaN(pnlNumber)) {
        if (pnlNumber > 0) return "hold_position / monitor target";
        if (pnlNumber < 0) return "review stop / avoid adding";
    }

    return "hold_position / monitor setup";
}

function getFirstValue(object, keys, fallback = null) {
    if (!object) return fallback;

    for (const key of keys) {
        if (object[key] !== undefined && object[key] !== null && object[key] !== "") {
            return object[key];
        }
    }

    return fallback;
}
