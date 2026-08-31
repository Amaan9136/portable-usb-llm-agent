// Renders everything that appears in the chat log: user/system/agent
// messages, and the live action-timeline feed (styled after Claude
// Code's transcript: one collapsed summary line per step, with an icon,
// a plain-English verb, the target file/command as an inline chip, and
// a +N/-N diff badge for writes - click a step to expand full detail).
// streaming.js calls into this as SSE events arrive.
import { el, escapeHtml, cssEscape, icon } from "./dom.js";
import { toolIconHtml } from "./icons.js";
import { flashArtifact, loadTree } from "./explorer.js";
import * as api from "./api.js";
import { state } from "./state.js";

const chatLog = el("chatLog");

function clearWelcome() {
  if (chatLog.querySelector(".signature-orb")) chatLog.innerHTML = "";
}

export function addUserMessage(text) {
  clearWelcome();
  const div = document.createElement("div");
  div.className = "msg msg-user";
  div.innerHTML = `<div class="msg-bubble msg-bubble-user">${escapeHtml(text)}</div>`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

export function addSystemMessage(text) {
  clearWelcome();
  const div = document.createElement("div");
  div.className = "msg msg-system";
  div.innerHTML = `<div class="msg-system-text">${icon("fa-solid fa-circle-info")} ${escapeHtml(text)}</div>`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

export function startAgentMessage(meta) {
  clearWelcome();
  const div = document.createElement("div");
  div.className = "msg msg-agent";
  const metaLine = meta
    ? `<div class="agent-meta">${icon("fa-solid fa-microchip")} ${escapeHtml(meta.backend || "")} &middot; ${escapeHtml(meta.model || "")}</div>`
    : "";
  div.innerHTML = `
    <div class="msg-bubble msg-bubble-agent">
      ${metaLine}
      <div class="action-timeline">
        <div class="action-timeline-summary hidden"></div>
        <div class="action-timeline-steps"></div>
      </div>
      <div class="agent-text"></div>
      <div class="agent-perf hidden"></div>
    </div>`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  div._stepCount = 0;
  return div;
}

function bumpStepCount(container) {
  container._stepCount = (container._stepCount || 0) + 1;
  const summary = container.querySelector(".action-timeline-summary");
  summary.classList.remove("hidden");
  const verb = container._stepCount === 1 ? "step" : "steps";
  summary.innerHTML = `${icon("fa-solid fa-list-check")} Ran ${container._stepCount} ${verb}`;
}

// ---------------------------------------------------------------------
// Each tool call renders as one collapsed timeline row:
//   [icon] Verb target.ext   [+N -M]  [chevron]
// Clicking the row expands a detail panel below it (command output,
// file diff preview, or the raw arguments/result for anything else).
// This mirrors the Claude Code transcript: compact by default, full
// detail on demand, never a wall of raw JSON by default.
// ---------------------------------------------------------------------
const STEP_VERBS = {
  write_file: "Wrote",
  read_file: "Read",
  list_files: "Listed",
  run_command: "Ran",
  create_zip: "Packaged",
};

function stepTarget(tool, args) {
  if (tool === "write_file" || tool === "read_file") return args.relative_path || "";
  if (tool === "list_files") return args.relative_path || ".";
  if (tool === "run_command") return (args.command || []).join(" ");
  if (tool === "create_zip") return args.artifact_name || "";
  return "";
}

function diffBadge(args, result) {
  if (!result || !result.ok) return "";
  const content = args.content || "";
  if (!content) return "";
  const lines = content.split("\n").length;
  // We don't have the previous file content client-side to diff against,
  // so we show total lines written as a proxy for "+N" - a real diff
  // count would require the backend to return one, which is a possible
  // follow-up. Existing files show as a plain write rather than a
  // fabricated -N line count.
  return `<span class="diff-badge diff-add">+${lines}</span>`;
}

export function addToolEvent(container, role, tool, args, result) {
  const stepsWrap = container.querySelector(".action-timeline-steps");
  const key = `${role}:${tool}:${JSON.stringify(args)}`;
  let row = stepsWrap.querySelector(`[data-event-key="${cssEscape(key)}"]`);
  const ok = result ? result.ok : null;
  const pending = ok === null;
  const failed = ok === false;

  const isNew = !row;
  if (isNew) {
    row = document.createElement("div");
    row.dataset.eventKey = key;
    row.className = "action-step";
    stepsWrap.appendChild(row);
    bumpStepCount(container);
  }

  const verb = STEP_VERBS[tool] || "Called";
  const target = stepTarget(tool, args);
  const statusIcon = failed
    ? icon("fa-solid fa-circle-xmark", "action-step-status-fail")
    : pending
    ? icon("fa-solid fa-spinner fa-spin", "action-step-status-pending")
    : icon("fa-solid fa-circle-check", "action-step-status-ok");

  row.className = `action-step ${failed ? "action-step-fail" : ""} ${pending ? "action-step-pending" : ""}`;
  row.innerHTML = `
    <button type="button" class="action-step-head">
      <span class="action-step-icon">${statusIcon}</span>
      <span class="action-step-verb">${escapeHtml(verb)}</span>
      ${target ? `<code class="action-step-target">${escapeHtml(target)}</code>` : ""}
      ${!pending ? diffBadge(args, result) : ""}
      <span class="action-step-chevron">${icon("fa-solid fa-chevron-right")}</span>
    </button>
    <div class="action-step-detail hidden"></div>`;

  const detail = row.querySelector(".action-step-detail");
  detail.innerHTML = renderStepDetail(tool, args, result);

  row.querySelector(".action-step-head").addEventListener("click", () => {
    const isOpen = !detail.classList.contains("hidden");
    detail.classList.toggle("hidden");
    row.querySelector(".action-step-chevron").innerHTML = icon(isOpen ? "fa-solid fa-chevron-right" : "fa-solid fa-chevron-down");
  });

  chatLog.scrollTop = chatLog.scrollHeight;

  if (tool === "write_file" && ok) {
    flashArtifact(args.relative_path, args.content);
    if (state.currentProject) loadTree(state.currentProject);
  }
}

function renderStepDetail(tool, args, result) {
  if (tool === "run_command") {
    const cmd = (args.command || []).join(" ");
    const stdout = result ? (result.stdout || "").trim() : "";
    const stderr = result ? (result.stderr || "").trim() : "";
    const exitCode = result && typeof result.returncode === "number" ? result.returncode : null;
    return `
      <div class="command-output-cmd">${icon("fa-solid fa-terminal")} <code>${escapeHtml(cmd)}</code>${
      exitCode !== null ? `<span class="exit-code ${exitCode === 0 ? "exit-ok" : "exit-fail"}">exit ${exitCode}</span>` : ""
    }</div>
      ${stdout ? `<pre class="command-output-stream">${escapeHtml(stdout)}</pre>` : ""}
      ${stderr ? `<pre class="command-output-stream command-output-stderr">${escapeHtml(stderr)}</pre>` : ""}
      ${!stdout && !stderr && result ? `<p class="text-dim text-xs px-1">(no output)</p>` : ""}`;
  }
  if (tool === "write_file") {
    const content = args.content || "";
    const preview = content.length > 2000 ? content.slice(0, 2000) + "\n…(truncated)" : content;
    return `<pre class="command-output-stream diff-preview">${escapeHtml(preview)}</pre>`;
  }
  if (tool === "read_file") {
    const content = result && result.ok ? result.content || "" : "";
    const preview = content.length > 1500 ? content.slice(0, 1500) + "\n…(truncated)" : content;
    return preview
      ? `<pre class="command-output-stream">${escapeHtml(preview)}</pre>`
      : `<p class="text-dim text-xs px-1">${result && result.error ? escapeHtml(result.error) : "(empty)"}</p>`;
  }
  if (tool === "list_files") {
    const entries = result && result.ok ? result.files || [] : [];
    if (!entries.length) return `<p class="text-dim text-xs px-1">(no entries returned)</p>`;
    return `<ul class="list-files-detail">${entries.map((e) => `<li>${icon("fa-solid fa-file")}${escapeHtml(typeof e === "string" ? e : e.name || "")}</li>`).join("")}</ul>`;
  }
  if (tool === "create_zip") {
    const name = result && result.ok ? result.artifact : args.artifact_name || "";
    return `<p class="text-xs px-1">${icon("fa-solid fa-file-zipper")} ${escapeHtml(name)}</p>`;
  }
  // Fallback for any tool we don't have a bespoke view for: pretty JSON.
  return `<pre class="command-output-stream">${escapeHtml(JSON.stringify({ args, result }, null, 2))}</pre>`;
}

export function appendAgentToken(container, text) {
  const textEl = container.querySelector(".agent-text");
  textEl.textContent += text;
  chatLog.scrollTop = chatLog.scrollHeight;
}

export function showPerf(container, payload) {
  const perfEl = container.querySelector(".agent-perf");
  perfEl.classList.remove("hidden");
  perfEl.innerHTML = `
    ${icon("fa-solid fa-gauge-high")}
    <span>${payload.tokens_per_second} tok/s</span>
    <span class="agent-perf-sep">&middot;</span>
    <span>${payload.total_tokens} tokens</span>
    <span class="agent-perf-sep">&middot;</span>
    <span>${payload.total_elapsed_seconds.toFixed(1)}s</span>`;
}

export function finishAgentMessage(container, payload) {
  const textEl = container.querySelector(".agent-text");
  if (!textEl.textContent.trim() && payload.text) {
    textEl.textContent = payload.text;
  }
  if (payload.changed_files && payload.changed_files.length) {
    const list = document.createElement("div");
    list.className = "changed-files";
    list.innerHTML =
      `<div class="text-xs text-dim uppercase tracking-wide mt-3 mb-1">Changed files</div>` +
      payload.changed_files.map((f) => `<div class="changed-file-chip">${icon("fa-solid fa-pen")}${escapeHtml(f)}</div>`).join("");
    container.querySelector(".msg-bubble-agent").appendChild(list);
  }
  if (payload.artifact_filename) {
    const link = document.createElement("a");
    link.href = api.artifactDownloadUrl(payload.artifact_filename);
    link.className = "artifact-download";
    link.innerHTML = `${icon("fa-solid fa-download")} Download ${escapeHtml(payload.artifact_filename)}`;
    container.querySelector(".msg-bubble-agent").appendChild(link);
  }
}
