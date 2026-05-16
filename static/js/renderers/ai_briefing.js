// TradeLayer AI Briefing Renderer

function renderAiBriefingShell() {
    return `
        <div id="aiBriefingPanel" class="card ai-briefing-card">
            <div class="section-title">AI TradeLayer Briefing</div>
            <div class="section-subtitle">
                Plain-English interpretation of market state, trade setup, risk controls, and performance context.
            </div>
            <div class="empty-state">Fetching /ai-briefing...</div>
        </div>
    `;
}

async function loadAiBriefingPanel() {
    const panel = document.getElementById("aiBriefingPanel");

    if (!panel) {
        return;
    }

    try {
        const data = await fetchJson(`${API_BASE}/ai-briefing`);
        panel.outerHTML = renderAiBriefingPanel(data);
    } catch (error) {
        console.error("AI briefing unavailable:", error);

        panel.innerHTML = `
            <div class="section-title">AI TradeLayer Briefing</div>
            <div class="section-subtitle">
                AI interpretation unavailable. Confirm /ai-briefing is running.
            </div>
            <div class="empty-state">Unable to load AI briefing.</div>
        `;
    }
}

function renderAiBriefingPanel(data) {
    if (!data) {
        return `
            <div class="card ai-briefing-card">
                <div class="section-title">AI TradeLayer Briefing</div>
                <div class="empty-state">No AI briefing returned.</div>
            </div>
        `;
    }

    const statusClass = getAiBriefingStatusClass(data.trade_status || data.status);
    const conflicts = Array.isArray(data.key_conflicts) ? data.key_conflicts : [];

    return `
        <div class="card ai-briefing-card">
            <div class="ai-briefing-hero">
                <div class="ai-briefing-main">
                    <div class="daily-mode-label">AI Interpretation</div>
                    <div class="ai-briefing-status ${statusClass}">${safe(data.trade_status || data.status)}</div>
                    <div class="ai-briefing-text">${safe(data.briefing)}</div>

                    <div class="badge-row">
                        <div class="badge blue-bg">${safe(data.provider)}</div>
                        <div class="badge">${safe(data.engine)}</div>
                    </div>
                </div>

                <div class="ai-briefing-side">
                    <div class="section-title">Risk Note</div>
                    <div class="empty-state">${safe(data.risk_note)}</div>

                    <div class="section-title" style="margin-top:14px;">Next Action</div>
                    <div class="empty-state">${safe(data.next_action)}</div>
                </div>
            </div>

            ${conflicts.length ? `
                <div class="why-box">
                    <div class="section-title">Key Conflicts / Caution Flags</div>
                    ${conflicts.map(item => `<div class="small">• ${safe(item)}</div>`).join("")}
                </div>
            ` : ""}

            <div class="small" style="margin-top:14px;">
                ${safe(data.disclaimer)}
            </div>
        </div>
    `;
}

function getAiBriefingStatusClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("risk-on") || text.includes("allowed") || text.includes("supportive")) return "green";
    if (text.includes("selective") || text.includes("wait")) return "blue";
    if (text.includes("defensive") || text.includes("avoid") || text.includes("manage")) return "yellow";

    return "blue";
}
