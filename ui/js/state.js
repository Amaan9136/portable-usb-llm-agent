// Single shared mutable state object. Every module that needs to read or
// change app-wide state (current project, whether a run is in progress,
// the active model, etc.) imports this same object rather than keeping
// its own copy, so there is exactly one source of truth.
import { SETTINGS_STORAGE_KEYS as KEYS } from "./config.js";

function readBoolSetting(key, fallback) {
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  return raw === "true";
}

export const state = {
  agentUrl: localStorage.getItem("agentUrl") || "http://127.0.0.1:8787",
  currentProject: localStorage.getItem("currentProject") || "",
  running: false,
  activeFile: null,

  // Settings toggles. Defaults here are placeholders until /health tells
  // us the agent's real TESTING_PHASE_DEFAULT / VERBOSE_STREAM_DEFAULT;
  // once loaded, a stored user override (if any) still wins.
  verboseStream: readBoolSetting(KEYS.verboseStream, true),
  testingPhase: readBoolSetting(KEYS.testingPhase, true),
  hasStoredVerbose: localStorage.getItem(KEYS.verboseStream) !== null,
  hasStoredTesting: localStorage.getItem(KEYS.testingPhase) !== null,

  // Model backend/selection. backend is "llama-cpp" or "ollama".
  backend: localStorage.getItem(KEYS.backend) || "llama-cpp",
  modelName: localStorage.getItem(KEYS.modelName) || "",
};

export function setSetting(key, value) {
  state[key] = value;
  const storageKey = KEYS[key];
  if (storageKey) localStorage.setItem(storageKey, String(value));
}

export function apiUrl(path) {
  return state.agentUrl.replace(/\/$/, "") + path;
}
