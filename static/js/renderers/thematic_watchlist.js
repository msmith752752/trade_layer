// TradeLayer Thematic Watchlist Renderer
// Displays thematic stock groups (e.g. Energy Supply Shock) with live scanner scores.

function renderThematicWatchlistShell() {
    return `
        <div id="thematicWatchlistPanel" class="card thematic-watchlist-card">
            <div class="section-title">Thematic Watchlists</div>
            <div class="section-subtitle">
                Curated stock groups from high-conviction research themes, scored daily by TradeLayer.
            </div>
            <div class="empty-state">Fetching thematic watchlist data...</div>
        </div>
    `;
}

async function loadThematicWatchlistPanel(scanData) {
    const panel = document.getElementById("thematicWatchlistPanel");
    if (!panel) return;

    try {
        const watchlistMeta = await fetchJson(`${API_BASE}/thematic-watchlists`);
        panel.outerHTML = renderThematicWatchlistPanel(watchlistMeta, scanData);
    } catch (error) {
        console.error("Thematic watchlist unavailable:", error);
        panel.innerHTML = `
            <div class="section-title">Thematic Watchlists</div>
            <div class="empty-state">Thematic watchlist unavailable. Confirm /thematic-watchlists is running.</div>
        `;
    }
}

function renderThematicWatchlistPanel(watchlistMeta, scanData) {
    if (!watchlistMeta || !watchlistMeta.watchlists) {
        return `
            <div class="card thematic-watchlist-card">
                <div class="section-title">Thematic Watchlists</div>
                <div class="empty-state">No thematic watchlists returned.</div>
            </div>
        `;
    }

    const watchlists = watchlistMeta.watchlists;
    const allSignals = getAllSignals(scanData);

    const sections = Object.entries(watchlists).map(([key, meta]) => {
        return renderThematicGroup(key, meta, allSignals);
    }).join("");

    return `
        <div class="card thematic-watchlist-card">
            <div class="section-title">Thematic Watchlists</div>
            <div class="section-subtitle">
                Curated stock groups from high-conviction research themes, scored daily by TradeLayer.
            </div>
            ${sections}
        </div>
    `;
}

function renderThematicGroup(key, meta, allSignals) {
    const label = meta.label || key;
    const source = meta.source || "";
    const symbols = meta.symbols || [];

    // Match each symbol to its live scan signal
    const matched = symbols.map(sym => {
        const signal = allSignals.find(s => s.symbol === sym) || null;
        return { symbol: sym, signal };
    });

    // Summary stats
    const actionable = matched.filter(m => m.signal?.action_label === "ACTIONABLE TODAY").length;
    const watching = matched.filter(m => m.signal?.action_label === "WAIT FOR CONFIRMATION").length;
    const noTrade = matched.filter(m => m.signal?.action_label === "NO TRADE").length;
    const notScanned = matched.filter(m => !m.signal).length;

    const topSignal = matched
        .filter(m => m.signal)
        .sort((a, b) => (b.signal.score || 0) - (a.signal.score || 0))[0];

    return `
        <div class="thematic-group">
            <div class="thematic-group-header">
                <div>
                    <div class="thematic-group-title">${safe(label)}</div>
                    <div class="small" style="margin-top:2px;">Source: ${safe(source)} · ${symbols.length} stocks tracked</div>
                </div>
                <div class="badge-row">
                    <div class="badge green-bg">${actionable} Actionable</div>
                    <div class="badge blue-bg">${watching} Watching</div>
                    <div class="badge red-bg">${noTrade} No Trade</div>
                    ${notScanned ? `<div class="badge">${notScanned} Not Scanned</div>` : ""}
                </div>
            </div>

            ${topSignal ? `
                <div class="thematic-top-pick">
                    <div class="daily-mode-label">Top Pick Today</div>
                    <div class="thematic-top-symbol">${safe(topSignal.symbol)}</div>
                    <div class="badge-row">
                        <div class="badge ${getActionLabelClass(topSignal.signal.action_label)}">${safe(topSignal.signal.action_label)}</div>
                        <div class="badge">Score: ${safe(topSignal.signal.score)}</div>
                        <div class="badge">${safe(topSignal.signal.recommended_strategy?.replaceAll("_", " "))}</div>
                    </div>
                    <div class="small" style="margin-top:6px;">${safe(topSignal.signal.action_reason)}</div>
                </div>
            ` : `<div class="empty-state">No signals returned for this group yet.</div>`}

            <div class="thematic-symbol-grid">
                ${matched.map(m => renderThematicSymbolCard(m.symbol, m.signal)).join("")}
            </div>
        </div>
    `;
}

function renderThematicSymbolCard(symbol, signal) {
    if (!signal) {
        return `
            <div class="thematic-symbol-card faded">
                <div class="thematic-symbol-name">${safe(symbol)}</div>
                <div class="small">Not yet scanned</div>
            </div>
        `;
    }

    const actionClass = getActionLabelClass(signal.action_label);
    const changeClass = Number(signal.daily_change_pct || 0) >= 0 ? "green" : "red";

    return `
        <div class="thematic-symbol-card">
            <div class="thematic-symbol-top">
                <div class="thematic-symbol-name">${safe(symbol)}</div>
                <div class="badge ${actionClass}" style="font-size:10px;">${safe(signal.action_label)}</div>
            </div>

            <div class="thematic-symbol-price">${formatCurrency(signal.entry)}</div>
            <div class="small ${changeClass}">${formatSignedPercent(signal.daily_change_pct)}</div>

            <div class="thematic-symbol-metrics">
                <div class="mini-metric">
                    <div class="label">Score</div>
                    <div class="value">${safe(signal.score)}</div>
                </div>
                <div class="mini-metric">
                    <div class="label">Options</div>
                    <div class="value ${getOptionsPressureClass(signal.options_pressure)}">${safe(signal.options_pressure?.replace("_", " "))}</div>
                </div>
            </div>

            <div class="small" style="margin-top:6px;">${safe(signal.market_state?.replace("_", " "))}</div>
        </div>
    `;
}

// ─── Helpers ─────────────────────────────────────────────

function getAllSignals(scanData) {
    if (!scanData) return [];
    return [
        ...(scanData.trade_opportunities || []),
        ...(scanData.watchlist || []),
        ...(scanData.avoid || []),
    ];
}

function getActionLabelClass(label) {
    const text = String(label || "").toLowerCase();
    if (text.includes("actionable")) return "green-bg";
    if (text.includes("wait") || text.includes("confirmation")) return "blue-bg";
    if (text.includes("pullback")) return "yellow-bg";
    return "red-bg";
}

function getOptionsPressureClass(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("strong_bullish") || text.includes("bullish")) return "green";
    if (text.includes("strong_bearish") || text.includes("bearish")) return "red";
    return "yellow";
}
