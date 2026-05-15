// TradeLayer Workspace Tabs
// Keeps the dashboard organized into major operating workspaces.

function initializeWorkspaceTabs() {
    const buttons = document.querySelectorAll(".workspace-tab-button");
    const panels = document.querySelectorAll(".workspace-tab-panel");

    if (!buttons.length || !panels.length) {
        return;
    }

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            const target = button.dataset.workspaceTab;

            buttons.forEach(item => item.classList.remove("active"));
            panels.forEach(panel => panel.classList.remove("active"));

            button.classList.add("active");

            const activePanel = document.querySelector(`[data-workspace-panel="${target}"]`);
            if (activePanel) {
                activePanel.classList.add("active");
            }
        });
    });
}
