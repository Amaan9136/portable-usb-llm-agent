// Polls /health and reflects the agent's reachability, active backend,
// and active model in the header status pill.
import { el, icon } from "./dom.js";
import * as api from "./api.js";
import { state } from "./state.js";

let onHealthCallbacks = [];
/** Lets other modules (settings.js) react whenever a fresh /health
 * response comes in, without connection.js needing to know about them. */
export function onHealth(cb) {
  onHealthCallbacks.push(cb);
}

export async function checkHealth() {
  const connStatus = el("connStatus");
  try {
    const data = await api.health();
    const backendLabel = data.backend === "ollama" ? "ollama" : "llama.cpp";
    connStatus.innerHTML = `${icon("fa-solid fa-circle", "text-[8px]")} online &middot; ${backendLabel} &middot; ${data.active_model || data.model}`;
    connStatus.classList.remove("text-magenta");
    connStatus.classList.add("text-cyan");
    onHealthCallbacks.forEach((cb) => cb(data));
  } catch {
    connStatus.innerHTML = `${icon("fa-solid fa-triangle-exclamation")} agent unreachable`;
    connStatus.classList.remove("text-cyan");
    connStatus.classList.add("text-magenta");
  }
}
