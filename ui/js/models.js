// Lets the user pick which backend/model the agent uses - the built-in
// portable llama.cpp GGUF model, or (opt-in) any model Ollama reports
// installed, local or "-cloud". Selecting here calls /models/select so
// the switch takes effect immediately, without restarting the agent.
import { el, escapeHtml, icon } from "./dom.js";
import * as api from "./api.js";
import { state, setSetting } from "./state.js";

const modelSelect = el("modelSelect");
const modelStatus = el("modelStatus");

export async function loadModels() {
  modelSelect.innerHTML = `<option value="">Loading models&hellip;</option>`;
  try {
    const data = await api.models();
    modelSelect.innerHTML = "";

    const llamaGroup = document.createElement("optgroup");
    llamaGroup.label = "Portable (llama.cpp)";
    for (const m of data.llama_cpp || []) {
      const opt = document.createElement("option");
      opt.value = `llama-cpp::${m.name}`;
      opt.textContent = m.name;
      llamaGroup.appendChild(opt);
    }
    modelSelect.appendChild(llamaGroup);

    const ollama = data.ollama || {};
    if (ollama.available && (ollama.models || []).length) {
      const ollamaGroup = document.createElement("optgroup");
      ollamaGroup.label = "Ollama";
      for (const m of ollama.models) {
        const opt = document.createElement("option");
        opt.value = `ollama::${m.name}`;
        opt.textContent = `${m.name} ${m.cloud ? "(cloud)" : "(local)"}`;
        ollamaGroup.appendChild(opt);
      }
      modelSelect.appendChild(ollamaGroup);
    } else if (!ollama.available) {
      const opt = document.createElement("option");
      opt.disabled = true;
      opt.textContent = `Ollama unavailable (${ollama.error || "not reachable"})`;
      modelSelect.appendChild(opt);
    }

    const active = data.active || {};
    const activeValue = active.backend === "ollama" ? `ollama::${active.model_name}` : `llama-cpp::${active.model_name}`;
    if ([...modelSelect.options].some((o) => o.value === activeValue)) {
      modelSelect.value = activeValue;
    }
    modelStatus.innerHTML = `${icon("fa-solid fa-check", "text-cyan")} active: ${escapeHtml(active.backend)} / ${escapeHtml(active.model_name || "(none)")}`;
  } catch (e) {
    modelSelect.innerHTML = `<option value="">Could not load models</option>`;
    modelStatus.innerHTML = `${icon("fa-solid fa-triangle-exclamation", "text-magenta")} ${escapeHtml(e.message)}`;
  }
}

export async function applySelectedModel() {
  const [backend, ...rest] = (modelSelect.value || "").split("::");
  const modelName = rest.join("::");
  if (!backend) return;
  modelStatus.innerHTML = `${icon("fa-solid fa-spinner fa-spin")} switching&hellip;`;
  try {
    const result = await api.selectModel(backend, backend === "ollama" ? modelName : null);
    setSetting("backend", result.active.backend);
    setSetting("modelName", result.active.model_name || "");
    modelStatus.innerHTML = `${icon("fa-solid fa-check", "text-cyan")} now using ${escapeHtml(result.active.backend)} / ${escapeHtml(result.active.model_name || "(none)")}`;
  } catch (e) {
    modelStatus.innerHTML = `${icon("fa-solid fa-triangle-exclamation", "text-magenta")} ${escapeHtml(e.message)}`;
  }
}
