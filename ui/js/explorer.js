// File tree, the code viewer panel, and the ZIP-download affordances for
// both a single file's project and the whole explorer.
import { el, escapeHtml, cssEscape, icon } from "./dom.js";
import { fileIconHtml } from "./icons.js";
import * as api from "./api.js";
import { state } from "./state.js";

const fileTree = el("fileTree");
const artifactBody = el("artifactBody");
const artifactFileName = el("artifactFileName");

export async function loadProjects() {
  const projectSelect = el("projectSelect");
  try {
    const data = await api.projects();
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

export async function doImportProject(sourcePath, projectName, onError, onDone) {
  try {
    const data = await api.importProject(sourcePath, projectName);
    state.currentProject = data.project;
    localStorage.setItem("currentProject", data.project);
    await loadProjects();
    onDone(data);
  } catch (e) {
    onError(e.message);
  }
}

export async function loadTree(projectName) {
  el("btnDownloadProjectZip").classList.toggle("hidden", !projectName);
  if (!projectName) {
    fileTree.innerHTML = `<p class="text-dim text-xs px-2 py-4 text-center">Open a project to browse files.</p>`;
    return;
  }
  try {
    const data = await api.tree(projectName);
    fileTree.innerHTML = "";
    fileTree.appendChild(renderTreeNode(data.tree, 0));
  } catch {
    fileTree.innerHTML = `<p class="text-magenta text-xs px-2 py-4 text-center">Could not load files.</p>`;
  }
}

function renderTreeNode(node, depth) {
  const wrap = document.createElement("div");
  if (node.type === "dir") {
    const row = document.createElement("div");
    row.className = "tree-row tree-dir";
    row.style.paddingLeft = `${depth * 12 + 6}px`;
    row.innerHTML = `<span class="tree-caret">${icon("fa-solid fa-caret-right")}</span><span class="tree-icon">${icon("fa-solid fa-folder")}</span><span class="truncate">${escapeHtml(node.name)}</span>`;
    const childWrap = document.createElement("div");
    childWrap.className = "hidden";
    for (const child of node.children || []) {
      childWrap.appendChild(renderTreeNode(child, depth + 1));
    }
    row.addEventListener("click", () => {
      const isOpen = !childWrap.classList.contains("hidden");
      childWrap.classList.toggle("hidden");
      row.querySelector(".tree-caret").innerHTML = icon(isOpen ? "fa-solid fa-caret-right" : "fa-solid fa-caret-down");
    });
    wrap.appendChild(row);
    wrap.appendChild(childWrap);
  } else {
    const row = document.createElement("div");
    row.className = "tree-row tree-file group";
    row.dataset.path = node.path;
    row.style.paddingLeft = `${depth * 12 + 6}px`;
    row.innerHTML = `
      <span class="tree-icon">${fileIconHtml(node.name)}</span>
      <span class="truncate flex-1">${escapeHtml(node.name)}</span>
      <button class="tree-file-download opacity-0 group-hover:opacity-100" title="Download this file" aria-label="Download ${escapeHtml(node.name)}">
        ${icon("fa-solid fa-download")}
      </button>`;
    row.addEventListener("click", (e) => {
      if (e.target.closest(".tree-file-download")) return;
      openFile(node.path);
    });
    row.querySelector(".tree-file-download").addEventListener("click", (e) => {
      e.stopPropagation();
      downloadSingleFile(node.path);
    });
    wrap.appendChild(row);
  }
  return wrap;
}

/** Zips a single file (via the same explorer-download endpoint the
 * whole-project button uses) and triggers a browser download for it. */
function downloadSingleFile(relativePath) {
  const a = document.createElement("a");
  a.href = api.explorerDownloadUrl(relativePath);
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function downloadProjectZip() {
  if (!state.currentProject) return;
  const a = document.createElement("a");
  a.href = api.explorerDownloadUrl(state.currentProject);
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export async function openFile(relativePath) {
  document.querySelectorAll(".tree-file").forEach((r) => r.classList.remove("tree-file-active"));
  const row = fileTree.querySelector(`[data-path="${cssEscape(relativePath)}"]`);
  if (row) row.classList.add("tree-file-active");

  state.activeFile = relativePath;
  artifactFileName.textContent = relativePath;
  artifactBody.innerHTML = `<p class="text-dim text-xs px-4 py-8 text-center">Loading&hellip;</p>`;
  try {
    const data = await api.readFile(relativePath);
    renderFileViewer(relativePath, data.content);
  } catch {
    artifactBody.innerHTML = `<p class="text-magenta text-xs px-4 py-8 text-center">Could not load file.</p>`;
  }
}

export function renderFileViewer(path, content) {
  const pre = document.createElement("pre");
  pre.className = "code-view";
  const code = document.createElement("code");
  code.textContent = content;
  pre.appendChild(code);
  artifactBody.innerHTML = "";
  artifactBody.appendChild(pre);
}

export function flashArtifact(path, content) {
  artifactFileName.textContent = path;
  renderFileViewer(path, content || "");
  artifactBody.classList.add("flash-write");
  setTimeout(() => artifactBody.classList.remove("flash-write"), 700);
  if (window.innerWidth < 1024) {
    el("artifactPanel").classList.add("drawer-open");
    el("viewerScrim").classList.remove("hidden");
  }
}
