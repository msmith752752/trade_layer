const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
    ? "http://127.0.0.1:8000"
    : "http://" + window.location.hostname + ":8001";

async function loadDashboard() {
    try {
        const scanData = await fetchJson(`${API_BASE}/trade-scan`);
        const tradeLogData = await fetchJson(`${API_BASE}/trade-log`, { optional: true });
        const portfolioData = await fetchJson(`${API_BASE}/portfolio`, { optional: true });
        const portfolioAnalysisData = await fetchJson(`${API_BASE}/portfolio-analysis`, { optional: true });
        const performanceData = await fetchJson(`${API_BASE}/performance`, { optional: true });
        const dailyActionData = await fetchJson(`${API_BASE}/daily-action-plan`, { optional: true });
        const capitalAllocationData = await fetchJson(`${API_BASE}/capital-allocation-guidance`, { optional: true });
        const marketDriverData = await fetchJson(`${API_BASE}/market-driver-impact`, { optional: true });
        const marketStatusData = await fetchJson(`${API_BASE}/market-status-strip`, { optional: true });
        const tradeRecommendationData = await fetchJson(`${API_BASE}/trade-recommendations`, { optional: true });

        renderDashboard(
            scanData,
            tradeLogData,
            portfolioData,
            portfolioAnalysisData,
            performanceData,
            dailyActionData,
            capitalAllocationData,
            marketDriverData,
            marketStatusData,
            tradeRecommendationData
        );

        const top = scanData?.top_trade;
        if (top?.entry && top?.stop_loss && top?.symbol) {
            calculateRisk(top.entry, top.stop_loss, top.symbol);
        }

        updateRefreshStatus();

    } catch (error) {
        console.error(error);
        document.getElementById("dashboard").innerHTML = `
            <div class="card">
                <div class="section-title">Unable to load TradeLayer</div>
                <div class="small">
                    Make sure the backend is running at ${API_BASE}.<br><br>
                    Expected command:<br>
                    <strong>python -m uvicorn app.main:app --reload</strong>
                </div>
            </div>
        `;
        document.getElementById("refreshStatus").textContent = "Backend not connected";
    }
}

async function fetchJson(url, options = {}) {
    try {
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`${url} returned ${response.status}`);
        }

        return await response.json();

    } catch (error) {
        if (options.optional) {
            console.warn(`Optional endpoint unavailable: ${url}`, error);
            return null;
        }
        throw error;
    }
}
