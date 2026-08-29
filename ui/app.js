(() => {
  "use strict";

  const state = {
    agentUrl: localStorage.getItem("agentUrl") || "http://127.0.0.1:8787",
    currentProject: localStorage.getItem("currentProject") || "",
    running: false,
    activeFile: null,
  };

  const el = (id) => document.getElementById(id);
  const chatLog = el("chatLog");
  const fileTree = el("fileTree");
  const pipelineBar = el("pipelineBar");
  const artifactBody = el("artifactBody");
  const artifactFileName = el("artifactFileName");
  const connStatus = el("connStatus");
  const projectSelect = el("projectSelect");

  function apiUrl(path) {
    return state.agentUrl.replace(/\/$/, "") + path;
  }

  // ---------- Starfield background ----------
  function initStarfield() {
    const canvas = el("starfield");
    const ctx = canvas.getContext("2d");
    let stars = [];
    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      const count = Math.floor((canvas.width * canvas.height) / 9000);
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.2 + 0.2,
        tw: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.15 + 0.02,
      }));
    }
    function draw(t) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const s of stars) {
        const alpha = 0.35 + 0.65 * Math.abs(Math.sin(s.tw + t * 0.001 * s.speed));
        ctx.beginPath();
        ctx.fillStyle = `rgba(232,232,245,${alpha.toFixed(2)})`;
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      requestAnimationFrame(draw);
    }
    window.addEventListener("resize", resize);
    resize();
    requestAnimationFrame(draw);
  }

  // ---------- Connection status ----------
  async function checkHealth() {
    try {
      const res = await fetch(apiUrl("/health"));
      if (!res.ok) throw new Error();
      const data = await res.json();
      connStatus.textContent = `online · ${data.model}`;
      connStatus.classList.remove("text-magenta");
      connStatus.classList.add("text-cyan");
    } catch {
      connStatus.textContent = "agent unreachable";
      connStatus.classList.remove("text-cyan");
      connStatus.classList.add("text-magenta");
    }
  }

  // ---------- Projects ----------
  async function loadProjects() {
    try {
      const res = await fetch(apiUrl("/projects"));
      const data = await res.json();
      projectSelect.innerHTML = '<option value="">No project</option>';
      for (const p of data.projects || []) {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = p.name;
        if (p.name === state.currentProject) opt.selected = true;
        projectSelect.appendChild(opt);
      }
      if (state.currentProject) loadTree(state.currentProject);
    } catch {
      /* agent offline; explorer stays empty */
    }
  }

  async function importProject(sourcePath, projectName) {
    const errBox = el("importError");
    errBox.classList.add("hidden");
    try {
      const res = await fetch(apiUrl("/projects/import"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_path: sourcePath, project_name: projectName || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed.");
      state.currentProject = data.project;
      localStorage.setItem("currentProject", data.project);
      closeModal("openProjectModal");
      await loadProjects();
      addSystemMessage(`Imported "${data.project}" (${data.files_imported} files). It now lives in the sandboxed workspace.`);
    } catch (e) {
      errBox.textContent = e.message;
      errBox.classList.remove("hidden");
    }
  }

  // ---------- File tree ----------
  async function loadTree(projectName) {
    if (!projectName) {
      fileTree.innerHTML = '<p class="text-dim text-xs px-2 py-4 text-center">Open a project to browse files.</p>';
      return;
    }
    try {
      const res = await fetch(apiUrl(`/tree?relative_path=${encodeURIComponent(projectName)}`));
      const data = await res.json();
      fileTree.innerHTML = "";
      fileTree.appendChild(renderTreeNode(data.tree, 0));
    } catch {
      fileTree.innerHTML = '<p class="text-magenta text-xs px-2 py-4 text-center">Could not load files.</p>';
    }
  }

  function renderTreeNode(node, depth) {
    const wrap = document.createElement("div");
    if (node.type === "dir") {
      const row = document.createElement("div");
      row.className = "tree-row tree-dir";
      row.style.paddingLeft = `${depth * 12 + 6}px`;
      row.innerHTML = `<span class="tree-caret">▸</span><span class="tree-icon">📁</span><span class="truncate">${escapeHtml(node.name)}</span>`;
      const childWrap = document.createElement("div");
      childWrap.className = "hidden";
      for (const child of node.children || []) {
        childWrap.appendChild(renderTreeNode(child, depth + 1));
      }
      row.addEventListener("click", () => {
        const isOpen = !childWrap.classList.contains("hidden");
        childWrap.classList.toggle("hidden");
        row.querySelector(".tree-caret").textContent = isOpen ? "▸" : "▾";
      });
      wrap.appendChild(row);
      wrap.appendChild(childWrap);
    } else {
      const row = document.createElement("div");
      row.className = "tree-row tree-file";
      row.dataset.path = node.path;
      row.style.paddingLeft = `${depth * 12 + 6}px`;
      row.innerHTML = `<span class="tree-icon">${fileIcon(node.name)}</span><span class="truncate">${escapeHtml(node.name)}</span>`;
      row.addEventListener("click", () => openFile(node.path));
      wrap.appendChild(row);
    }
    return wrap;
  }

  function fileIcon(name) {
    const ext = name.split(".").pop().toLowerCase();
    const map = {
      py: "🐍", js: "📜", ts: "📜", json: "🧩", md: "📝",
      html: "🌐", css: "🎨", txt: "📄", yml: "⚙", yaml: "⚙",
      bat: "🪟", sh: "🐚", gitignore: "🚫",
    };
    return map[ext] || "📄";
  }

  async function openFile(relativePath) {
    document.querySelectorAll(".tree-file").forEach((r) => r.classList.remove("tree-file-active"));
    const row = fileTree.querySelector(`[data-path="${cssEscape(relativePath)}"]`);
    if (row) row.classList.add("tree-file-active");

    state.activeFile = relativePath;
    artifactFileName.textContent = relativePath;
    artifactBody.innerHTML = '<p class="text-dim text-xs px-4 py-8 text-center">Loading…</p>';
    try {
      const res = await fetch(apiUrl(`/file?relative_path=${encodeURIComponent(relativePath)}`));
      const data = await res.json();
      renderFileViewer(relativePath, data.content);
    } catch {
      artifactBody.innerHTML = '<p class="text-magenta text-xs px-4 py-8 text-center">Could not load file.</p>';
    }
  }

  function renderFileViewer(path, content) {
    const pre = document.createElement("pre");
    pre.className = "code-view";
    const code = document.createElement("code");
    code.textContent = content;
    pre.appendChild(code);
    artifactBody.innerHTML = "";
    artifactBody.appendChild(pre);
  }

  function cssEscape(s) {
    return s.replace(/["\\]/g, "\\$&");
  }
  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // ---------- Pipeline status bar ----------
  function setRoleState(role, status) {
    const node = pipelineBar.querySelector(`[data-role="${role}"]`);
    if (!node) return;
    node.classList.remove("role-active", "role-done");
    if (status === "active") node.classList.add("role-active");
    if (status === "done") node.classList.add("role-done");
  }

  function resetPipeline() {
    pipelineBar.querySelectorAll("[data-role]").forEach((n) => {
      n.classList.remove("role-active", "role-done");
    });
  }

  const ROLE_ORDER = ["planner", "implementer", "reviewer", "tester", "packager"];
  function advancePipelineTo(role) {
    const idx = ROLE_ORDER.indexOf(role);
    ROLE_ORDER.forEach((r, i) => {
      if (i < idx) setRoleState(r, "done");
      else if (i === idx) setRoleState(r, "active");
      else setRoleState(r, "");
    });
  }

  // ---------- Chat rendering ----------
  function clearWelcome() {
    if (chatLog.querySelector(".signature-orb")) chatLog.innerHTML = "";
  }

  function addUserMessage(text) {
    clearWelcome();
    const div = document.createElement("div");
    div.className = "msg msg-user";
    div.innerHTML = `<div class="msg-bubble msg-bubble-user">${escapeHtml(text)}</div>`;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function addSystemMessage(text) {
    clearWelcome();
    const div = document.createElement("div");
    div.className = "msg msg-system";
    div.innerHTML = `<div class="msg-system-text">${escapeHtml(text)}</div>`;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function startAgentMessage() {
    clearWelcome();
    const div = document.createElement("div");
    div.className = "msg msg-agent";
    div.innerHTML = `
      <div class="msg-bubble msg-bubble-agent">
        <div class="agent-events space-y-1.5 mb-2"></div>
        <div class="agent-text"></div>
      </div>`;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
    return div;
  }

  function addToolEvent(container, role, tool, args, result) {
    const events = container.querySelector(".agent-events");
    const key = `${role}:${tool}:${JSON.stringify(args)}`;
    let row = events.querySelector(`[data-event-key="${cssEscape(key)}"]`);
    const ok = result ? result.ok : null;
    const statusClass = ok === false ? "event-fail" : ok === true ? "event-ok" : "event-pending";
    const summary = summarizeTool(tool, args, result);

    if (!row) {
      row = document.createElement("div");
      row.dataset.eventKey = key;
      events.appendChild(row);
    }
    row.className = `tool-event ${statusClass}`;
    row.innerHTML = `
      <span class="tool-event-role">${role}</span>
      <span class="tool-event-name">${tool}</span>
      <span class="tool-event-detail">${escapeHtml(summary)}</span>`;
    chatLog.scrollTop = chatLog.scrollHeight;

    if (tool === "write_file" && ok) {
      flashArtifact(args.relative_path, args.content);
      if (state.currentProject) loadTree(state.currentProject);
    }
  }

  function summarizeTool(tool, args, result) {
    if (tool === "write_file") return args.relative_path || "";
    if (tool === "read_file") return args.relative_path || "";
    if (tool === "list_files") return args.relative_path || ".";
    if (tool === "run_command") return (args.command || []).join(" ");
    if (tool === "create_zip") return args.artifact_name || "";
    return "";
  }

  function flashArtifact(path, content) {
    artifactFileName.textContent = path;
    renderFileViewer(path, content || "");
    artifactBody.classList.add("flash-write");
    setTimeout(() => artifactBody.classList.remove("flash-write"), 700);
    if (window.innerWidth < 1024) {
      const panel = el("artifactPanel");
      const scrim = el("viewerScrim");
      panel.classList.add("drawer-open");
      scrim.classList.remove("hidden");
    }
  }

  function appendAgentToken(container, text) {
    const textEl = container.querySelector(".agent-text");
    textEl.textContent += text;
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function finishAgentMessage(container, payload) {
    const textEl = container.querySelector(".agent-text");
    if (!textEl.textContent.trim() && payload.text) {
      textEl.textContent = payload.text;
    }
    if (payload.changed_files && payload.changed_files.length) {
      const list = document.createElement("div");
      list.className = "changed-files";
      list.innerHTML =
        `<div class="text-xs text-dim uppercase tracking-wide mt-3 mb-1">Changed files</div>` +
        payload.changed_files.map((f) => `<div class="changed-file-chip">${escapeHtml(f)}</div>`).join("");
      container.querySelector(".msg-bubble-agent").appendChild(list);
    }
    if (payload.artifact_filename) {
      const link = document.createElement("a");
      link.href = apiUrl(`/artifacts/${encodeURIComponent(payload.artifact_filename)}`);
      link.className = "artifact-download";
      link.textContent = `⬇ Download ${payload.artifact_filename}`;
      container.querySelector(".msg-bubble-agent").appendChild(link);
    }
  }

  // ---------- Streaming run ----------
  async function runTask(task) {
    if (state.running) return;
    if (!state.currentProject) {
      addSystemMessage("Open a project first so the agent has somewhere to work.");
      return;
    }
    state.running = true;
    el("btnSend").disabled = true;
    resetPipeline();
    addUserMessage(task);
    const agentDiv = startAgentMessage();

    const payload = {
      task: `Work inside the "${state.currentProject}" project folder (workspace/${state.currentProject}). ${task}`,
      project_name: state.currentProject,
      create_zip: el("createZip").checked,
      allow_commands: el("allowCommands").checked,
      allow_overwrite: el("allowOverwrite").checked,
    };

    try {
      const res = await fetch(apiUrl("/agent/stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok || !res.body) throw new Error("Stream request failed.");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          handleSseChunk(chunk, agentDiv);
        }
      }
    } catch (e) {
      addSystemMessage(`Connection error: ${e.message}`);
    } finally {
      state.running = false;
      el("btnSend").disabled = false;
    }
  }

  function handleSseChunk(chunk, agentDiv) {
    const lines = chunk.split("\n");
    let event = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }

    switch (event) {
      case "start":
        break;
      case "turn_start":
        break;
      case "token":
        appendAgentToken(agentDiv, payload.text);
        break;
      case "tool_call_start":
        advancePipelineTo(payload.role);
        addToolEvent(agentDiv, payload.role, payload.tool, payload.arguments, null);
        break;
      case "tool_call_end":
        advancePipelineTo(payload.role);
        addToolEvent(agentDiv, payload.role, payload.tool, payload.arguments, payload.result);
        break;
      case "warning":
        addSystemMessage(payload.message);
        break;
      case "error":
        addSystemMessage(payload.message);
        ROLE_ORDER.forEach((r) => setRoleState(r, ""));
        break;
      case "final_answer":
        finishAgentMessage(agentDiv, payload);
        ROLE_ORDER.forEach((r) => setRoleState(r, "done"));
        break;
    }
  }

  // ---------- Modals ----------
  function openModal(id) {
    el(id).classList.remove("hidden");
  }
  function closeModal(id) {
    el(id).classList.add("hidden");
  }

  // ---------- Wiring ----------
  function wireUp() {
    el("btnOpenProject").addEventListener("click", () => openModal("openProjectModal"));
    el("btnCancelImport").addEventListener("click", () => closeModal("openProjectModal"));
    el("btnConfirmImport").addEventListener("click", () => {
      const path = el("importPathInput").value.trim();
      const name = el("importNameInput").value.trim();
      if (!path) return;
      importProject(path, name);
    });

    el("btnCli").addEventListener("click", () => openModal("cliModal"));
    el("btnCloseCli").addEventListener("click", () => closeModal("cliModal"));

    el("btnSettings").addEventListener("click", () => {
      el("agentUrlInput").value = state.agentUrl;
      openModal("settingsModal");
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
      loadProjects();
    });

    projectSelect.addEventListener("change", () => {
      state.currentProject = projectSelect.value;
      localStorage.setItem("currentProject", state.currentProject);
      loadTree(state.currentProject);
    });

    // Mobile drawers for the explorer (left) and viewer (right) panels.
    const explorerPanel = el("explorerPanel");
    const explorerScrim = el("explorerScrim");
    const viewerPanel = el("artifactPanel");
    const viewerScrim = el("viewerScrim");

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

    // Selecting a file on mobile should also show the viewer drawer.
    fileTree.addEventListener("click", (e) => {
      if (e.target.closest(".tree-file") && window.innerWidth < 1024) {
        openViewerDrawer();
      }
      if (e.target.closest(".tree-file") && window.innerWidth < 768) {
        closeExplorerDrawer();
      }
    });

    el("btnCliMobile").addEventListener("click", () => {
      closeExplorerDrawer();
      openModal("cliModal");
    });

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

    document.querySelectorAll(".modal-overlay").forEach((overlay) => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.add("hidden");
      });
    });
  }

  // ---------- Init ----------
  initStarfield();
  wireUp();
  checkHealth();
  loadProjects();
  setInterval(checkHealth, 8000);
})();
