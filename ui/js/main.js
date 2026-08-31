// App entry point. Imports every module for its side effects / exported
// functions, wires up DOM event listeners, and kicks off the initial
// loads (starfield, health check, projects, models). Loaded from
// index.html as <script type="module" src="/js/main.js">.
import { el } from "./dom.js";
import { state } from "./state.js";
import { initStarfield } from "./starfield.js";
import { checkHealth } from "./connection.js";
import * as explorer from "./explorer.js";
import { runTask } from "./streaming.js";
import { addSystemMessage } from "./chat.js";
import { openModal, closeModal, wireOverlayDismiss } from "./modals.js";
import { loadModels, applySelectedModel } from "./models.js";
import { initSettingsToggles } from "./settings.js";
import { mountModals } from "./components/mount.js";

const projectSelect = el("projectSelect");

function wireHeader() {
  el("btnOpenProject").addEventListener("click", () => openModal("openProjectModal"));
  el("btnCancelImport").addEventListener("click", () => closeModal("openProjectModal"));
  el("btnConfirmImport").addEventListener("click", () => {
    const path = el("importPathInput").value.trim();
    const name = el("importNameInput").value.trim();
    const errBox = el("importError");
    errBox.classList.add("hidden");
    if (!path) return;
    explorer.doImportProject(
      path,
      name,
      (msg) => {
        errBox.textContent = msg;
        errBox.classList.remove("hidden");
      },
      (data) => {
        closeModal("openProjectModal");
        addSystemMessage(`Imported "${data.project}" (${data.files_imported} files). It now lives in the sandboxed workspace.`);
      }
    );
  });

  el("btnCli").addEventListener("click", () => openModal("cliModal"));
  el("btnCloseCli").addEventListener("click", () => closeModal("cliModal"));

  el("btnSettings").addEventListener("click", () => {
    el("agentUrlInput").value = state.agentUrl;
    openModal("settingsModal");
    loadModels();
  });
  el("btnCancelSettings").addEventListener("click", () => closeModal("settingsModal"));
  el("btnSaveSettings").addEventListener("click", () => {
    const url = el("agentUrlInput").value.trim();
    if (url) {
      state.agentUrl = url;
      localStorage.setItem("agentUrl", url);
    }
    closeModal("settingsModal");
    checkHealth();
    explorer.loadProjects();
  });
  el("btnApplyModel").addEventListener("click", applySelectedModel);
  el("btnRefreshModels").addEventListener("click", loadModels);

  projectSelect.addEventListener("change", () => {
    state.currentProject = projectSelect.value;
    localStorage.setItem("currentProject", state.currentProject);
    explorer.loadTree(state.currentProject);
  });

  el("btnDownloadProjectZip").addEventListener("click", explorer.downloadProjectZip);
}

function wireDrawers() {
  const explorerPanel = el("explorerPanel");
  const explorerScrim = el("explorerScrim");
  const viewerPanel = el("artifactPanel");
  const viewerScrim = el("viewerScrim");
  const fileTree = el("fileTree");

  function openExplorerDrawer() {
    explorerPanel.classList.add("drawer-open");
    explorerScrim.classList.remove("hidden");
  }
  function closeExplorerDrawer() {
    explorerPanel.classList.remove("drawer-open");
    explorerScrim.classList.add("hidden");
  }
  function openViewerDrawer() {
    viewerPanel.classList.add("drawer-open");
    viewerScrim.classList.remove("hidden");
  }
  function closeViewerDrawer() {
    viewerPanel.classList.remove("drawer-open");
    viewerScrim.classList.add("hidden");
  }

  el("btnToggleExplorer").addEventListener("click", openExplorerDrawer);
  el("btnCloseExplorer").addEventListener("click", closeExplorerDrawer);
  explorerScrim.addEventListener("click", closeExplorerDrawer);
  el("btnToggleViewer").addEventListener("click", openViewerDrawer);
  el("btnCloseViewer").addEventListener("click", closeViewerDrawer);
  viewerScrim.addEventListener("click", closeViewerDrawer);

  fileTree.addEventListener("click", (e) => {
    if (e.target.closest(".tree-file") && window.innerWidth < 1024) openViewerDrawer();
    if (e.target.closest(".tree-file") && window.innerWidth < 768) closeExplorerDrawer();
  });

  el("btnCliMobile").addEventListener("click", () => {
    closeExplorerDrawer();
    openModal("cliModal");
  });
}

function wireComposer() {
  const taskInput = el("taskInput");
  taskInput.addEventListener("input", () => {
    taskInput.style.height = "auto";
    taskInput.style.height = Math.min(taskInput.scrollHeight, 160) + "px";
  });
  taskInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitTask();
    }
  });
  el("btnSend").addEventListener("click", submitTask);

  function submitTask() {
    const text = taskInput.value.trim();
    if (!text || state.running) return;
    taskInput.value = "";
    taskInput.style.height = "auto";
    runTask(text);
  }
}

// ---------- init ----------
mountModals();
initStarfield();
wireHeader();
wireDrawers();
wireComposer();
wireOverlayDismiss();
initSettingsToggles();
checkHealth();
explorer.loadProjects();
setInterval(checkHealth, 8000);